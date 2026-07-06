"""End-to-end smoke test for Benkas ERP. Run:
    bench --site <site> execute benkas_erp.setup.selftest.run
"""

import frappe
from frappe.desk.query_report import run as run_report
from frappe.model.workflow import apply_workflow

MODULES = ["Benkas Core", "Manpower", "Material", "Work Schedule", "Site Safety Assets"]


def run():
    out = {"reports": {}, "checks": {}}

    # 1. every benkas report executes and returns rows
    for r in frappe.get_all("Report", filters={"module": ["in", MODULES]}, pluck="name"):
        try:
            res = run_report(r, filters={})
            out["reports"][r] = f"OK ({len(res.get('result', []))} rows)"
        except Exception as e:
            out["reports"][r] = f"FAIL: {e}"

    # 1b. workspaces present
    out["checks"]["workspaces"] = ", ".join(
        frappe.get_all("Workspace", filters={"module": "Benkas Core"},
                       order_by="sequence_id", pluck="name"))

    # 1c. a print format renders without error
    ge = frappe.db.get_value("Gate Entry", {}, "name")
    if ge:
        try:
            html = frappe.get_print("Gate Entry", ge, print_format="Gate Entry Slip")
            out["checks"]["print_gate_entry_slip"] = f"OK ({len(html)} chars)"
        except Exception as e:
            out["checks"]["print_gate_entry_slip"] = f"FAIL: {e}"

    # 1d. WBS sub-tasks exist
    out["checks"]["wbs_subtasks"] = frappe.db.count("Task", {"parent_task": ["!=", ""]})

    # 2. Daily Progress Log rollups auto-fetched (DIST had 3 gate-ins)
    dpl = frappe.db.get_value("Daily Progress Log", {"plant_section": "DIST"},
                              ["name", "manpower_deployed"], as_dict=True)
    out["checks"]["dpl_rollup_manpower(DIST)"] = dpl.manpower_deployed if dpl else "no DPL"

    # 3. Workflow transition: confirm a pending Gate Entry
    ge = frappe.db.get_value("Gate Entry", {"acknowledgement_status": "Pending"}, "name")
    if ge:
        try:
            doc = frappe.get_doc("Gate Entry", ge)
            apply_workflow(doc, "Confirm")
            out["checks"]["workflow_confirm"] = frappe.db.get_value(
                "Gate Entry", ge, "acknowledgement_status")
        except Exception as e:
            out["checks"]["workflow_confirm"] = f"FAIL: {e}"
    else:
        out["checks"]["workflow_confirm"] = "no pending gate entry"

    # 4. Validation: gate entry without photo must be blocked
    try:
        frappe.get_doc({"doctype": "Gate Entry", "person_type": "Employee",
                        "person": frappe.db.get_value("Employee", {}, "name"),
                        "plant_section": "DIST", "entry_type": "In"}).insert(ignore_permissions=True)
        out["checks"]["photo_mandatory_enforced"] = "FAIL: saved without photo"
    except Exception:
        out["checks"]["photo_mandatory_enforced"] = "OK (blocked)"

    # 5. Validation: inactive labour blocked at gate
    lab = frappe.db.get_value("Labour Master", {}, "name")
    if lab:
        frappe.db.set_value("Labour Master", lab, "status", "Exited")
        try:
            frappe.get_doc({"doctype": "Gate Entry", "person_type": "Labour Master",
                            "person": lab, "plant_section": "DIST", "entry_type": "In",
                            "photo": "/x.png"}).insert(ignore_permissions=True)
            out["checks"]["inactive_labour_blocked"] = "FAIL: allowed"
        except Exception:
            out["checks"]["inactive_labour_blocked"] = "OK (blocked)"
        frappe.db.set_value("Labour Master", lab, "status", "Active")

    frappe.db.rollback()  # discard the test-only writes in checks 3-5
    print("SELFTEST RESULTS:")
    for k, v in out["reports"].items():
        print(f"  report  {k:42} {v}")
    for k, v in out["checks"].items():
        print(f"  check   {k:42} {v}")
    return out
