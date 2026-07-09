"""
Section 360 view + Section Task Planner — read-only aggregation over what
already exists (no new doctypes) plus write actions: set a task's %, mark a task
complete, bulk-save tentative task dates.

The task block is sourced from the manual EOD log: each task shows its current
% (editable inline by the PM), the latest status chip, the last work
description, and the photos tagged to that task.
"""

import frappe
from frappe.utils import getdate, today, add_days, flt


# --------------------------------------------------------------------------
# link query: task dropdowns on the Daily Progress Log are scoped to a section
# --------------------------------------------------------------------------
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def section_task_query(doctype, txt, searchfield, start, page_len, filters):
    section = (filters or {}).get("section")
    parent = frappe.db.get_value("Plant Section", section, "project_task") if section else None
    if not parent:
        return []
    like = f"%{txt}%"
    return frappe.db.sql(
        """SELECT name, subject FROM `tabTask`
           WHERE (parent_task = %(p)s OR name = %(p)s)
             AND (subject LIKE %(txt)s OR name LIKE %(txt)s)
           ORDER BY subject LIMIT %(start)s, %(len)s""",
        {"p": parent, "txt": like, "start": start, "len": page_len})


# --------------------------------------------------------------------------
def _task_status(progress, end_date):
    """Simple date/% derived label, still used by the Task Planner."""
    progress = flt(progress)
    if progress >= 100:
        return "Completed"
    if end_date and getdate(end_date) < getdate(today()):
        return "Delayed"
    if progress > 0:
        return "In Progress"
    return "Not Started"


def _status_meta(status):
    if not status:
        return "Grey", 0
    m = frappe.db.get_value("Progress Status", status, ["color", "is_stopped"], as_dict=1) or {}
    return (m.get("color") or "Grey"), int(m.get("is_stopped") or 0)


def _latest_progress(task):
    """Most recent submitted EOD row for a task."""
    row = frappe.db.sql(
        """SELECT dtp.status, dtp.work_description, dtp.percent_complete, dpl.log_date
           FROM `tabDaily Task Progress` dtp
           JOIN `tabDaily Progress Log` dpl ON dpl.name = dtp.parent
           WHERE dtp.task = %s AND dpl.docstatus = 1
           ORDER BY dpl.log_date DESC, dpl.creation DESC LIMIT 1""", task, as_dict=1)
    if not row:
        return {}
    r = row[0]
    color, stopped = _status_meta(r.status)
    return {"status": r.status, "color": color, "is_stopped": stopped,
            "description": r.work_description or "", "date": str(r.log_date)}


def _task_photos(section, task, limit=6):
    return [
        {"image": r[0], "caption": r[1], "date": str(r[2])}
        for r in frappe.db.sql(
            """SELECT dpp.image, dpp.caption, dpl.log_date
               FROM `tabDaily Progress Photo` dpp
               JOIN `tabDaily Progress Log` dpl ON dpl.name = dpp.parent
               WHERE dpp.activity_task = %s AND dpl.plant_section = %s AND dpl.docstatus = 1
                 AND IFNULL(dpp.image, '') <> ''
               ORDER BY dpl.log_date DESC LIMIT %s""", (task, section, limit))]


def _build_tasks(section, parent):
    tasks = frappe.get_all("Task", filters={"parent_task": parent},
                           fields=["name", "subject", "progress", "status",
                                   "exp_start_date", "exp_end_date"],
                           order_by="exp_start_date asc, subject asc") if parent else []
    for t in tasks:
        lp = _latest_progress(t.name)
        t["percent"] = flt(t.get("progress"))
        t["latest_status"] = lp.get("status") or "Not started"
        t["color"] = lp.get("color") or "Grey"
        t["is_stopped"] = lp.get("is_stopped") or 0
        t["last_description"] = lp.get("description") or ""
        t["last_date"] = lp.get("date")
        t["photos"] = _task_photos(section, t.name)
    return tasks


# --------------------------------------------------------------------------
@frappe.whitelist()
def get_section_360(section):
    if not frappe.db.exists("Plant Section", section):
        frappe.throw("Unknown section")
    ps = frappe.db.get_value("Plant Section", section,
                             ["section_name", "incharge", "project_task", "warehouse",
                              "section_percent_complete", "section_start_date"], as_dict=1)
    parent = ps.project_task

    tasks = _build_tasks(section, parent)
    actual = flt(ps.section_percent_complete)
    done = sum(1 for t in tasks if t["percent"] >= 100)
    stopped = sum(1 for t in tasks if t["is_stopped"])
    in_progress = sum(1 for t in tasks if 0 < t["percent"] < 100 and not t["is_stopped"])

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

    # ---- recent activity feed ----
    logs = frappe.get_all("Daily Progress Log", filters={"plant_section": section, "docstatus": 1},
                          fields=["name", "log_date", "no_work_today", "no_work_reason"],
                          order_by="log_date desc", limit=10)
    activity = []
    for lg in logs:
        row = frappe.db.get_value("Daily Task Progress", {"parent": lg.name},
                                  ["percent_complete", "work_description", "status"], as_dict=1) or {}
        photo = frappe.db.get_value("Daily Progress Photo", {"parent": lg.name}, "image")
        text = lg.no_work_reason if lg.no_work_today else (row.get("work_description") or "")
        activity.append({"name": lg.name, "date": str(lg.log_date),
                         "pct": None if lg.no_work_today else row.get("percent_complete"),
                         "status": "No work" if lg.no_work_today else (row.get("status") or ""),
                         "text": text, "photo": photo})
    visitors = frappe.db.count("Visitor Log", {"plant_section": section})
    open_violations = frappe.db.count("Safety Violation Log", {"plant_section": section, "status": "Open"})

    return {
        "header": {"section": section, "section_name": ps.section_name, "incharge": ps.incharge,
                   "percent_complete": actual, "status": "Attention" if stopped else "On Track",
                   "total_tasks": len(tasks), "done": done, "in_progress": in_progress,
                   "stopped": stopped,
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
def set_task_percent(task, percent):
    """Inline % edit from the Section 360 task checklist (PM)."""
    if not frappe.db.exists("Task", task):
        frappe.throw("Unknown task")
    pct = max(0, min(100, flt(percent)))
    vals = {"progress": pct}
    if pct >= 100:
        vals["status"] = "Completed"
    frappe.db.set_value("Task", task, vals)
    section = _rollup(task)
    frappe.db.commit()
    return {"ok": True, "task": task, "percent": pct, "section": section,
            "section_percent": frappe.db.get_value("Plant Section", section, "section_percent_complete") if section else None}


@frappe.whitelist()
def mark_task_complete(task):
    return set_task_percent(task, 100)


def _rollup(task):
    from benkas_erp.work_schedule.dpl_hooks import _recalc_section
    parent = frappe.db.get_value("Task", task, "parent_task")
    section = frappe.db.get_value("Plant Section", {"project_task": parent}, "name")
    if section:
        _recalc_section(section)
    return section


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
