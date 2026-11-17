frappe.ui.form.on("Rental Handover", {
	rental_booking(frm) {
		if (!frm.doc.rental_booking || frm.doc.items?.length) return;
		frappe.db.get_doc("Rental Booking", frm.doc.rental_booking).then((booking) => {
			frm.set_value("company", booking.company);
			frm.set_value("branch", booking.branch);
		});
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Rental Unit Allocation",
				filters: {
					rental_booking: frm.doc.rental_booking,
					docstatus: 1,
					allocation_status: "Confirmed",
				},
				fields: ["rental_costume_unit"],
				limit_page_length: 50,
			},
		}).then((r) => {
			(r.message || []).forEach((row) => {
				const child = frm.add_child("items");
				child.rental_costume_unit = row.rental_costume_unit;
			});
			frm.refresh_field("items");
		});
	},
});
