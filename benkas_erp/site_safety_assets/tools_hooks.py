def set_status(doc, method=None):
    """Auto-flag contractor tools as In / Returned / Mismatch on save."""
    qty_in = doc.qty or 0
    qty_out = doc.qty_returned or 0
    if qty_out == 0:
        doc.status = "In"
    elif qty_out == qty_in and qty_in > 0:
        doc.status = "Returned"
    else:
        doc.status = "Mismatch"
