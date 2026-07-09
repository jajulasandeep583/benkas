// Copyright (c) 2026, Benkas Engineering and contributors
// For license information, please see license.txt

// Keep every task dropdown on the log scoped to the chosen section's tasks.
frappe.ui.form.on("Daily Progress Log", {
	onload: (frm) => set_task_filters(frm),
	refresh: (frm) => set_task_filters(frm),
	plant_section: (frm) => set_task_filters(frm),
});

function set_task_filters(frm) {
	const q = () => ({
		query: "benkas_erp.section360.section_task_query",
		filters: { section: frm.doc.plant_section || "" },
	});
	["task_progress", "workers_present", "material_consumed"].forEach((tbl) =>
		frm.set_query("task", tbl, q)
	);
	frm.set_query("activity_task", "photos", q);
}
