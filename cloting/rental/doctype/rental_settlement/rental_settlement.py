from frappe.model.document import Document

from cloting.rental.api.rental_settlement import (
	before_submit_settlement,
	on_settlement_submit,
	validate_settlement,
)
from cloting.rental.utils import default_company


class RentalSettlement(Document):
	def validate(self):
		self.company = self.company or default_company(self)
		if not self.customer:
			import frappe

			self.customer = frappe.db.get_value("Rental Booking", self.rental_booking, "customer")
		validate_settlement(self)

	def before_submit(self):
		before_submit_settlement(self)

	def on_submit(self):
		on_settlement_submit(self)
