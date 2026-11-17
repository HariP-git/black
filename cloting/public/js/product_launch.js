frappe.ui.form.on("Product Launch", {
	setup(frm) {
		frm.set_query("item", "products", () => ({
			filters: {
				is_sales_item: 1,
			},
		}));
	},

	refresh(frm) {
		frm.set_df_property(
			"status",
			"read_only",
			["Live", "Ended", "Cancelled"].includes(frm.doc.status)
		);

		if (!frm.is_new()) {
			frm.add_custom_button(__("Refresh Stock"), () => refresh_stock(frm));
			if (["Planned", "Ready"].includes(frm.doc.status)) {
				frm.add_custom_button(__("Go Live Now"), () => confirm_go_live(frm));
			}
			refresh_stock(frm);
		}

		update_readiness_summary(frm);
	},
});

frappe.ui.form.on("Launch Product", {
	item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item) {
			return;
		}

		frappe.call({
			method: "cloting.clothing.doctype.product_launch.product_launch.get_stock_for_item",
			args: { item: row.item },
		}).then((response) => {
			const result = response.message;
			frappe.model.set_value(cdt, cdn, "available_stock", result.available_stock || 0);
			frm.refresh_field("products");
			update_readiness_summary(frm);
		});
	},

	planned_qty(frm) {
		update_readiness_summary(frm);
	},

	launch_price(frm) {
		update_readiness_summary(frm);
	},
});

function refresh_stock(frm) {
	if (frm.is_new()) {
		return;
	}

	frappe.call({
		method: "cloting.clothing.doctype.product_launch.product_launch.get_stock_snapshot",
		args: { name: frm.doc.name },
		freeze: true,
		freeze_message: __("Refreshing stock..."),
	}).then((response) => {
		const stock_by_row = response.message || {};
		(frm.doc.products || []).forEach((row) => {
			if (stock_by_row[row.name] !== undefined) {
				frappe.model.set_value(row.doctype, row.name, "available_stock", stock_by_row[row.name]);
			}
		});
		frm.refresh_field("products");
		update_readiness_summary(frm);
	});
}

function update_readiness_summary(frm) {
	const products = frm.doc.products || [];
	const ready = products.filter(
		(row) =>
			flt(row.planned_qty) > 0 &&
			flt(row.launch_price) > 0 &&
			flt(row.available_stock) >= flt(row.planned_qty)
	).length;
	const messages = products
		.filter(
			(row) =>
				flt(row.planned_qty) <= 0 ||
				flt(row.launch_price) <= 0 ||
				flt(row.available_stock) < flt(row.planned_qty)
		)
		.map((row) => {
			if (flt(row.planned_qty) <= 0) {
				return `${row.item || __("Unselected item")}: ${__("planned quantity is missing")}`;
			}
			if (flt(row.launch_price) <= 0) {
				return `${row.item}: ${__("launch price is missing")}`;
			}
			return `${row.item}: ${__("insufficient stock")}`;
		});

	if (!products.length) {
		frm.dashboard.set_headline_alert(__("Add at least one product before this collection can be Ready."), "orange");
	} else if (messages.length) {
		frm.dashboard.set_headline_alert(
			__("{0} of {1} products are ready. {2}", [ready, products.length, messages.join("; ")]),
			"orange"
		);
	} else {
		frm.dashboard.set_headline_alert(__("{0} of {1} products are ready.", [ready, products.length]), "green");
	}
}

function confirm_go_live(frm) {
	frappe.confirm(
		__("Are you sure you want to make this collection available for sale?"),
		() => {
			frappe.call({
				method: "cloting.clothing.doctype.product_launch.product_launch.go_live",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Validating launch and applying prices..."),
			}).then((response) => {
				const result = response.message;
				frappe.show_alert({
					message: __("Collection is now Live. Price lists: {0}", [
						(result.price_lists || []).join(", "),
					]),
					indicator: "green",
				});
				frm.reload_doc();
			});
		}
	);
}
