// ===========================================================================
// Return Reason Popup – POS Invoice (Client Script)
// App: cloting  |  DocType: POS Invoice
//
// Identical logic to the Sales Invoice script; maintained separately so each
// DocType's client script bundle is independent and can be enabled/disabled
// individually.
// ===========================================================================

frappe.ui.form.on("POS Invoice", {
	refresh(frm) {
		if (!_should_show_return_reason_dialog(frm)) {
			return;
		}
		frm._return_reason_dialog_shown = true;
		_show_return_reason_dialog(frm);
	},
});

// ---------------------------------------------------------------------------
// Guard: decide whether the popup should appear right now.
// ---------------------------------------------------------------------------
function _should_show_return_reason_dialog(frm) {
	if (!frm.doc.is_return) return false;
	if (frm.doc.docstatus !== 0) return false;
	if (frm.doc.custom_return_reason) return false;
	if (frm._return_reason_dialog_shown) return false;
	return true;
}

// ---------------------------------------------------------------------------
// Dialog builder and submission handler.
// ---------------------------------------------------------------------------
function _show_return_reason_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Return Reason"),
		fields: [
			{
				fieldname: "custom_return_reason",
				label: __("Return Reason"),
				fieldtype: "Select",
				options: "Size Issue\nColour Issue\nDefect\nWrong Item\nBilling Error\nChanged Mind\nOther",
				reqd: 1,
				onchange() {
					_toggle_other_reason(dialog);
				},
			},
			{
				fieldname: "custom_other_return_reason",
				label: __("Other Return Reason"),
				fieldtype: "Small Text",
				hidden: 1,
				reqd: 0,
			},
			{
				fieldname: "custom_return_remarks",
				label: __("Return Remarks"),
				fieldtype: "Small Text",
				reqd: 0,
			},
		],
		primary_action_label: __("Continue"),
		primary_action(values) {
			if (!values.custom_return_reason) {
				frappe.msgprint({
					title: __("Required"),
					message: __("Please select a Return Reason before continuing."),
					indicator: "orange",
				});
				return;
			}
			if (
				values.custom_return_reason === "Other" &&
				!String(values.custom_other_return_reason || "").trim()
			) {
				frappe.msgprint({
					title: __("Required"),
					message: __("Please describe the specific reason in Other Return Reason."),
					indicator: "orange",
				});
				return;
			}

			dialog.hide();

			frm.set_value("custom_return_reason", values.custom_return_reason);
			frm.set_value(
				"custom_other_return_reason",
				values.custom_return_reason === "Other"
					? (values.custom_other_return_reason || "").trim()
					: ""
			);
			frm.set_value("custom_return_remarks", (values.custom_return_remarks || "").trim());

			frm.save("Save").then(() => {
				frm.reload_doc();
			}).catch(() => {
				// Keep values in-memory on failure.
			});
		},
		secondary_action_label: __("Cancel"),
		secondary_action() {
			dialog.hide();
			frm._return_reason_dialog_shown = false;
		},
	});

	dialog.show();
}

// ---------------------------------------------------------------------------
// Toggle the Other Return Reason field visibility and mandatory state.
// ---------------------------------------------------------------------------
function _toggle_other_reason(dialog) {
	const reason = dialog.get_value("custom_return_reason");
	const is_other = reason === "Other";

	const other_field = dialog.get_field("custom_other_return_reason");
	if (!other_field) return;

	other_field.df.hidden = is_other ? 0 : 1;
	other_field.df.reqd   = is_other ? 1 : 0;

	if (!is_other) {
		dialog.set_value("custom_other_return_reason", "");
	}

	dialog.refresh();
}
