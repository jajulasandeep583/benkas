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
    # pin firmly to TODAY (a "minutes ago" offset can cross midnight to yesterday,
    # which then fails the daily worker-gate-entry check in the site log)
    from frappe.utils import get_datetime
    time_in = add_to_date(get_datetime(today() + " 08:00:00"), minutes=minutes_ago % 240)
    doc = frappe.get_doc({
        "doctype": "Gate Entry", "person_type": ptype, "person": person,
        "plant_section": section, "entry_type": "In",
        "time_in": time_in,
        "work_description": work, "photo": PLACEHOLDER_IMG,
        "ppe_checklist": [{"ppe_item": "Helmet", "is_available": 1},
                          {"ppe_item": "Safety Shoes", "is_available": 1}],
    }).insert(ignore_permissions=True)
    return doc.name


def reset():
    """Cancel + delete transactional demo data so it can be regenerated cleanly
    against the current schema (used when doctype fields/workflows change)."""
    for dt in ["Daily Progress Log", "Stock Entry", "Material Request", "Quality Inspection",
               "Gate Entry"]:
        for name in frappe.get_all(dt, pluck="name", order_by="creation desc"):
            try:
                doc = frappe.get_doc(dt, name)
                if doc.docstatus == 1:
                    doc.flags.ignore_permissions = True
                    doc.cancel()
                frappe.delete_doc(dt, name, force=1, ignore_permissions=True)
            except Exception:
                frappe.log_error(frappe.get_traceback(), f"Benkas: reset {dt} {name}")
    frappe.db.commit()
    print("reset done")


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

    # material stock (receipt + supplier/PR/QI + material request) must exist
    # before the site log issues material
    mat = _material_demo(company)

    # single end-to-end Daily Site Log for DIST: task progress + workers + material
    if not frappe.db.count("Daily Progress Log"):
        dparent = frappe.db.get_value("Plant Section", "DIST", "project_task")
        civil = frappe.db.get_value("Task", {"subject": "DIST - Civil & Foundation", "parent_task": dparent}, "name")
        erection = frappe.db.get_value("Task", {"subject": "DIST - Structural / Erection", "parent_task": dparent}, "name")
        dpl = frappe.get_doc({
            "doctype": "Daily Progress Log", "plant_section": "DIST", "log_date": today(),
            "incharge": "Administrator", "remarks": "Distillation civil complete; erection ongoing.",
            "task_progress": [
                {"task": civil, "percent_complete": 100, "activity_description": "Foundation & civil complete"},
                {"task": erection, "percent_complete": 60, "activity_description": "Columns erected",
                 "delay_reason": "Material Delay"},
            ],
            "workers_present": [
                {"person_type": "Employee", "person": e1, "task": erection, "hours": 8},
                {"person_type": "Labour Master", "person": l1, "task": erection, "hours": 9},
                {"person_type": "Labour Master", "person": l2, "task": civil, "hours": 8},
            ],
            "material_consumed": [
                {"item": mat["item"], "qty": 30, "uom": "Nos", "task": erection,
                 "material_request": mat.get("mr")},
            ],
            "photos": [{"image": PLACEHOLDER_IMG, "caption": "Site view"}],
        })
        dpl.insert(ignore_permissions=True)
        dpl.submit()

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

    _liven_dashboard()
    frappe.db.commit()

    counts = {dt: frappe.db.count(dt) for dt in [
        "Employee", "Contractor", "Labour Master", "Gate Entry", "Daily Progress Log",
        "Generator Log", "Power Consumption Log", "Site Vehicle Log", "Safety Violation Log",
        "Visitor Log", "Gate Pass", "Contractor Tools Register", "Safety Work Permit",
        "Electrical Work Permit", "Stock Entry", "Quality Inspection"]}
    print("DEMO DATA COUNTS:", counts)
    return counts


def _liven_dashboard():
    """Set some task progress / statuses so exec cards show real movement."""
    prog = [("DIST", "Civil & Foundation", 100, "Completed"),
            ("DIST", "Structural / Erection", 60, "Working"),
            ("FERM", "Civil & Foundation", 80, "Working")]
    for code, act, pct, status in prog:
        parent = frappe.db.get_value("Plant Section", code, "project_task")
        t = frappe.db.get_value("Task", {"subject": f"{code} - {act}", "parent_task": parent}, "name")
        if t:
            frappe.db.set_value("Task", t, {"progress": pct, "status": status})

    # a tools mismatch -> Tool Mismatches card
    ctr = frappe.db.get_value("Contractor Tools Register", {}, "name")
    if ctr:
        doc = frappe.get_doc("Contractor Tools Register", ctr)
        if doc.qty and doc.qty_returned != 1:
            doc.qty_returned = 1  # returned fewer than taken -> Mismatch (hook sets status)
            doc.save(ignore_permissions=True)

    # a permit in progress -> Active Safety Permits card
    swp = frappe.db.get_value("Safety Work Permit", {}, "name")
    if swp:
        frappe.db.set_value("Safety Work Permit", swp, "permit_status", "Work in Progress")

    frappe.db.commit()


def _material_demo(company):
    """Item + Material Receipt/Issue stock entries + a rejected Quality Inspection,
    so the material/QC/stock-balance reports and charts show real data."""
    warehouse = frappe.db.get_value("Plant Section", "DIST", "warehouse")
    if not warehouse:
        return {}

    item_code = "BK-CEMENT-OPC53"
    if not frappe.db.exists("Item", item_code):
        item_group = (frappe.db.get_value("Item Group", {"is_group": 0}, "name")
                      or "All Item Groups")
        frappe.get_doc({
            "doctype": "Item", "item_code": item_code, "item_name": "Cement OPC 53 (Demo)",
            "item_group": item_group, "stock_uom": "Nos", "is_stock_item": 1,
            "inspection_required_before_purchase": 1,
        }).insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Item", item_code, "inspection_required_before_purchase", 1)

    # Material Receipt (adds stock -> Bin) tagged to DIST
    if not frappe.db.exists("Stock Entry", {"stock_entry_type": "Material Receipt",
                                            "plant_section": "DIST"}):
        se = frappe.get_doc({
            "doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
            "company": company, "plant_section": "DIST", "posting_date": today(),
            "items": [{"item_code": item_code, "qty": 500, "t_warehouse": warehouse,
                       "basic_rate": 350, "allow_zero_valuation_rate": 1}],
        })
        se.insert(ignore_permissions=True)
        se.submit()

    # Material Request (Material Issue) against a real section + task, then APPROVE it
    # via workflow (so benkas_status = Approved). The site log will consume against it.
    dparent = frappe.db.get_value("Plant Section", "DIST", "project_task")
    erection = frappe.db.get_value("Task", {"subject": "DIST - Structural / Erection",
                                            "parent_task": dparent}, "name")
    mr_name = frappe.db.get_value("Material Request",
                                  {"material_request_type": "Material Issue", "plant_section": "DIST"}, "name")
    if not mr_name:
        try:
            mr = frappe.get_doc({
                "doctype": "Material Request", "material_request_type": "Material Issue",
                "transaction_date": today(), "company": company,
                "plant_section": "DIST", "benkas_task": erection,
                "items": [{"item_code": item_code, "qty": 40, "uom": "Nos",
                           "warehouse": warehouse, "schedule_date": today()}],
            })
            mr.insert(ignore_permissions=True)
            from frappe.model.workflow import apply_workflow
            apply_workflow(mr, "Approve")  # submits + benkas_status = Approved
            mr_name = mr.name
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Benkas: demo MR failed")

    # Supplier + draft Purchase Receipt (weighbridge + invoice photo, weight variance)
    supplier = "Benkas Test Supplier"
    if not frappe.db.exists("Supplier", supplier):
        sg = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name") or "All Supplier Groups"
        frappe.get_doc({"doctype": "Supplier", "supplier_name": supplier,
                        "supplier_group": sg}).insert(ignore_permissions=True)

    pr_name = frappe.db.get_value("Purchase Receipt", {"supplier": supplier, "docstatus": 0}, "name")
    if not pr_name:
        try:
            pr = frappe.get_doc({
                "doctype": "Purchase Receipt", "supplier": supplier, "company": company,
                "posting_date": today(), "plant_section": "DIST",
                "weighbridge_slip_no": "WB-0001", "gross_weight": 60, "tare_weight": 5,
                "supplier_invoice_photo": PLACEHOLDER_IMG,
                "items": [{"item_code": item_code, "qty": 50, "rate": 350,
                           "warehouse": warehouse, "allow_zero_valuation_rate": 1}],
            })
            pr.insert(ignore_permissions=True)
            pr_name = pr.name
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Benkas: demo PR failed")

    # a rejected Quality Inspection against the PR -> QC Rejection report + QC chart
    if pr_name and not frappe.db.exists("Quality Inspection", {"item_code": item_code}):
        try:
            frappe.get_doc({
                "doctype": "Quality Inspection", "inspection_type": "Incoming",
                "reference_type": "Purchase Receipt", "reference_name": pr_name,
                "item_code": item_code, "sample_size": 5, "report_date": today(),
                "status": "Rejected", "inspected_by": "Administrator",
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Benkas: demo QI failed")

    frappe.db.commit()
    return {"item": item_code, "mr": mr_name, "warehouse": warehouse}
