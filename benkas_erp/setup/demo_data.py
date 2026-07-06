"""
Dummy / UAT test data for Benkas ERP. Safe to re-run (guarded by markers).

    bench --site <site> execute benkas_erp.setup.demo_data.run
"""

import frappe
from frappe.utils import today, add_days, now_datetime, add_to_date

PLACEHOLDER_IMG = "/assets/frappe/images/ui/avatar.png"


def _company():
    return frappe.defaults.get_defaults().get("company") or \
        frappe.db.get_value("Company", {}, "name")


def _employee(first_name, emp_type):
    existing = frappe.db.get_value("Employee", {"employee_name": first_name}, "name")
    if existing:
        return existing
    if not frappe.db.exists("Employment Type", emp_type):
        frappe.get_doc({"doctype": "Employment Type", "employee_type_name": emp_type}).insert(ignore_permissions=True)
    doc = frappe.get_doc({
        "doctype": "Employee", "first_name": first_name, "gender": "Male",
        "date_of_birth": "1990-01-01", "date_of_joining": add_days(today(), -120),
        "company": _company(), "status": "Active", "employment_type": emp_type,
    }).insert(ignore_permissions=True)
    return doc.name


def _contractor(name, lic):
    if frappe.db.exists("Contractor", name):
        return name
    return frappe.get_doc({
        "doctype": "Contractor", "agency_name": name, "registration_no": "REG-" + lic,
        "labour_license_no": lic, "contact_person": "Site Manager", "phone": "98765" + lic[-5:],
        "agreement_valid_upto": add_days(today(), 300),
    }).insert(ignore_permissions=True).name


def _labour(name, contractor, category):
    existing = frappe.db.get_value("Labour Master", {"labour_name": name}, "name")
    if existing:
        return existing
    return frappe.get_doc({
        "doctype": "Labour Master", "labour_name": name, "contractor": contractor,
        "category": category, "status": "Active", "id_proof_type": "Aadhaar",
        "id_proof_no": "XXXX-" + name[-4:].rjust(4, "0"),
    }).insert(ignore_permissions=True).name


def _gate_entry(ptype, person, section, minutes_ago, work):
    doc = frappe.get_doc({
        "doctype": "Gate Entry", "person_type": ptype, "person": person,
        "plant_section": section, "entry_type": "In",
        "time_in": add_to_date(now_datetime(), minutes=-minutes_ago),
        "work_description": work, "photo": PLACEHOLDER_IMG,
        "ppe_checklist": [{"ppe_item": "Helmet", "is_available": 1},
                          {"ppe_item": "Safety Shoes", "is_available": 1}],
    }).insert(ignore_permissions=True)
    return doc.name


def run():
    made = {}
    company = _company()

    # set two section incharges to Administrator so notifications have a target
    for code in ("DIST", "FERM"):
        if frappe.db.exists("Plant Section", code):
            frappe.db.set_value("Plant Section", code, "incharge", "Administrator")

    # masters
    e1 = _employee("Ravi Kumar", "Ramshy Bio Staff")
    e2 = _employee("Suresh Rao", "Benkas Staff")
    c1 = _contractor("Sri Sai Constructions", "LIC10021")
    c2 = _contractor("Balaji Engineering Works", "LIC10022")
    l1 = _labour("Mohan Das", c1, "Skilled")
    l2 = _labour("Iqbal Shaikh", c1, "Unskilled")
    l3 = _labour("Ganesh Patil", c2, "Semi-skilled")
    made["employees"] = [e1, e2]
    made["contractors"] = [c1, c2]
    made["labour"] = [l1, l2, l3]
    frappe.db.commit()

    # gate entries (only if none yet)
    if not frappe.db.count("Gate Entry"):
        ge = [
            _gate_entry("Employee", e1, "DIST", 300, "Erection - Distillation column"),
            _gate_entry("Employee", e2, "FERM", 280, "Supervision - Fermenter piping"),
            _gate_entry("Labour Master", l1, "DIST", 260, "Welding support"),
            _gate_entry("Labour Master", l2, "DIST", 250, "Material shifting"),
            _gate_entry("Contractor", c1, "FERM", 240, "Site inspection"),
        ]
        made["gate_entries"] = ge
    frappe.db.commit()

    # generator + logs
    if not frappe.db.exists("Generator Master", "DG-01"):
        frappe.get_doc({"doctype": "Generator Master", "generator_id": "DG-01",
                        "capacity": "500 kVA", "plant_section": "PP"}).insert(ignore_permissions=True)
    if not frappe.db.count("Generator Log"):
        for d, filled, oh, ch in [(-1, 200, 1000, 1008), (0, 150, 1008, 1014)]:
            frappe.get_doc({
                "doctype": "Generator Log", "generator": "DG-01", "log_date": add_days(today(), d),
                "shift": "Day", "opening_meter": oh, "closing_meter": ch,
                "diesel_filled": filled, "diesel_balance": 500 - filled,
            }).insert(ignore_permissions=True)

    # power consumption
    if not frappe.db.count("Power Consumption Log"):
        frappe.get_doc({"doctype": "Power Consumption Log", "log_date": today(), "shift": "Day",
                        "plant_section": "DIST", "r_phase": 210, "y_phase": 205, "b_phase": 208,
                        "voltage": 415, "reading_by": "Administrator"}).insert(ignore_permissions=True)

    # vehicle + logs
    if not frappe.db.exists("Site Vehicle", "AP16TT1234"):
        frappe.get_doc({"doctype": "Site Vehicle", "vehicle_no": "AP16TT1234",
                        "vehicle_type": "Forklift", "owner_type": "Company",
                        "assigned_driver": "Ramesh"}).insert(ignore_permissions=True)
    if not frappe.db.count("Site Vehicle Log"):
        for d, s, e in [(-1, 4500, 4520), (0, 4520, 4535)]:
            frappe.get_doc({
                "doctype": "Site Vehicle Log", "vehicle": "AP16TT1234", "driver": "Ramesh",
                "plant_section": "DIST", "purpose": "Material movement",
                "time_out": add_to_date(now_datetime(), hours=-4),
                "time_in": add_to_date(now_datetime(), hours=-1),
                "odometer_start": s, "odometer_end": e}).insert(ignore_permissions=True)

    # daily progress logs (rollups auto-fetch)
    if not frappe.db.count("Daily Progress Log"):
        for code, pct in [("DIST", 35), ("FERM", 50)]:
            task = frappe.db.get_value("Plant Section", code, "project_task")
            frappe.get_doc({
                "doctype": "Daily Progress Log", "task": task, "plant_section": code,
                "log_date": today(), "percent_complete": pct,
                "activity_description": f"Progress update for {code}",
                "photos": [{"image": PLACEHOLDER_IMG, "caption": "Site view"}],
            }).insert(ignore_permissions=True)

    # safety violation
    if not frappe.db.count("Safety Violation Log"):
        frappe.get_doc({"doctype": "Safety Violation Log", "violation_type": "No Helmet",
                        "person_type": "Labour Master", "person": l2, "plant_section": "DIST",
                        "violation_datetime": now_datetime(), "photo": PLACEHOLDER_IMG,
                        "corrective_action": "Helmet issued, warning given",
                        "status": "Open"}).insert(ignore_permissions=True)

    # visitor
    if not frappe.db.count("Visitor Log"):
        frappe.get_doc({"doctype": "Visitor Log", "visitor_name": "Anil Mehta",
                        "company": "Pump Suppliers Ltd", "purpose": "Pump demo",
                        "plant_section": "FERM", "host_person": "Administrator",
                        "time_in": now_datetime(), "photo": PLACEHOLDER_IMG}).insert(ignore_permissions=True)

    # gate pass
    if not frappe.db.count("Gate Pass"):
        frappe.get_doc({"doctype": "Gate Pass", "person_type": "Employee", "person": e1,
                        "plant_section": "DIST", "reason": "Material pickup from town",
                        "destination": "Hardware market",
                        "expected_out_time": now_datetime(),
                        "expected_return_time": add_to_date(now_datetime(), hours=3)}).insert(ignore_permissions=True)

    # contractor tools
    if not frappe.db.count("Contractor Tools Register"):
        frappe.get_doc({"doctype": "Contractor Tools Register", "contractor": c1,
                        "tool_description": "Welding machine + cables", "qty": 2,
                        "qty_returned": 0, "photo": PLACEHOLDER_IMG}).insert(ignore_permissions=True)

    # safety work permit
    if not frappe.db.count("Safety Work Permit"):
        frappe.get_doc({"doctype": "Safety Work Permit", "permit_type": "Hot Work",
                        "plant_section": "DIST", "work_description": "Welding of column supports",
                        "workers_involved": [{"worker_name": "Mohan Das", "worker_role": "Welder"}],
                        "valid_from": now_datetime(), "valid_to": add_to_date(now_datetime(), hours=8),
                        "issuing_incharge": "Administrator", "approving_incharge": "Administrator",
                        "site_photo": PLACEHOLDER_IMG, "ppe_photo": PLACEHOLDER_IMG}).insert(ignore_permissions=True)

    # electrical work permit
    if not frappe.db.count("Electrical Work Permit"):
        frappe.get_doc({"doctype": "Electrical Work Permit",
                        "job_description": "MCC panel maintenance", "plant_section": "PP",
                        "equipment": "MCC-01", "loto_confirmed": 1,
                        "issuing_engineer": "Administrator", "receiving_engineer": "Administrator",
                        "valid_from": now_datetime(), "valid_to": add_to_date(now_datetime(), hours=4),
                        "job_log": [{"start_time": now_datetime(),
                                     "handover_notes": "Isolation done"}]}).insert(ignore_permissions=True)

    frappe.db.commit()

    counts = {dt: frappe.db.count(dt) for dt in [
        "Employee", "Contractor", "Labour Master", "Gate Entry", "Daily Progress Log",
        "Generator Log", "Power Consumption Log", "Site Vehicle Log", "Safety Violation Log",
        "Visitor Log", "Gate Pass", "Contractor Tools Register", "Safety Work Permit",
        "Electrical Work Permit"]}
    print("DEMO DATA COUNTS:", counts)
    return counts
