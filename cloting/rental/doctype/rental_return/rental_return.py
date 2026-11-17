from frappe.model.document import Document

from cloting.rental.api.rental_return import on_return_submit, validate_return
from cloting.rental.utils import default_company


class RentalReturn(Document):
	def validate(self):
		self.company = self.company or default_company(self)
		validate_return(self)

	def on_submit(self):
		on_return_submit(self)
