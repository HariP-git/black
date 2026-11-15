import frappe
from frappe.utils import add_to_date, today, date_diff




def return_limitation(doc, method=None):
    day1= doc.posting_date
    posting_date1 = frappe.db.get_value("POS Invoice", doc.return_against, "posting_date")
    
    day_diff = date_diff(day1, posting_date1) 
    
    if day_diff > 2:
        frappe.throw("Return is only allowed within 2 days of the original invoice date.")
        
def validate_customers(doc, method=None):
    if doc.custom_is_customized :
        frappe.msgprint("Sales Order submitted sucessfully , Make advance payment !!!")
        
    