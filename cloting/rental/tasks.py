import frappe
from frappe.utils import nowdate

from cloting.rental.api.rental_availability import release_expired_holds
from cloting.rental.api.rental_booking import refresh_overdue_bookings


def hourly():
	release_expired_holds()


def daily():
	refresh_overdue_bookings()
	expire_open_enquiries()


def expire_open_enquiries():
	today = nowdate()
	for name in frappe.get_all(
		"Rental Enquiry",
		filters={"status": ["in", ["Open", "Availability Checked", "Quotation Prepared"]], "pickup_date": ["<", today]},
		pluck="name",
	):
		frappe.db.set_value("Rental Enquiry", name, "status", "Expired")
