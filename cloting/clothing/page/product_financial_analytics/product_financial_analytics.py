from datetime import date, timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime


ALLOWED_ROLES = {
	"System Manager",
	"Administrator",
	"Owner",
	"Business Manager",
	"Accounts Manager",
	"Stock Manager",
	"Rental Manager",
	"Rental Admin",
}


@frappe.whitelist()
def get_dashboard_data(
	from_date=None,
	to_date=None,
	company=None,
	warehouse=None,
	item_group=None,
	item_code=None,
	supplier=None,
	customer=None,
	transaction_type="All",
):
	_validate_access()
	filters = _validate_filters(
		from_date,
		to_date,
		company,
		warehouse,
		item_group,
		item_code,
		supplier,
		customer,
		transaction_type,
	)
	return {
		"filters": filters,
		"currency": frappe.get_cached_value("Company", filters["company"], "default_currency"),
		"updated_at": now_datetime().strftime("%Y-%m-%d %H:%M:%S"),
		"kpis": _get_kpis(filters),
		"pnl": _get_pnl(filters),
		"products": _get_product_performance(filters),
		"inventory": _get_inventory(filters),
		"no_sales_products": _get_no_sales_products(filters),
		"purchases": _get_purchase_analysis(filters),
		"sales": _get_sales_analysis(filters),
		"rental": _get_rental_analysis(filters),
		"charts": _get_chart_data(filters),
		"limitations": _get_limitations(),
	}


@frappe.whitelist()
def get_product_detail(item_code, from_date=None, to_date=None, company=None):
	_validate_access()
	filters = _validate_filters(from_date, to_date, company, None, None, item_code, None, None, "All")
	item = frappe.db.get_value(
		"Item",
		item_code,
		["item_code", "item_name", "item_group", "brand", "stock_uom", "standard_rate", "variant_of"],
		as_dict=True,
	)
	if not item:
		frappe.throw(_("Product {0} does not exist.").format(item_code))
	stock = frappe.db.sql(
		"""
		SELECT warehouse, actual_qty AS stock_qty, stock_value
		FROM `tabBin`
		WHERE item_code = %s AND company = %s
		ORDER BY warehouse
		""",
		[item_code, filters["company"]],
		as_dict=True,
	)
	sales = frappe.db.sql(
		"""
		SELECT si.name, si.posting_date, si.customer, sii.qty, sii.base_net_amount,
			sii.discount_amount, sii.incoming_rate
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1 AND sii.item_code = %s
			AND si.company = %s AND si.posting_date BETWEEN %s AND %s
		ORDER BY si.posting_date DESC
		LIMIT 200
		""",
		[item_code, filters["company"], filters["from_date"], filters["to_date"]],
		as_dict=True,
	)
	purchases = frappe.db.sql(
		"""
		SELECT pi.name, pi.posting_date, pi.supplier, pii.qty, pii.base_net_amount, pii.rate
		FROM `tabPurchase Invoice` pi
		INNER JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
		WHERE pi.docstatus = 1 AND pii.item_code = %s
			AND pi.company = %s AND pi.posting_date BETWEEN %s AND %s
		ORDER BY pi.posting_date DESC
		LIMIT 200
		""",
		[item_code, filters["company"], filters["from_date"], filters["to_date"]],
		as_dict=True,
	)
	monthly = frappe.db.sql(
		"""
		SELECT DATE_FORMAT(si.posting_date, '%%Y-%%m') AS label,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.base_net_amount
				ELSE -ABS(sii.base_net_amount) END), 0) AS value
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1 AND sii.item_code = %s
			AND si.company = %s AND si.posting_date BETWEEN %s AND %s
		GROUP BY DATE_FORMAT(si.posting_date, '%%Y-%%m') ORDER BY label
		""",
		[item_code, filters["company"], filters["from_date"], filters["to_date"]],
		as_dict=True,
	)
	variants = frappe.get_all(
		"Item",
		filters={"variant_of": item_code, "disabled": 0},
		fields=["name", "item_name", "item_group"],
		order_by="name",
	)
	reorder = frappe.get_all(
		"Item Reorder",
		filters={"parent": item_code},
		fields=["warehouse", "warehouse_reorder_level", "warehouse_reorder_qty"],
	)
	return {
		"item": item,
		"variants": variants,
		"stock": stock,
		"sales": sales,
		"purchases": purchases,
		"monthly_sales": monthly,
		"reorder": reorder,
	}


def _validate_access():
	if not ALLOWED_ROLES.intersection(set(frappe.get_roles())):
		frappe.throw(_("You do not have permission to access Product & Financial Analytics."), frappe.PermissionError)


def _validate_filters(
	from_date,
	to_date,
	company,
	warehouse,
	item_group,
	item_code,
	supplier,
	customer,
	transaction_type,
):
	try:
		to_date = getdate(to_date) if to_date else date.today()
		from_date = getdate(from_date) if from_date else to_date - timedelta(days=29)
	except Exception:
		frappe.throw(_("Please provide valid dashboard dates."))
	if from_date > to_date:
		frappe.throw(_("From Date cannot be later than To Date."))
	if (to_date - from_date).days > 366:
		frappe.throw(_("The dashboard date range cannot exceed one year."))

	companies = frappe.get_list("Company", filters={"is_group": 0}, pluck="name")
	if company and company not in companies:
		frappe.throw(_("Invalid company."))
	if len(companies) == 1:
		company = companies[0]
	elif not company:
		frappe.throw(_("Please select a company."))

	if warehouse and not frappe.get_list(
		"Warehouse",
		filters={"name": warehouse, "company": company, "disabled": 0},
		pluck="name",
	):
		frappe.throw(_("Invalid warehouse for the selected company."))
	if item_code and not frappe.db.exists("Item", item_code):
		frappe.throw(_("Invalid item."))
	if item_group and not frappe.db.exists("Item Group", item_group):
		frappe.throw(_("Invalid item group."))
	if supplier and not frappe.db.exists("Supplier", supplier):
		frappe.throw(_("Invalid supplier."))
	if customer and not frappe.db.exists("Customer", customer):
		frappe.throw(_("Invalid customer."))
	if transaction_type not in ("All", "Retail", "Rental"):
		frappe.throw(_("Invalid transaction type."))

	return {
		"from_date": from_date.isoformat(),
		"to_date": to_date.isoformat(),
		"company": company,
		"warehouse": warehouse,
		"item_group": item_group,
		"item_code": item_code,
		"supplier": supplier,
		"customer": customer,
		"transaction_type": transaction_type,
	}


def _invoice_conditions(filters, alias="si", item_alias="sii", args=None):
	args = args if args is not None else []
	conditions = [
		f"{alias}.docstatus = 1",
		f"{alias}.posting_date BETWEEN %s AND %s",
		f"{alias}.company = %s",
	]
	args.extend([filters["from_date"], filters["to_date"], filters["company"]])
	if filters.get("warehouse"):
		conditions.append(f"{item_alias}.warehouse = %s")
		args.append(filters["warehouse"])
	if filters.get("item_group"):
		conditions.append(f"{item_alias}.item_group = %s")
		args.append(filters["item_group"])
	if filters.get("item_code"):
		conditions.append(f"{item_alias}.item_code = %s")
		args.append(filters["item_code"])
	if filters.get("customer"):
		conditions.append(f"{alias}.customer = %s")
		args.append(filters["customer"])
	return " AND ".join(conditions)


def _is_rental_condition(alias="si", item_alias="sii", args=None):
	settings_item = frappe.db.get_single_value("Rental Settings", "rental_item")
	if settings_item:
		args.append(settings_item)
		return f"({item_alias}.item_code = %s OR COALESCE({alias}.remarks, '') LIKE 'Rental Booking %%')"
	return f"COALESCE({alias}.remarks, '') LIKE 'Rental Booking %%'"


def _get_kpis(filters):
	args = []
	conditions = _invoice_conditions(filters, args=args)
	rental_args = []
	rental_condition = _is_rental_condition(args=rental_args)
	sales = frappe.db.sql(
		f"""
		SELECT
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.base_amount + sii.discount_amount ELSE 0 END), 0) AS gross_sales,
			COALESCE(SUM(CASE WHEN si.is_return = 1 THEN ABS(sii.base_net_amount) ELSE 0 END), 0) AS sales_returns,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.discount_amount ELSE 0 END), 0) AS discounts,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN ABS(sii.qty * sii.incoming_rate)
				ELSE -ABS(sii.qty * sii.incoming_rate) END), 0) AS cogs,
			COALESCE(SUM(CASE WHEN {rental_condition} AND si.is_return = 0
				THEN sii.base_net_amount ELSE 0 END), 0) AS rental_revenue
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {conditions}
		""",
		rental_args + args,
		as_dict=True,
	)[0]

	purchase_args = [filters["from_date"], filters["to_date"], filters["company"]]
	purchase = frappe.db.sql(
		"""
		SELECT
			COALESCE(SUM(CASE WHEN is_return = 0 THEN base_net_total ELSE 0 END), 0) AS purchases,
			COALESCE(SUM(CASE WHEN is_return = 1 THEN ABS(base_net_total) ELSE 0 END), 0) AS purchase_returns
		FROM `tabPurchase Invoice`
		WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s AND company = %s
		""",
		purchase_args,
		as_dict=True,
	)[0]
	pnl = _get_pnl(filters)
	stock = _stock_totals(filters)
	receivables = frappe.db.sql(
		"SELECT COALESCE(SUM(outstanding_amount), 0) FROM `tabSales Invoice` WHERE docstatus = 1 AND company = %s",
		[filters["company"]],
	)[0][0]
	payables = frappe.db.sql(
		"SELECT COALESCE(SUM(outstanding_amount), 0) FROM `tabPurchase Invoice` WHERE docstatus = 1 AND company = %s",
		[filters["company"]],
	)[0][0]
	customer_advances, supplier_advances = _get_unallocated_advances(filters["company"])
	net_sales = flt(sales.gross_sales) - flt(sales.sales_returns) - flt(sales.discounts)
	gross_profit = net_sales - flt(sales.cogs)

	return {
		"total_sales_revenue": flt(sales.gross_sales),
		"sales_returns": flt(sales.sales_returns),
		"total_discounts": flt(sales.discounts),
		"net_sales": net_sales,
		"total_purchase_amount": flt(purchase.purchases),
		"purchase_returns": flt(purchase.purchase_returns),
		"total_cogs": flt(sales.cogs),
		"gross_profit": gross_profit,
		"net_profit": flt(pnl["net_profit"]),
		"total_expenses": flt(pnl["total_expenses"]),
		"current_stock_value": flt(stock["stock_value"]),
		"total_stock_qty": flt(stock["stock_qty"]),
		"outstanding_receivables": flt(receivables),
		"outstanding_payables": flt(payables),
		"customer_advances": flt(customer_advances),
		"supplier_advances": flt(supplier_advances),
		"rental_revenue": flt(sales.rental_revenue),
		"gross_profit_margin": _margin(gross_profit, net_sales),
	}


def _get_pnl(filters):
	rows = frappe.db.sql(
		"""
		SELECT a.root_type, a.account_type,
			COALESCE(SUM(gl.debit), 0) AS debit,
			COALESCE(SUM(gl.credit), 0) AS credit
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` a ON a.name = gl.account
		WHERE gl.is_cancelled = 0 AND gl.company = %s
			AND gl.posting_date BETWEEN %s AND %s
			AND a.root_type IN ('Income', 'Expense')
		GROUP BY a.root_type, a.account_type
		""",
		[filters["company"], filters["from_date"], filters["to_date"]],
		as_dict=True,
	)
	income = sum(flt(row.credit) - flt(row.debit) for row in rows if row.root_type == "Income")
	expenses = sum(flt(row.debit) - flt(row.credit) for row in rows if row.root_type == "Expense")
	cogs = sum(
		flt(row.debit) - flt(row.credit)
		for row in rows
		if row.root_type == "Expense" and row.account_type == "Cost of Goods Sold"
	)
	operating_expenses = expenses - cogs
	return {
		"gross_sales": _get_kpis_invoice_value(filters, "gross_sales"),
		"sales_returns": _get_kpis_invoice_value(filters, "sales_returns"),
		"discounts": _get_kpis_invoice_value(filters, "discounts"),
		"net_sales": _get_kpis_invoice_value(filters, "net_sales"),
		"cogs": cogs,
		"gross_profit": _get_kpis_invoice_value(filters, "net_sales") - cogs,
		"total_income": income,
		"total_expenses": expenses,
		"operating_expenses": operating_expenses,
		"net_profit": income - expenses,
	}


def _get_kpis_invoice_value(filters, metric):
	args = []
	conditions = _invoice_conditions(filters, args=args)
	if metric == "gross_sales":
		expression = "CASE WHEN si.is_return = 0 THEN sii.base_amount + sii.discount_amount ELSE 0 END"
	elif metric == "sales_returns":
		expression = "CASE WHEN si.is_return = 1 THEN ABS(sii.base_net_amount) ELSE 0 END"
	elif metric == "discounts":
		expression = "CASE WHEN si.is_return = 0 THEN sii.discount_amount ELSE 0 END"
	else:
		expression = "CASE WHEN si.is_return = 0 THEN sii.base_net_amount ELSE -ABS(sii.base_net_amount) END"
	return flt(
		frappe.db.sql(
			f"SELECT COALESCE(SUM({expression}), 0) FROM `tabSales Invoice` si "
			f"INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name WHERE {conditions}",
			args,
		)[0][0]
	)


def _get_product_performance(filters):
	args = [filters["from_date"], filters["to_date"], filters["company"]]
	conditions = ["si.docstatus = 1", "si.posting_date BETWEEN %s AND %s", "si.company = %s"]
	if filters.get("warehouse"):
		conditions.append("sii.warehouse = %s")
		args.append(filters["warehouse"])
	if filters.get("item_group"):
		conditions.append("sii.item_group = %s")
		args.append(filters["item_group"])
	if filters.get("item_code"):
		conditions.append("sii.item_code = %s")
		args.append(filters["item_code"])
	if filters.get("customer"):
		conditions.append("si.customer = %s")
		args.append(filters["customer"])
	rental_filter = ""
	if filters["transaction_type"] == "Retail":
		rental_args = []
		rental_filter = f" AND NOT {_is_rental_condition(args=rental_args)}"
		args.extend(rental_args)
	elif filters["transaction_type"] == "Rental":
		rental_args = []
		rental_filter = f" AND {_is_rental_condition(args=rental_args)}"
		args.extend(rental_args)
	stock_args = [filters["company"]]
	stock_conditions = ["company = %s"]
	if filters.get("warehouse"):
		stock_conditions.append("warehouse = %s")
		stock_args.append(filters["warehouse"])

	rows = frappe.db.sql(
		f"""
		SELECT
			i.item_code, i.item_name, i.item_group, i.brand,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.qty ELSE -ABS(sii.qty) END), 0) AS qty_sold,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.base_amount + sii.discount_amount ELSE 0 END), 0) AS gross_sales,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.discount_amount ELSE 0 END), 0) AS discount,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.base_net_amount
				ELSE -ABS(sii.base_net_amount) END), 0) AS net_sales,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN ABS(sii.qty * sii.incoming_rate)
				ELSE -ABS(sii.qty * sii.incoming_rate) END), 0) AS cogs,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.base_net_amount
				ELSE -ABS(sii.base_net_amount) END), 0)
				- COALESCE(SUM(CASE WHEN si.is_return = 0 THEN ABS(sii.qty * sii.incoming_rate)
				ELSE -ABS(sii.qty * sii.incoming_rate) END), 0) AS gross_profit,
			COALESCE(MAX(b.stock_qty), 0) AS stock_qty,
			COALESCE(MAX(b.stock_value), 0) AS stock_value
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		INNER JOIN `tabItem` i ON i.name = sii.item_code
		LEFT JOIN (
			SELECT item_code, SUM(actual_qty) AS stock_qty, SUM(stock_value) AS stock_value
			FROM `tabBin`
			WHERE {" AND ".join(stock_conditions)}
			GROUP BY item_code
		) b ON b.item_code = i.name
		WHERE {" AND ".join(conditions)} {rental_filter}
		GROUP BY i.item_code, i.item_name, i.item_group, i.brand
		ORDER BY gross_profit DESC
		LIMIT 500
		""",
		stock_args + args,
		as_dict=True,
	)
	for row in rows:
		row["profit_margin"] = _margin(row.gross_profit, row.net_sales)
		row["average_selling_price"] = flt(row.net_sales) / flt(row.qty_sold) if row.qty_sold else 0
		row["average_cost"] = flt(row.cogs) / flt(row.qty_sold) if row.qty_sold else 0
		row["profit_per_unit"] = flt(row.gross_profit) / flt(row.qty_sold) if row.qty_sold else 0
	return rows


def _get_inventory(filters):
	args = [filters["company"]]
	conditions = ["b.company = %s", "i.disabled = 0", "i.is_stock_item = 1"]
	if filters.get("warehouse"):
		conditions.append("b.warehouse = %s")
		args.append(filters["warehouse"])
	if filters.get("item_group"):
		conditions.append("i.item_group = %s")
		args.append(filters["item_group"])
	if filters.get("item_code"):
		conditions.append("i.name = %s")
		args.append(filters["item_code"])
	rows = frappe.db.sql(
		f"""
		SELECT b.item_code, i.item_name, i.item_group, b.warehouse,
			b.actual_qty AS stock_qty, b.stock_value,
			latest.last_posting_date, COALESCE(reorder.reorder_level, 0) AS reorder_level
		FROM `tabBin` b
		INNER JOIN `tabItem` i ON i.name = b.item_code
		LEFT JOIN (
			SELECT parent, MAX(warehouse_reorder_level) AS reorder_level
			FROM `tabItem Reorder`
			GROUP BY parent
		) reorder ON reorder.parent = b.item_code
		LEFT JOIN (
			SELECT item_code, warehouse, company, MAX(posting_date) AS last_posting_date
			FROM `tabStock Ledger Entry`
			WHERE is_cancelled = 0 AND company = %s
			GROUP BY item_code, warehouse, company
		) latest ON latest.item_code = b.item_code AND latest.warehouse = b.warehouse
			AND latest.company = b.company
		WHERE {" AND ".join(conditions)}
		ORDER BY b.stock_value DESC
		LIMIT 500
		""",
		[filters["company"]] + args,
		as_dict=True,
	)
	warehouse_values = frappe.db.sql(
		f"""
		SELECT b.warehouse AS label, COALESCE(SUM(b.stock_value), 0) AS value
		FROM `tabBin` b INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE {" AND ".join(conditions)}
		GROUP BY b.warehouse ORDER BY value DESC
		""",
		args,
		as_dict=True,
	)
	category_values = frappe.db.sql(
		f"""
		SELECT i.item_group AS label, COALESCE(SUM(b.stock_value), 0) AS value
		FROM `tabBin` b INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE {" AND ".join(conditions)}
		GROUP BY i.item_group ORDER BY value DESC
		""",
		args,
		as_dict=True,
	)
	return {
		"rows": rows,
		"warehouse_values": warehouse_values,
		"category_values": category_values,
		"stock_qty": sum(flt(row.stock_qty) for row in rows),
		"stock_value": sum(flt(row.stock_value) for row in rows),
		"out_of_stock_count": sum(1 for row in rows if flt(row.stock_qty) <= 0),
		"low_stock_count": sum(
			1 for row in rows if flt(row.reorder_level) > 0 and flt(row.stock_qty) <= flt(row.reorder_level)
		),
		"excess_stock_count": sum(
			1 for row in rows if flt(row.reorder_level) > 0 and flt(row.stock_qty) > flt(row.reorder_level) * 2
		),
	}


def _get_no_sales_products(filters):
	args = [filters["from_date"], filters["to_date"], filters["company"]]
	conditions = ["si.docstatus = 1", "si.posting_date BETWEEN %s AND %s", "si.company = %s"]
	if filters.get("warehouse"):
		conditions.append("sii.warehouse = %s")
		args.append(filters["warehouse"])
	if filters.get("item_group"):
		conditions.append("sii.item_group = %s")
		args.append(filters["item_group"])
	sold_query = f"""
		SELECT DISTINCT sii.item_code
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {" AND ".join(conditions)}
	"""
	return frappe.db.sql(
		f"""
		SELECT i.item_code, i.item_name, i.item_group, i.brand
		FROM `tabItem` i
		LEFT JOIN ({sold_query}) sold ON sold.item_code = i.name
		WHERE i.disabled = 0 AND i.is_stock_item = 1 AND sold.item_code IS NULL
			{("AND i.name = %s" if filters.get("item_code") else "")}
		ORDER BY i.item_code
		LIMIT 200
		""",
		args + ([filters["item_code"]] if filters.get("item_code") else []),
		as_dict=True,
	)


def _get_purchase_analysis(filters):
	args = [filters["from_date"], filters["to_date"], filters["company"]]
	conditions = ["pi.docstatus = 1", "pi.posting_date BETWEEN %s AND %s", "pi.company = %s"]
	if filters.get("supplier"):
		conditions.append("pi.supplier = %s")
		args.append(filters["supplier"])
	rows = frappe.db.sql(
		f"""
		SELECT pi.supplier AS label,
			COALESCE(SUM(CASE WHEN pi.is_return = 0 THEN pi.base_net_total
				ELSE -ABS(pi.base_net_total) END), 0) AS value
		FROM `tabPurchase Invoice` pi
		WHERE {" AND ".join(conditions)}
		GROUP BY pi.supplier ORDER BY value DESC LIMIT 20
		""",
		args,
		as_dict=True,
	)
	return {"supplier_values": rows}


def _get_sales_analysis(filters):
	args = []
	conditions = _invoice_conditions(filters, args=args)
	monthly = frappe.db.sql(
		f"""
		SELECT DATE_FORMAT(si.posting_date, '%%Y-%%m') AS label,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.base_net_amount
				ELSE -ABS(sii.base_net_amount) END), 0) AS value
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {conditions}
		GROUP BY DATE_FORMAT(si.posting_date, '%%Y-%%m') ORDER BY label
		""",
		args,
		as_dict=True,
	)
	category = frappe.db.sql(
		f"""
		SELECT COALESCE(sii.item_group, 'Unspecified') AS label,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.base_net_amount
				ELSE -ABS(sii.base_net_amount) END), 0) AS value
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {conditions}
		GROUP BY sii.item_group ORDER BY value DESC LIMIT 20
		""",
		args,
		as_dict=True,
	)
	customers = frappe.db.sql(
		f"""
		SELECT si.customer AS label,
			COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.base_net_amount
				ELSE -ABS(sii.base_net_amount) END), 0) AS value
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {conditions}
		GROUP BY si.customer ORDER BY value DESC LIMIT 20
		""",
		args,
		as_dict=True,
	)
	return {"monthly": monthly, "category_values": category, "customer_values": customers}


def _get_rental_analysis(filters):
	args = [filters["from_date"], filters["to_date"], filters["company"]]
	condition_args = []
	rental_condition = _is_rental_condition(args=condition_args)
	args.extend(condition_args)
	revenue = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(CASE WHEN si.is_return = 0 THEN sii.base_net_amount
			ELSE -ABS(sii.base_net_amount) END), 0)
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1 AND si.posting_date BETWEEN %s AND %s AND si.company = %s
			AND {rental_condition}
		""",
		args,
	)[0][0]
	booking_count = frappe.db.count(
		"Rental Booking",
		{
			"docstatus": 1,
			"company": filters["company"],
			"pickup_date": ["<=", filters["to_date"]],
			"return_date": [">=", filters["from_date"]],
			"booking_status": ["not in", ["Cancelled", "Expired", "Rejected"]],
		},
	)
	settlement = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(late_fee), 0) AS late_fee,
			COALESCE(SUM(damage_deduction + missing_accessories_deduction + replacement_recovery), 0) AS damage_recovery
		FROM `tabRental Settlement`
		WHERE docstatus = 1 AND company = %s
		""",
		[filters["company"]],
		as_dict=True,
	)[0]
	return {
		"revenue": flt(revenue),
		"booking_count": booking_count,
		"late_fee": flt(settlement.late_fee),
		"damage_recovery": flt(settlement.damage_recovery),
		"utilization_days": _rental_utilization_days(filters),
		"profitability_note": _("Rental operating profit requires configured rental accounting and reliable maintenance cost entries."),
	}


def _rental_utilization_days(filters):
	return flt(
		frappe.db.sql(
			"""
			SELECT COALESCE(SUM(DATEDIFF(LEAST(end_date, %s), GREATEST(start_date, %s)) + 1), 0)
			FROM `tabRental Unit Allocation`
			WHERE docstatus = 1 AND allocation_status IN ('Hold', 'Confirmed')
				AND start_date <= %s AND end_date >= %s
			""",
			[filters["to_date"], filters["from_date"], filters["to_date"], filters["from_date"]],
		)[0][0]
	)


def _get_chart_data(filters):
	args = [filters["from_date"], filters["to_date"], filters["company"]]
	rows = frappe.db.sql(
		"""
		SELECT DATE_FORMAT(gl.posting_date, '%%Y-%%m') AS label,
			COALESCE(SUM(CASE WHEN a.root_type = 'Income' THEN gl.credit - gl.debit ELSE 0 END), 0) AS income,
			COALESCE(SUM(CASE WHEN a.root_type = 'Expense' THEN gl.debit - gl.credit ELSE 0 END), 0) AS expense
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` a ON a.name = gl.account
		WHERE gl.is_cancelled = 0 AND gl.company = %s
			AND gl.posting_date BETWEEN %s AND %s
			AND a.root_type IN ('Income', 'Expense')
		GROUP BY DATE_FORMAT(gl.posting_date, '%%Y-%%m') ORDER BY label
		""",
		[filters["company"], filters["from_date"], filters["to_date"]],
		as_dict=True,
	)
	top_revenue = sorted(_get_product_performance(filters), key=lambda row: flt(row.net_sales), reverse=True)[:10]
	top_profit = sorted(_get_product_performance(filters), key=lambda row: flt(row.gross_profit), reverse=True)[:10]
	return {
		"monthly_income_expense": rows,
		"top_revenue": [{"label": row.item_code, "value": flt(row.net_sales)} for row in top_revenue],
		"top_profit": [{"label": row.item_code, "value": flt(row.gross_profit)} for row in top_profit],
	}


def _stock_totals(filters):
	args = [filters["company"]]
	where = ["b.company = %s", "i.disabled = 0", "i.is_stock_item = 1"]
	if filters.get("warehouse"):
		where.append("b.warehouse = %s")
		args.append(filters["warehouse"])
	return dict(
		zip(
			("stock_qty", "stock_value"),
			frappe.db.sql(
				f"""
				SELECT COALESCE(SUM(b.actual_qty), 0), COALESCE(SUM(b.stock_value), 0)
				FROM `tabBin` b INNER JOIN `tabItem` i ON i.name = b.item_code
				WHERE {" AND ".join(where)}
				""",
				args,
			)[0],
		)
	)


def _get_unallocated_advances(company):
	return (
		flt(
			frappe.db.sql(
				"""
				SELECT COALESCE(SUM(unallocated_amount), 0)
				FROM `tabPayment Entry`
				WHERE docstatus = 1 AND company = %s AND payment_type = 'Receive'
					AND unallocated_amount > 0 AND party_type = 'Customer'
				""",
				[company],
			)[0][0]
		),
		flt(
			frappe.db.sql(
				"""
				SELECT COALESCE(SUM(unallocated_amount), 0)
				FROM `tabPayment Entry`
				WHERE docstatus = 1 AND company = %s AND payment_type = 'Pay'
					AND unallocated_amount > 0 AND party_type = 'Supplier'
				""",
				[company],
			)[0][0]
		),
	)


def _margin(profit, revenue):
	return flt(profit) / flt(revenue) * 100 if flt(revenue) else 0


def _get_limitations():
	return [
		_("Revenue uses submitted Sales Invoices and excludes taxes through base net amounts."),
		_("Product COGS uses Sales Invoice Item incoming rates; validate against stock valuation for items with incomplete incoming rates."),
		_("Net Profit, income, expenses, and COGS use submitted non-cancelled GL Entries and the configured chart of accounts."),
		_("Customer and supplier advances show unallocated submitted Payment Entry amounts, not every advance allocation scenario."),
		_("Rental deposits are excluded from revenue; rental revenue is counted only from matching submitted Sales Invoices."),
		_("Manufacturing variance and maintenance expense are unavailable until corresponding actual cost fields/transactions are present."),
	]
