import frappe
from frappe import _

from cloting.rental.report.query import company_clause, date_clause, filters_dict


def execute(filters=None):
	filters = filters_dict(filters)
	values = {}
	data = frappe.db.sql(
		f"""
		SELECT h.name, h.rental_booking, h.handover_datetime, h.storekeeper, i.rental_costume_unit, i.condition_at_issue
		FROM `tabRental Handover` h
		INNER JOIN `tabRental Handover Item` i ON i.parent = h.name
		WHERE h.docstatus = 1
		{company_clause("h", filters, values)}
		{date_clause("DATE(h.handover_datetime)", filters, values)}
		ORDER BY h.handover_datetime DESC
		""",
		values,
		as_dict=True,
	)
	columns = [
		{"label": _("Handover"), "fieldname": "name", "fieldtype": "Link", "options": "Rental Handover", "width": 150},
		{"label": _("Booking"), "fieldname": "rental_booking", "fieldtype": "Link", "options": "Rental Booking", "width": 150},
		{"label": _("When"), "fieldname": "handover_datetime", "fieldtype": "Datetime", "width": 160},
		{"label": _("Unit"), "fieldname": "rental_costume_unit", "fieldtype": "Link", "options": "Rental Costume Unit", "width": 160},
		{"label": _("Condition"), "fieldname": "condition_at_issue", "width": 120},
	]
	return columns, data
