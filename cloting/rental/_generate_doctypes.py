#!/usr/bin/env python3
"""Generate Rental module DocType JSON + stub controllers. Run from repo root once."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "doctype"

SYSTEM = {
	"create": 1,
	"delete": 1,
	"email": 1,
	"export": 1,
	"print": 1,
	"read": 1,
	"report": 1,
	"role": "System Manager",
	"share": 1,
	"write": 1,
	"if_owner": 0,
}

ADMIN = {**SYSTEM, "role": "Rental Admin"}
MANAGER = {**SYSTEM, "role": "Rental Manager", "delete": 0}


def with_submit(p, submit=1, cancel=1, amend=1):
	q = dict(p)
	q["submit"] = submit
	q["cancel"] = cancel
	q["amend"] = amend
	return q


def perm(role, **kwargs):
	base = {
		"role": role,
		"read": 1,
		"create": 0,
		"write": 0,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"email": 1,
		"export": 1,
		"print": 1,
		"report": 1,
		"share": 0,
		"if_owner": 0,
	}
	base.update(kwargs)
	return base


def field(fieldname, fieldtype, label=None, **kwargs):
	f = {"fieldname": fieldname, "fieldtype": fieldtype, "label": label or fieldname.replace("_", " ").title()}
	f.update(kwargs)
	return f


def naming(series):
	return field("naming_series", "Select", "Naming Series", options=series, default=series, reqd=1)


def amended(dt):
	return field(
		"amended_from",
		"Link",
		"Amended From",
		options=dt,
		no_copy=1,
		print_hide=1,
		read_only=1,
		search_index=1,
	)


def company_branch():
	return [
		field("company", "Link", "Company", options="Company", reqd=1, in_list_view=1),
		field("branch", "Link", "Branch", options="Branch"),
	]


def write_dt(slug, meta, python_class):
	folder = ROOT / slug
	folder.mkdir(parents=True, exist_ok=True)
	meta.setdefault("doctype", "DocType")
	meta.setdefault("engine", "InnoDB")
	meta.setdefault("module", "Rental")
	meta.setdefault("actions", [])
	meta.setdefault("links", [])
	meta.setdefault("sort_field", "creation")
	meta.setdefault("sort_order", "DESC")
	meta.setdefault("states", [])
	meta.setdefault("row_format", "Dynamic")
	meta.setdefault("grid_page_length", 50)
	meta.setdefault("index_web_pages_for_search", 1)
	meta.setdefault("creation", "2026-11-17 00:00:00.000000")
	meta.setdefault("field_order", [f["fieldname"] for f in meta["fields"]])
	(folder / f"{slug}.json").write_text(json.dumps(meta, indent=1) + "\n")
	py = folder / f"{slug}.py"
	if not py.exists():
		py.write_text(
			"from frappe.model.document import Document\n\n\n"
			f"class {python_class}(Document):\n\tpass\n"
		)
	js = folder / f"{slug}.js"
	if not js.exists() and not meta.get("istable") and not meta.get("issingle"):
		js.write_text(f"frappe.ui.form.on('{meta['name']}', {{\n\trefresh(frm) {{}}\n}});\n")
	(folder / "__init__.py").write_text("")
	test = folder / f"test_{slug}.py"
	if not test.exists() and not meta.get("istable"):
		test.write_text(
			"from frappe.tests import IntegrationTestCase\n\n\n"
			f"class Test{python_class}(IntegrationTestCase):\n\tpass\n"
		)


def main():
	# --- Rental Settings ---
	write_dt(
		"rental_settings",
		{
			"name": "Rental Settings",
			"issingle": 1,
			"track_changes": 1,
			"permissions": [SYSTEM, ADMIN, perm("Rental Manager", write=1, report=1)],
			"fields": [
				field("defaults_section", "Section Break", "Defaults"),
				field("company", "Link", "Company", options="Company"),
				field("default_branch", "Link", "Default Branch", options="Branch"),
				field("default_warehouse", "Link", "Default Warehouse", options="Warehouse"),
				field("rental_item", "Link", "Rental Charge Item", options="Item"),
				field("col_defaults", "Column Break"),
				field("cost_center", "Link", "Cost Center", options="Cost Center"),
				field("mode_of_payment", "Link", "Default Mode of Payment", options="Mode of Payment"),
				field("auto_create_accounting_documents", "Check", "Auto Create Accounting Documents", default="0"),
				field("pricing_section", "Section Break", "Pricing and Holds"),
				field("deposit_percent", "Percent", "Default Deposit % of Replacement", default="0"),
				field("late_fee_per_day", "Currency", "Late Fee Per Day", default="0"),
				field("cleaning_buffer_days", "Int", "Cleaning Buffer Days", default="1", non_negative=1),
				field("hold_expiry_hours", "Int", "Hold Expiry Hours", default="2", non_negative=1),
				field("col_pricing", "Column Break"),
				field("advance_payment_percent", "Percent", "Advance Required to Confirm %", default="100"),
				field("auto_approve_deduction_limit", "Currency", "Auto-Approve Deduction Limit", default="0"),
				field("cancellation_hours_before_pickup", "Int", "Free Cancel Hours Before Pickup", default="24"),
				field("accounts_section", "Section Break", "Accounts (confirm GST with accountant)"),
				field("rental_income_account", "Link", "Rental Income Account", options="Account"),
				field("deposit_liability_account", "Link", "Security Deposit Liability Account", options="Account"),
				field("late_fee_income_account", "Link", "Late Fee Income Account", options="Account"),
				field("damage_recovery_income_account", "Link", "Damage Recovery Income Account", options="Account"),
				field("col_accounts", "Column Break"),
				field("deposit_cash_account", "Link", "Deposit Cash/Bank Account", options="Account"),
				field("policy_section", "Section Break", "Policies shown on quotation"),
				field("rental_conditions", "Text Editor", "Rental Conditions"),
				field("cancellation_policy", "Text Editor", "Cancellation Policy"),
				field("late_fee_policy", "Text Editor", "Late Fee Policy"),
			],
		},
		"RentalSettings",
	)

	# --- Rental Costume ---
	write_dt(
		"rental_costume",
		{
			"name": "Rental Costume",
			"autoname": "field:costume_code",
			"allow_rename": 1,
			"allow_import": 1,
			"track_changes": 1,
			"search_fields": "costume_name,item,category",
			"title_field": "costume_name",
			"permissions": [
				SYSTEM, ADMIN, MANAGER,
				perm("Rental Cashier", read=1, report=1),
				perm("Rental Storekeeper", read=1, report=1),
				perm("Accounts User", read=1, report=1),
			],
			"fields": [
				field("costume_code", "Data", "Costume Code", reqd=1, unique=1),
				field("costume_name", "Data", "Costume Name", reqd=1, in_list_view=1, in_standard_filter=1),
				field("item", "Link", "Item", options="Item", reqd=1, in_list_view=1),
				field("category", "Data", "Category", in_standard_filter=1),
				field("col1", "Column Break"),
				*company_branch(),
				field("is_active", "Check", "Is Active", default="1"),
				field("pricing_section", "Section Break", "Default Pricing"),
				field("default_rental_rate", "Currency", "Default Rental Rate", reqd=1),
				field("default_deposit", "Currency", "Default Deposit"),
				field("col2", "Column Break"),
				field("replacement_value", "Currency", "Replacement Value"),
				field("description", "Small Text", "Description"),
			],
		},
		"RentalCostume",
	)

	# --- Rental Costume Unit ---
	write_dt(
		"rental_costume_unit",
		{
			"name": "Rental Costume Unit",
			"autoname": "field:unit_code",
			"allow_rename": 0,
			"allow_import": 1,
			"track_changes": 1,
			"search_fields": "barcode,colour,size,rental_costume",
			"title_field": "unit_code",
			"permissions": [
				SYSTEM, ADMIN, MANAGER,
				perm("Rental Cashier", read=1, report=1),
				perm("Rental Storekeeper", read=1, write=1, create=1, report=1),
				perm("Accounts User", read=1, report=1),
			],
			"fields": [
				field("unit_code", "Data", "Unit Code", reqd=1, unique=1, in_list_view=1),
				field("rental_costume", "Link", "Rental Costume", options="Rental Costume", reqd=1, in_standard_filter=1),
				field("item", "Link", "Item", options="Item", fetch_from="rental_costume.item"),
				field("colour", "Data", "Colour", reqd=1, in_list_view=1, in_standard_filter=1),
				field("size", "Data", "Size", reqd=1, in_list_view=1, in_standard_filter=1),
				field("col1", "Column Break"),
				field("barcode", "Data", "Barcode", unique=1, reqd=1, in_global_search=1),
				field("serial_no", "Link", "Serial No", options="Serial No"),
				field("warehouse", "Link", "Warehouse", options="Warehouse"),
				*company_branch(),
				field("status_section", "Section Break", "Condition and Status"),
				field(
					"operational_status",
					"Select",
					"Operational Status",
					options="\n".join(
						[
							"Available",
							"Reserved",
							"Rented Out",
							"Returned",
							"Under Inspection",
							"Under Cleaning",
							"Under Repair",
							"Lost",
							"Retired",
						]
					),
					default="Available",
					reqd=1,
					in_list_view=1,
					in_standard_filter=1,
				),
				field("condition", "Select", "Condition", options="Good\nNormal Wear\nDamaged\nMissing Accessories", default="Good"),
				field("current_booking", "Link", "Current Booking", options="Rental Booking", read_only=1),
				field("col2", "Column Break"),
				field("purchase_value", "Currency", "Purchase Value"),
				field("replacement_value", "Currency", "Replacement Value"),
				field("rental_rate", "Currency", "Rental Rate"),
				field("deposit_amount", "Currency", "Deposit Amount"),
				field("photo", "Attach Image", "Photo"),
				field("notes", "Small Text", "Notes"),
			],
		},
		"RentalCostumeUnit",
	)

	# --- Enquiry Item (child) ---
	write_dt(
		"rental_enquiry_item",
		{
			"name": "Rental Enquiry Item",
			"istable": 1,
			"editable_grid": 1,
			"permissions": [],
			"fields": [
				field("rental_costume", "Link", "Rental Costume", options="Rental Costume", in_list_view=1, reqd=1),
				field("colour", "Data", "Colour", in_list_view=1),
				field("size", "Data", "Size", in_list_view=1),
				field("qty", "Int", "Qty", default="1", reqd=1, in_list_view=1),
				field("notes", "Data", "Notes"),
			],
		},
		"RentalEnquiryItem",
	)

	write_dt(
		"rental_enquiry",
		{
			"name": "Rental Enquiry",
			"autoname": "naming_series:",
			"is_submittable": 1,
			"track_changes": 1,
			"search_fields": "customer,occasion,status",
			"title_field": "customer",
			"permissions": [
				with_submit(SYSTEM),
				with_submit(ADMIN),
				with_submit(MANAGER, cancel=1),
				perm("Rental Cashier", create=1, write=1, submit=1, report=1, share=1),
				perm("Rental Storekeeper", read=1, report=1),
				perm("Accounts User", read=1, report=1),
			],
			"fields": [
				naming("RENQ-.YYYY.-.#####"),
				field("customer", "Link", "Customer", options="Customer", reqd=1, in_list_view=1),
				field("customer_name", "Data", "Customer Name", fetch_from="customer.customer_name", read_only=1),
				field("occasion", "Data", "Occasion", in_list_view=1),
				field("col1", "Column Break"),
				*company_branch(),
				field(
					"status",
					"Select",
					"Status",
					options="Open\nAvailability Checked\nQuotation Prepared\nConverted to Booking\nLost\nExpired",
					default="Open",
					reqd=1,
					in_list_view=1,
					in_standard_filter=1,
				),
				field("lost_reason", "Small Text", "Lost Reason"),
				field("dates_section", "Section Break", "Requested Period"),
				field("pickup_date", "Date", "Pickup Date", reqd=1, in_list_view=1),
				field("return_date", "Date", "Return Date", reqd=1),
				field("items_section", "Section Break", "Requested Costumes"),
				field("items", "Table", "Items", options="Rental Enquiry Item", reqd=1),
				field("converted_booking", "Link", "Converted Booking", options="Rental Booking", read_only=1),
				amended("Rental Enquiry"),
			],
		},
		"RentalEnquiry",
	)

	write_dt(
		"rental_booking_item",
		{
			"name": "Rental Booking Item",
			"istable": 1,
			"editable_grid": 1,
			"permissions": [],
			"fields": [
				field("rental_costume", "Link", "Rental Costume", options="Rental Costume", reqd=1, in_list_view=1),
				field("item", "Link", "Item", options="Item", fetch_from="rental_costume.item", read_only=1),
				field("colour", "Data", "Colour", reqd=1, in_list_view=1),
				field("size", "Data", "Size", reqd=1, in_list_view=1),
				field("qty", "Int", "Qty", default="1", reqd=1, in_list_view=1),
				field("rental_rate", "Currency", "Rental Rate", in_list_view=1),
				field("deposit_rate", "Currency", "Deposit / Unit"),
				field("amount", "Currency", "Rental Amount", read_only=1),
				field("deposit_amount", "Currency", "Deposit Amount", read_only=1),
				field("allocated_qty", "Int", "Allocated Qty", read_only=1, default="0"),
				field("handed_over_qty", "Int", "Handed Over Qty", read_only=1, default="0"),
				field("returned_qty", "Int", "Returned Qty", read_only=1, default="0"),
			],
		},
		"RentalBookingItem",
	)

	write_dt(
		"rental_booking",
		{
			"name": "Rental Booking",
			"autoname": "naming_series:",
			"is_submittable": 1,
			"track_changes": 1,
			"search_fields": "customer,booking_status,pickup_date",
			"title_field": "customer",
			"permissions": [
				with_submit(SYSTEM),
				with_submit(ADMIN),
				with_submit(MANAGER),
				perm("Rental Cashier", create=1, write=1, submit=1, report=1, share=1),
				perm("Rental Storekeeper", read=1, report=1),
				perm("Accounts User", read=1, report=1),
			],
			"fields": [
				naming("RB-.YYYY.-.#####"),
				field("customer", "Link", "Customer", options="Customer", reqd=1, in_list_view=1),
				field("customer_name", "Data", "Customer Name", fetch_from="customer.customer_name", read_only=1),
				field("rental_enquiry", "Link", "Rental Enquiry", options="Rental Enquiry"),
				field("idempotency_key", "Data", "Idempotency Key", unique=1, no_copy=1),
				field("col1", "Column Break"),
				*company_branch(),
				field(
					"booking_status",
					"Select",
					"Booking Status",
					options="\n".join(
						[
							"Draft",
							"Availability Checked",
							"Awaiting Payment",
							"Confirmed",
							"Partially Handed Over",
							"Rented Out",
							"Partially Returned",
							"Return Inspection",
							"Settlement Pending",
							"Closed",
							"Rejected",
							"Cancelled",
							"Expired",
							"Overdue",
							"Disputed",
						]
					),
					default="Draft",
					reqd=1,
					in_list_view=1,
					in_standard_filter=1,
					read_only=1,
				),
				field(
					"payment_status",
					"Select",
					"Payment Status",
					options="Unpaid\nPartial\nPaid",
					default="Unpaid",
					in_list_view=1,
				),
				field("hold_expires_on", "Datetime", "Hold Expires On", read_only=1),
				field("dates_section", "Section Break", "Rental Period"),
				field("pickup_date", "Date", "Pickup Date", reqd=1, in_list_view=1),
				field("return_date", "Date", "Return Date", reqd=1),
				field("col2", "Column Break"),
				field("is_overdue", "Check", "Is Overdue", read_only=1, default="0"),
				field("items_section", "Section Break", "Costumes"),
				field("items", "Table", "Items", options="Rental Booking Item", reqd=1),
				field("totals_section", "Section Break", "Totals", permlevel=1),
				field("rental_amount", "Currency", "Rental Amount", read_only=1, permlevel=1),
				field("deposit_amount", "Currency", "Security Deposit", read_only=1, permlevel=1),
				field("discount_amount", "Currency", "Discount", permlevel=1, default="0"),
				field("tax_amount", "Currency", "Tax", permlevel=1, default="0"),
				field("col3", "Column Break"),
				field("grand_total", "Currency", "Grand Total (Rental)", read_only=1, permlevel=1),
				field("advance_received", "Currency", "Advance Received", permlevel=1, default="0"),
				field("deposit_received", "Currency", "Deposit Received", permlevel=1, default="0"),
				field("accounting_section", "Section Break", "Accounting Links"),
				field("sales_invoice", "Link", "Sales Invoice", options="Sales Invoice", read_only=1),
				field("deposit_journal_entry", "Link", "Deposit Journal Entry", options="Journal Entry", read_only=1),
				field("policy_section", "Section Break", "Policies"),
				field("rental_conditions", "Text Editor", "Rental Conditions"),
				field("cancellation_policy", "Text Editor", "Cancellation Policy"),
				field("late_fee_policy", "Text Editor", "Late Fee Policy"),
				amended("Rental Booking"),
			],
		},
		"RentalBooking",
	)

	# permlevel 1 for manager/accounts/admin
	# Frappe needs a second DocPerm with permlevel 1
	booking_json = ROOT / "rental_booking" / "rental_booking.json"
	data = json.loads(booking_json.read_text())
	for role in ("System Manager", "Rental Admin", "Rental Manager", "Accounts User", "Rental Cashier"):
		data["permissions"].append(
			perm(role, read=1, write=1 if role != "Rental Cashier" and role != "Accounts User" else 0, permlevel=1)
		)
	booking_json.write_text(json.dumps(data, indent=1) + "\n")

	write_dt(
		"rental_unit_allocation",
		{
			"name": "Rental Unit Allocation",
			"autoname": "naming_series:",
			"is_submittable": 1,
			"track_changes": 1,
			"permissions": [
				with_submit(SYSTEM),
				with_submit(ADMIN),
				with_submit(MANAGER),
				perm("Rental Cashier", create=1, write=1, submit=1, report=1),
				perm("Rental Storekeeper", read=1, report=1),
				perm("Accounts User", read=1, report=1),
			],
			"fields": [
				naming("RUA-.YYYY.-.#####"),
				field("rental_booking", "Link", "Rental Booking", options="Rental Booking", reqd=1, in_list_view=1, search_index=1),
				field("rental_booking_item", "Data", "Rental Booking Item"),
				field("rental_costume_unit", "Link", "Costume Unit", options="Rental Costume Unit", reqd=1, in_list_view=1, search_index=1),
				field("col1", "Column Break"),
				*company_branch(),
				field("start_date", "Date", "Start Date", reqd=1, in_list_view=1),
				field("end_date", "Date", "End Date", reqd=1, in_list_view=1),
				field(
					"allocation_status",
					"Select",
					"Allocation Status",
					options="Hold\nConfirmed\nReleased\nCancelled",
					default="Hold",
					reqd=1,
					in_standard_filter=1,
				),
				field("hold_expires_on", "Datetime", "Hold Expires On"),
				amended("Rental Unit Allocation"),
			],
		},
		"RentalUnitAllocation",
	)

	write_dt(
		"rental_handover_item",
		{
			"name": "Rental Handover Item",
			"istable": 1,
			"editable_grid": 1,
			"permissions": [],
			"fields": [
				field("rental_costume_unit", "Link", "Costume Unit", options="Rental Costume Unit", reqd=1, in_list_view=1),
				field("barcode", "Data", "Barcode", in_list_view=1),
				field("rental_booking_item", "Data", "Booking Item"),
				field("condition_at_issue", "Select", "Condition at Issue", options="Good\nNormal Wear\nDamaged\nMissing Accessories", default="Good", in_list_view=1),
				field("accessories", "Small Text", "Accessories"),
				field("photo", "Attach Image", "Photo"),
				field("remarks", "Small Text", "Remarks"),
			],
		},
		"RentalHandoverItem",
	)

	write_dt(
		"rental_handover",
		{
			"name": "Rental Handover",
			"autoname": "naming_series:",
			"is_submittable": 1,
			"track_changes": 1,
			"permissions": [
				with_submit(SYSTEM),
				with_submit(ADMIN),
				with_submit(MANAGER),
				perm("Rental Storekeeper", create=1, write=1, submit=1, report=1, share=1),
				perm("Rental Cashier", read=1, report=1),
				perm("Accounts User", read=1, report=1),
			],
			"fields": [
				naming("RH-.YYYY.-.#####"),
				field("rental_booking", "Link", "Rental Booking", options="Rental Booking", reqd=1, in_list_view=1),
				field("handover_datetime", "Datetime", "Handover Date/Time", reqd=1, default="Now"),
				field("storekeeper", "Link", "Storekeeper", options="User", default="__user"),
				field("col1", "Column Break"),
				*company_branch(),
				field("items", "Table", "Items", options="Rental Handover Item", reqd=1),
				field("remarks", "Small Text", "Remarks"),
				amended("Rental Handover"),
			],
		},
		"RentalHandover",
	)

	write_dt(
		"rental_return_item",
		{
			"name": "Rental Return Item",
			"istable": 1,
			"editable_grid": 1,
			"permissions": [],
			"fields": [
				field("rental_costume_unit", "Link", "Costume Unit", options="Rental Costume Unit", reqd=1, in_list_view=1),
				field("barcode", "Data", "Barcode", in_list_view=1),
				field("condition_at_return", "Select", "Condition at Return", options="Good\nNormal Wear\nDamaged\nMissing Accessories\nLost", default="Good", in_list_view=1),
				field("damage_notes", "Small Text", "Damage Notes"),
				field("missing_accessories", "Small Text", "Missing Accessories"),
				field("photo", "Attach Image", "Photo"),
				field("remarks", "Small Text", "Remarks"),
			],
		},
		"RentalReturnItem",
	)

	write_dt(
		"rental_return",
		{
			"name": "Rental Return",
			"autoname": "naming_series:",
			"is_submittable": 1,
			"track_changes": 1,
			"permissions": [
				with_submit(SYSTEM),
				with_submit(ADMIN),
				with_submit(MANAGER),
				perm("Rental Storekeeper", create=1, write=1, submit=1, report=1, share=1),
				perm("Rental Cashier", read=1, report=1),
				perm("Accounts User", read=1, report=1),
			],
			"fields": [
				naming("RRET-.YYYY.-.#####"),
				field("rental_booking", "Link", "Rental Booking", options="Rental Booking", reqd=1, in_list_view=1),
				field("return_datetime", "Datetime", "Return Date/Time", reqd=1, default="Now"),
				field("storekeeper", "Link", "Storekeeper", options="User", default="__user"),
				field("is_late", "Check", "Is Late", read_only=1, default="0"),
				field("col1", "Column Break"),
				*company_branch(),
				field("items", "Table", "Items", options="Rental Return Item", reqd=1),
				field("remarks", "Small Text", "Remarks"),
				amended("Rental Return"),
			],
		},
		"RentalReturn",
	)

	write_dt(
		"rental_inspection",
		{
			"name": "Rental Inspection",
			"autoname": "naming_series:",
			"is_submittable": 1,
			"track_changes": 1,
			"permissions": [
				with_submit(SYSTEM),
				with_submit(ADMIN),
				with_submit(MANAGER),
				perm("Rental Storekeeper", create=1, write=1, submit=1, report=1, share=1),
				perm("Rental Cashier", read=1, report=1),
				perm("Accounts User", read=1, report=1),
			],
			"fields": [
				naming("RINS-.YYYY.-.#####"),
				field("rental_booking", "Link", "Rental Booking", options="Rental Booking", reqd=1),
				field("rental_return", "Link", "Rental Return", options="Rental Return"),
				field("rental_costume_unit", "Link", "Costume Unit", options="Rental Costume Unit", reqd=1, in_list_view=1),
				field("inspector", "Link", "Inspector", options="User", default="__user"),
				field("col1", "Column Break"),
				*company_branch(),
				field(
					"classification",
					"Select",
					"Classification",
					options="Good\nNormal Wear\nRequires Cleaning\nMinor Damage\nMajor Damage\nMissing Accessories\nLost",
					reqd=1,
					in_list_view=1,
				),
				field("proposed_deduction", "Currency", "Proposed Deduction", default="0"),
				field("photo", "Attach Image", "Photo"),
				field("remarks", "Small Text", "Remarks"),
				amended("Rental Inspection"),
			],
		},
		"RentalInspection",
	)

	write_dt(
		"rental_maintenance",
		{
			"name": "Rental Maintenance",
			"autoname": "naming_series:",
			"is_submittable": 1,
			"track_changes": 1,
			"permissions": [
				with_submit(SYSTEM),
				with_submit(ADMIN),
				with_submit(MANAGER),
				perm("Rental Storekeeper", create=1, write=1, submit=1, report=1, share=1),
				perm("Rental Cashier", read=1, report=1),
			],
			"fields": [
				naming("RMAINT-.YYYY.-.#####"),
				field("rental_costume_unit", "Link", "Costume Unit", options="Rental Costume Unit", reqd=1, in_list_view=1),
				field("job_type", "Select", "Job Type", options="Cleaning\nRepair", reqd=1, in_list_view=1),
				field("rental_inspection", "Link", "Rental Inspection", options="Rental Inspection"),
				field("rental_booking", "Link", "Rental Booking", options="Rental Booking"),
				field("col1", "Column Break"),
				*company_branch(),
				field(
					"job_status",
					"Select",
					"Job Status",
					options="Open\nIn Progress\nCompleted",
					default="Open",
					reqd=1,
					in_list_view=1,
				),
				field("completed_on", "Datetime", "Completed On"),
				field("storekeeper", "Link", "Storekeeper", options="User", default="__user"),
				field("remarks", "Small Text", "Remarks"),
				amended("Rental Maintenance"),
			],
		},
		"RentalMaintenance",
	)

	write_dt(
		"rental_settlement",
		{
			"name": "Rental Settlement",
			"autoname": "naming_series:",
			"is_submittable": 1,
			"track_changes": 1,
			"permissions": [
				with_submit(SYSTEM),
				with_submit(ADMIN),
				with_submit(MANAGER),
				perm("Rental Cashier", create=1, write=1, report=1),
				perm("Rental Storekeeper", read=1, report=1),
				perm("Accounts User", create=1, write=1, submit=1, report=1, share=1),
			],
			"fields": [
				naming("RSET-.YYYY.-.#####"),
				field("rental_booking", "Link", "Rental Booking", options="Rental Booking", reqd=1, unique=1, in_list_view=1),
				field("customer", "Link", "Customer", options="Customer", reqd=1),
				field(
					"settlement_status",
					"Select",
					"Settlement Status",
					options="Draft\nPending Approval\nApproved\nPosted",
					default="Draft",
					reqd=1,
					in_list_view=1,
					read_only=1,
				),
				field("col1", "Column Break"),
				*company_branch(),
				field("requires_manager_approval", "Check", "Requires Manager Approval", read_only=1, default="0"),
				field("approved_by", "Link", "Approved By", options="User", read_only=1),
				field("refunded", "Check", "Refund Posted", read_only=1, default="0"),
				field("amounts_section", "Section Break", "Amounts", permlevel=1),
				field("rental_amount", "Currency", "Rental Amount", read_only=1, permlevel=1),
				field("deposit_amount", "Currency", "Deposit Held", read_only=1, permlevel=1),
				field("late_fee", "Currency", "Late Fee", permlevel=1, default="0"),
				field("damage_deduction", "Currency", "Damage Deduction", permlevel=1, default="0"),
				field("missing_accessories_deduction", "Currency", "Missing Accessories Deduction", permlevel=1, default="0"),
				field("replacement_recovery", "Currency", "Replacement Recovery", permlevel=1, default="0"),
				field("col2", "Column Break"),
				field("total_deductions", "Currency", "Total Deductions", read_only=1, permlevel=1),
				field("refund_amount", "Currency", "Refund Amount", read_only=1, permlevel=1),
				field("receivable_shortfall", "Currency", "Receivable Shortfall", read_only=1, permlevel=1),
				field("links_section", "Section Break", "Accounting"),
				field("refund_journal_entry", "Link", "Refund Journal Entry", options="Journal Entry", read_only=1),
				field("deduction_journal_entry", "Link", "Deduction Journal Entry", options="Journal Entry", read_only=1),
				field("shortfall_sales_invoice", "Link", "Shortfall Sales Invoice", options="Sales Invoice", read_only=1),
				field("remarks", "Small Text", "Remarks"),
				amended("Rental Settlement"),
			],
		},
		"RentalSettlement",
	)

	settlement_json = ROOT / "rental_settlement" / "rental_settlement.json"
	data = json.loads(settlement_json.read_text())
	for role in ("System Manager", "Rental Admin", "Rental Manager", "Accounts User"):
		data["permissions"].append(perm(role, read=1, write=1, permlevel=1))
	data["permissions"].append(perm("Rental Cashier", read=1, permlevel=1))
	settlement_json.write_text(json.dumps(data, indent=1) + "\n")

	print("Generated doctypes in", ROOT)


if __name__ == "__main__":
	main()
