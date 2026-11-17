frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		if (
			frm.is_new()
			|| frm.doc.docstatus !== 1
			|| !["To Receive", "To Receive and Bill", "To Bill"].includes(frm.doc.status)
		) {
			return;
		}

		frm.add_custom_button(__("Gate Pass"), () => {
			frappe.new_doc("Gate Pass", {
				supplier: frm.doc.supplier,
				purchase_order: frm.doc.name,
			});
		}, __("Create"));
	},

	supplier(frm) {
		if (!frm.doc.supplier) {
			return;
		}

		const supplier = frm.doc.supplier;
		frappe.call({
			method: "cloting.api.get_supplier_quality_rating",
			args: { supplier },
			callback(response) {
				if (frm.doc.supplier !== supplier) {
					return;
				}

				const rating = response.message;
				if (!rating || !rating.warning || !rating.average_rating) {
					return;
				}

				frappe.show_alert(
					{
						message: __(
							"Warning: This supplier has a low quality performance rating of {0}/5. "
								+ "Please review the supplier's quality history before proceeding with this Purchase Order.",
							[rating.average_rating.toFixed(2)]
						),
						indicator: "orange",
					},
					10
				);
			},
		});
	},
});
