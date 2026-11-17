import frappe

RENTAL_ROLES = [
	"Rental Cashier",
	"Rental Storekeeper",
	"Rental Manager",
	"Rental Admin",
]


def after_migrate():
	ensure_roles()
	ensure_indexes()
	ensure_onboarding()


def ensure_roles():
	for role in RENTAL_ROLES:
		if not frappe.db.exists("Role", role):
			doc = frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1, "is_custom": 1})
			doc.insert(ignore_permissions=True)


def ensure_indexes():
	if not frappe.db.exists("DocType", "Rental Unit Allocation"):
		return
	try:
		frappe.db.add_index(
			"Rental Unit Allocation",
			["rental_costume_unit", "start_date", "end_date"],
			index_name="rental_unit_dates",
		)
	except Exception:
		pass
	try:
		frappe.db.add_index("Rental Costume Unit", ["rental_costume", "colour", "size", "operational_status"])
	except Exception:
		pass


def ensure_onboarding():
	if not frappe.db.exists("Module Onboarding", "Rental Onboarding"):
		return
	titles = {
		"Configure Rental Settings": "Configure rental settings",
		"Add Rental Costume": "Add a rental costume design",
		"Create Rental Bundle Design": "Create a rental bundle design",
		"Register Physical Costume Unit": "Register a physical costume unit",
		"Create Rental Customer": "Add a customer",
		"Create Rental Enquiry": "Create a rental enquiry",
		"Create Rental Booking": "Create a rental booking",
		"View Costume Availability": "Check costume availability",
	}
	for name, title in titles.items():
		if frappe.db.exists("Onboarding Step", name):
			frappe.db.set_value("Onboarding Step", name, "title", title, update_modified=False)
	for row in frappe.get_all(
		"Onboarding Step Map",
		filters={"parenttype": "Module Onboarding", "parent": "Rental Onboarding", "step": "View Costume Availability"},
		pluck="name",
	):
		frappe.db.set_value("Onboarding Step Map", row, "is_optional", 0, update_modified=False)
