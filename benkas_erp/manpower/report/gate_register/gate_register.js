frappe.query_reports["Gate Register"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
			default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date",
			default: frappe.datetime.get_today(), reqd: 1 },
		{ fieldname: "etype", label: __("Type"), fieldtype: "Select", default: "",
			options: ["", "Person-Staff", "Person-Labour", "Person-Contractor", "Visitor",
				"Vehicle-Site", "Vehicle-Material", "Tools", "Gate Pass"].join("\n") },
		{ fieldname: "direction", label: __("Direction"), fieldtype: "Select", default: "",
			options: ["", "IN", "OUT"].join("\n") },
		{ fieldname: "section", label: __("Plant Section"), fieldtype: "Link",
			options: "Plant Section", default: "" },
		{ fieldname: "contractor", label: __("Contractor"), fieldtype: "Link",
			options: "Contractor", default: "" },
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "reference" && data && data.source && value) {
			const raw = data.reference;
			value = `<a href="/app/${frappe.router.slug(data.source)}/${encodeURIComponent(raw)}">${raw}</a>`;
		}
		if (column.fieldname === "dir") {
			const c = data && data.dir === "IN" ? "green" : "orange";
			value = `<span style="color:var(--text-on-${c},#333);font-weight:600">${data.dir}</span>`;
		}
		return value;
	},
};
