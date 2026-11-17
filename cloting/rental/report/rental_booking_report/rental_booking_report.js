frappe.query_reports['Rental Booking Report'] = {
	filters: [
		{fieldname:'company', label:__('Company'), fieldtype:'Link', options:'Company'},
		{fieldname:'from_date', label:__('From Date'), fieldtype:'Date'},
		{fieldname:'to_date', label:__('To Date'), fieldtype:'Date'},
	],
};
