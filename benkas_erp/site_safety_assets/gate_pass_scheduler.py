import frappe
from frappe.utils import get_datetime, now_datetime


def flag_overdue_passes():
    """Scheduled: flip 'Out' gate passes to 'Overdue' once past expected return."""
    now = now_datetime()
    passes = frappe.get_all(
        "Gate Pass",
        filters={"pass_status": "Out"},
        fields=["name", "expected_return_time"],
    )
    for p in passes:
        if p.expected_return_time and get_datetime(p.expected_return_time) < now:
            frappe.db.set_value("Gate Pass", p.name, "pass_status", "Overdue")
    frappe.db.commit()
