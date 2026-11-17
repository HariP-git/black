import frappe
from frappe import _
from frappe.utils import get_datetime, getdate

from cloting.rental.constants import RETURN_READY_STATUSES


def _handed_units(booking):
	return {
		r[0]
		for r in frappe.db.sql(
			"""
			SELECT i.rental_costume_unit
			FROM `tabRental Handover Item` i
			INNER JOIN `tabRental Handover` h ON h.name = i.parent
			WHERE h.docstatus = 1 AND h.rental_booking = %s
			""",
			booking,
		)
	}


def validate_return(doc):
	booking = frappe.get_doc("Rental Booking", doc.rental_booking)
	if booking.booking_status not in RETURN_READY_STATUSES + ("Overdue",):
		frappe.throw(_("Booking {0} is not in a returnable status ({1}).").format(booking.name, booking.booking_status))

	handed = _handed_units(booking.name)
	for row in doc.items:
		if row.rental_costume_unit not in handed:
			frappe.throw(_("Unit {0} was not handed over on this booking.").format(row.rental_costume_unit))
		allocation = frappe.db.get_value(
			"Rental Unit Allocation",
			{"rental_booking": booking.name, "rental_costume_unit": row.rental_costume_unit, "docstatus": 1},
			["rental_booking_item", "bundle_instance", "bundle_component_role"],
			as_dict=True,
		)
		if allocation:
			row.rental_booking_item = allocation.rental_booking_item
			row.bundle_instance = allocation.bundle_instance
			row.bundle_component_role = allocation.bundle_component_role
		already = frappe.db.sql(
			"""
			SELECT r.name FROM `tabRental Return` r
			INNER JOIN `tabRental Return Item` i ON i.parent = r.name
			WHERE r.docstatus = 1 AND r.rental_booking = %s AND i.rental_costume_unit = %s
			""",
			(booking.name, row.rental_costume_unit),
		)
		if already:
			frappe.throw(_("Unit {0} has already been returned.").format(row.rental_costume_unit))
		if not row.barcode:
			row.barcode = frappe.db.get_value("Rental Costume Unit", row.rental_costume_unit, "barcode")

	doc.is_late = 1 if get_datetime(doc.return_datetime).date() > getdate(booking.return_date) else 0


def on_return_submit(doc):
	booking = frappe.get_doc("Rental Booking", doc.rental_booking)
	for row in doc.items:
		# A returned unit must remain unavailable until its inspection and any
		# resulting cleaning or repair job are completed.
		status = "Lost" if row.condition_at_return == "Lost" else "Under Inspection"
		frappe.db.set_value(
			"Rental Costume Unit",
			row.rental_costume_unit,
			{"operational_status": status, "condition": row.condition_at_return},
		)
		_create_inspection(doc, row, booking)
	_sync_return_qty(booking)
	_update_booking_after_return(booking)


def _create_inspection(return_doc, row, booking):
	if frappe.db.exists(
		"Rental Inspection",
		{"rental_return": return_doc.name, "rental_costume_unit": row.rental_costume_unit, "docstatus": ["<", 2]},
	):
		return
	classification = {
		"Good": "Good",
		"Normal Wear": "Normal Wear",
		"Damaged": "Minor Damage",
		"Missing Accessories": "Missing Accessories",
		"Lost": "Lost",
	}.get(row.condition_at_return, "Requires Cleaning")
	insp = frappe.get_doc(
		{
			"doctype": "Rental Inspection",
			"rental_booking": booking.name,
			"rental_return": return_doc.name,
			"rental_costume_unit": row.rental_costume_unit,
			"company": return_doc.company,
			"branch": return_doc.branch,
			"classification": classification,
			"remarks": row.remarks or row.damage_notes,
		}
	)
	insp.insert(ignore_permissions=True)


def _sync_return_qty(booking):
	rows = frappe.db.sql(
		"""
		SELECT i.rental_costume_unit, i.rental_booking_item, i.bundle_instance, i.bundle_component_role
		FROM `tabRental Return Item` i
		INNER JOIN `tabRental Return` r ON r.name = i.parent
		WHERE r.docstatus = 1 AND r.rental_booking = %s
		""",
		booking.name,
		as_dict=True,
	)
	units = frappe.get_all(
		"Rental Costume Unit",
		filters={"name": ["in", [r.rental_costume_unit for r in rows]]} if rows else {"name": "__none__"},
		fields=["name", "rental_costume", "colour", "size"],
	)
	meta = {u.name: u for u in units}
	for item in booking.items:
		item.returned_qty = 0
		if getattr(item, "is_bundle", 0):
			components = {
				component.component_role: int(component.qty or 0)
				for component in frappe.get_all(
					"Rental Costume Component",
					filters={"parent": item.rental_costume},
					fields=["component_role", "qty"],
				)
			}
			mandatory_roles = {
				component.component_role
				for component in frappe.get_all(
					"Rental Costume Component",
					filters={"parent": item.rental_costume, "mandatory": 1},
					fields=["component_role"],
				)
			}
			instances = {}
			for row in rows:
				if row.rental_booking_item != item.name or not row.bundle_instance:
					continue
				instances.setdefault(row.bundle_instance, {}).setdefault(row.bundle_component_role, 0)
				instances[row.bundle_instance][row.bundle_component_role] += 1
			item.returned_qty = sum(
				all(
					counts.get(role, 0) >= required
					for role, required in components.items()
					if role in mandatory_roles or role in counts
				)
				for counts in instances.values()
			)
			continue
		for r in rows:
			u = meta.get(r.rental_costume_unit)
			if u and u.rental_costume == item.rental_costume and u.colour == item.colour and u.size == item.size:
				item.returned_qty += 1
	booking.flags.ignore_validate_update_after_submit = True
	booking.save(ignore_permissions=True)


def _update_booking_after_return(booking):
	total = sum(int(i.qty or 0) for i in booking.items)
	returned = sum(int(i.returned_qty or 0) for i in booking.items)
	if returned < total:
		booking.db_set("booking_status", "Partially Returned")
	else:
		booking.db_set("booking_status", "Return Inspection")


@frappe.whitelist()
def process_rental_return(rental_return):
	doc = frappe.get_doc("Rental Return", rental_return)
	frappe.has_permission(doc, "submit", throw=True)
	if doc.docstatus == 0:
		doc.submit()
	return doc.name


@frappe.whitelist()
def calculate_late_fee(booking, actual_return_date=None):
	from frappe.utils import date_diff, getdate

	from cloting.rental.utils import get_settings, money

	doc = frappe.get_doc("Rental Booking", booking)
	frappe.has_permission(doc, "read", throw=True)
	settings = get_settings()
	actual = getdate(actual_return_date or frappe.utils.nowdate())
	days = date_diff(actual, getdate(doc.return_date))
	if days <= 0:
		return {"late_days": 0, "late_fee": 0}
	return {"late_days": days, "late_fee": money(days * (settings.late_fee_per_day or 0))}
