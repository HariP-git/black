import frappe
from frappe import _

from cloting.rental.constants import HANDOVER_READY_STATUSES


def validate_handover(doc):
	booking = frappe.get_doc("Rental Booking", doc.rental_booking)
	if booking.docstatus != 1 or booking.booking_status not in HANDOVER_READY_STATUSES + ("Overdue",):
		if booking.booking_status != "Confirmed" and booking.booking_status not in HANDOVER_READY_STATUSES:
			frappe.throw(_("Booking {0} is not ready for handover (status {1}).").format(booking.name, booking.booking_status))

	settings = frappe.get_single("Rental Settings")
	required = (booking.grand_total or 0) * (settings.advance_payment_percent or 100) / 100.0
	if (booking.advance_received or 0) + 0.005 < required:
		frappe.throw(_("Payment threshold not met for handover of {0}.").format(booking.name))

	allocated = set(
		frappe.get_all(
			"Rental Unit Allocation",
			filters={
				"rental_booking": booking.name,
				"docstatus": 1,
				"allocation_status": "Confirmed",
			},
			pluck="rental_costume_unit",
		)
	)
	seen = set()
	for row in doc.items:
		if row.rental_costume_unit in seen:
			frappe.throw(_("Unit {0} is listed twice on this handover.").format(row.rental_costume_unit))
		seen.add(row.rental_costume_unit)
		if row.rental_costume_unit not in allocated:
			frappe.throw(_("Unit {0} is not allocated to this booking.").format(row.rental_costume_unit))
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
		if frappe.db.exists(
			"Rental Handover Item",
			{
				"rental_costume_unit": row.rental_costume_unit,
				"parenttype": "Rental Handover",
				"docstatus": 1,
			},
		):
			# allow only if previous handover cancelled
			already = frappe.db.sql(
				"""
				SELECT h.name FROM `tabRental Handover` h
				INNER JOIN `tabRental Handover Item` i ON i.parent = h.name
				WHERE h.docstatus = 1 AND h.rental_booking = %s AND i.rental_costume_unit = %s
				""",
				(booking.name, row.rental_costume_unit),
			)
			if already:
				frappe.throw(_("Unit {0} has already been handed over.").format(row.rental_costume_unit))
		if not row.barcode:
			row.barcode = frappe.db.get_value("Rental Costume Unit", row.rental_costume_unit, "barcode")


def on_handover_submit(doc):
	booking = frappe.get_doc("Rental Booking", doc.rental_booking)
	for row in doc.items:
		frappe.db.set_value("Rental Costume Unit", row.rental_costume_unit, {
			"operational_status": "Rented Out",
			"condition": row.condition_at_issue,
			"current_booking": booking.name,
		})
	_sync_handover_qty(booking)
	_update_booking_after_handover(booking)


def _sync_handover_qty(booking):
	rows = frappe.db.sql(
		"""
		SELECT i.rental_costume_unit, i.rental_booking_item, i.bundle_instance, i.bundle_component_role
		FROM `tabRental Handover Item` i
		INNER JOIN `tabRental Handover` h ON h.name = i.parent
		WHERE h.docstatus = 1 AND h.rental_booking = %s
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
		item.handed_over_qty = 0
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
			item.handed_over_qty = sum(
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
				item.handed_over_qty += 1
	booking.flags.ignore_validate_update_after_submit = True
	booking.save(ignore_permissions=True)


def _update_booking_after_handover(booking):
	total = sum(int(i.qty or 0) for i in booking.items)
	handed = sum(int(i.handed_over_qty or 0) for i in booking.items)
	if handed <= 0:
		return
	if handed < total:
		booking.db_set("booking_status", "Partially Handed Over")
	else:
		booking.db_set("booking_status", "Rented Out")


@frappe.whitelist()
def confirm_rental_handover(handover):
	doc = frappe.get_doc("Rental Handover", handover)
	frappe.has_permission(doc, "submit", throw=True)
	if doc.docstatus == 0:
		doc.submit()
	return doc.name
