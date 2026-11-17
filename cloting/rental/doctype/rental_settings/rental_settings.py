import frappe
from frappe import _
from frappe.model.document import Document


class RentalSettings(Document):
	def validate(self):
		if (self.cleaning_buffer_days or 0) < 0:
			frappe.throw(_("Cleaning buffer days cannot be negative."))
		if (self.hold_expiry_hours or 0) < 0:
			frappe.throw(_("Hold expiry hours cannot be negative."))
