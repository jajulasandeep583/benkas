# Copyright (c) 2026, Benkas Engineering and contributors
# For license information, please see license.txt
"""Stoppage Analysis — stopped section-days across a week, grouped by reason and
by section/task. This is where "rain cost us 6 section-days this week" comes from.

Counts task rows whose status is flagged is_stopped, plus whole 'No Work Today'
logs. Script report so the optional section filter + date range default safely."""

import frappe
from frappe.utils import today, add_days

COLUMNS = [
    {"label": "Section", "fieldname": "section", "fieldtype": "Data", "width": 150},
    {"label": "Task", "fieldname": "task", "fieldtype": "Data", "width": 210},
    {"label": "Reason", "fieldname": "reason", "fieldtype": "Data", "width": 230},
    {"label": "Stopped Days", "fieldname": "days", "fieldtype": "Int", "width": 120},
    {"label": "Last Occurrence", "fieldname": "last_date", "fieldtype": "Date", "width": 130},
]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    to_date = filters.get("to_date") or today()
    from_date = filters.get("from_date") or add_days(to_date, -6)
    section = filters.get("section") or ""

    stopped = frappe.db.sql(
        """SELECT ps.section_name, t.subject, dtp.status,
                  COUNT(DISTINCT dpl.log_date) days, MAX(dpl.log_date) last_date
           FROM `tabDaily Task Progress` dtp
           JOIN `tabDaily Progress Log` dpl ON dpl.name=dtp.parent AND dpl.docstatus=1
           JOIN `tabProgress Status` pst ON pst.name=dtp.status AND pst.is_stopped=1
           JOIN `tabPlant Section` ps ON ps.name=dpl.plant_section
           LEFT JOIN `tabTask` t ON t.name=dtp.task
           WHERE dpl.log_date BETWEEN %(f)s AND %(t)s
             AND (%(s)s='' OR dpl.plant_section=%(s)s)
           GROUP BY ps.section_name, t.subject, dtp.status""",
        {"f": from_date, "t": to_date, "s": section}, as_dict=1)

    no_work = frappe.db.sql(
        """SELECT ps.section_name, COUNT(DISTINCT dpl.log_date) days, MAX(dpl.log_date) last_date
           FROM `tabDaily Progress Log` dpl
           JOIN `tabPlant Section` ps ON ps.name=dpl.plant_section
           WHERE dpl.no_work_today=1 AND dpl.docstatus=1 AND dpl.log_date BETWEEN %(f)s AND %(t)s
             AND (%(s)s='' OR dpl.plant_section=%(s)s)
           GROUP BY ps.section_name""",
        {"f": from_date, "t": to_date, "s": section}, as_dict=1)

    rows = [{"section": r.section_name, "task": r.subject or "—", "reason": r.status,
             "days": r.days, "last_date": r.last_date} for r in stopped]
    rows += [{"section": r.section_name, "task": "(whole section)", "reason": "No Work Today",
              "days": r.days, "last_date": r.last_date} for r in no_work]
    rows.sort(key=lambda r: r["days"], reverse=True)
    return COLUMNS, rows
