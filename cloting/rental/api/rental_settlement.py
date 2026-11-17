import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate

from cloting.rental.constants import APPROVER_ROLES, FINANCIAL_ROLES
from cloting.rental.utils import get_settings, money, user_has_any_role


def calculate_settlement_values(booking_name):
	booking = frappe.get_doc("Rental Booking", booking_name)
	settings = get_settings()
	late_fee = 0
	returns = frappe.get_all(
		"Rental Return",
		filters={"rental_booking": booking_name, "docstatus": 1},
		fields=["name", "return_datetime", "is_late"],
	)
	seen_days = 0
	for ret in returns:
		days = date_diff(getdate(ret.return_datetime), getdate(booking.return_date))
		if days > seen_days:
			seen_days = days
	if seen_days > 0:
		late_fee = money(seen_days * flt(settings.late_fee_per_day))

	damage = 0
	missing = 0
	replacement = 0
	for insp in frappe.get_all(
		"Rental Inspection",
		filters={"rental_booking": booking_name, "docstatus": 1},
		fields=["classification", "proposed_deduction", "rental_costume_unit"],
	):
		proposed = money(insp.proposed_deduction)
		if insp.classification in ("Minor Damage", "Major Damage"):
			damage += proposed
		elif insp.classification == "Missing Accessories":
			missing += proposed
		elif insp.classification == "Lost":
			repl = frappe.db.get_value("Rental Costume Unit", insp.rental_costume_unit, "replacement_value") or 0
			replacement += money(repl)

	deposit = money(booking.deposit_received or booking.deposit_amount)
	deductions = money(late_fee + damage + missing + replacement)
	refund = money(max(deposit - deductions, 0))
	shortfall = money(max(deductions - deposit, 0))
	limit = money(settings.auto_approve_deduction_limit)
	requires_approval = deductions > limit + 0.005
	return {
		"rental_amount": money(booking.rental_amount),
		"deposit_amount": deposit,
		"late_fee": money(late_fee),
		"damage_deduction": money(damage),
		"missing_accessories_deduction": money(missing),
		"replacement_recovery": money(replacement),
		"total_deductions": deductions,
		"refund_amount": refund,
		"receivable_shortfall": shortfall,
		"requires_manager_approval": 1 if requires_approval else 0,
	}


@frappe.whitelist()
def calculate_rental_settlement(booking):
	doc = frappe.get_doc("Rental Booking", booking)
	frappe.has_permission(doc, "read", throw=True)
	return calculate_settlement_values(booking)


def validate_settlement(doc):
	if frappe.db.exists(
		"Rental Settlement",
		{"rental_booking": doc.rental_booking, "name": ["!=", doc.name], "docstatus": ["<", 2]},
	):
		frappe.throw(_("A settlement already exists for booking {0}.").format(doc.rental_booking))

	computed = calculate_settlement_values(doc.rental_booking)
	for key in (
		"rental_amount",
		"deposit_amount",
		"late_fee",
		"damage_deduction",
		"missing_accessories_deduction",
		"replacement_recovery",
		"total_deductions",
		"refund_amount",
		"receivable_shortfall",
		"requires_manager_approval",
	):
		if key != "requires_manager_approval":
			doc.set(key, computed[key])
	doc.total_deductions = money(
		flt(doc.late_fee)
		+ flt(doc.damage_deduction)
		+ flt(doc.missing_accessories_deduction)
		+ flt(doc.replacement_recovery)
	)
	deposit = money(doc.deposit_amount)
	doc.refund_amount = money(max(deposit - doc.total_deductions, 0))
	doc.receivable_shortfall = money(max(doc.total_deductions - deposit, 0))
	limit = money(get_settings().auto_approve_deduction_limit)
	doc.requires_manager_approval = 1 if doc.total_deductions > limit + 0.005 else 0

	if doc.requires_manager_approval:
		doc.settlement_status = "Pending Approval"
	else:
		doc.settlement_status = "Approved" if doc.settlement_status == "Draft" else doc.settlement_status


def before_submit_settlement(doc):
	if doc.requires_manager_approval:
		if not user_has_any_role(APPROVER_ROLES):
			frappe.throw(
				_("Deductions of {0} exceed the auto-approve limit and need a Rental Manager.").format(
					doc.total_deductions
				),
				frappe.PermissionError,
			)
		booking_owner = frappe.db.get_value("Rental Booking", doc.rental_booking, "owner")
		if frappe.session.user == booking_owner and not user_has_any_role({"Rental Admin", "System Manager"}):
			frappe.throw(
				_("The user who created the booking cannot approve deductions on the same settlement."),
				frappe.PermissionError,
			)
		doc.approved_by = frappe.session.user
	doc.settlement_status = "Approved"


def on_settlement_submit(doc):
	if cint(get_settings().auto_create_accounting_documents):
		from cloting.rental.api.rental_accounting import post_settlement_accounting

		post_settlement_accounting(doc.name)
	doc.db_set("settlement_status", "Posted")
	frappe.db.set_value("Rental Booking", doc.rental_booking, "booking_status", "Closed")


@frappe.whitelist()
def approve_settlement(settlement):
	if not user_has_any_role(APPROVER_ROLES):
		frappe.throw(_("You cannot call the deduction-approval API."), frappe.PermissionError)
	doc = frappe.get_doc("Rental Settlement", settlement)
	booking_owner = frappe.db.get_value("Rental Booking", doc.rental_booking, "owner")
	if frappe.session.user == booking_owner and not user_has_any_role({"Rental Admin", "System Manager"}):
		frappe.throw(_("Separation of duties: you cannot approve deductions on your own booking."))
	doc.approved_by = frappe.session.user
	doc.settlement_status = "Approved"
	doc.save()
	return doc.name


@frappe.whitelist()
def process_deposit_refund(settlement):
	if not user_has_any_role(FINANCIAL_ROLES):
		frappe.throw(_("Only Accounts or a Rental Manager can process a deposit refund."), frappe.PermissionError)
	doc = frappe.get_doc("Rental Settlement", settlement)
	if doc.refunded or doc.refund_journal_entry:
		frappe.throw(_("This settlement has already been refunded."))
	if doc.docstatus != 1:
		frappe.throw(_("Submit the settlement before refunding."))
	from cloting.rental.api.rental_accounting import post_deposit_refund

	post_deposit_refund(doc.name)
	return doc.name
