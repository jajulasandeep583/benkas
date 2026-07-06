import frappe
from frappe import _


def validate(doc, method=None):
    # Mandatory gate photo (belt-and-braces beyond the field's reqd flag).
    if not doc.photo:
        frappe.throw(_("Gate Photo is mandatory for every gate entry."))

    # Block scanning an inactive / exited labour ID.
    if doc.person_type == "Labour Master" and doc.person:
        status = frappe.db.get_value("Labour Master", doc.person, "status")
        if status and status != "Active":
            frappe.throw(_("Labour {0} is {1} — gate entry blocked.").format(doc.person, status))

    # Auto-stamp the relevant time on scan when not manually entered.
    if doc.entry_type == "In" and not doc.time_in:
        doc.time_in = frappe.utils.now_datetime()
    if doc.entry_type == "Out" and not doc.time_out:
        doc.time_out = frappe.utils.now_datetime()


def notify_incharge(doc, method=None):
    """Alert the section Incharge that a gate entry awaits acknowledgement."""
    if not doc.plant_section:
        return
    incharge = frappe.db.get_value("Plant Section", doc.plant_section, "incharge")
    if not incharge:
        return
    try:
        frappe.get_doc({
            "doctype": "Notification Log",
            "for_user": incharge,
            "type": "Alert",
            "document_type": "Gate Entry",
            "document_name": doc.name,
            "subject": _("Gate Entry {0} at {1} awaits your acknowledgement").format(
                doc.name, doc.plant_section),
        }).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: gate entry notify failed")
