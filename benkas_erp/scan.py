"""
Gate Scan Station — server side of the QR loop.

Standardised QR content:  <PREFIX>-<docname>
    LAB-LM-00001            Labour Master ID card
    EMP-HR-EMP-00001        Employee ID card
    GP-GP-2026-00012        Gate Pass slip
    VIS-VIS-2026-00034      Visitor slip

The scan station (desk page /app/benkas-scan) feeds the scanned string to
`scan()`, which identifies the record and decides the action. Everything is
server-side so a USB HID scanner, a tablet camera, or a raw REST POST all get
identical behaviour.
"""

import base64
import frappe
from frappe.utils import now_datetime, today

PREFIX_BY_DOCTYPE = {
    "Labour Master": "LAB",
    "Employee": "EMP",
    "Gate Pass": "GP",
    "Visitor Log": "VIS",
}
DOCTYPE_BY_PREFIX = {v: k for k, v in PREFIX_BY_DOCTYPE.items()}
PERSON_DOCTYPES = ("Labour Master", "Employee")


def qr_key(doctype, name):
    """The exact string encoded in this record's QR."""
    prefix = PREFIX_BY_DOCTYPE.get(doctype)
    return f"{prefix}-{name}" if prefix else name


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _err(msg, person=None):
    return {"ok": False, "action": "ERROR", "message": msg, "person": person or {}}


def _person_card(person_type, person):
    if not person:
        return {}
    if person_type == "Labour Master":
        d = frappe.db.get_value("Labour Master", person,
                                ["labour_name", "photo", "contractor", "category", "status"], as_dict=1)
        if not d:
            return {}
        return {"photo": d.photo, "name": d.labour_name, "sub": d.contractor or "",
                "meta": f"{d.category or ''} · {d.status}".strip(" ·"), "code": qr_key("Labour Master", person)}
    if person_type == "Employee":
        d = frappe.db.get_value("Employee", person,
                                ["employee_name", "image", "department", "designation"], as_dict=1)
        if not d:
            return {}
        return {"photo": d.image, "name": d.employee_name, "sub": d.department or "",
                "meta": d.designation or "Staff", "code": qr_key("Employee", person)}
    if person_type == "Contractor":
        d = frappe.db.get_value("Contractor", person, ["agency_name", "contact_person"], as_dict=1)
        return {"photo": None, "name": (d.agency_name if d else person),
                "sub": (d.contact_person if d else "") or "", "meta": "Contractor"}
    return {"photo": None, "name": person, "sub": "", "meta": person_type}


def _open_in_entry(person_type, person):
    """The person's Gate Entry that is In today and not yet closed (no time_out)."""
    return frappe.db.get_value("Gate Entry", {
        "person_type": person_type, "person": person, "entry_type": "In",
        "time_out": ["is", "not set"],
        "time_in": ["between", [today() + " 00:00:00", today() + " 23:59:59"]],
    }, "name")


def _last_section(person_type, person):
    ge = frappe.db.get_value("Gate Entry", {"person_type": person_type, "person": person},
                             "plant_section", order_by="creation desc")
    return ge or frappe.db.get_value("Plant Section", {"is_active": 1}, "name", order_by="creation asc")


def _save_photo(image_data, person):
    """Persist a base64 data-URL image as a File and return its URL."""
    from frappe.utils.file_manager import save_file
    if not image_data or "," not in image_data:
        return None
    content = base64.b64decode(image_data.split(",", 1)[1])
    fname = f"gate-{frappe.scrub(person)}-{frappe.utils.now().replace(' ', '_').replace(':', '')}.png"
    f = save_file(fname, content, "Gate Entry", "", decode=False, is_private=0)
    return f.file_url


# --------------------------------------------------------------------------
# main whitelisted entrypoints
# --------------------------------------------------------------------------
@frappe.whitelist()
def scan(code):
    code = (code or "").strip()
    if not code:
        return _err("Empty scan")
    prefix, _, name = code.partition("-")
    doctype = DOCTYPE_BY_PREFIX.get(prefix.upper())
    if not doctype:
        return _err(f"Unrecognised code: {code}")
    if not frappe.db.exists(doctype, name):
        return _err(f"{doctype} not found: {name}")

    if doctype in PERSON_DOCTYPES:
        return _scan_person(doctype, name)
    if doctype == "Gate Pass":
        return _scan_gate_pass(name)
    if doctype == "Visitor Log":
        return _scan_visitor(name)
    return _err("Unsupported code")


def _scan_person(doctype, name):
    if doctype == "Labour Master":
        status = frappe.db.get_value("Labour Master", name, "status")
        if status and status != "Active":
            return _err(f"{name} is {status} — ENTRY BLOCKED", person=_person_card(doctype, name))

    card = _person_card(doctype, name)
    open_in = _open_in_entry(doctype, name)
    if open_in:
        frappe.db.set_value("Gate Entry", open_in, "time_out", now_datetime())
        frappe.db.commit()
        return {"ok": True, "action": "OUT", "message": f"OUT recorded — {card.get('name')}",
                "person": card, "reference": open_in}

    return {"ok": True, "action": "IN", "message": f"{card.get('name')} — take photo & confirm IN",
            "person": card,
            "prefill": {"person_type": doctype, "person": name,
                        "plant_section": _last_section(doctype, name), "entry_type": "In"}}


def _scan_gate_pass(name):
    gp = frappe.db.get_value("Gate Pass", name, ["pass_status", "person_type", "person"], as_dict=1)
    card = _person_card(gp.person_type, gp.person)
    card.setdefault("meta", f"Gate Pass {name}")
    st = gp.pass_status
    if st == "Approved":
        frappe.db.set_value("Gate Pass", name, {"pass_status": "Out", "actual_out_time": now_datetime()})
        frappe.db.commit()
        return {"ok": True, "action": "GATE_PASS_OUT", "message": f"Gate Pass OUT — {card.get('name')}",
                "person": card, "reference": name}
    if st == "Out":
        frappe.db.set_value("Gate Pass", name, {"pass_status": "Returned", "actual_return_time": now_datetime()})
        frappe.db.commit()
        return {"ok": True, "action": "GATE_PASS_RETURN", "message": f"Returned — {card.get('name')}",
                "person": card, "reference": name}
    if st == "Returned":
        return _err("Gate pass already returned", person=card)
    return _err("PASS NOT APPROVED — send person back to their Incharge", person=card)


def _scan_visitor(name):
    d = frappe.db.get_value("Visitor Log", name, ["visitor_name", "company", "time_out", "photo"], as_dict=1)
    card = {"photo": d.photo, "name": d.visitor_name, "sub": d.company or "", "meta": "Visitor"}
    if not d.time_out:
        frappe.db.set_value("Visitor Log", name, "time_out", now_datetime())
        frappe.db.commit()
        return {"ok": True, "action": "VISITOR_OUT", "message": f"Visitor signed OUT — {d.visitor_name}",
                "person": card, "reference": name}
    return _err("Visitor already signed out", person=card)


@frappe.whitelist()
def create_gate_in(code, plant_section, image=None):
    """Called by the scan station after the guard captures the live photo on an
    IN scan — creates the Gate Entry with zero typing."""
    code = (code or "").strip()
    prefix, _, name = code.partition("-")
    doctype = DOCTYPE_BY_PREFIX.get(prefix.upper())
    if doctype not in PERSON_DOCTYPES:
        return _err("Not a person code")
    if not frappe.db.exists(doctype, name):
        return _err(f"{doctype} not found: {name}")
    if doctype == "Labour Master":
        status = frappe.db.get_value("Labour Master", name, "status")
        if status and status != "Active":
            return _err(f"{name} is {status} — ENTRY BLOCKED")
    if not plant_section:
        return _err("Plant Section required")

    photo_url = _save_photo(image, name) or "/assets/frappe/images/ui/avatar.png"
    doc = frappe.get_doc({
        "doctype": "Gate Entry", "person_type": doctype, "person": name,
        "plant_section": plant_section, "entry_type": "In",
        "time_in": now_datetime(), "photo": photo_url,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    card = _person_card(doctype, name)
    return {"ok": True, "action": "IN_DONE", "reference": doc.name, "person": card,
            "message": f"IN logged — {card.get('name')} @ {plant_section}"}


# --------------------------------------------------------------------------
# barcode field maintenance
# --------------------------------------------------------------------------
def set_person_barcode(doc, method=None):
    key = qr_key(doc.doctype, doc.name)
    if getattr(doc, "id_card_barcode", None) != key:
        doc.db_set("id_card_barcode", key, update_modified=False)


def set_gatepass_barcode(doc, method=None):
    key = qr_key("Gate Pass", doc.name)
    if doc.barcode != key:
        doc.db_set("barcode", key, update_modified=False)


def set_visitor_barcode(doc, method=None):
    key = qr_key("Visitor Log", doc.name)
    if doc.visitor_slip != key:
        doc.db_set("visitor_slip", key, update_modified=False)


def backfill_barcodes():
    """Set the standardised scan key on every existing card/slip (idempotent)."""
    mapping = [("Labour Master", "id_card_barcode"), ("Employee", "id_card_barcode"),
               ("Gate Pass", "barcode"), ("Visitor Log", "visitor_slip")]
    for dt, field in mapping:
        if not frappe.db.exists("DocType", dt):
            continue
        meta = frappe.get_meta(dt)
        if not meta.get_field(field):
            continue
        for name in frappe.get_all(dt, pluck="name"):
            key = qr_key(dt, name)
            if frappe.db.get_value(dt, name, field) != key:
                frappe.db.set_value(dt, name, field, key, update_modified=False)
    frappe.db.commit()
