frappe.ui.form.on("Rental Booking", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Check Availability"), () => {
				frappe.call({
					method: "cloting.rental.api.rental_booking.check_booking_availability",
					args: { booking: frm.doc.name },
					freeze: true,
				}).then((r) => {
					const lines = r.message.lines || [];
					const ok = r.message.ok;
					const details = lines
						.map(
							(l) =>
								`${__("Available")}: ${l.available_qty} / ${l.requested_qty}` +
								(l.available_unit_ids || []).join(", ")
						)
						.join("<br>");
					frappe.msgprint({
						title: ok ? __("Availability OK") : __("Insufficient stock"),
						indicator: ok ? "green" : "red",
						message: details,
					});
					frm.reload_doc();
				});
			});
			if (frm.doc.booking_status === "Availability Checked" || frm.doc.booking_status === "Draft") {
				frm.add_custom_button(__("Place Hold"), () => {
					frappe.call({
						method: "cloting.rental.api.rental_booking.place_temporary_hold",
						args: { booking: frm.doc.name },
						freeze: true,
					}).then(() => frm.reload_doc());
				});
			}
			if (["Awaiting Payment", "Availability Checked"].includes(frm.doc.booking_status)) {
				frm.add_custom_button(__("Record Payment"), () => {
					frappe.prompt(
						[
							{
								fieldname: "rental_amount_paid",
								fieldtype: "Currency",
								label: __("Rental Amount Paid"),
								default: frm.doc.grand_total,
							},
							{
								fieldname: "deposit_amount_paid",
								fieldtype: "Currency",
								label: __("Deposit Collected"),
								default: frm.doc.deposit_amount,
							},
						],
						(values) => {
							frappe.call({
								method: "cloting.rental.api.rental_booking.record_booking_payment",
								args: { booking: frm.doc.name, ...values },
								freeze: true,
							}).then(() => frm.reload_doc());
						},
						__("Record Payment")
					);
				});
			}
		}
		if (frm.doc.docstatus === 1 && ["Confirmed", "Partially Handed Over"].includes(frm.doc.booking_status)) {
			frm.add_custom_button(__("New Handover"), () => {
				frappe.new_doc("Rental Handover", { rental_booking: frm.doc.name, company: frm.doc.company });
			});
		}
	},
});

frappe.ui.form.on("Rental Booking Item", {
	rental_costume(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.rental_costume) return;
		frappe.db.get_doc("Rental Costume", row.rental_costume).then((costume) => {
			if (!row.rental_rate) frappe.model.set_value(cdt, cdn, "rental_rate", costume.default_rental_rate);
			if (!row.deposit_rate) frappe.model.set_value(cdt, cdn, "deposit_rate", costume.default_deposit);
		});
	},
});
