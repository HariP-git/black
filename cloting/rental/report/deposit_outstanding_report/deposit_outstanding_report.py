import frappe
from frappe import _

from cloting.rental.report.query import company_clause, filters_dict


def execute(filters=None):
	filters = filters_dict(filters)
	values = {}
	data = frappe.db.sql(
		f"""
		SELECT name, rental_booking, customer, deposit_amount, total_deductions, refund_amount,
			settlement_status, refunded, company
		FROM `tabRental Settlement` s
		WHERE s.docstatus < 2 AND (s.refunded = 0 OR s.settlement_status != 'Posted')
		{company_clause("s", filters, values)}
		ORDER BY s.creation ASC
		""",
		values,
		as_dict=True,
	)
	columns = [
		{"label": _("Settlement"), "fieldname": "name", "fieldtype": "Link", "options": "Rental Settlement", "width": 160},
		{"label": _("Booking"), "fieldname": "rental_booking", "fieldtype": "Link", "options": "Rental Booking", "width": 150},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
		{"label": _("Deposit"), "fieldname": "deposit_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Refund"), "fieldname": "refund_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Status"), "fieldname": "settlement_status", "width": 120},
	]
	return columns, data
