"""
Construction Activity master + per-section Work Breakdown Structure (WBS).

Each Plant Section's top Task is expanded into standard construction activity
sub-tasks (Civil, Erection, Piping, Electrical/Wiring, Installation, Testing,
Commissioning...). The activity list is a master the user can edit, then re-run
`generate_section_tasks` to (idempotently) create any missing sub-tasks.

    bench --site <site> execute benkas_erp.setup.activities.setup_activities
"""

import frappe

# (activity_name, sequence, default_weight_%)
DEFAULT_ACTIVITIES = [
    ("Civil & Foundation", 10, 12),
    ("Structural / Erection", 20, 15),
    ("Equipment Installation", 30, 18),
    ("Piping & Fabrication", 40, 15),
    ("Electrical & Wiring", 50, 12),
    ("Instrumentation & Control", 60, 10),
    ("Insulation & Painting", 70, 6),
    ("Testing & Inspection", 80, 7),
    ("Commissioning & Verification", 90, 5),
]


def seed_activities():
    for name, seq, wt in DEFAULT_ACTIVITIES:
        if not frappe.db.exists("Construction Activity", name):
            frappe.get_doc({
                "doctype": "Construction Activity", "activity_name": name,
                "sequence": seq, "default_weight": wt, "is_active": 1,
            }).insert(ignore_permissions=True)
    frappe.db.commit()


def generate_section_tasks():
    """Create one sub-Task per active Construction Activity under each Plant
    Section's parent Task. Idempotent (skips existing subject+parent pairs)."""
    activities = frappe.get_all("Construction Activity", filters={"is_active": 1},
                                fields=["activity_name", "sequence", "default_weight"],
                                order_by="sequence asc")
    if not activities:
        return {"created": 0, "note": "no activities defined"}

    created = 0
    sections = frappe.get_all("Plant Section",
                              fields=["name", "section_name", "section_code", "project_task"])
    for sec in sections:
        parent_task = sec.project_task
        if not parent_task:
            continue
        project = frappe.db.get_value("Task", parent_task, "project")
        # ensure the section's parent task is a group so it can hold children
        if not frappe.db.get_value("Task", parent_task, "is_group"):
            frappe.db.set_value("Task", parent_task, "is_group", 1)
        for act in activities:
            subject = f"{sec.section_code} - {act.activity_name}"
            if frappe.db.exists("Task", {"subject": subject, "parent_task": parent_task}):
                continue
            frappe.get_doc({
                "doctype": "Task", "subject": subject, "project": project,
                "parent_task": parent_task, "is_group": 0,
                "task_weight": (act.default_weight or 0) / 100.0,
            }).insert(ignore_permissions=True)
            created += 1
    frappe.db.commit()
    return {"created": created, "sections": len(sections), "activities": len(activities)}


def setup_activities():
    seed_activities()
    result = generate_section_tasks()
    print("Activities seeded; section sub-tasks:", result)
    return result
