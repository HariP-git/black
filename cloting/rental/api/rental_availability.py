import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, now_datetime

from cloting.rental.constants import ACTIVE_ALLOCATION_STATUSES, BLOCKING_UNIT_STATUSES, CLEANING_STATUS
from cloting.rental.utils import assert_date_range, cleaning_buffer_days, occupancy_end_exclusive


def _candidate_units(costume, size, colour, company=None):
	filters = {
		"rental_costume": costume,
		"size": size,
		"colour": colour,
		"operational_status": ["not in", list(BLOCKING_UNIT_STATUSES) + [CLEANING_STATUS]],
	}
	if company:
		filters["company"] = company
	return frappe.get_all(
		"Rental Costume Unit",
		filters=filters,
		fields=[
			"name",
			"unit_code",
			"barcode",
			"operational_status",
			"condition",
			"rental_rate",
			"deposit_amount",
			"replacement_value",
			"warehouse",
			"company",
			"branch",
		],
		order_by="unit_code asc",
	)


def _overlap_map(unit_names, start_date, end_date, buffer_days, ignore_allocation=None):
	"""Return {unit: [blocking allocations]} for the requested inclusive date range."""
	if not unit_names:
		return {}
	now = now_datetime()
	rows = frappe.db.sql(
		"""
		SELECT
			name,
			rental_costume_unit,
			rental_booking,
			start_date,
			end_date,
			allocation_status,
			hold_expires_on,
			docstatus
		FROM `tabRental Unit Allocation`
		WHERE rental_costume_unit IN %(units)s
			AND docstatus = 1
			AND allocation_status IN %(statuses)s
			AND start_date <= %(end_date)s
		""",
		{
			"units": unit_names,
			"statuses": ACTIVE_ALLOCATION_STATUSES,
			"end_date": end_date,
		},
		as_dict=True,
	)
	blocked = {name: [] for name in unit_names}
	for row in rows:
		if ignore_allocation and row.name == ignore_allocation:
			continue
		if row.allocation_status == "Hold" and row.hold_expires_on and get_datetime(row.hold_expires_on) < now:
			continue
		exclusive_end = occupancy_end_exclusive(row.end_date, buffer_days)
		if exclusive_end > getdate(start_date):
			blocked[row.rental_costume_unit].append(row)
	return blocked


def find_available_units(costume, size, colour, start_date, end_date, qty=1, company=None, exclude_units=None):
	start_date, end_date = assert_date_range(start_date, end_date)
	qty = int(qty or 0)
	if qty < 1:
		frappe.throw(_("Quantity must be at least 1."))

	buffer_days = cleaning_buffer_days()
	candidates = _candidate_units(costume, size, colour, company=company)
	if exclude_units:
		exclude = set(exclude_units)
		candidates = [c for c in candidates if c.name not in exclude]

	unit_names = [c.name for c in candidates]
	blocked = _overlap_map(unit_names, start_date, end_date, buffer_days)

	available = [c for c in candidates if not blocked.get(c.name)]
	unavailable_counts = {
		"reserved_or_rented": len(unit_names) - len(available),
		"blocked_operational": frappe.db.count(
			"Rental Costume Unit",
			{
				"rental_costume": costume,
				"size": size,
				"colour": colour,
				"operational_status": ["in", list(BLOCKING_UNIT_STATUSES) + [CLEANING_STATUS]],
			},
		),
	}

	alternatives = []
	if len(available) < qty:
		alternatives = _suggest_alternatives(costume, size, colour, start_date, end_date, qty, company)

	return {
		"requested_qty": qty,
		"available_qty": len(available),
		"sufficient": len(available) >= qty,
		"available_unit_ids": [c.name for c in available[:qty]] if len(available) >= qty else [c.name for c in available],
		"available_units": available[: max(qty, len(available))],
		"cleaning_buffer_days": buffer_days,
		"start_date": str(start_date),
		"end_date": str(end_date),
		"breakdown": unavailable_counts,
		"alternatives": alternatives,
	}


def _bundle_components(bundle):
	return frappe.get_all(
		"Rental Costume Component",
		filters={"parent": bundle, "parenttype": "Rental Costume"},
		fields=["component_costume", "component_role", "qty", "mandatory", "size", "colour"],
		order_by="idx asc",
	)


def find_available_bundles(
	bundle, size, colour, start_date, end_date, qty=1, company=None, include_optional=False
):
	"""Return complete, compatible physical component combinations for a bundle."""
	start_date, end_date = assert_date_range(start_date, end_date)
	qty = int(qty or 0)
	if qty < 1:
		frappe.throw(_("Quantity must be at least 1."))
	if not frappe.db.get_value("Rental Costume", bundle, "is_bundle"):
		frappe.throw(_("Rental Costume {0} is not a bundle design.").format(bundle))

	components = _bundle_components(bundle)
	selected_components = [component for component in components if component.mandatory or include_optional]
	if not selected_components:
		frappe.throw(_("Bundle {0} must have at least one mandatory component.").format(bundle))

	used = set()
	instances = []
	for index in range(1, qty + 1):
		instance = {"bundle_instance": index, "components": []}
		for component in selected_components:
			component_size = component.size or size
			component_colour = component.colour or colour
			result = find_available_units(
				component.component_costume,
				component_size,
				component_colour,
				start_date,
				end_date,
				qty=component.qty,
				company=company,
				exclude_units=used,
			)
			if not result["sufficient"]:
				return {
					"bundle": bundle,
					"requested_qty": qty,
					"available_qty": len(instances),
					"sufficient": len(instances) >= qty,
					"instances": instances,
					"blocked_component": component.component_role,
					"component_breakdown": {
						"component_role": component.component_role,
						"required_qty": component.qty,
						"available_qty": result["available_qty"],
						"size": component_size,
						"colour": component_colour,
					},
				}
			unit_ids = result["available_unit_ids"][: int(component.qty)]
			used.update(unit_ids)
			instance["components"].append(
				{
					"component_role": component.component_role,
					"component_costume": component.component_costume,
					"unit_ids": unit_ids,
					"size": component_size,
					"colour": component_colour,
				}
			)
		instances.append(instance)

	return {
		"bundle": bundle,
		"requested_qty": qty,
		"available_qty": len(instances),
		"sufficient": len(instances) >= qty,
		"instances": instances,
	}


@frappe.whitelist()
def check_rental_bundle_availability(
	bundle, size, colour, start_date, end_date, qty=1, company=None, include_optional=False
):
	frappe.has_permission("Rental Costume Unit", "read", throw=True)
	return find_available_bundles(
		bundle,
		size,
		colour,
		start_date,
		end_date,
		qty=qty,
		company=company,
		include_optional=include_optional,
	)


def _suggest_alternatives(costume, size, colour, start_date, end_date, qty, company):
	other_units = frappe.get_all(
		"Rental Costume Unit",
		filters={
			"rental_costume": costume,
			"operational_status": ["not in", list(BLOCKING_UNIT_STATUSES) + [CLEANING_STATUS]],
			**({"company": company} if company else {}),
		},
		fields=["name", "size", "colour"],
	)
	groups = {}
	for row in other_units:
		key = (row.colour, row.size)
		if key == (colour, size):
			continue
		groups.setdefault(key, []).append(row.name)

	suggestions = []
	buffer_days = cleaning_buffer_days()
	for (alt_colour, alt_size), names in groups.items():
		blocked = _overlap_map(names, start_date, end_date, buffer_days)
		free = [n for n in names if not blocked.get(n)]
		if free:
			suggestions.append(
				{
					"rental_costume": costume,
					"colour": alt_colour,
					"size": alt_size,
					"available_qty": len(free),
					"sufficient": len(free) >= qty,
					"available_unit_ids": free[:qty],
				}
			)
	suggestions.sort(key=lambda s: (-int(s["sufficient"]), -s["available_qty"]))
	return suggestions[:8]


@frappe.whitelist()
def check_rental_availability(costume, size, colour, start_date, end_date, qty=1, company=None):
	frappe.has_permission("Rental Costume Unit", "read", throw=True)
	return find_available_units(costume, size, colour, start_date, end_date, qty=qty, company=company)


@frappe.whitelist()
def get_available_costume_units(costume, size, colour, start_date, end_date, qty=1, company=None):
	frappe.has_permission("Rental Costume Unit", "read", throw=True)
	return find_available_units(costume, size, colour, start_date, end_date, qty=qty, company=company)


def unit_is_free(unit_id, start_date, end_date, ignore_allocation=None, for_update=False):
	start_date, end_date = assert_date_range(start_date, end_date)
	status = frappe.db.get_value(
		"Rental Costume Unit",
		unit_id,
		"operational_status",
		for_update=for_update,
	)
	if not status:
		frappe.throw(_("Costume unit {0} does not exist.").format(unit_id))
	if status in BLOCKING_UNIT_STATUSES or status == CLEANING_STATUS:
		return False
	blocked = _overlap_map([unit_id], start_date, end_date, cleaning_buffer_days(), ignore_allocation=ignore_allocation)
	return not blocked.get(unit_id)


@frappe.whitelist()
def allocate_rental_units(booking, unit_ids=None, allocation_status="Confirmed"):
	"""Lock specific physical units to a booking inside one request transaction."""
	frappe.has_permission("Rental Unit Allocation", "create", throw=True)
	if allocation_status not in ("Hold", "Confirmed"):
		frappe.throw(_("Allocations can only be created as Hold or Confirmed."))
	booking_doc = frappe.get_doc("Rental Booking", booking)
	frappe.has_permission(booking_doc, "write", throw=True)

	if isinstance(unit_ids, str):
		unit_ids = frappe.parse_json(unit_ids)
	unit_ids = list(unit_ids or [])
	if not unit_ids:
		frappe.throw(_("Select at least one costume unit to allocate."))

	created = []
	for unit_id in unit_ids:
		created.append(_allocate_one(booking_doc, unit_id, allocation_status))
	_sync_allocated_qty(booking_doc.name)
	return created


def allocate_units_for_booking(booking_doc, allocation_status="Hold"):
	"""Pick free units for each booking line and lock them."""
	allocated = []
	used = []
	for row in booking_doc.items:
		if getattr(row, "is_bundle", 0):
			allocated.extend(_allocate_bundle_for_item(booking_doc, row, allocation_status))
			continue
		needed = int(row.qty or 0)
		result = find_available_units(
			row.rental_costume,
			row.size,
			row.colour,
			booking_doc.pickup_date,
			booking_doc.return_date,
			qty=needed,
			company=booking_doc.company,
			exclude_units=used,
		)
		if not result["sufficient"]:
			frappe.throw(
				_(
					"Only {0} of {1} units available for {2} / {3} / {4} from {5} to {6}."
				).format(
					result["available_qty"],
					needed,
					row.rental_costume,
					row.colour,
					row.size,
					booking_doc.pickup_date,
					booking_doc.return_date,
				)
			)
		for unit_id in result["available_unit_ids"]:
			allocated.append(_allocate_one(booking_doc, unit_id, allocation_status, booking_item=row.name))
			used.append(unit_id)
	_sync_allocated_qty(booking_doc.name)
	return allocated


def _allocate_bundle_for_item(booking_doc, row, allocation_status):
	"""Allocate every mandatory component of every bundle instance atomically."""
	from frappe.utils import cint

	components = _bundle_components(row.rental_costume)
	selected_components = [
		component for component in components if component.mandatory or getattr(row, "include_optional_components", 0)
	]
	if not selected_components:
		frappe.throw(_("Bundle {0} has no mandatory components.").format(row.rental_costume))

	created = []
	used = []
	savepoint = f"bundle_allocation_{frappe.generate_hash(length=12)}"
	frappe.db.savepoint(savepoint)
	try:
		for bundle_index in range(1, cint(row.qty) + 1):
			bundle_instance = f"{booking_doc.name}-{row.name}-{bundle_index}"
			for component in selected_components:
				component_size = component.size or row.size
				component_colour = component.colour or row.colour
				result = find_available_units(
					component.component_costume,
					component_size,
					component_colour,
					booking_doc.pickup_date,
					booking_doc.return_date,
					qty=component.qty,
					company=booking_doc.company,
					exclude_units=used,
				)
				if not result["sufficient"]:
					frappe.throw(
						_(
							"Bundle {0} cannot be allocated: component {1} has only {2} of {3} available."
						).format(
							row.rental_costume,
							component.component_role,
							result["available_qty"],
							component.qty,
						)
					)
				for unit_id in sorted(result["available_unit_ids"][: cint(component.qty)]):
					created.append(
						_allocate_one(
							booking_doc,
							unit_id,
							allocation_status,
							booking_item=row.name,
							bundle_instance=bundle_instance,
							bundle_component_role=component.component_role,
							bundle_component_costume=component.component_costume,
						)
					)
					used.append(unit_id)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		raise
	frappe.db.release_savepoint(savepoint)
	return created


def _allocate_one(
	booking_doc,
	unit_id,
	allocation_status,
	booking_item=None,
	bundle_instance=None,
	bundle_component_role=None,
	bundle_component_costume=None,
):
	unit_name = frappe.db.get_value("Rental Costume Unit", unit_id, "name", for_update=True)
	if not unit_name:
		frappe.throw(_("Costume unit {0} does not exist.").format(unit_id))
	if not unit_is_free(unit_id, booking_doc.pickup_date, booking_doc.return_date, for_update=False):
		# Re-check after lock
		if not unit_is_free(unit_id, booking_doc.pickup_date, booking_doc.return_date):
			frappe.throw(
				_("Unit {0} is no longer available for these dates. Re-checking availability.").format(unit_id)
			)

	allocation = frappe.get_doc(
		{
			"doctype": "Rental Unit Allocation",
			"rental_booking": booking_doc.name,
			"rental_booking_item": booking_item,
			"bundle_instance": bundle_instance,
			"bundle_component_role": bundle_component_role,
			"bundle_component_costume": bundle_component_costume,
			"rental_costume_unit": unit_id,
			"company": booking_doc.company,
			"branch": booking_doc.branch,
			"start_date": booking_doc.pickup_date,
			"end_date": booking_doc.return_date,
			"allocation_status": allocation_status,
			"hold_expires_on": booking_doc.hold_expires_on if allocation_status == "Hold" else None,
		}
	)
	allocation.insert()
	allocation.submit()

	new_status = "Reserved" if allocation_status in ACTIVE_ALLOCATION_STATUSES else None
	if new_status:
		current = frappe.db.get_value("Rental Costume Unit", unit_id, "operational_status")
		if current == "Available":
			frappe.db.set_value("Rental Costume Unit", unit_id, "operational_status", "Reserved")
			frappe.db.set_value("Rental Costume Unit", unit_id, "current_booking", booking_doc.name)
	return allocation.name


def _sync_allocated_qty(booking):
	booking_doc = frappe.get_doc("Rental Booking", booking)
	counts = frappe.db.sql(
		"""
		SELECT rental_costume_unit, rental_booking_item, bundle_instance
		FROM `tabRental Unit Allocation`
		WHERE rental_booking=%s AND docstatus=1 AND allocation_status IN ('Hold','Confirmed')
		""",
		booking,
		as_dict=True,
	)
	unit_meta = {
		u.name: u
		for u in frappe.get_all(
			"Rental Costume Unit",
			filters={"name": ["in", [c.rental_costume_unit for c in counts]]} if counts else {"name": "__none__"},
			fields=["name", "rental_costume", "colour", "size"],
		)
	}
	for row in booking_doc.items:
		row.allocated_qty = 0
		row.bundle_allocated_qty = 0
		if getattr(row, "is_bundle", 0):
			row.bundle_allocated_qty = len(
				{
					c.bundle_instance
					for c in counts
					if c.bundle_instance and c.rental_booking_item == row.name
				}
			)
			row.allocated_qty = row.bundle_allocated_qty
			continue
		for alloc in counts:
			meta = unit_meta.get(alloc.rental_costume_unit)
			if (
				meta
				and meta.rental_costume == row.rental_costume
				and meta.colour == row.colour
				and meta.size == row.size
			):
				row.allocated_qty += 1
	booking_doc.flags.ignore_validate_update_after_submit = True
	booking_doc.save(ignore_permissions=True)


def release_allocations(booking, reason="Released"):
	for name in frappe.get_all(
		"Rental Unit Allocation",
		filters={
			"rental_booking": booking,
			"docstatus": 1,
			"allocation_status": ["in", list(ACTIVE_ALLOCATION_STATUSES)],
		},
		pluck="name",
	):
		doc = frappe.get_doc("Rental Unit Allocation", name)
		doc.allocation_status = "Released"
		doc.db_set("allocation_status", "Released")
		doc.cancel()
		_maybe_free_unit(doc.rental_costume_unit, booking)


def _maybe_free_unit(unit_id, booking):
	still = frappe.db.exists(
		"Rental Unit Allocation",
		{
			"rental_costume_unit": unit_id,
			"docstatus": 1,
			"allocation_status": ["in", list(ACTIVE_ALLOCATION_STATUSES)],
		},
	)
	status = frappe.db.get_value("Rental Costume Unit", unit_id, "operational_status")
	if not still and status in ("Reserved", "Available"):
		frappe.db.set_value("Rental Costume Unit", unit_id, "operational_status", "Available")
		if frappe.db.get_value("Rental Costume Unit", unit_id, "current_booking") == booking:
			frappe.db.set_value("Rental Costume Unit", unit_id, "current_booking", None)


def confirm_holds(booking):
	for name in frappe.get_all(
		"Rental Unit Allocation",
		filters={"rental_booking": booking, "docstatus": 1, "allocation_status": "Hold"},
		pluck="name",
	):
		frappe.db.set_value("Rental Unit Allocation", name, "allocation_status", "Confirmed")
		frappe.db.set_value("Rental Unit Allocation", name, "hold_expires_on", None)


def release_expired_holds():
	now = now_datetime()
	expired = frappe.get_all(
		"Rental Unit Allocation",
		filters={"docstatus": 1, "allocation_status": "Hold", "hold_expires_on": ["<", now]},
		fields=["name", "rental_booking", "rental_costume_unit"],
	)
	for row in expired:
		frappe.db.set_value("Rental Unit Allocation", row.name, "allocation_status", "Released")
		doc = frappe.get_doc("Rental Unit Allocation", row.name)
		doc.cancel()
		_maybe_free_unit(row.rental_costume_unit, row.rental_booking)
		booking_status = frappe.db.get_value("Rental Booking", row.rental_booking, "booking_status")
		if booking_status in ("Awaiting Payment", "Availability Checked"):
			frappe.db.set_value("Rental Booking", row.rental_booking, "booking_status", "Expired")
