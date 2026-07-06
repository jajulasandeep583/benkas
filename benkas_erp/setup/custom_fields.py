"""Custom fields added to standard ERPNext DocTypes (code-driven, idempotent)."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _ccf

CUSTOM_FIELDS = {
    "Purchase Receipt": [
        {"fieldname": "benkas_site_sb", "label": "Benkas Site Details",
         "fieldtype": "Section Break", "insert_after": "company"},
        {"fieldname": "plant_section", "label": "Plant Section", "fieldtype": "Link",
         "options": "Plant Section", "insert_after": "benkas_site_sb"},
        {"fieldname": "weighbridge_slip_no", "label": "Weighbridge Slip No",
         "fieldtype": "Data", "insert_after": "plant_section"},
        {"fieldname": "benkas_weigh_cb", "fieldtype": "Column Break",
         "insert_after": "weighbridge_slip_no"},
        {"fieldname": "gross_weight", "label": "Gross Weight", "fieldtype": "Float",
         "insert_after": "benkas_weigh_cb"},
        {"fieldname": "tare_weight", "label": "Tare Weight", "fieldtype": "Float",
         "insert_after": "gross_weight"},
        {"fieldname": "net_weight", "label": "Net Weight", "fieldtype": "Float",
         "insert_after": "tare_weight"},
        {"fieldname": "weight_variance_flag", "label": "Weight Variance",
         "fieldtype": "Check", "read_only": 1, "insert_after": "net_weight"},
        {"fieldname": "supplier_invoice_photo", "label": "Supplier Invoice Photo",
         "fieldtype": "Attach Image", "reqd": 1, "insert_after": "weight_variance_flag"},
    ],
    "Stock Entry": [
        {"fieldname": "benkas_site_sb", "label": "Benkas Site Details",
         "fieldtype": "Section Break", "insert_after": "company"},
        {"fieldname": "plant_section", "label": "Plant Section", "fieldtype": "Link",
         "options": "Plant Section", "insert_after": "benkas_site_sb"},
        {"fieldname": "benkas_task", "label": "Task", "fieldtype": "Link",
         "options": "Task", "insert_after": "plant_section"},
    ],
    "Employee": [
        {"fieldname": "id_card_barcode", "label": "ID Card Barcode",
         "fieldtype": "Barcode", "insert_after": "employee_name"},
    ],
    "Quality Inspection": [
        {"fieldname": "inspection_photos", "label": "Inspection Photos",
         "fieldtype": "Table", "options": "Quality Inspection Photo",
         "insert_after": "readings"},
    ],
    "Task": [
        {"fieldname": "benkas_rollup_sb", "label": "Benkas Rollups",
         "fieldtype": "Section Break", "insert_after": "progress", "collapsible": 1},
        {"fieldname": "manpower_days_logged", "label": "Manpower Days Logged",
         "fieldtype": "Float", "read_only": 1, "insert_after": "benkas_rollup_sb"},
        {"fieldname": "material_consumed_value", "label": "Material Consumed Value",
         "fieldtype": "Currency", "read_only": 1, "insert_after": "manpower_days_logged"},
    ],
    "Plant Section": [
        {"fieldname": "section_percent_complete", "label": "Section % Complete",
         "fieldtype": "Percent", "read_only": 1, "insert_after": "is_active"},
    ],
}


def create():
    # Only add fields whose link/table targets already exist.
    payload = {}
    for dt, fields in CUSTOM_FIELDS.items():
        if not frappe.db.exists("DocType", dt):
            continue
        ok = []
        for f in fields:
            opt = f.get("options")
            if f.get("fieldtype") in ("Link", "Table") and opt and not frappe.db.exists("DocType", opt):
                continue
            ok.append(f)
        if ok:
            payload[dt] = ok
    if payload:
        _ccf(payload, ignore_validate=True)
