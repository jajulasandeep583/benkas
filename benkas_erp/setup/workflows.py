"""Approval workflows for Benkas ERP (code-driven, idempotent)."""

import frappe

STATES = {
    "Pending": "Warning", "Confirmed": "Success", "Disputed": "Danger",
    "Requested": "Warning", "Approved": "Success", "Out": "Info",
    "Returned": "Success", "Overdue": "Danger",
    "Work in Progress": "Info", "Closed": "Success",
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
    if frappe.db.exists("Workflow", name):
        return
    doc = frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": name,
        "document_type": doctype,
        "is_active": 1,
        "override_status": 1,
        "workflow_state_field": state_field,
        "states": [
            {"state": s, "doc_status": "0", "allow_edit": role}
            for (s, role) in states
        ],
        "transitions": [
            {"state": frm, "action": act, "next_state": to,
             "allowed": role, "allow_self_approval": 1, "condition": cond or ""}
            for (frm, act, to, role, cond) in transitions
        ],
    })
    doc.insert(ignore_permissions=True)


def create_workflows():
    _ensure_states_and_actions()

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
