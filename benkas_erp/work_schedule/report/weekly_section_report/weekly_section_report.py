# Copyright (c) 2026, Benkas Engineering and contributors
# For license information, please see license.txt
"""Weekly Section Report — pick a section and a week, see everything that
happened: each task's latest %, latest status, days worked vs stopped, the
work-description narrative in date order, person-days, material and photo count.

Script report so the optional section filter and the date range default safely
on the initial auto-run."""

import frappe
from frappe.utils import today, add_days, flt, formatdate

COLUMNS = [
    {"label": "Section", "fieldname": "section", "fieldtype": "Data", "width": 130},
    {"label": "Task", "fieldname": "task", "fieldtype": "Data", "width": 200},
    {"label": "Latest %", "fieldname": "latest_pct", "fieldtype": "Percent", "width": 90},
    {"label": "Latest Status", "fieldname": "latest_status", "fieldtype": "Data", "width": 160},
    {"label": "Worked", "fieldname": "days_worked", "fieldtype": "Int", "width": 70},
    {"label": "Stopped", "fieldname": "days_stopped", "fieldtype": "Int", "width": 70},
    {"label": "P-days", "fieldname": "person_days", "fieldtype": "Float", "width": 75},
    {"label": "Material", "fieldname": "material", "fieldtype": "Data", "width": 200},
    {"label": "Photos", "fieldname": "photos", "fieldtype": "Int", "width": 65},
    {"label": "Narrative (in date order)", "fieldname": "narrative", "fieldtype": "Small Text", "width": 460},
]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    to_date = filters.get("to_date") or today()
    from_date = filters.get("from_date") or add_days(to_date, -6)

    section_filter = {"is_active": 1}
    if filters.get("section"):
        section_filter["name"] = filters.get("section")
    sections = frappe.get_all("Plant Section", filters=section_filter,
                              fields=["name", "section_name", "project_task"],
                              order_by="section_code asc")

    rows = []
    for s in sections:
        if not s.project_task:
            continue
        tasks = frappe.get_all("Task", filters={"parent_task": s.project_task},
                               fields=["name", "subject", "progress"], order_by="subject asc")
        for t in tasks:
            log = frappe.db.sql(
                """SELECT dtp.work_description, dtp.percent_complete, dtp.status,
                          dpl.log_date, IFNULL(ps.is_stopped,0) stopped
                   FROM `tabDaily Task Progress` dtp
                   JOIN `tabDaily Progress Log` dpl ON dpl.name=dtp.parent
                   LEFT JOIN `tabProgress Status` ps ON ps.name=dtp.status
                   WHERE dtp.task=%s AND dpl.docstatus=1 AND dpl.log_date BETWEEN %s AND %s
                   ORDER BY dpl.log_date""", (t.name, from_date, to_date), as_dict=1)
            if not log:
                continue  # only tasks that saw activity this week
            worked = len({r.log_date for r in log if not r.stopped})
            stopped = len({r.log_date for r in log if r.stopped})
            latest = log[-1]
            narrative = "  •  ".join(
                f"{formatdate(r.log_date,'dd MMM')} [{r.status or '—'}]: {(r.work_description or '').strip()}"
                for r in log)
            person_days = frappe.db.sql(
                """SELECT COALESCE(SUM(dwl.hours),0)/8 FROM `tabDaily Worker Log` dwl
                   JOIN `tabDaily Progress Log` dpl ON dpl.name=dwl.parent
                   WHERE dwl.task=%s AND dpl.log_date BETWEEN %s AND %s""",
                (t.name, from_date, to_date))[0][0] or 0
            mat = frappe.db.sql(
                """SELECT dmc.item, SUM(dmc.qty), dmc.uom FROM `tabDaily Material Consumed` dmc
                   JOIN `tabDaily Progress Log` dpl ON dpl.name=dmc.parent
                   WHERE dmc.task=%s AND dpl.log_date BETWEEN %s AND %s
                   GROUP BY dmc.item, dmc.uom ORDER BY 2 DESC""", (t.name, from_date, to_date))
            material = ", ".join(f"{m[0]} {m[1]:g}{(' '+m[2]) if m[2] else ''}" for m in mat)
            photos = frappe.db.sql(
                """SELECT COUNT(*) FROM `tabDaily Progress Photo` dpp
                   JOIN `tabDaily Progress Log` dpl ON dpl.name=dpp.parent
                   WHERE dpp.activity_task=%s AND dpl.log_date BETWEEN %s AND %s
                     AND IFNULL(dpp.image,'')<>''""", (t.name, from_date, to_date))[0][0] or 0
            rows.append({
                "section": s.section_name, "task": t.subject,
                "latest_pct": flt(t.progress), "latest_status": latest.status or "—",
                "days_worked": worked, "days_stopped": stopped,
                "person_days": round(person_days, 1), "material": material,
                "photos": photos, "narrative": narrative,
            })
    return COLUMNS, rows
