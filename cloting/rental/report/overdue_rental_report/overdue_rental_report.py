import frappe
from frappe import _
from frappe.utils import nowdate

from cloting.rental.report.query import company_clause, filters_dict


def execute(filters=None):
	filters = filters_dict(filters)
	values = {"today": nowdate()}
	data = frappe.db.sql(
		f"""
		SELECT name, customer, pickup_date, return_date, booking_status, deposit_amount, company
		FROM `tabRental Booking` b
		WHERE b.docstatus = 1
			AND b.return_date < %(today)s
			AND b.booking_status NOT IN ('Closed','Cancelled','Rejected','Expired')
		{company_clause("b", filters, values)}
		ORDER BY b.return_date ASC
		""",
		values,
		as_dict=True,
	)
	columns = [
		{"label": _("Booking"), "fieldname": "name", "fieldtype": "Link", "options": "Rental Booking", "width": 160},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Due"), "fieldname": "return_date", "fieldtype": "Date", "width": 100},
		{"label": _("Status"), "fieldname": "booking_status", "width": 140},
		{"label": _("Deposit"), "fieldname": "deposit_amount", "fieldtype": "Currency", "width": 110},
	]
	return columns, data
