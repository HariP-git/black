frappe.ui.form.on("Rental Settlement", {
	rental_booking(frm) {
		if (!frm.doc.rental_booking) return;
		frappe.call({
			method: "cloting.rental.api.rental_settlement.calculate_rental_settlement",
			args: { booking: frm.doc.rental_booking },
		}).then((r) => {
			Object.entries(r.message || {}).forEach(([key, value]) => {
				if (frm.fields_dict[key]) frm.set_value(key, value);
			});
		});
	},
	refresh(frm) {
		if (frm.doc.docstatus === 1 && !frm.doc.refunded) {
			frm.add_custom_button(__("Process Deposit Refund"), () => {
				frappe.call({
					method: "cloting.rental.api.rental_settlement.process_deposit_refund",
					args: { settlement: frm.doc.name },
					freeze: true,
				}).then(() => frm.reload_doc());
			});
		}
		if (frm.doc.docstatus === 0 && frm.doc.requires_manager_approval) {
			frm.add_custom_button(__("Approve Deductions"), () => {
				frappe.call({
					method: "cloting.rental.api.rental_settlement.approve_settlement",
					args: { settlement: frm.doc.name },
					freeze: true,
				}).then(() => frm.reload_doc());
			});
		}
	},
});
