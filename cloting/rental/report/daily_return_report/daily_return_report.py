import frappe
from frappe import _

from cloting.rental.report.query import company_clause, date_clause, filters_dict


def execute(filters=None):
	filters = filters_dict(filters)
	values = {}
	data = frappe.db.sql(
		f"""
		SELECT r.name, r.rental_booking, r.return_datetime, r.is_late, i.rental_costume_unit, i.condition_at_return
		FROM `tabRental Return` r
		INNER JOIN `tabRental Return Item` i ON i.parent = r.name
		WHERE r.docstatus = 1
		{company_clause("r", filters, values)}
		{date_clause("DATE(r.return_datetime)", filters, values)}
		ORDER BY r.return_datetime DESC
		""",
		values,
		as_dict=True,
	)
	columns = [
		{"label": _("Return"), "fieldname": "name", "fieldtype": "Link", "options": "Rental Return", "width": 150},
		{"label": _("Booking"), "fieldname": "rental_booking", "fieldtype": "Link", "options": "Rental Booking", "width": 150},
		{"label": _("When"), "fieldname": "return_datetime", "fieldtype": "Datetime", "width": 160},
		{"label": _("Late"), "fieldname": "is_late", "fieldtype": "Check", "width": 70},
		{"label": _("Unit"), "fieldname": "rental_costume_unit", "fieldtype": "Link", "options": "Rental Costume Unit", "width": 160},
		{"label": _("Condition"), "fieldname": "condition_at_return", "width": 120},
	]
	return columns, data
