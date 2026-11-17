import frappe
from frappe import _
from frappe.utils import date_diff, getdate

from cloting.rental.constants import ACTIVE_ALLOCATION_STATUSES
from cloting.rental.report.query import filters_dict


def _occupied_days(allocations, from_date, to_date):
	intervals = []
	for allocation in allocations:
		start = max(getdate(allocation.start_date), from_date)
		end = min(getdate(allocation.end_date), to_date)
		if start <= end:
			intervals.append((start, end))

	occupied = 0
	for start, end in sorted(intervals):
		if not occupied:
			current_start, current_end = start, end
			occupied = date_diff(current_end, current_start) + 1
			continue
		if start <= current_end:
			if end > current_end:
				occupied += date_diff(end, current_end)
				current_end = end
		else:
			occupied += date_diff(end, start) + 1
			current_start, current_end = start, end
	return occupied


def execute(filters=None):
	filters = filters_dict(filters)
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))

	from_date = getdate(filters.from_date)
	to_date = getdate(filters.to_date)
	if to_date < from_date:
		frappe.throw(_("To Date cannot be before From Date."))

	unit_filters = {}
	if filters.get("company"):
		unit_filters["company"] = filters.company
	units = frappe.get_all(
		"Rental Costume Unit",
		filters=unit_filters,
		fields=["name", "rental_costume", "colour", "size", "company", "operational_status"],
		order_by="unit_code asc",
	)
	allocations = frappe.get_all(
		"Rental Unit Allocation",
		filters={
			"docstatus": 1,
			"allocation_status": ["in", list(ACTIVE_ALLOCATION_STATUSES)],
			"start_date": ["<=", to_date],
			"end_date": [">=", from_date],
		},
		fields=["rental_costume_unit", "start_date", "end_date"],
	)
	by_unit = {}
	for allocation in allocations:
		by_unit.setdefault(allocation.rental_costume_unit, []).append(allocation)

	available_days = date_diff(to_date, from_date) + 1
	data = []
	for unit in units:
		rented_days = _occupied_days(by_unit.get(unit.name, []), from_date, to_date)
		data.append(
			{
				**unit,
				"available_days": available_days,
				"rented_days": rented_days,
				"utilization_percent": round(rented_days * 100 / available_days, 2),
			}
		)

	columns = [
		{"label": _("Unit"), "fieldname": "name", "fieldtype": "Link", "options": "Rental Costume Unit", "width": 180},
		{"label": _("Costume"), "fieldname": "rental_costume", "fieldtype": "Link", "options": "Rental Costume", "width": 140},
		{"label": _("Colour"), "fieldname": "colour", "width": 100},
		{"label": _("Size"), "fieldname": "size", "width": 80},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
		{"label": _("Status"), "fieldname": "operational_status", "width": 120},
		{"label": _("Available Days"), "fieldname": "available_days", "fieldtype": "Int", "width": 120},
		{"label": _("Rented Days"), "fieldname": "rented_days", "fieldtype": "Int", "width": 110},
		{"label": _("Utilization %"), "fieldname": "utilization_percent", "fieldtype": "Percent", "width": 120},
	]
	return columns, data
