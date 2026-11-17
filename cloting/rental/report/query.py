import frappe
from frappe.utils import getdate


def filters_dict(filters):
	return frappe._dict(filters or {})


def company_clause(alias, filters, values):
	if filters.get("company"):
		values["company"] = filters.company
		return f" AND {alias}.company = %(company)s"
	return ""


def date_clause(field, filters, values):
	parts = []
	if filters.get("from_date"):
		values["from_date"] = getdate(filters.from_date)
		parts.append(f"{field} >= %(from_date)s")
	if filters.get("to_date"):
		values["to_date"] = getdate(filters.to_date)
		parts.append(f"{field} <= %(to_date)s")
	return (" AND " + " AND ".join(parts)) if parts else ""
