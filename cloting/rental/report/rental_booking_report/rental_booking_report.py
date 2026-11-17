import frappe
from frappe import _

from cloting.rental.report.query import company_clause, date_clause, filters_dict


def execute(filters=None):
	filters = filters_dict(filters)
	values = {}
	status = ""
	if filters.get("booking_status"):
		values["booking_status"] = filters.booking_status
		status = " AND b.booking_status = %(booking_status)s"
	if filters.get("customer"):
		values["customer"] = filters.customer
		status += " AND b.customer = %(customer)s"
	data = frappe.db.sql(
		f"""
		SELECT b.name, b.customer, b.pickup_date, b.return_date, b.booking_status,
			b.payment_status, b.rental_amount, b.deposit_amount, b.grand_total, b.company
		FROM `tabRental Booking` b
		WHERE b.docstatus < 2
		{company_clause("b", filters, values)}
		{date_clause("b.pickup_date", filters, values)}
		{status}
		ORDER BY b.pickup_date DESC
		""",
		values,
		as_dict=True,
	)
	columns = [
		{"label": _("Booking"), "fieldname": "name", "fieldtype": "Link", "options": "Rental Booking", "width": 160},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Pickup"), "fieldname": "pickup_date", "fieldtype": "Date", "width": 100},
		{"label": _("Return"), "fieldname": "return_date", "fieldtype": "Date", "width": 100},
		{"label": _("Status"), "fieldname": "booking_status", "width": 140},
		{"label": _("Payment"), "fieldname": "payment_status", "width": 90},
		{"label": _("Rental"), "fieldname": "rental_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Deposit"), "fieldname": "deposit_amount", "fieldtype": "Currency", "width": 110},
	]
	return columns, data
