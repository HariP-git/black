# Copyright (c) 2026, Hari and contributors
# For license information, please see license.txt

# import frappe
import frappe
from frappe.model.document import Document


class IndividualCustomizationDetail(Document):
    def validate(self):
        if self.garment_item == "" or self.garment_item is None:
            frappe.throw("Garment Item is required.")
        if self.measument_value ==  "":
            frappe.throw("Measurement Value is required.")
            	



        
     
     
