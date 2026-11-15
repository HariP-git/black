# Copyright (c) 2026, Hari and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document


class SupplierQualityRating(Document):
	def before_save(self):
		self.rating_date = frappe.utils.nowdate()
		val1 = self.quality_rating
		val2 = self.lead_time_rating
		val3 = self.price_rating
		self.overall_rating = (val1 + val2 + val3) / 3
	def validate(self):
		if self.quality_rating < 1 or self.quality_rating > 5:
			frappe.throw("Quality rating must be between 1 and 5.")
		if self.lead_time_rating < 1 or self.lead_time_rating > 5:
			frappe.throw("Lead time rating must be between 1 and 5.")
		if self.price_rating < 1 or self.price_rating > 5:
			frappe.throw("Price rating must be between 1 and 5.")

   

