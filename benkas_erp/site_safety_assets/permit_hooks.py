import frappe
from frappe import _


def validate_safety_permit(doc, method=None):
    if doc.permit_status == "Closed" and not doc.closing_confirmation:
        frappe.throw(_("Closing Confirmation by the Incharge is required before closing this permit."))


def validate_electrical_permit(doc, method=None):
    if doc.permit_status in ("Approved", "Work in Progress", "Closed") and not doc.loto_confirmed:
        frappe.throw(_("LOTO (Lock-Out/Tag-Out) must be confirmed before this permit is approved."))
    if doc.permit_status == "Closed" and not doc.closure_signoff:
        frappe.throw(_("Closure sign-off (equipment safely re-energized) is required before closing."))
