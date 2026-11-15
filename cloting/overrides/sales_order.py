import frappe
from frappe.utils import flt, getdate, nowdate
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

def validate_customers(doc, method=None):
    if doc.custom_is_customized :
        frappe.msgprint("Sales Order submitted sucessfully , Make advance payment !!!")
        



@frappe.whitelist()
def create_advance_payment(
    sales_order,
    paid_amount,
    posting_date,
    mode_of_payment,
    paid_to
):
    so = frappe.get_doc("Sales Order", sales_order)
    so.check_permission("read")

    
    if so.docstatus != 1:
        frappe.throw(("Sales Order must be submitted."))

   
    paid_amount = flt(paid_amount)

    if paid_amount <= 0:
        frappe.throw(("Amount Collected must be greater than zero."))

    if getdate(posting_date) > getdate(nowdate()):
        frappe.throw(("Posting Date cannot be in the future."))


    if not frappe.db.exists("Mode of Payment", mode_of_payment):
        frappe.throw(("Invalid Mode of Payment."))

    account = frappe.db.get_value(
        "Account",
        paid_to,
        ["company", "is_group", "disabled"],
        as_dict=True
    )


    pe = get_payment_entry(
        "Sales Order",
        so.name,
        bank_account=paid_to
    )

  
    pe.payment_type = "Receive"
    pe.party_type = "Customer"
    pe.party = so.customer
    pe.company = so.company
    pe.posting_date = posting_date
    pe.mode_of_payment = mode_of_payment
    pe.paid_to = paid_to


    if not pe.references:
        frappe.throw(
            ("Sales Order reference was not generated in Payment Entry.")
        )



    pe.paid_amount = paid_amount
    pe.received_amount = paid_amount


    reference = pe.references[0]
    reference.reference_doctype = "Sales Order"
    reference.reference_name = so.name
    reference.allocated_amount = paid_amount


    pe.insert()
    pe.submit()

    return pe.name           
     
        
        

        
        
