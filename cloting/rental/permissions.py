import frappe

from cloting.rental.constants import APPROVER_ROLES

RENTAL_APP_ROLES = APPROVER_ROLES | {"Rental Cashier", "Rental Storekeeper", "Accounts User"}


def has_app_permission():
	return bool(set(frappe.get_roles()).intersection(RENTAL_APP_ROLES))


def settlement_has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if ptype != "submit":
		return None
	if getattr(doc, "requires_manager_approval", 0):
		roles = set(frappe.get_roles(user))
		if not roles.intersection(APPROVER_ROLES):
			return False
		if user == frappe.db.get_value("Rental Booking", doc.rental_booking, "owner") and "Rental Admin" not in roles and "System Manager" not in roles:
			return False
	return None
