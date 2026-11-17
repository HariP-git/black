import frappe
from frappe.model.document import Document

from cloting.rental.utils import default_company


class RentalInspection(Document):
	def validate(self):
		self.company = self.company or default_company(self)

	def on_submit(self):
		unit_status = "Under Inspection"
		if self.classification in ("Good", "Normal Wear", "Requires Cleaning"):
			unit_status = "Under Cleaning"
			self._ensure_maintenance("Cleaning")
		elif self.classification in ("Minor Damage", "Major Damage"):
			unit_status = "Under Repair"
			self._ensure_maintenance("Repair")
		elif self.classification == "Lost":
			unit_status = "Lost"
		elif self.classification == "Missing Accessories":
			unit_status = "Under Cleaning"
			self._ensure_maintenance("Cleaning")
		frappe.db.set_value("Rental Costume Unit", self.rental_costume_unit, "operational_status", unit_status)
		booking = frappe.get_doc("Rental Booking", self.rental_booking)
		if booking.booking_status == "Return Inspection":
			booking.db_set("booking_status", "Settlement Pending")

	def _ensure_maintenance(self, job_type):
		if frappe.db.exists(
			"Rental Maintenance",
			{"rental_inspection": self.name, "docstatus": ["<", 2]},
		):
			return
		doc = frappe.get_doc(
			{
				"doctype": "Rental Maintenance",
				"rental_costume_unit": self.rental_costume_unit,
				"job_type": job_type,
				"rental_inspection": self.name,
				"rental_booking": self.rental_booking,
				"company": self.company,
				"branch": self.branch,
				"job_status": "Open",
			}
		)
		doc.insert(ignore_permissions=True)
