import frappe


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = []
	values = {}

	if filters.get("from_date"):
		conditions.append("gp.entry_time >= %(from_date)s")
		values["from_date"] = f"{filters.from_date} 00:00:00"
	if filters.get("to_date"):
		conditions.append("gp.entry_time < DATE_ADD(%(to_date)s, INTERVAL 1 DAY)")
		values["to_date"] = f"{filters.to_date} 00:00:00"
	if filters.get("supplier"):
		conditions.append("gp.supplier = %(supplier)s")
		values["supplier"] = filters.supplier
	if filters.get("status"):
		conditions.append("gp.status = %(status)s")
		values["status"] = filters.status

	where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
	data = frappe.db.sql(
		f"""
		SELECT
			gp.name,
			gp.supplier,
			gp.purchase_order,
			gp.vehicle_no,
			gp.driver_name,
			gp.challan_no,
			gp.packages,
			gp.entry_time,
			gp.received_time,
			gp.exit_time,
			gp.status,
			TIMESTAMPDIFF(
				MINUTE,
				gp.entry_time,
				COALESCE(gp.received_time, NOW())
			) AS waiting_minutes
		FROM `tabGate Pass` gp
		{where_clause}
		ORDER BY gp.entry_time DESC
		""",
		values,
		as_dict=True,
	)

	columns = [
		{"label": "Gate Pass", "fieldname": "name", "fieldtype": "Link", "options": "Gate Pass", "width": 150},
		{"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 180},
		{"label": "Purchase Order", "fieldname": "purchase_order", "fieldtype": "Link", "options": "Purchase Order", "width": 160},
		{"label": "Vehicle No", "fieldname": "vehicle_no", "fieldtype": "Data", "width": 110},
		{"label": "Driver", "fieldname": "driver_name", "fieldtype": "Data", "width": 130},
		{"label": "Challan No", "fieldname": "challan_no", "fieldtype": "Data", "width": 130},
		{"label": "Packages", "fieldname": "packages", "fieldtype": "Int", "width": 90},
		{"label": "Entry Time", "fieldname": "entry_time", "fieldtype": "Datetime", "width": 150},
		{"label": "Received Time", "fieldname": "received_time", "fieldtype": "Datetime", "width": 150},
		{"label": "Exit Time", "fieldname": "exit_time", "fieldtype": "Datetime", "width": 150},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": "Waiting (Minutes)", "fieldname": "waiting_minutes", "fieldtype": "Int", "width": 125},
	]
	return columns, data
