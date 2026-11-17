frappe.query_reports["Slow-Moving Stock Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		},
		{
			fieldname: "warehouse",
			label: __("Warehouse"),
			fieldtype: "Link",
			options: "Warehouse",
			get_query() {
				return {
					filters: {
						company: frappe.query_report.get_filter_value("company"),
						is_group: 0,
					},
				};
			},
		},
		{
			fieldname: "item_group",
			label: __("Item Group"),
			fieldtype: "Link",
			options: "Item Group",
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Link",
			options: "Brand",
		},
		{
			fieldname: "days_without_sale",
			label: __("Days Without Sale"),
			fieldtype: "Int",
			default: 60,
			reqd: 1,
		},
	],
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname === "sales_status" || column.fieldname === "days_without_sale") {
			return `<span class="text-warning">${formatted}</span>`;
		}
		return formatted;
	},
};
