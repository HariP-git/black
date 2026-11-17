import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "report"

REPORTS = [
	("costume_availability_report", "Costume Availability Report", "Rental Costume Unit"),
	("rental_booking_report", "Rental Booking Report", "Rental Booking"),
	("customer_rental_history", "Customer Rental History", "Rental Booking"),
	("daily_handover_report", "Daily Handover Report", "Rental Handover"),
	("daily_return_report", "Daily Return Report", "Rental Return"),
	("overdue_rental_report", "Overdue Rental Report", "Rental Booking"),
	("deposit_outstanding_report", "Deposit Outstanding Report", "Rental Settlement"),
	("rental_revenue_report", "Rental Revenue Report", "Sales Invoice"),
	("damage_and_maintenance_report", "Damage and Maintenance Report", "Rental Inspection"),
	("costume_utilization_report", "Costume Utilization Report", "Rental Unit Allocation"),
]


def write_report(slug, name, ref):
	folder = ROOT / slug
	folder.mkdir(parents=True, exist_ok=True)
	(folder / "__init__.py").write_text("")
	meta = {
		"add_total_row": 0,
		"disabled": 0,
		"doctype": "Report",
		"is_standard": "Yes",
		"module": "Rental",
		"name": name,
		"ref_doctype": ref,
		"report_name": name,
		"report_type": "Script Report",
		"roles": [
			{"role": "Rental Manager"},
			{"role": "Rental Admin"},
			{"role": "System Manager"},
			{"role": "Accounts User"},
		],
	}
	(folder / f"{slug}.json").write_text(json.dumps(meta, indent=1) + "\n")
	(folder / f"{slug}.js").write_text(
		"frappe.query_reports['%s'] = {\n\tfilters: [\n"
		"\t\t{fieldname:'company', label:__('Company'), fieldtype:'Link', options:'Company'},\n"
		"\t\t{fieldname:'from_date', label:__('From Date'), fieldtype:'Date'},\n"
		"\t\t{fieldname:'to_date', label:__('To Date'), fieldtype:'Date'},\n"
		"\t],\n};\n" % name
	)


if __name__ == "__main__":
	for slug, name, ref in REPORTS:
		write_report(slug, name, ref)
	print("report stubs", len(REPORTS))
