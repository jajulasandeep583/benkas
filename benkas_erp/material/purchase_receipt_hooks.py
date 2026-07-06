import frappe
from frappe import _


def validate(doc, method=None):
    # Mandatory supplier invoice photo before the GRN can proceed.
    if hasattr(doc, "supplier_invoice_photo") and not doc.supplier_invoice_photo:
        frappe.throw(_("Supplier Invoice Photo is mandatory before this GRN can proceed."))

    # Derive net weight if only gross/tare captured.
    gross = getattr(doc, "gross_weight", 0) or 0
    tare = getattr(doc, "tare_weight", 0) or 0
    if gross and tare and not getattr(doc, "net_weight", 0):
        doc.net_weight = gross - tare

    # Flag a weighbridge vs PO/GRN quantity mismatch for the incharge.
    net = getattr(doc, "net_weight", 0) or 0
    total_qty = getattr(doc, "total_qty", 0) or 0
    if hasattr(doc, "weight_variance_flag"):
        doc.weight_variance_flag = 1 if (net and total_qty and abs(net - total_qty) > 0.5) else 0
