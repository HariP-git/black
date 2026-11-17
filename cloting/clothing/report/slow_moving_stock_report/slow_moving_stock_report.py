import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, today


DEFAULT_DAYS_WITHOUT_SALE = 60


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	data = get_data(filters)
	return get_columns(), data, None, None, get_report_summary(data, filters)


def validate_filters(filters):
	filters.days_without_sale = cint(
		filters.get("days_without_sale") or DEFAULT_DAYS_WITHOUT_SALE
	)
	if filters.days_without_sale < 0:
		frappe.throw(_("Days Without Sale cannot be negative."))


def get_columns():
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 130,
		},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Link", "options": "Brand", "width": 110},
		{
			"label": _("Warehouse"),
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 150,
		},
		{
			"label": _("Available Quantity"),
			"fieldname": "available_qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Last Sales Date"),
			"fieldname": "last_sales_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": _("Days Without Sale"),
			"fieldname": "days_without_sale",
			"fieldtype": "Int",
			"width": 125,
		},
		{
			"label": _("Stock Value"),
			"fieldname": "stock_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
		},
		{"label": _("Sales Status"), "fieldname": "sales_status", "fieldtype": "Data", "width": 110},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


def get_data(filters):
	conditions = [
		"item.disabled = 0",
		"item.is_stock_item = 1",
		"bin.actual_qty > 0",
		"(sales.last_sales_date IS NULL OR DATEDIFF(%(as_of_date)s, sales.last_sales_date) >= %(days_without_sale)s)",
	]
	values = {
		"as_of_date": getdate(today()),
		"days_without_sale": filters.days_without_sale,
	}

	for fieldname in ("company", "warehouse"):
		if filters.get(fieldname):
			conditions.append(f"bin.{fieldname} = %({fieldname})s")
			values[fieldname] = filters[fieldname]

	for fieldname in ("item_group", "brand"):
		if filters.get(fieldname):
			conditions.append(f"item.{fieldname} = %({fieldname})s")
			values[fieldname] = filters[fieldname]

	return frappe.db.sql(
		f"""
		SELECT
			item.item_code,
			item.item_name,
			item.item_group,
			item.brand,
			bin.warehouse,
			bin.actual_qty AS available_qty,
			sales.last_sales_date,
			CASE
				WHEN sales.last_sales_date IS NULL THEN NULL
				ELSE DATEDIFF(%(as_of_date)s, sales.last_sales_date)
			END AS days_without_sale,
			bin.stock_value,
			company.default_currency AS currency,
			CASE
				WHEN sales.last_sales_date IS NULL THEN 'Never Sold'
				ELSE 'Slow Moving'
			END AS sales_status
		FROM `tabBin` bin
		INNER JOIN `tabItem` item
			ON item.name = bin.item_code
		INNER JOIN `tabCompany` company
			ON company.name = bin.company
		LEFT JOIN (
			SELECT
				sales_invoice_item.item_code,
				sales_invoice_item.warehouse,
				sales_invoice.company,
				MAX(sales_invoice.posting_date) AS last_sales_date
			FROM `tabSales Invoice Item` sales_invoice_item
			INNER JOIN `tabSales Invoice` sales_invoice
				ON sales_invoice.name = sales_invoice_item.parent
			WHERE sales_invoice.docstatus = 1
				AND COALESCE(sales_invoice.is_return, 0) = 0
				AND sales_invoice_item.qty > 0
				AND sales_invoice_item.warehouse IS NOT NULL
				AND sales_invoice_item.warehouse != ''
			GROUP BY
				sales_invoice_item.item_code,
				sales_invoice_item.warehouse,
				sales_invoice.company
		) sales
			ON sales.item_code = bin.item_code
			AND sales.warehouse = bin.warehouse
			AND sales.company = bin.company
		WHERE {" AND ".join(conditions)}
		ORDER BY sales_status, item.item_code, bin.warehouse
		""",
		values,
		as_dict=True,
	)


def get_report_summary(data, filters):
	if not data or not filters.get("company"):
		return None

	return [
		{
			"value": sum(flt(row.stock_value) for row in data),
			"indicator": "Orange",
			"label": _("Total Stock Value"),
			"datatype": "Currency",
			"currency": data[0].currency,
		}
	]
