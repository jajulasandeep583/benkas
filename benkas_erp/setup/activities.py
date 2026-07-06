"""
Construction Activity master + per-section Work Breakdown Structure (WBS).

Each Plant Section's top Task is expanded into standard construction activity
sub-tasks (Civil, Erection, Piping, Electrical/Wiring, Testing, Commissioning...).
Tentative start/end dates are pre-filled from the section start date + cumulative
activity durations (the PM then adjusts in the Section Task Planner).

    bench --site <site> execute benkas_erp.setup.activities.setup_activities
"""

import frappe
from frappe.utils import add_days, getdate, today

# (activity_name, sequence, default_weight_%, default_duration_days)
DEFAULT_ACTIVITIES = [
    ("Civil & Foundation", 10, 12, 21),
    ("Structural / Erection", 20, 15, 21),
    ("Equipment Installation", 30, 18, 28),
    ("Piping & Fabrication", 40, 15, 21),
    ("Electrical & Wiring", 50, 12, 18),
    ("Instrumentation & Control", 60, 10, 14),
    ("Insulation & Painting", 70, 6, 10),
    ("Testing & Inspection", 80, 7, 10),
    ("Commissioning & Verification", 90, 5, 7),
]


def seed_activities():
    has_dur = bool(frappe.get_meta("Construction Activity").get_field("default_duration_days"))
    for name, seq, wt, dur in DEFAULT_ACTIVITIES:
        if not frappe.db.exists("Construction Activity", name):
            frappe.get_doc({
                "doctype": "Construction Activity", "activity_name": name,
                "sequence": seq, "default_weight": wt,
                "default_duration_days": dur if has_dur else None,
                "is_active": 1,
            }).insert(ignore_permissions=True)
        elif has_dur:
            # code is the source of truth for the standard durations/weights —
            # keep them in sync on every migrate (the generic field default of 7
            # otherwise masks the real per-activity durations)
            cur = frappe.db.get_value("Construction Activity", name,
                                      ["default_duration_days", "default_weight", "sequence"], as_dict=1)
            if cur.default_duration_days != dur or cur.default_weight != wt or cur.sequence != seq:
                frappe.db.set_value("Construction Activity", name,
                                    {"default_duration_days": dur, "default_weight": wt, "sequence": seq})
    frappe.db.commit()


def generate_section_tasks():
    """Create one sub-Task per active Construction Activity under each Plant
    Section's parent Task, with pre-filled tentative dates + weight. Idempotent."""
    fields = ["activity_name", "sequence", "default_weight"]
    if frappe.get_meta("Construction Activity").get_field("default_duration_days"):
        fields.append("default_duration_days")
    activities = frappe.get_all("Construction Activity", filters={"is_active": 1},
                                fields=fields, order_by="sequence asc")
    if not activities:
        return {"created": 0, "note": "no activities defined"}

    has_start = bool(frappe.get_meta("Plant Section").get_field("section_start_date"))
    created = 0
    sections = frappe.get_all("Plant Section",
                              fields=["name", "section_code", "project_task"]
                              + (["section_start_date"] if has_start else []))
    for sec in sections:
        parent_task = sec.project_task
        if not parent_task:
            continue
        project = frappe.db.get_value("Task", parent_task, "project")
        if not frappe.db.get_value("Task", parent_task, "is_group"):
            frappe.db.set_value("Task", parent_task, "is_group", 1)
        has_anchor = bool(sec.get("section_start_date"))
        cursor = getdate(sec.get("section_start_date")) if has_anchor else getdate(today())
        for act in activities:
            subject = f"{sec.section_code} - {act.activity_name}"
            dur = (act.get("default_duration_days") or 7)
            start = cursor
            end = add_days(start, max(dur - 1, 0))
            cursor = add_days(end, 1)
            existing = frappe.db.get_value("Task", {"subject": subject, "parent_task": parent_task},
                                           ["name", "exp_start_date"], as_dict=1)
            if existing:
                # backfill tentative dates onto a task created before a start
                # date existed (idempotent — only fills blanks, never overwrites)
                if has_anchor and not existing.exp_start_date:
                    frappe.db.set_value("Task", existing.name,
                                        {"exp_start_date": start, "exp_end_date": end})
                continue
            frappe.get_doc({
                "doctype": "Task", "subject": subject, "project": project,
                "parent_task": parent_task, "is_group": 0,
                "task_weight": (act.default_weight or 0) / 100.0,
                "exp_start_date": start, "exp_end_date": end,
            }).insert(ignore_permissions=True)
            created += 1
    frappe.db.commit()
    return {"created": created, "sections": len(sections), "activities": len(activities)}


def resync_task_dates():
    """One-off / dev maintenance: clear the auto-generated tentative dates on
    every section sub-task and re-fill them from the (now-correct) activity
    durations. Preserves progress. Use after changing activity durations."""
    seed_activities()
    parents = [s.project_task for s in frappe.get_all("Plant Section", fields=["project_task"])
               if s.project_task]
    if parents:
        frappe.db.sql(
            """UPDATE `tabTask` SET exp_start_date=NULL, exp_end_date=NULL
               WHERE parent_task IN %(p)s""", {"p": parents})
        frappe.db.commit()
    return generate_section_tasks()


def setup_activities():
    seed_activities()
    result = generate_section_tasks()
    print("Activities seeded; section sub-tasks:", result)
    return result
