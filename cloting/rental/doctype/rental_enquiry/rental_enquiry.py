import frappe
from frappe import _
from frappe.model.document import Document

from cloting.rental.utils import assert_date_range, default_company


class RentalEnquiry(Document):
	def validate(self):
		assert_date_range(self.pickup_date, self.return_date)
		self.company = self.company or default_company(self)
		if not self.items:
			frappe.throw(_("Add at least one costume to the enquiry."))
		if self.status == "Lost" and not self.lost_reason:
			frappe.throw(_("Enter a lost reason."))
