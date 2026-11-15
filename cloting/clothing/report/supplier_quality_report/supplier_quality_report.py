# Copyright (c) 2026, Hari and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters: dict | None = None):
	
	columns = get_columns()
	data = get_data()

	return columns, data, report_summary


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
 


def get_data() -> list[list]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a list of cell values.
	"""
 
	
	data = frappe.db.sql("""
                      SELECT supplier,
                      quality_rating,
                      lead_time_rating, 
                      price_rating, 
                      overall_rating
					  FROM `tabSupplier Quality Rating`
                      """
                      )
	return data

def overall_rating():
    data = frappe.db.sql("""
                         select avg(overall_rating) FROM `tabSupplier Quality Rating`
                         """)
    return data

def report_summary():
   return  [{
 		"value": overall_rating,
 		"indicator": "Green" if overall_rating > 3 else "Red",
 		"label": ("Overall rating"),
 		"datatype": "Int",
		}]

