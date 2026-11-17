import frappe
from frappe import _

from cloting.rental.api.rental_availability import find_available_units
from cloting.rental.report.query import filters_dict


def execute(filters=None):
	filters = filters_dict(filters)
	columns = [
		{"label": _("Unit"), "fieldname": "name", "fieldtype": "Link", "options": "Rental Costume Unit", "width": 180},
		{"label": _("Costume"), "fieldname": "rental_costume", "fieldtype": "Link", "options": "Rental Costume", "width": 140},
		{"label": _("Colour"), "fieldname": "colour", "width": 100},
		{"label": _("Size"), "fieldname": "size", "width": 80},
		{"label": _("Status"), "fieldname": "operational_status", "width": 120},
		{"label": _("Available for range"), "fieldname": "available_for_range", "fieldtype": "Check", "width": 140},
	]
	units = frappe.get_all(
		"Rental Costume Unit",
		filters={k: filters[k] for k in ("rental_costume", "colour", "size", "company") if filters.get(k)},
		fields=["name", "rental_costume", "colour", "size", "operational_status", "company"],
	)
	if not (filters.get("from_date") and filters.get("to_date") and filters.get("rental_costume") and filters.get("colour") and filters.get("size")):
		for u in units:
			u["available_for_range"] = 0
		return columns, units

	result = find_available_units(
		filters.rental_costume,
		filters.size,
		filters.colour,
		filters.from_date,
		filters.to_date,
		qty=1,
		company=filters.get("company"),
	)
	free = set(result.get("available_unit_ids") or [])
	# available_units may contain more than qty
	free = set(u["name"] for u in result.get("available_units") or [])
	for u in units:
		u["available_for_range"] = 1 if u.name in free else 0
	return columns, units
