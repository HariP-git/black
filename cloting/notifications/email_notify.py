
from frappe.utils import add_to_date, today, date_diff
import frappe


def customer_fit_notify():
    
    date = frappe.db.get_value("Customer Fitting Appointment", filters={"docstatus": 1}, fieldname="appointment_date")
    email = frappe.db.get_value("Customer Fitting Appointment", filters={"docstatus": 1}, fieldname="email")
    
    t_date = today()
    
    if date and date_diff(date, t_date) == 2:
        frappe.msgprint("Customer Fit Appointment is scheduled for today.")
        
        frappe.sendmail(
                recipients=[email],
                subject="Customer Fit Notification",
                message="Your appointment scheduled will shortly be in 2 days."
        )
    