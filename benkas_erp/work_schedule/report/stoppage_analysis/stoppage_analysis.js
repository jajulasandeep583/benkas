frappe.query_reports["Stoppage Analysis"] = {
	filters: [
		{ fieldname: "section", label: __("Plant Section"), fieldtype: "Link",
			options: "Plant Section", default: "" },
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -6), reqd: 1 },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
			default: frappe.datetime.get_today(), reqd: 1 },
	],
};
