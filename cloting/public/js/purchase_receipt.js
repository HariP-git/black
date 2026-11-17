frappe.ui.form.on('Purchase Receipt', {
	setup(frm) {
		frm.set_query('custom_gate_pass', () => ({
			filters: {
				supplier: frm.doc.supplier,
				status: 'Entered',
			},
		}));
	},
});
