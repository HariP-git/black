import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class GatePass(Document):
	def before_validate(self):
		if not self.entry_time:
			self.entry_time = now_datetime()
		if not self.security_guard:
			self.security_guard = frappe.session.user

	def validate(self):
		if not self.items:
			frappe.throw(_("Add at least one item to the gate pass."))

		if self.purchase_order:
			purchase_order = frappe.db.get_value(
				"Purchase Order",
				self.purchase_order,
				["supplier", "docstatus"],
				as_dict=True,
			)
			if not purchase_order or purchase_order.docstatus != 1:
				frappe.throw(_("Purchase Order must be a submitted document."))
			if purchase_order.supplier != self.supplier:
				frappe.throw(_("This Purchase Order belongs to another supplier."))

		if self.status == "Rejected" and not self.rejection_reason:
			frappe.throw(_("Enter a reason before rejecting the gate pass."))

		for row in self.items:
			if row.expected_qty and flt(row.declared_qty) > flt(row.expected_qty):
				frappe.msgprint(
					_("{0}: declared quantity is more than the pending Purchase Order quantity.").format(
						row.item_code
					),
					alert=True,
				)


@frappe.whitelist()
def get_po_items(purchase_order):
	purchase_order_doc = frappe.get_doc("Purchase Order", purchase_order)
	frappe.has_permission(purchase_order_doc, "read", throw=True)
	if purchase_order_doc.docstatus != 1:
		frappe.throw(_("Purchase Order must be submitted."))

	rows = []
	for row in purchase_order_doc.items:
		pending = flt(row.qty) - flt(row.received_qty)
		if pending > 0:
			rows.append(
				{
					"item_code": row.item_code,
					"item_name": row.item_name,
					"expected_qty": pending,
					"declared_qty": pending,
				}
			)
	return rows


@frappe.whitelist()
def make_purchase_receipt(gate_pass):
	gate_pass_doc = frappe.get_doc("Gate Pass", gate_pass)
	frappe.has_permission(gate_pass_doc, "write", throw=True)
	if gate_pass_doc.status != "Entered":
		frappe.throw(_("Only an Entered gate pass can create a Purchase Receipt."))
	if not gate_pass_doc.purchase_order:
		frappe.throw(_("Select a Purchase Order before creating a Purchase Receipt."))
	if gate_pass_doc.purchase_receipt:
		frappe.throw(_("This gate pass is already linked to {0}.").format(gate_pass_doc.purchase_receipt))

	purchase_order = frappe.get_doc("Purchase Order", gate_pass_doc.purchase_order)
	if purchase_order.docstatus != 1:
		frappe.throw(_("Purchase Order must be submitted."))
	if purchase_order.supplier != gate_pass_doc.supplier:
		frappe.throw(_("This Purchase Order belongs to another supplier."))

	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	purchase_receipt = make_purchase_receipt(gate_pass_doc.purchase_order)
	purchase_receipt.custom_gate_pass = gate_pass_doc.name
	purchase_receipt.supplier_delivery_note = gate_pass_doc.challan_no
	return purchase_receipt


@frappe.whitelist()
def reject_entry(gate_pass, reason):
	gate_pass_doc = frappe.get_doc("Gate Pass", gate_pass)
	frappe.has_permission(gate_pass_doc, "write", throw=True)
	if gate_pass_doc.status != "Entered":
		frappe.throw(_("Only an Entered gate pass can be rejected."))
	if not reason or not reason.strip():
		frappe.throw(_("A rejection reason is required."))

	gate_pass_doc.db_set(
		{"status": "Rejected", "rejection_reason": reason.strip()},
		update_modified=True,
	)
	return {"status": "Rejected"}


@frappe.whitelist()
def mark_exit(gate_pass):
	gate_pass_doc = frappe.get_doc("Gate Pass", gate_pass)
	frappe.has_permission(gate_pass_doc, "write", throw=True)
	if gate_pass_doc.status == "Entered":
		frappe.throw(_("The vehicle cannot leave before the goods are received or the entry is rejected."))
	if gate_pass_doc.exit_time:
		frappe.throw(_("Exit is already recorded."))

	exit_time = now_datetime()
	gate_pass_doc.db_set("exit_time", exit_time, update_modified=True)
	return {"exit_time": exit_time}


def notify_storekeepers(doc, method=None):
	storekeeper_users = frappe.get_all(
		"Has Role",
		filters={"role": "Storekeeper", "parenttype": "User"},
		pluck="parent",
	)
	if not storekeeper_users:
		return

	recipients = frappe.get_all(
		"User",
		filters={"name": ["in", storekeeper_users], "enabled": 1},
		pluck="email",
	)
	recipients = [email for email in recipients if email]
	if not recipients:
		frappe.logger("cloting.gate_pass").warning(
			"Gate Pass %s was created, but no enabled Storekeeper email was found.",
			doc.name,
		)
		return

	frappe.sendmail(
		recipients=recipients,
		subject=_("New Inward Gate Pass {0}").format(doc.name),
		message=_(
			"Vehicle {0} from supplier {1} has arrived at the gate.<br><br>"
			"Gate Pass: {2}<br>"
			"Purchase Order: {3}"
		).format(doc.vehicle_no, doc.supplier, doc.name, doc.purchase_order or _("Not provided")),
	)


def check_gate_pass(doc, method=None):
	if doc.is_return:
		return
	if not doc.get("custom_gate_pass"):
		frappe.throw(_("A Gate Pass is required before receiving stock from a supplier."))

	gate_pass = frappe.db.get_value(
		"Gate Pass",
		doc.custom_gate_pass,
		["supplier", "purchase_order", "status", "purchase_receipt"],
		as_dict=True,
	)
	if not gate_pass:
		frappe.throw(_("The selected Gate Pass does not exist."))
	if gate_pass.supplier != doc.supplier:
		frappe.throw(_("This Gate Pass is for a different supplier."))
	if gate_pass.purchase_order and gate_pass.purchase_order != doc.purchase_order:
		frappe.throw(_("This Gate Pass is linked to a different Purchase Order."))
	if gate_pass.status == "Rejected":
		frappe.throw(_("This Gate Pass was rejected."))
	if gate_pass.purchase_receipt and gate_pass.purchase_receipt != doc.name:
		frappe.throw(_("This Gate Pass is already used in {0}.").format(gate_pass.purchase_receipt))


def mark_received(doc, method=None):
	if doc.is_return or not doc.get("custom_gate_pass"):
		return
	frappe.db.set_value(
		"Gate Pass",
		doc.custom_gate_pass,
		{
			"status": "Received",
			"purchase_receipt": doc.name,
			"received_time": now_datetime(),
		},
	)


def undo_received(doc, method=None):
	if doc.is_return or not doc.get("custom_gate_pass"):
		return
	if frappe.db.get_value("Gate Pass", doc.custom_gate_pass, "purchase_receipt") != doc.name:
		return
	frappe.db.set_value(
		"Gate Pass",
		doc.custom_gate_pass,
		{"status": "Entered", "purchase_receipt": None, "received_time": None},
	)
