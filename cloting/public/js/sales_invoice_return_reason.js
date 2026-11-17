// ===========================================================================
// Return Reason Popup – Sales Invoice (Client Script)
// App: cloting  |  DocType: Sales Invoice
//
// Strategy:
//   • The standard ERPNext return button uses frappe.model.open_mapped_doc()
//     which calls the server mapper, then navigates to the new draft doc.
//   • When the new return draft loads, frm.doc.is_return == 1 and
//     frm.doc.docstatus == 0 (draft) and frm.doc.__islocal == 1.
//   • We hook the refresh event.  On each refresh we check if this is a
//     return draft that still needs its reason captured.
//   • A session-level flag (frm._return_reason_dialog_shown) prevents the
//     dialog from reopening while the cashier is filling in the form.
//     The flag is cleared when the form reloads from the server (after save),
//     so if the reason was never saved, the dialog reappears on reopening.
// ===========================================================================

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (!_should_show_return_reason_dialog(frm)) {
			return;
		}
		// Mark that we have shown the dialog for this in-memory session so
		// repeated refresh calls (triggered by field changes) don't stack dialogs.
		frm._return_reason_dialog_shown = true;
		_show_return_reason_dialog(frm);
	},
});

// ---------------------------------------------------------------------------
// Guard: decide whether the popup should appear right now.
// ---------------------------------------------------------------------------
function _should_show_return_reason_dialog(frm) {
	// Must be a return document.
	if (!frm.doc.is_return) return false;

	// Only show for draft (unsaved / newly mapped) documents.
	if (frm.doc.docstatus !== 0) return false;

	// If the return reason is already filled in, do not show again.
	if (frm.doc.custom_return_reason) return false;

	// Prevent repeated popups within the same form session.
	if (frm._return_reason_dialog_shown) return false;

	return true;
}

// ---------------------------------------------------------------------------
// Dialog builder and submission handler.
// ---------------------------------------------------------------------------
function _show_return_reason_dialog(frm) {
	const REASON_OPTIONS = [
		{ label: __("Size Issue"),    value: "Size Issue" },
		{ label: __("Colour Issue"),  value: "Colour Issue" },
		{ label: __("Defect"),        value: "Defect" },
		{ label: __("Wrong Item"),    value: "Wrong Item" },
		{ label: __("Billing Error"), value: "Billing Error" },
		{ label: __("Changed Mind"),  value: "Changed Mind" },
		{ label: __("Other"),         value: "Other" },
	];

	const dialog = new frappe.ui.Dialog({
		title: __("Return Reason"),
		fields: [
			{
				fieldname: "custom_return_reason",
				label: __("Return Reason"),
				fieldtype: "Select",
				options: REASON_OPTIONS.map((o) => o.value).join("\n"),
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
			// --- Validation ---
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

			// --- Apply values to the form ---
			frm.set_value("custom_return_reason", values.custom_return_reason);
			frm.set_value(
				"custom_other_return_reason",
				values.custom_return_reason === "Other"
					? (values.custom_other_return_reason || "").trim()
					: ""
			);
			frm.set_value("custom_return_remarks", (values.custom_return_remarks || "").trim());

			// Save the draft so the values persist when the cashier reviews.
			frm.save("Save").then(() => {
				frm.reload_doc();
			}).catch(() => {
				// Save failed; keep values in the in-memory doc so the cashier
				// can still see them and retry manually.
			});
		},
		secondary_action_label: __("Cancel"),
		secondary_action() {
			dialog.hide();
			// Clear the session flag so the popup can reappear if the cashier
			// navigates away and reopens the document without saving a reason.
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
