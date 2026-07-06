"""System notifications for Benkas ERP (code-driven, idempotent)."""

import frappe


def _mk(name, doctype, event, role, subject, message, condition=None):
    if frappe.db.exists("Notification", name):
        return
    doc = frappe.get_doc({
        "doctype": "Notification",
        "name": name,
        "subject": subject,
        "document_type": doctype,
        "event": event,
        "channel": "System Notification",
        "is_standard": 0,
        "enabled": 1,
        "message": message,
        "recipients": [{"receiver_by_role": role}],
    })
    if condition:
        doc.condition = condition
    doc.insert(ignore_permissions=True)


def create_notifications():
    _mk("Benkas - Safety Violation Reported", "Safety Violation Log", "New",
        "Safety Officer",
        "Safety violation logged: {{ doc.violation_type }} at {{ doc.plant_section }}",
        "A new safety violation ({{ doc.violation_type }}) was recorded for "
        "{{ doc.person or 'unknown' }} at section {{ doc.plant_section }}.")

    _mk("Benkas - Safety Permit Awaiting Approval", "Safety Work Permit", "New",
        "Safety Officer",
        "Safety Work Permit {{ doc.name }} awaiting approval",
        "A {{ doc.permit_type }} permit was raised for {{ doc.plant_section }} "
        "and needs your approval.")

    _mk("Benkas - Electrical Permit Awaiting Approval", "Electrical Work Permit", "New",
        "Generator Electrical Operator",
        "Electrical Work Permit {{ doc.name }} awaiting approval",
        "An electrical work permit was raised for {{ doc.plant_section }} "
        "and needs LOTO confirmation & approval.")
