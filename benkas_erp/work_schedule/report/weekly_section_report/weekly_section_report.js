frappe.query_reports["Weekly Section Report"] = {
	filters: [
		{ fieldname: "section", label: __("Plant Section"), fieldtype: "Link",
			options: "Plant Section", default: "" },
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -6), reqd: 1 },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
			default: frappe.datetime.get_today(), reqd: 1 },
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "days_stopped" && data && data.days_stopped > 0) {
			value = `<span style="color:#c0271e;font-weight:700">${data.days_stopped}</span>`;
		}
		return value;
	},
};
