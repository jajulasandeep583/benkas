"""
Staff attendance via HRMS: gate scans create Employee Checkins, and a default
auto-attendance Shift Type turns those checkins into HRMS Attendance records.
We do NOT hand-roll attendance — this drives HRMS's native Checkin->Attendance
pipeline. Labour (non-Employee) attendance stays derived from Gate Entry.
"""

import frappe
from frappe.utils import now_datetime, today, add_days

SHIFT = "Site General Shift"


def ensure_shift_type():
    """Default site shift with auto-attendance enabled."""
    if not frappe.db.exists("DocType", "Shift Type"):
        return
    if frappe.db.exists("Shift Type", SHIFT):
        # keep auto-attendance on and the process window open
        frappe.db.set_value("Shift Type", SHIFT, {
            "enable_auto_attendance": 1,
            "process_attendance_after": add_days(today(), -1),
        })
        return
    try:
        doc = frappe.get_doc({
            "doctype": "Shift Type",
            "name": SHIFT,
            "shift_type_name": SHIFT,
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "enable_auto_attendance": 1,
            "determine_check_in_and_check_out": "Alternating entries as IN and OUT during the same shift",
            "working_hours_calculation_based_on": "First Check-in and Last Check-out",
            "begin_check_in_before_shift_start_time": 120,
            "allow_check_out_after_shift_end_time": 120,
            "late_entry_grace_period": 15,
            "early_exit_grace_period": 15,
            "working_hours_threshold_for_half_day": 4,
            "working_hours_threshold_for_absent": 1,
            "process_attendance_after": add_days(today(), -1),
            "last_sync_of_checkin": now_datetime(),
        })
        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: Shift Type create failed")


def assign_default_shift(employee):
    """Give an Employee the site shift so their checkins mark attendance."""
    if frappe.db.exists("Shift Type", SHIFT) and frappe.db.exists("Employee", employee):
        if not frappe.db.get_value("Employee", employee, "default_shift"):
            frappe.db.set_value("Employee", employee, "default_shift", SHIFT)


def process_day():
    """Run HRMS auto-attendance so today's checkins become Attendance rows."""
    if not frappe.db.exists("Shift Type", SHIFT):
        return
    try:
        frappe.db.set_value("Shift Type", SHIFT, "last_sync_of_checkin", now_datetime())
        frappe.db.commit()
        shift = frappe.get_doc("Shift Type", SHIFT)
        shift.process_auto_attendance()
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: process_auto_attendance failed")

