"""
Module Onboarding + Onboarding Steps for the 5 operational workspaces
(code-driven, idempotent). Each workspace references its onboarding via an
'onboarding' content block.
"""

import frappe

SM = "System Manager"

# onboarding_name -> {module, subtitle, success, roles, steps:[(title, action, target)]}
# action "Create Entry" -> target is a DocType; "Go to Page" -> target is a desk path
ONBOARDING = {
    "Benkas Manpower": {
        "module": "Manpower",
        "subtitle": "Track site manpower end to end",
        "success": "Great — you're ready to run daily manpower tracking!",
        "roles": ["Gate Security", "Section Incharge", "Benkas Project Manager"],
        "steps": [
            ("Add a Labour Master", "Create Entry", "Labour Master"),
            ("Log a Gate Entry at the gate", "Create Entry", "Gate Entry"),
            ("Acknowledge gate entries as Incharge", "Go to Page", "app/gate-entry"),
        ],
    },
    "Benkas Material": {
        "module": "Material",
        "subtitle": "Receive, inspect and issue material",
        "success": "Material flow is set up — GRNs, QC and stock will now roll up.",
        "roles": ["Gate Security", "Stores Weighbridge Operator", "Benkas Project Manager"],
        "steps": [
            ("Raise a Material Request", "Create Entry", "Material Request"),
            ("Create a Purchase Receipt (GRN)", "Create Entry", "Purchase Receipt"),
            ("Run a Quality Inspection", "Create Entry", "Quality Inspection"),
        ],
    },
    "Benkas Work Schedule": {
        "module": "Work Schedule",
        "subtitle": "Plan tasks and log daily progress",
        "success": "You're logging progress — section rollups will update on submit.",
        "roles": ["Section Incharge", "Benkas Project Manager"],
        "steps": [
            ("Check your section's Task list", "Go to Page", "app/task"),
            ("Submit your first Daily Progress Log", "Create Entry", "Daily Progress Log"),
        ],
    },
    "Benkas Site Safety": {
        "module": "Site Safety Assets",
        "subtitle": "Visitors, permits and safety",
        "success": "Site control is set up — visitors, permits and violations are tracked.",
        "roles": ["Section Incharge", "Safety Officer", "Generator Electrical Operator",
                  "Benkas Project Manager"],
        "steps": [
            ("Log a Visitor", "Create Entry", "Visitor Log"),
            ("Raise a Safety Work Permit", "Create Entry", "Safety Work Permit"),
            ("Log a Safety Violation (if any)", "Create Entry", "Safety Violation Log"),
        ],
    },
    "Benkas Core Setup": {
        "module": "Benkas Core",
        "subtitle": "Set up plant master data",
        "success": "Masters are in — daily operations can begin.",
        "roles": ["Benkas Project Manager"],
        "steps": [
            ("Add your Plant Sections", "Create Entry", "Plant Section"),
            ("Add Contractors", "Create Entry", "Contractor"),
            ("Add Labour", "Create Entry", "Labour Master"),
        ],
    },
}

# workspace name -> onboarding name
WORKSPACE_ONBOARDING = {
    "Manpower Manager": "Benkas Manpower",
    "Material and Purchase": "Benkas Material",
    "Work Schedule and Progress": "Benkas Work Schedule",
    "Site Safety and Assets": "Benkas Site Safety",
    "Benkas Core": "Benkas Core Setup",
}


def _step(title, action, target):
    step_name = f"Benkas - {title}"
    if frappe.db.exists("Onboarding Step", step_name):
        return step_name
    payload = {"doctype": "Onboarding Step", "name": step_name, "title": title,
               "action": action, "is_complete": 0, "show_full_form": 0}
    if action == "Create Entry":
        payload["reference_document"] = target
    elif action == "Go to Page":
        payload["path"] = target
    return frappe.get_doc(payload).insert(ignore_permissions=True).name


def create():
    for name, cfg in ONBOARDING.items():
        if frappe.db.exists("Module Onboarding", name):
            continue
        if not frappe.db.exists("Module Def", cfg["module"]):
            continue
        step_names = [_step(t, a, tgt) for (t, a, tgt) in cfg["steps"]]
        roles = [r for r in (cfg["roles"] + [SM]) if frappe.db.exists("Role", r)]
        frappe.get_doc({
            "doctype": "Module Onboarding", "name": name, "title": name,
            "module": cfg["module"], "subtitle": cfg["subtitle"],
            "success_message": cfg["success"],
            "allow_roles": [{"role": r} for r in roles],
            "steps": [{"step": s} for s in step_names],
        }).insert(ignore_permissions=True)
