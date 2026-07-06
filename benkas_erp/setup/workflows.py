"""Approval workflows for Benkas ERP (code-driven, idempotent)."""

import frappe

# ---------------------------------------------------------------------------
# BEFORE GO-LIVE: set WORKFLOWS_ACTIVE = True and `bench --site <site> migrate`
# to re-enable all approval workflows. They are OFF during build-out because
# roles/users aren't finalised and active workflows block basic operations.
# The status fields (acknowledgement_status, pass_status, permit_status,
# benkas_status) remain on the doctypes as ordinary editable selects.
# ---------------------------------------------------------------------------
WORKFLOWS_ACTIVE = False

STATES = {
    "Pending": "Warning", "Confirmed": "Success", "Disputed": "Danger",
    "Requested": "Warning", "Approved": "Success", "Out": "Info",
    "Returned": "Success", "Overdue": "Danger",
    "Work in Progress": "Info", "Closed": "Success",
    "Partially Issued": "Info", "Issued": "Success",
}

ACTIONS = ["Confirm", "Dispute", "Approve", "Mark Out", "Mark Returned",
           "Start Work", "Close"]


def _ensure_states_and_actions():
    for state, style in STATES.items():
        if not frappe.db.exists("Workflow State", state):
            frappe.get_doc({"doctype": "Workflow State",
                            "workflow_state_name": state, "style": style}).insert(ignore_permissions=True)
    for action in ACTIONS:
        if not frappe.db.exists("Workflow Action Master", action):
            frappe.get_doc({"doctype": "Workflow Action Master",
                            "workflow_action_name": action}).insert(ignore_permissions=True)


def _mk(name, doctype, state_field, states, transitions):
    active = 1 if WORKFLOWS_ACTIVE else 0
    if frappe.db.exists("Workflow", name):
        # keep the active flag in sync with WORKFLOWS_ACTIVE on every migrate
        if frappe.db.get_value("Workflow", name, "is_active") != active:
            frappe.db.set_value("Workflow", name, "is_active", active)
        return
    doc = frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": name,
        "document_type": doctype,
        "is_active": active,
        "override_status": 1,
        "workflow_state_field": state_field,
        "states": [
            {"state": st[0], "doc_status": (st[2] if len(st) > 2 else "0"), "allow_edit": st[1]}
            for st in states
        ],
        "transitions": [
            {"state": frm, "action": act, "next_state": to,
             "allowed": role, "allow_self_approval": 1, "condition": cond or ""}
            for (frm, act, to, role, cond) in transitions
        ],
    })
    doc.insert(ignore_permissions=True)


# Status fields the workflows drive — when workflows are OFF these must be
# ordinary editable selects so people can set them by hand.
STATUS_FIELDS = [
    ("Gate Entry", "acknowledgement_status"),
    ("Gate Pass", "pass_status"),
    ("Safety Work Permit", "permit_status"),
    ("Electrical Work Permit", "permit_status"),
    ("Material Request", "benkas_status"),
]


def _sync_status_field_editability():
    from frappe.custom.doctype.property_setter.property_setter import make_property_setter
    read_only = 1 if WORKFLOWS_ACTIVE else 0
    for dt, field in STATUS_FIELDS:
        if frappe.db.exists("DocType", dt) and frappe.get_meta(dt).get_field(field):
            make_property_setter(dt, field, "read_only", read_only, "Check",
                                 validate_fields_for_doctype=False)


def create_workflows():
    _ensure_states_and_actions()
    _sync_status_field_editability()

    _mk("Gate Entry Acknowledgement", "Gate Entry", "acknowledgement_status",
        states=[("Pending", "Section Incharge"), ("Confirmed", "Section Incharge"),
                ("Disputed", "Section Incharge")],
        transitions=[
            ("Pending", "Confirm", "Confirmed", "Section Incharge", None),
            ("Pending", "Dispute", "Disputed", "Section Incharge", None),
        ])

    _mk("Gate Pass Approval", "Gate Pass", "pass_status",
        states=[("Requested", "Section Incharge"), ("Approved", "Gate Security"),
                ("Out", "Gate Security"), ("Returned", "Gate Security"),
                ("Overdue", "Gate Security")],
        transitions=[
            ("Requested", "Approve", "Approved", "Section Incharge", None),
            ("Approved", "Mark Out", "Out", "Gate Security", None),
            ("Out", "Mark Returned", "Returned", "Gate Security", None),
        ])

    _mk("Safety Work Permit Approval", "Safety Work Permit", "permit_status",
        states=[("Requested", "Safety Officer"), ("Approved", "Safety Officer"),
                ("Work in Progress", "Safety Officer"), ("Closed", "Safety Officer")],
        transitions=[
            ("Requested", "Approve", "Approved", "Safety Officer", None),
            ("Approved", "Start Work", "Work in Progress", "Safety Officer", None),
            ("Work in Progress", "Close", "Closed", "Safety Officer",
             "doc.closing_confirmation"),
        ])

    _mk("Electrical Work Permit Approval", "Electrical Work Permit", "permit_status",
        states=[("Requested", "Generator Electrical Operator"),
                ("Approved", "Generator Electrical Operator"),
                ("Work in Progress", "Generator Electrical Operator"),
                ("Closed", "Generator Electrical Operator")],
        transitions=[
            ("Requested", "Approve", "Approved", "Generator Electrical Operator",
             "doc.loto_confirmed"),
            ("Approved", "Start Work", "Work in Progress", "Generator Electrical Operator", None),
            ("Work in Progress", "Close", "Closed", "Generator Electrical Operator",
             "doc.closure_signoff"),
        ])

    # Material Request: Requested (draft) -> Approve = submit -> Partially Issued /
    # Issued are set by the site-log issue hook (not manual) -> Close (PM, when Issued).
    # doc_status per state keeps benkas_status independent yet consistent with docstatus.
    if frappe.get_meta("Material Request").get_field("benkas_status"):
        _mk("Material Request Approval", "Material Request", "benkas_status",
            states=[("Requested", "Section Incharge", "0"),
                    ("Approved", "Benkas Project Manager", "1"),
                    ("Partially Issued", "Benkas Project Manager", "1"),
                    ("Issued", "Benkas Project Manager", "1"),
                    ("Closed", "Benkas Project Manager", "1")],
            transitions=[
                ("Requested", "Approve", "Approved", "Section Incharge", None),
                ("Issued", "Close", "Closed", "Benkas Project Manager", None),
            ])
