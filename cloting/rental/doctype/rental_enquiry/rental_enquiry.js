frappe.ui.form.on("Rental Enquiry", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.status !== "Converted to Booking") {
			frm.add_custom_button(__("Create Booking"), () => {
				const items = (frm.doc.items || []).map((row) => ({
					rental_costume: row.rental_costume,
					colour: row.colour,
					size: row.size,
					qty: row.qty,
				}));
				frappe.call({
					method: "cloting.rental.api.rental_booking.create_rental_booking",
					args: {
						customer: frm.doc.customer,
						pickup_date: frm.doc.pickup_date,
						return_date: frm.doc.return_date,
						company: frm.doc.company,
						branch: frm.doc.branch,
						enquiry: frm.doc.name,
						items,
					},
					freeze: true,
				}).then((r) => {
					frappe.set_route("Form", "Rental Booking", r.message.name);
				});
			});
		}
	},
});
