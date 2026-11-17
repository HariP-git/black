from collections import defaultdict
from datetime import date, timedelta

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime


ALLOWED_ROLES = {"System Manager", "Owner", "Sales Manager", "Stock Manager"}


@frappe.whitelist()
def get_dashboard_data(from_date=None, to_date=None, company=None, warehouse=None):
	_validate_access()
	from_date, to_date = _validate_dates(from_date, to_date)
	company = _validate_company(company)
	warehouse = _validate_warehouse(warehouse, company)

	return {
		"filters": {
			"from_date": from_date.isoformat(),
			"to_date": to_date.isoformat(),
			"company": company,
			"warehouse": warehouse,
		},
		"updated_at": now_datetime().strftime("%Y-%m-%d %H:%M:%S"),
		"kpis": _get_kpis(from_date, to_date, company, warehouse),
		"sales": _get_sales_analytics(from_date, to_date, company),
		"inventory": _get_inventory_analytics(company, warehouse),
		"customers": _get_customer_analytics(from_date, to_date, company),
		"buying": _get_buying_analytics(from_date, to_date, company),
		"custom": _get_custom_analytics(from_date, to_date),
	}


def _validate_access():
	if not ALLOWED_ROLES.intersection(set(frappe.get_roles())):
		frappe.throw(_("You do not have permission to access the Retail Management Dashboard."), frappe.PermissionError)


def _validate_dates(from_date, to_date):
	try:
		to_date = getdate(to_date) if to_date else date.today()
		from_date = getdate(from_date) if from_date else to_date - timedelta(days=29)
	except Exception:
		frappe.throw(_("Please provide valid dashboard dates."))
	if from_date > to_date:
		frappe.throw(_("From Date cannot be later than To Date."))
	if (to_date - from_date).days > 366:
		frappe.throw(_("The dashboard date range cannot exceed one year."))
	return from_date, to_date


def _validate_company(company):
	companies = frappe.get_all("Company", filters={"is_group": 0}, pluck="name")
	if company and company not in companies:
		frappe.throw(_("Invalid company."))
	if len(companies) == 1:
		return companies[0]
	if not company:
		frappe.throw(_("Please select a company."))
	return company


def _validate_warehouse(warehouse, company):
	if not warehouse:
		return None
	if not frappe.db.exists("Warehouse", {"name": warehouse, "company": company, "disabled": 0}):
		frappe.throw(_("Invalid warehouse for the selected company."))
	return warehouse


def _company_condition(field, company, args):
	args.append(company)
	return f" AND {field} = %s"


def _warehouse_condition(field, warehouse, args):
	if warehouse:
		args.append(warehouse)
		return f" AND {field} = %s"
	return ""


def _get_kpis(from_date, to_date, company, warehouse):
	args = [from_date, to_date]
	company_condition = _company_condition("company", company, args)
	sales = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(base_grand_total), 0) AS total_sales,
			COUNT(*) AS invoice_count
		FROM `tabSales Invoice`
		WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s
			{company_condition}
		""",
		args,
		as_dict=True,
	)[0]
	purchase = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(base_grand_total), 0)
		FROM `tabPurchase Invoice`
		WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s
			AND is_return = 0 {company_condition}
		""",
		[from_date, to_date, company],
	)[0][0]
	stock_args = [company]
	stock_where = _warehouse_condition("b.warehouse", warehouse, stock_args)
	stock = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(b.actual_qty), 0), COALESCE(SUM(b.stock_value), 0)
		FROM `tabBin` b INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.company = %s AND i.disabled = 0 AND i.is_stock_item = 1 {stock_where}
		""",
		stock_args,
	)[0]
	outstanding = frappe.db.sql(
		"""SELECT COALESCE(SUM(outstanding_amount), 0)
		FROM `tabSales Invoice`
		WHERE docstatus = 1 AND company = %s""",
		[company],
	)[0][0]
	customers = frappe.db.sql(
		"SELECT COUNT(*) FROM `tabCustomer` WHERE disabled = 0",
	)[0][0]
	return {
		"total_sales": flt(sales.total_sales),
		"invoice_count": sales.invoice_count,
		"average_order_value": flt(sales.total_sales) / sales.invoice_count if sales.invoice_count else 0,
		"purchase_value": flt(purchase),
		"customers": customers,
		"outstanding": flt(outstanding),
		"stock_qty": flt(stock[0]),
		"stock_value": flt(stock[1]),
		"low_stock_count": _get_low_stock_count(company, warehouse),
	}


def _get_sales_analytics(from_date, to_date, company):
	args = [from_date, to_date, company]
	daily = frappe.db.sql(
		"""SELECT posting_date AS label, COALESCE(SUM(base_grand_total), 0) AS value
		FROM `tabSales Invoice`
		WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s
			AND company = %s GROUP BY posting_date ORDER BY posting_date""",
		args,
		as_dict=True,
	)
	monthly = frappe.db.sql(
		"""SELECT DATE_FORMAT(posting_date, '%%Y-%%m') AS label,
			COALESCE(SUM(base_grand_total), 0) AS value
		FROM `tabSales Invoice`
		WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s
			AND company = %s GROUP BY DATE_FORMAT(posting_date, '%%Y-%%m')
		ORDER BY label""",
		args,
		as_dict=True,
	)
	groups = frappe.db.sql(
		"""SELECT COALESCE(i.item_group, 'Unspecified') AS label,
			COALESCE(SUM(sii.base_amount), 0) AS value
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		LEFT JOIN `tabItem` i ON i.name = sii.item_code
		WHERE si.docstatus = 1 AND si.posting_date BETWEEN %s AND %s
			AND si.company = %s GROUP BY i.item_group ORDER BY value DESC LIMIT 10""",
		args,
		as_dict=True,
	)
	products = frappe.db.sql(
		"""SELECT sii.item_code AS label, COALESCE(SUM(sii.base_amount), 0) AS value
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1 AND si.posting_date BETWEEN %s AND %s
			AND si.company = %s GROUP BY sii.item_code ORDER BY value DESC LIMIT 10""",
		args,
		as_dict=True,
	)
	payments = frappe.db.sql(
		"""SELECT sip.mode_of_payment AS label, COALESCE(SUM(sip.amount), 0) AS value
		FROM `tabSales Invoice Payment` sip
		INNER JOIN `tabSales Invoice` si ON si.name = sip.parent
		WHERE si.docstatus = 1 AND si.posting_date BETWEEN %s AND %s
			AND si.company = %s GROUP BY sip.mode_of_payment ORDER BY value DESC""",
		args,
		as_dict=True,
	)
	return {key: _series(value) for key, value in {
		"daily": daily, "monthly": monthly, "item_groups": groups,
		"products": products, "payments": payments,
	}.items()}


def _get_inventory_analytics(company, warehouse):
	args = [company]
	warehouse_condition = _warehouse_condition("b.warehouse", warehouse, args)
	top_items = frappe.db.sql(
		f"""SELECT b.item_code AS label, COALESCE(SUM(b.stock_value), 0) AS value
		FROM `tabBin` b INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.company = %s AND i.disabled = 0 AND i.is_stock_item = 1 {warehouse_condition}
		GROUP BY b.item_code ORDER BY value DESC LIMIT 10""",
		args,
		as_dict=True,
	)
	warehouses = frappe.db.sql(
		f"""SELECT b.warehouse AS label, COALESCE(SUM(b.stock_value), 0) AS value
		FROM `tabBin` b INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.company = %s AND i.disabled = 0 AND i.is_stock_item = 1 {warehouse_condition}
		GROUP BY b.warehouse ORDER BY value DESC""",
		args,
		as_dict=True,
	)
	stock_args = [company]
	stock_where = _warehouse_condition("b.warehouse", warehouse, stock_args)
	counts = frappe.db.sql(
		f"""SELECT COALESCE(SUM(b.actual_qty), 0), COALESCE(SUM(b.stock_value), 0)
		FROM `tabBin` b INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.company = %s AND i.disabled = 0 AND i.is_stock_item = 1 {stock_where}""",
		stock_args,
	)[0]
	return {
		"stock_qty": flt(counts[0]), "stock_value": flt(counts[1]),
		"low_stock_count": _get_low_stock_count(company, warehouse),
		"out_of_stock_count": _get_out_of_stock_count(company, warehouse),
		"top_items": _series(top_items), "warehouses": _series(warehouses),
	}


def _get_low_stock_count(company, warehouse):
	args = [company]
	where = _warehouse_condition("b.warehouse", warehouse, args)
	return frappe.db.sql(
		f"""SELECT COUNT(DISTINCT b.item_code)
		FROM `tabBin` b INNER JOIN `tabItem` i ON i.name = b.item_code
		INNER JOIN `tabItem Reorder` r ON r.parent = b.item_code
		WHERE b.company = %s AND i.disabled = 0 AND i.is_stock_item = 1
			AND b.actual_qty <= r.warehouse_reorder_level {where}""",
		args,
	)[0][0]


def _get_out_of_stock_count(company, warehouse):
	args = [company]
	where = _warehouse_condition("b.warehouse", warehouse, args)
	return frappe.db.sql(
		f"""SELECT COUNT(DISTINCT b.item_code)
		FROM `tabBin` b INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.company = %s AND i.disabled = 0 AND i.is_stock_item = 1
			AND b.actual_qty <= 0 {where}""",
		args,
	)[0][0]


def _get_customer_analytics(from_date, to_date, company):
	args = [from_date, to_date, company]
	new_customers = frappe.db.sql(
		"SELECT COUNT(*) FROM `tabCustomer` WHERE creation BETWEEN %s AND DATE_ADD(%s, INTERVAL 1 DAY)",
		[from_date, to_date],
	)[0][0]
	top = frappe.db.sql(
		"""SELECT customer AS label, COALESCE(SUM(base_grand_total), 0) AS value
		FROM `tabSales Invoice` WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s
		AND company = %s GROUP BY customer ORDER BY value DESC LIMIT 10""",
		args,
		as_dict=True,
	)
	groups = frappe.db.sql(
		"""SELECT customer_group AS label, COALESCE(SUM(base_grand_total), 0) AS value
		FROM `tabSales Invoice` WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s
		AND company = %s GROUP BY customer_group ORDER BY value DESC""",
		args,
		as_dict=True,
	)
	types = frappe.db.sql(
		"""SELECT c.customer_type AS label, COALESCE(SUM(si.base_grand_total), 0) AS value
		FROM `tabSales Invoice` si INNER JOIN `tabCustomer` c ON c.name = si.customer
		WHERE si.docstatus = 1 AND si.posting_date BETWEEN %s AND %s AND si.company = %s
		GROUP BY c.customer_type""",
		args,
		as_dict=True,
	)
	return {"new_customers": new_customers, "top_customers": _series(top),
		"groups": _series(groups), "types": _series(types)}


def _get_buying_analytics(from_date, to_date, company):
	args = [from_date, to_date, company]
	supplier = frappe.db.sql(
		"""SELECT supplier AS label, COALESCE(SUM(base_grand_total), 0) AS value
		FROM `tabPurchase Invoice` WHERE docstatus = 1 AND posting_date BETWEEN %s AND %s
		AND company = %s AND is_return = 0 GROUP BY supplier ORDER BY value DESC LIMIT 10""",
		args,
		as_dict=True,
	)
	pending_po = frappe.db.sql(
		"""SELECT COUNT(*) FROM `tabPurchase Order`
		WHERE docstatus = 1 AND company = %s AND status NOT IN ('Completed','Closed','Cancelled')""",
		[company],
	)[0][0]
	pending_pr = frappe.db.sql(
		"""SELECT COUNT(*) FROM `tabPurchase Receipt`
		WHERE docstatus = 1 AND company = %s AND status NOT IN ('Completed','Closed','Cancelled')""",
		[company],
	)[0][0]
	return {"supplier_purchase": _series(supplier), "pending_po": pending_po, "pending_pr": pending_pr}


def _get_custom_analytics(from_date, to_date):
	feedback = frappe.db.sql(
		"""SELECT COUNT(*) AS count, COALESCE(AVG(overall_rating), 0) AS average_rating
		FROM `tabCustomer Feedback` WHERE feedback_date BETWEEN %s AND %s""",
		[from_date, to_date],
		as_dict=True,
	)[0]
	quality = frappe.db.sql(
		"""SELECT COUNT(*) AS count, COALESCE(AVG(overall_rating), 0) AS average_rating
		FROM `tabSupplier Quality Rating` WHERE docstatus = 1""",
		as_dict=True,
	)[0]
	launches = frappe.db.sql(
		"""SELECT status AS label, COUNT(*) AS value FROM `tabProduct Launch`
		GROUP BY status ORDER BY status""",
		as_dict=True,
	)
	return {
		"feedback": {"count": feedback.count, "average_rating": flt(feedback.average_rating)},
		"supplier_quality": {"count": quality.count, "average_rating": flt(quality.average_rating)},
		"launches": _series(launches),
		"omitted": [
			"Pending and completed customization orders: the available customization DocTypes have no status field.",
			"Customer loyalty: no loyalty metrics were found in the installed custom app.",
		],
	}


def _series(rows):
	return [{"label": row.label, "value": flt(row.value)} for row in rows]
