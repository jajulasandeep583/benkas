"""
Section 360 view + Section Task Planner — read-only aggregation over what
already exists (no new doctypes) plus two write actions: mark a task complete
and bulk-save tentative task dates.
"""

import frappe
from frappe.utils import getdate, today, add_days, flt


# --------------------------------------------------------------------------
def _task_status(progress, end_date):
    progress = flt(progress)
    if progress >= 100:
        return "Completed"
    if end_date and getdate(end_date) < getdate(today()):
        return "Delayed"
    if progress > 0:
        return "In Progress"
    return "Not Started"


def _planned_pct(tasks):
    """Weighted planned % for the section: each task's planned progress from
    where 'today' falls between its start and end dates."""
    tw = sum(flt(t.get("task_weight")) for t in tasks) or 0
    if not tw:
        done = sum(1 for t in tasks if _task_status(t.get("progress"), t.get("exp_end_date")) == "Completed")
        return round(100 * done / len(tasks), 1) if tasks else 0
    acc = 0.0
    td = getdate(today())
    for t in tasks:
        w = flt(t.get("task_weight"))
        s, e = t.get("exp_start_date"), t.get("exp_end_date")
        if not s or not e:
            p = 0
        elif td >= getdate(e):
            p = 100
        elif td <= getdate(s):
            p = 0
        else:
            span = (getdate(e) - getdate(s)).days or 1
            p = 100 * (td - getdate(s)).days / span
        acc += w * p
    return round(acc / tw, 1)


# --------------------------------------------------------------------------
@frappe.whitelist()
def get_section_360(section):
    if not frappe.db.exists("Plant Section", section):
        frappe.throw("Unknown section")
    ps = frappe.db.get_value("Plant Section", section,
                             ["section_name", "incharge", "project_task", "warehouse",
                              "section_percent_complete", "section_start_date"], as_dict=1)
    parent = ps.project_task

    tasks = frappe.get_all("Task", filters={"parent_task": parent},
                           fields=["name", "subject", "exp_start_date", "exp_end_date",
                                   "progress", "task_weight", "status"],
                           order_by="exp_start_date asc, subject asc") if parent else []
    for t in tasks:
        t["chip"] = _task_status(t.get("progress"), t.get("exp_end_date"))
    planned = _planned_pct(tasks)
    actual = flt(ps.section_percent_complete)
    delayed = any(t["chip"] == "Delayed" for t in tasks) or (actual < planned - 5)
    days = abs(int(round((actual - planned) / 100 * 30)))  # rough days ahead/behind

    # ---- manpower ----
    today_headcount = frappe.db.sql(
        """SELECT COUNT(DISTINCT person) FROM `tabGate Entry`
           WHERE plant_section=%s AND entry_type='In' AND DATE(time_in)=%s""",
        (section, today()))[0][0] or 0
    pd_week = frappe.db.sql(
        """SELECT COALESCE(SUM(dwl.hours),0)/8 FROM `tabDaily Worker Log` dwl
           JOIN `tabDaily Progress Log` dpl ON dpl.name=dwl.parent
           WHERE dpl.plant_section=%s AND dpl.log_date >= %s""",
        (section, add_days(today(), -6)))[0][0] or 0
    pd_total = frappe.db.sql(
        """SELECT COALESCE(SUM(dwl.hours),0)/8 FROM `tabDaily Worker Log` dwl
           JOIN `tabDaily Progress Log` dpl ON dpl.name=dwl.parent
           WHERE dpl.plant_section=%s""", (section,))[0][0] or 0
    by_category = frappe.db.sql(
        """SELECT dwl.person_type, ROUND(SUM(dwl.hours)/8,1) FROM `tabDaily Worker Log` dwl
           JOIN `tabDaily Progress Log` dpl ON dpl.name=dwl.parent
           WHERE dpl.plant_section=%s GROUP BY dwl.person_type""", (section,))
    by_contractor = frappe.db.sql(
        """SELECT COALESCE(lm.contractor, dwl.person_type), ROUND(SUM(dwl.hours)/8,1)
           FROM `tabDaily Worker Log` dwl
           JOIN `tabDaily Progress Log` dpl ON dpl.name=dwl.parent
           LEFT JOIN `tabLabour Master` lm ON lm.name=dwl.person
           WHERE dpl.plant_section=%s GROUP BY COALESCE(lm.contractor, dwl.person_type)""", (section,))
    recent_workers = frappe.db.sql(
        """SELECT DISTINCT ge.person, ge.person_type, DATE(ge.time_in)
           FROM `tabGate Entry` ge WHERE ge.plant_section=%s AND ge.entry_type='In'
           ORDER BY ge.time_in DESC LIMIT 10""", (section,))

    # ---- material ----
    top_items = frappe.db.sql(
        """SELECT sed.item_code, ROUND(SUM(sed.qty),2), ROUND(SUM(sed.amount),2)
           FROM `tabStock Entry Detail` sed JOIN `tabStock Entry` se ON se.name=sed.parent
           WHERE se.plant_section=%s AND se.purpose='Material Issue' AND se.docstatus=1
           GROUP BY sed.item_code ORDER BY SUM(sed.amount) DESC LIMIT 10""", (section,))
    mat_value = sum((r[2] or 0) for r in top_items)
    open_mrs = frappe.get_all("Material Request",
                              filters={"plant_section": section, "docstatus": ["<", 2],
                                       "benkas_status": ["not in", ["Issued", "Closed"]]},
                              fields=["name", "benkas_status", "transaction_date"], limit=10) \
        if frappe.get_meta("Material Request").get_field("benkas_status") else []
    last_issues = frappe.db.sql(
        """SELECT se.name, se.posting_date FROM `tabStock Entry` se
           WHERE se.plant_section=%s AND se.purpose='Material Issue' AND se.docstatus=1
           ORDER BY se.posting_date DESC, se.creation DESC LIMIT 5""", (section,))

    # ---- activity ----
    logs = frappe.get_all("Daily Progress Log", filters={"plant_section": section, "docstatus": 1},
                          fields=["name", "log_date"], order_by="log_date desc", limit=10)
    activity = []
    for lg in logs:
        row = frappe.db.get_value("Daily Task Progress", {"parent": lg.name},
                                  ["percent_complete", "activity_description"], as_dict=1) or {}
        photo = frappe.db.get_value("Daily Progress Photo", {"parent": lg.name}, "image")
        activity.append({"name": lg.name, "date": str(lg.log_date),
                         "pct": row.get("percent_complete"), "text": row.get("activity_description") or "",
                         "photo": photo})
    visitors = frappe.db.count("Visitor Log", {"plant_section": section})
    open_violations = frappe.db.count("Safety Violation Log", {"plant_section": section, "status": "Open"})

    return {
        "header": {"section": section, "section_name": ps.section_name, "incharge": ps.incharge,
                   "percent_complete": actual, "planned": planned,
                   "status": "Delayed" if delayed else "On Track", "days": days,
                   "start_date": str(ps.section_start_date) if ps.section_start_date else None},
        "tasks": tasks,
        "manpower": {"today": today_headcount, "person_days_week": round(pd_week, 1),
                     "person_days_total": round(pd_total, 1),
                     "by_category": [{"k": r[0], "v": r[1]} for r in by_category],
                     "by_contractor": [{"k": r[0], "v": r[1]} for r in by_contractor],
                     "recent": [{"person": r[0], "type": r[1], "date": str(r[2])} for r in recent_workers]},
        "material": {"total_value": round(mat_value, 2),
                     "top_items": [{"item": r[0], "qty": r[1], "value": r[2]} for r in top_items],
                     "open_requests": open_mrs,
                     "last_issues": [{"name": r[0], "date": str(r[1])} for r in last_issues]},
        "activity": {"logs": activity, "visitors": visitors, "open_violations": open_violations},
    }


@frappe.whitelist()
def mark_task_complete(task):
    if not frappe.db.exists("Task", task):
        frappe.throw("Unknown task")
    frappe.db.set_value("Task", task, {"progress": 100, "status": "Completed"})
    # roll the section % up, same as a Daily Progress Log submit would
    from benkas_erp.work_schedule.dpl_hooks import _recalc_section
    parent = frappe.db.get_value("Task", task, "parent_task")
    section = frappe.db.get_value("Plant Section", {"project_task": parent}, "name")
    if section:
        _recalc_section(section)
    frappe.db.commit()
    return {"ok": True, "task": task, "section": section,
            "section_percent": frappe.db.get_value("Plant Section", section, "section_percent_complete") if section else None}


# --------------------------------------------------------------------------
# Section Task Planner
# --------------------------------------------------------------------------
@frappe.whitelist()
def get_section_tasks(section):
    parent = frappe.db.get_value("Plant Section", section, "project_task")
    if not parent:
        return {"tasks": [], "section_start_date": None}
    tasks = frappe.get_all("Task", filters={"parent_task": parent},
                           fields=["name", "subject", "exp_start_date", "exp_end_date",
                                   "task_weight", "progress", "status"],
                           order_by="exp_start_date asc, subject asc")
    for t in tasks:
        t["chip"] = _task_status(t.get("progress"), t.get("exp_end_date"))
    return {"tasks": tasks,
            "section_start_date": frappe.db.get_value("Plant Section", section, "section_start_date")}


@frappe.whitelist()
def save_section_tasks(section, rows, section_start_date=None):
    import json
    rows = json.loads(rows) if isinstance(rows, str) else rows
    if section_start_date and frappe.get_meta("Plant Section").get_field("section_start_date"):
        frappe.db.set_value("Plant Section", section, "section_start_date", section_start_date)
    n = 0
    for r in rows:
        if not r.get("name") or not frappe.db.exists("Task", r["name"]):
            continue
        vals = {}
        if "exp_start_date" in r:
            vals["exp_start_date"] = r.get("exp_start_date") or None
        if "exp_end_date" in r:
            vals["exp_end_date"] = r.get("exp_end_date") or None
        if r.get("task_weight") is not None:
            vals["task_weight"] = flt(r.get("task_weight"))
        if vals:
            frappe.db.set_value("Task", r["name"], vals)
            n += 1
    frappe.db.commit()
    return {"ok": True, "updated": n}
