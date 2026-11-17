from frappe.model.document import Document

from cloting.rental.api.rental_handover import on_handover_submit, validate_handover
from cloting.rental.utils import default_company


class RentalHandover(Document):
	def validate(self):
		self.company = self.company or default_company(self)
		validate_handover(self)

	def on_submit(self):
		on_handover_submit(self)
