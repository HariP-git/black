import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate

from cloting.rental.constants import APPROVER_ROLES


def get_settings():
	return frappe.get_single("Rental Settings")


def cleaning_buffer_days():
	return cint(get_settings().cleaning_buffer_days)


def occupancy_end_exclusive(end_date, buffer_days=None):
	"""First date the unit may be booked again (exclusive of rental end + buffer)."""
	if buffer_days is None:
		buffer_days = cleaning_buffer_days()
	return add_days(getdate(end_date), cint(buffer_days))


def assert_date_range(start_date, end_date):
	start_date = getdate(start_date)
	end_date = getdate(end_date)
	if not start_date or not end_date:
		frappe.throw(_("Pickup and return dates are required."))
	if end_date < start_date:
		frappe.throw(_("Return date cannot be before pickup date."))
	return start_date, end_date


def user_has_any_role(roles):
	return bool(set(frappe.get_roles()).intersection(roles))


def assert_approver(action="approve this rental exception"):
	if not user_has_any_role(APPROVER_ROLES):
		frappe.throw(_("You are not allowed to {0}.").format(action), frappe.PermissionError)


def default_company(doc=None):
	if doc and getattr(doc, "company", None):
		return doc.company
	company = frappe.defaults.get_user_default("Company")
	if company:
		return company
	settings = get_settings()
	if settings.company:
		return settings.company
	companies = frappe.get_all("Company", pluck="name", limit=1)
	return companies[0] if companies else None


def money(value):
	return flt(value, 2)
