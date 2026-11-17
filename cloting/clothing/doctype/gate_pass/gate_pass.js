const GATE_PASS_API = 'cloting.clothing.doctype.gate_pass.gate_pass.';

frappe.ui.form.on('Gate Pass', {
	onload(frm) {
		if (frm.doc.purchase_order && !frm.doc.items?.length) {
			load_purchase_order_items(frm);
		}
	},

	setup(frm) {
		frm.set_query('purchase_order', () => ({
			filters: {
				supplier: frm.doc.supplier,
				docstatus: 1,
				status: ['in', ['To Receive and Bill', 'To Receive']],
			},
		}));
	},

	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.status === 'Entered') {
			frm.add_custom_button(__('Create Purchase Receipt'), () => {
				frappe.call({
					method: `${GATE_PASS_API}make_purchase_receipt`,
					args: { gate_pass: frm.doc.name },
					freeze: true,
					freeze_message: __('Preparing Purchase Receipt...'),
				}).then(({ message }) => {
					frappe.model.sync(message);
					frappe.set_route('Form', 'Purchase Receipt', message.name);
				});
			});

			frm.add_custom_button(__('Reject Entry'), () => {
				frappe.prompt(
					[{ fieldname: 'reason', fieldtype: 'Small Text', label: __('Reason'), reqd: 1 }],
					(values) => frappe.call({
						method: `${GATE_PASS_API}reject_entry`,
						args: { gate_pass: frm.doc.name, reason: values.reason },
						freeze: true,
					}).then(() => frm.reload_doc()),
					__('Reject Gate Pass'),
					__('Reject'),
				);
			});
		}

		if (frm.doc.status !== 'Entered' && !frm.doc.exit_time) {
			frm.add_custom_button(__('Mark Exit'), () => {
				frappe.call({
					method: `${GATE_PASS_API}mark_exit`,
					args: { gate_pass: frm.doc.name },
					freeze: true,
				}).then(() => frm.reload_doc());
			});
		}
	},

	purchase_order(frm) {
		load_purchase_order_items(frm);
	},
});

function load_purchase_order_items(frm) {
	if (!frm.doc.purchase_order || frm.__loading_gate_pass_items) return;

	frm.__loading_gate_pass_items = true;
	frappe.call({
		method: `${GATE_PASS_API}get_po_items`,
		args: { purchase_order: frm.doc.purchase_order },
		freeze: true,
	}).then(({ message }) => {
		frm.clear_table('items');
		(message || []).forEach((row) => frm.add_child('items', row));
		frm.refresh_field('items');
	}).finally(() => {
		frm.__loading_gate_pass_items = false;
	});
}
