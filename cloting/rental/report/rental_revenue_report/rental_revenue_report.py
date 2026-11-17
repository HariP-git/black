import frappe
from frappe import _

from cloting.rental.report.query import date_clause, filters_dict
from cloting.rental.utils import get_settings


def execute(filters=None):
	filters = filters_dict(filters)
	settings = get_settings()
	item = settings.rental_item
	values = {}
	item_clause = " AND sii.item_code = %(item)s" if item else ""
	if item:
		values["item"] = item
	company = ""
	if filters.get("company"):
		values["company"] = filters.company
		company = " AND si.company = %(company)s"
	data = frappe.db.sql(
		f"""
		SELECT si.name, si.posting_date, si.customer, si.grand_total, si.status, sii.item_code, si.remarks
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1
		{item_clause}
		{company}
		{date_clause("si.posting_date", filters, values)}
		ORDER BY si.posting_date DESC
		""",
		values,
		as_dict=True,
	)
	columns = [
		{"label": _("Invoice"), "fieldname": "name", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Amount"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
		{"label": _("Remarks"), "fieldname": "remarks", "width": 220},
	]
	return columns, data
