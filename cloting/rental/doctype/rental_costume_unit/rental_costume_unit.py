import frappe
from frappe import _
from frappe.model.document import Document


class RentalCostumeUnit(Document):
	def before_insert(self):
		if not self.unit_code:
			self.unit_code = self._next_unit_code()
		if not self.barcode:
			self.barcode = self.unit_code

	def validate(self):
		if not self.company:
			from cloting.rental.utils import default_company

			self.company = default_company(self)
		if self.rental_costume:
			item = frappe.db.get_value("Rental Costume", self.rental_costume, "item")
			if item:
				self.item = item
			if not self.rental_rate:
				self.rental_rate = frappe.db.get_value("Rental Costume", self.rental_costume, "default_rental_rate")
			if not self.deposit_amount:
				self.deposit_amount = frappe.db.get_value("Rental Costume", self.rental_costume, "default_deposit")
			if not self.replacement_value:
				self.replacement_value = frappe.db.get_value("Rental Costume", self.rental_costume, "replacement_value")

	def _next_unit_code(self):
		colour = "".join(ch for ch in (self.colour or "").upper() if ch.isalnum())[:4] or "CLR"
		size = "".join(ch for ch in (self.size or "").upper() if ch.isalnum())[:4] or "SZ"
		prefix = f"{self.rental_costume}-{colour}-{size}-"
		existing = frappe.db.sql(
			"""
			SELECT unit_code FROM `tabRental Costume Unit`
			WHERE unit_code LIKE %s
			ORDER BY unit_code DESC LIMIT 1
			""",
			prefix + "%",
		)
		seq = 1
		if existing:
			try:
				seq = int(str(existing[0][0]).split("-")[-1]) + 1
			except ValueError:
				seq = 1
		return f"{prefix}{seq:03d}"


def on_trash(doc, method=None):
	if frappe.db.exists("Rental Unit Allocation", {"rental_costume_unit": doc.name, "docstatus": 1}):
		frappe.throw(_("Cannot delete a costume unit that has rental allocations. Cancel those first."))
