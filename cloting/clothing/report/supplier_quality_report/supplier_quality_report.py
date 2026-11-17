# Copyright (c) 2026, Hari and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart_data(data)
	report_summary = get_report_summary(data)

	return columns, data, None, chart, report_summary


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Data",
		},
		{
			"label": _("Quality Rating"),
			"fieldname": "quality_rating",
			"fieldtype": "Int",
		},
		{
			"label": _("Lead Time Rating"),
			"fieldname": "lead_time_rating",
			"fieldtype": "Int",
		},
		{
			"label": _("Price Rating"),
			"fieldname": "price_rating",
			"fieldtype": "Int",
		},
		{
			"label": _("Overall Rating"),
			"fieldname": "overall_rating",
			"fieldtype": "float",
		},
	]


def get_data(filters: dict) -> list[dict]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a dictionary of cell values.
	"""

	conditions = ""
	values = {}
	if filters.get("supplier"):
		conditions = "WHERE supplier = %(supplier)s"
		values["supplier"] = filters.supplier

	data = frappe.db.sql(
		f"""
		SELECT supplier, quality_rating, lead_time_rating, price_rating, overall_rating
		FROM `tabSupplier Quality Rating`
		{conditions}
		ORDER BY supplier
		""",
		values,
		as_dict=True,
	)
	return data


def get_chart_data(data: list[dict]) -> dict:
	labels = [row["supplier"] for row in data[:30]]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{
					"name": _("Quality Rating"),
					"values": [row["quality_rating"] or 0 for row in data[:30]],
				},
				{
					"name": _("Lead Time Rating"),
					"values": [row["lead_time_rating"] or 0 for row in data[:30]],
				},
				{
					"name": _("Price Rating"),
					"values": [row["price_rating"] or 0 for row in data[:30]],
				},
				{
					"name": _("Overall Rating"),
					"values": [row["overall_rating"] or 0 for row in data[:30]],
				},
			],
		},
		"type": "bar",
		"height": 300,
	}


def get_report_summary(data: list[dict]) -> list[dict]:
	average_rating = (
		sum(row["overall_rating"] or 0 for row in data) / len(data) if data else 0
	)

	return [
		{
			"value": average_rating,
			"indicator": "Green" if average_rating >= 3 else "Red",
			"label": _("Average Overall Rating"),
			"datatype": "Float",
		}
	]

