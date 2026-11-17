import frappe
from frappe import _

from cloting.rental.report.query import company_clause, date_clause, filters_dict


def execute(filters=None):
	filters = filters_dict(filters)
	values = {}
	data = frappe.db.sql(
		f"""
		SELECT i.name, i.rental_booking, i.rental_costume_unit, i.classification, i.proposed_deduction,
			m.name AS maintenance, m.job_type, m.job_status
		FROM `tabRental Inspection` i
		LEFT JOIN `tabRental Maintenance` m ON m.rental_inspection = i.name
		WHERE i.docstatus < 2
		{company_clause("i", filters, values)}
		{date_clause("i.creation", filters, values)}
		ORDER BY i.creation DESC
		""",
		values,
		as_dict=True,
	)
	columns = [
		{"label": _("Inspection"), "fieldname": "name", "fieldtype": "Link", "options": "Rental Inspection", "width": 150},
		{"label": _("Unit"), "fieldname": "rental_costume_unit", "fieldtype": "Link", "options": "Rental Costume Unit", "width": 150},
		{"label": _("Classification"), "fieldname": "classification", "width": 140},
		{"label": _("Deduction"), "fieldname": "proposed_deduction", "fieldtype": "Currency", "width": 110},
		{"label": _("Job"), "fieldname": "job_type", "width": 100},
		{"label": _("Job Status"), "fieldname": "job_status", "width": 110},
	]
	return columns, data
