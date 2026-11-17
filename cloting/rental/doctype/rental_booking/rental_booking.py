import frappe
from frappe import _
from frappe.model.document import Document

from cloting.rental.utils import assert_date_range, default_company, get_settings, money


class RentalBooking(Document):
	def before_insert(self):
		if not self.idempotency_key:
			self.idempotency_key = frappe.generate_hash(length=16)
		else:
			existing = frappe.db.get_value(
				"Rental Booking",
				{"idempotency_key": self.idempotency_key, "name": ["!=", self.name or ""]},
				"name",
			)
			if existing:
				frappe.throw(_("A booking with this request already exists: {0}.").format(existing))

	def validate(self):
		assert_date_range(self.pickup_date, self.return_date)
		self.company = self.company or default_company(self)
		if not self.items:
			frappe.throw(_("Add at least one costume line."))
		for row in self.items:
			is_bundle = frappe.db.get_value("Rental Costume", row.rental_costume, "is_bundle")
			if row.is_bundle and not is_bundle:
				frappe.throw(_("{0} is not configured as a bundle design.").format(row.rental_costume))
			if is_bundle:
				row.is_bundle = 1
		self._set_rates_and_totals()
		self._copy_policies()
		if not self.booking_status:
			self.booking_status = "Draft"

	def before_submit(self):
		if self.booking_status in ("Draft", "Rejected", "Cancelled", "Expired"):
			frappe.throw(_("Cannot submit a booking in status {0}.").format(self.booking_status))
		for row in self.items:
			if int(row.qty or 0) < 1:
				frappe.throw(_("Quantity must be at least 1."))

	def on_cancel(self):
		from cloting.rental.api.rental_availability import release_allocations

		if self.booking_status not in ("Cancelled",):
			self.db_set("booking_status", "Cancelled")
		release_allocations(self.name)

	def _set_rates_and_totals(self):
		rental_total = 0
		deposit_total = 0
		for row in self.items:
			if not row.rental_rate:
				row.rental_rate = frappe.db.get_value("Rental Costume", row.rental_costume, "default_rental_rate")
			if not row.deposit_rate:
				row.deposit_rate = frappe.db.get_value("Rental Costume", row.rental_costume, "default_deposit")
			row.amount = money((row.rental_rate or 0) * (row.qty or 0))
			row.deposit_amount = money((row.deposit_rate or 0) * (row.qty or 0))
			rental_total += row.amount
			deposit_total += row.deposit_amount
		self.rental_amount = money(rental_total)
		self.deposit_amount = money(deposit_total)
		self.grand_total = money(rental_total - (self.discount_amount or 0) + (self.tax_amount or 0))

	def _copy_policies(self):
		settings = get_settings()
		if not self.rental_conditions:
			self.rental_conditions = settings.rental_conditions
		if not self.cancellation_policy:
			self.cancellation_policy = settings.cancellation_policy
		if not self.late_fee_policy:
			self.late_fee_policy = settings.late_fee_policy
