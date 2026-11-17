import frappe
from frappe import _
from frappe.model.document import Document


class RentalCostume(Document):
	def validate(self):
		if not self.company:
			from cloting.rental.utils import default_company

			self.company = default_company(self)
		if self.item and not frappe.db.exists("Item", self.item):
			frappe.throw(_("Item {0} does not exist.").format(self.item))
		if not self.is_bundle:
			return
		if not self.components:
			frappe.throw(_("A bundle design must contain at least one component."))
		seen = set()
		seen_costumes = set()
		for row in self.components:
			if row.component_costume == self.name:
				frappe.throw(_("A bundle cannot contain itself."))
			if row.component_role in seen:
				frappe.throw(_("Component role {0} is duplicated.").format(row.component_role))
			if row.component_costume in seen_costumes:
				frappe.throw(_("Component costume {0} is duplicated. Use its quantity instead.").format(row.component_costume))
			if int(row.qty or 0) < 1:
				frappe.throw(_("Component quantity must be at least 1."))
			if not frappe.db.exists("Rental Costume", row.component_costume):
				frappe.throw(_("Component costume {0} does not exist.").format(row.component_costume))
			seen.add(row.component_role)
			seen_costumes.add(row.component_costume)
