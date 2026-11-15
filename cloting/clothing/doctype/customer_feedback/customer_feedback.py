# Copyright (c) 2026, Hari and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from frappe.utils import today


class CustomerFeedback(Document):
	def before_insert(self):
		self.feedback_date = today()
     
