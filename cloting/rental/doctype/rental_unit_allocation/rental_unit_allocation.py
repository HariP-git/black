import frappe
from frappe import _
from frappe.model.document import Document

from cloting.rental.api.rental_availability import unit_is_free
from cloting.rental.utils import assert_date_range


class RentalUnitAllocation(Document):
	def validate(self):
		assert_date_range(self.start_date, self.end_date)
		if self.allocation_status not in ("Hold", "Confirmed", "Released", "Cancelled"):
			frappe.throw(_("Invalid allocation status: {0}.").format(self.allocation_status))
		booking = frappe.get_doc("Rental Booking", self.rental_booking)
		if booking.docstatus == 2 or booking.booking_status in ("Cancelled", "Expired", "Closed"):
			frappe.throw(_("Allocations cannot be created for booking {0} in status {1}.").format(
				booking.name, booking.booking_status
			))
		if self.start_date != booking.pickup_date or self.end_date != booking.return_date:
			frappe.throw(_("Allocation dates must match booking {0}.").format(booking.name))
		if self.company != booking.company:
			frappe.throw(_("Allocation company must match booking {0}.").format(booking.name))
		if self.allocation_status in ("Hold", "Confirmed") and self.docstatus < 2:
			if not unit_is_free(
				self.rental_costume_unit,
				self.start_date,
				self.end_date,
				ignore_allocation=self.name,
				for_update=True,
			):
				frappe.throw(
					_("Unit {0} is no longer available for {1} to {2}.").format(
						self.rental_costume_unit, self.start_date, self.end_date
					)
				)

	def on_submit(self):
		if self.allocation_status not in ("Hold", "Confirmed"):
			return
		status = frappe.db.get_value("Rental Costume Unit", self.rental_costume_unit, "operational_status")
		if status == "Available":
			frappe.db.set_value(
				"Rental Costume Unit",
				self.rental_costume_unit,
				{"operational_status": "Reserved", "current_booking": self.rental_booking},
			)

	def on_cancel(self):
		if self.allocation_status in ("Hold", "Confirmed"):
			self.db_set("allocation_status", "Released")
		from cloting.rental.api.rental_availability import _maybe_free_unit

		_maybe_free_unit(self.rental_costume_unit, self.rental_booking)
