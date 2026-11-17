import frappe
from frappe import _
from frappe.utils import add_days, add_to_date, cint, flt, get_datetime, now_datetime

from cloting.rental.api.rental_availability import (
	allocate_units_for_booking,
	check_rental_availability,
	confirm_holds,
	find_available_units,
	release_allocations,
)
from cloting.rental.utils import default_company, get_settings, money


@frappe.whitelist()
def create_rental_booking(customer, pickup_date, return_date, items, company=None, branch=None, enquiry=None, idempotency_key=None):
	frappe.has_permission("Rental Booking", "create", throw=True)
	if idempotency_key:
		existing = frappe.db.get_value("Rental Booking", {"idempotency_key": idempotency_key}, "name")
		if existing:
			return frappe.get_doc("Rental Booking", existing).as_dict()

	if isinstance(items, str):
		items = frappe.parse_json(items)

	doc = frappe.new_doc("Rental Booking")
	doc.customer = customer
	doc.pickup_date = pickup_date
	doc.return_date = return_date
	doc.company = company or default_company()
	doc.branch = branch
	doc.rental_enquiry = enquiry
	doc.idempotency_key = idempotency_key
	doc.booking_status = "Draft"
	for row in items:
		doc.append("items", row)
	doc.insert()
	return doc.as_dict()


@frappe.whitelist()
def check_booking_availability(booking):
	doc = frappe.get_doc("Rental Booking", booking)
	frappe.has_permission(doc, "write", throw=True)
	results = []
	for row in doc.items:
		result = find_available_units(
			row.rental_costume,
			row.size,
			row.colour,
			doc.pickup_date,
			doc.return_date,
			qty=row.qty,
			company=doc.company,
		)
		results.append(result)
		if not result["sufficient"]:
			doc.booking_status = "Draft"
			doc.save()
			return {"ok": False, "lines": results}
	doc.booking_status = "Availability Checked"
	doc.save()
	return {"ok": True, "lines": results}


@frappe.whitelist()
def place_temporary_hold(booking):
	doc = frappe.get_doc("Rental Booking", booking)
	frappe.has_permission(doc, "write", throw=True)
	if doc.booking_status not in ("Draft", "Availability Checked", "Awaiting Payment"):
		frappe.throw(_("Cannot place a hold on a booking in status {0}.").format(doc.booking_status))

	settings = get_settings()
	doc.hold_expires_on = add_to_date(now_datetime(), hours=cint(settings.hold_expiry_hours) or 2)
	if doc.booking_status == "Draft":
		check_booking_availability(doc.name)
		doc.reload()
	existing = frappe.db.exists(
		"Rental Unit Allocation",
		{"rental_booking": doc.name, "docstatus": 1, "allocation_status": ["in", ["Hold", "Confirmed"]]},
	)
	if not existing:
		allocate_units_for_booking(doc, allocation_status="Hold")
		doc.reload()
	doc.booking_status = "Awaiting Payment"
	doc.save()
	return {"hold_expires_on": str(doc.hold_expires_on)}


@frappe.whitelist()
def record_booking_payment(booking, rental_amount_paid=None, deposit_amount_paid=None):
	"""Record collected amounts. Accounting documents are posted separately when enabled."""
	doc = frappe.get_doc("Rental Booking", booking)
	frappe.has_permission(doc, "write", throw=True)
	if rental_amount_paid is not None:
		doc.advance_received = money(rental_amount_paid)
	if deposit_amount_paid is not None:
		doc.deposit_received = money(deposit_amount_paid)
	_refresh_payment_status(doc)
	doc.save()
	return {"payment_status": doc.payment_status, "booking_status": doc.booking_status}


def _refresh_payment_status(doc):
	settings = get_settings()
	required = money(doc.grand_total) * flt(settings.advance_payment_percent or 100) / 100.0
	if money(doc.advance_received) <= 0 and money(doc.deposit_received) <= 0:
		doc.payment_status = "Unpaid"
	elif money(doc.advance_received) + 0.005 < money(doc.grand_total):
		doc.payment_status = "Partial"
	else:
		doc.payment_status = "Paid"

	if money(doc.advance_received) + 0.005 >= required and doc.booking_status in (
		"Awaiting Payment",
		"Availability Checked",
	):
		confirm_booking(doc.name, already_loaded=doc)


@frappe.whitelist()
def confirm_booking(booking, already_loaded=None):
	doc = already_loaded or frappe.get_doc("Rental Booking", booking)
	frappe.has_permission(doc, "write", throw=True)
	settings = get_settings()
	required = money(doc.grand_total) * flt(settings.advance_payment_percent or 100) / 100.0
	if money(doc.advance_received) + 0.005 < required:
		frappe.throw(
			_("Advance of {0} is required before confirmation. Received {1}.").format(
				required, doc.advance_received
			)
		)

	holds = frappe.get_all(
		"Rental Unit Allocation",
		filters={"rental_booking": doc.name, "docstatus": 1, "allocation_status": "Hold"},
		pluck="name",
	)
	if not holds and not frappe.db.exists(
		"Rental Unit Allocation",
		{"rental_booking": doc.name, "docstatus": 1, "allocation_status": "Confirmed"},
	):
		allocate_units_for_booking(doc, allocation_status="Confirmed")
	else:
		confirm_holds(doc.name)

	doc.booking_status = "Confirmed"
	if doc.docstatus == 0:
		doc.save()
		doc.submit()
	else:
		doc.db_set("booking_status", "Confirmed")

	if doc.rental_enquiry:
		frappe.db.set_value("Rental Enquiry", doc.rental_enquiry, "status", "Converted to Booking")
		frappe.db.set_value("Rental Enquiry", doc.rental_enquiry, "converted_booking", doc.name)

	if cint(get_settings().auto_create_accounting_documents):
		from cloting.rental.api.rental_accounting import post_booking_accounting

		post_booking_accounting(doc.name)
	return doc.name


@frappe.whitelist()
def cancel_booking(booking, reason=None):
	doc = frappe.get_doc("Rental Booking", booking)
	frappe.has_permission(doc, "cancel", throw=True)
	if doc.booking_status in ("Partially Handed Over", "Rented Out", "Partially Returned", "Return Inspection"):
		frappe.throw(_("Cannot cancel after handover. Manager must resolve this as a dispute."))
	if not set(frappe.get_roles()).intersection({"Rental Manager", "Rental Admin", "System Manager"}):
		frappe.throw(_("Only a Rental Manager can cancel a booking."), frappe.PermissionError)
	release_allocations(doc.name)
	doc.booking_status = "Cancelled"
	if doc.docstatus == 1:
		doc.cancel()
	else:
		doc.save()
	if reason:
		doc.add_comment("Comment", reason)
	return doc.name


def refresh_overdue_bookings():
	# Rental dates are date-only; the return date remains due through that
	# calendar day and becomes overdue at the start of the next day.
	for name in frappe.get_all(
		"Rental Booking",
		filters={
			"docstatus": 1,
			"booking_status": ["in", ["Rented Out", "Partially Handed Over", "Partially Returned"]],
		},
		pluck="name",
	):
		return_date = frappe.db.get_value("Rental Booking", name, "return_date")
		if not return_date or now_datetime() < get_datetime(add_days(return_date, 1)):
			continue
		frappe.db.set_value("Rental Booking", name, "is_overdue", 1)
		frappe.db.set_value("Rental Booking", name, "booking_status", "Overdue")
