"""
Code-first DocType generator for Benkas ERP.

Run once (developer_mode = 1) to materialise every custom DocType as a
version-controlled JSON file inside the app modules:

    bench --site <site> execute benkas_erp.setup.build_doctypes.build

It is idempotent: DocTypes that already exist are skipped, so it is safe
to re-run after adding new definitions here.
"""

import frappe

PERSON_TYPES = "Employee\nContractor\nLabour Master"
PERMIT_STATUS = "Requested\nApproved\nWork in Progress\nClosed"

DEFAULT_PERMS = [{
    "role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1,
    "report": 1, "export": 1, "print": 1, "email": 1, "share": 1,
}]


def F(fieldname, label, fieldtype, **kw):
    d = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype}
    d.update(kw)
    return d


def SB(fieldname, label=""):
    return {"fieldname": fieldname, "label": label, "fieldtype": "Section Break"}


def CB(fieldname):
    return {"fieldname": fieldname, "fieldtype": "Column Break"}


# ---------------------------------------------------------------------------
# DocType definitions, in dependency order (linked targets created first).
# ---------------------------------------------------------------------------
def doctypes():
    return [
        # ---------------- Benkas Core ----------------
        {
            "name": "Plant Section", "module": "Benkas Core",
            "autoname": "field:section_code", "naming_rule": "By fieldname",
            "title_field": "section_name",
            "fields": [
                F("section_name", "Section Name", "Data", reqd=1, in_list_view=1),
                F("section_code", "Section Code", "Data", reqd=1, unique=1, in_list_view=1),
                F("is_active", "Is Active", "Check", default="1"),
                CB("cb1"),
                F("warehouse", "Warehouse", "Link", options="Warehouse"),
                F("project_task", "Project Task", "Link", options="Task"),
                F("cost_center", "Cost Center", "Link", options="Cost Center"),
                F("incharge", "Incharge", "Link", options="User", in_list_view=1),
            ],
        },
        {
            "name": "Contractor", "module": "Benkas Core",
            "autoname": "field:agency_name", "naming_rule": "By fieldname",
            "title_field": "agency_name",
            "fields": [
                F("agency_name", "Agency Name", "Data", reqd=1, unique=1, in_list_view=1),
                F("registration_no", "Registration No", "Data"),
                F("labour_license_no", "Labour License No", "Data"),
                F("agreement_valid_upto", "Agreement Valid Upto", "Date", in_list_view=1),
                CB("cb1"),
                F("contact_person", "Contact Person", "Data"),
                F("phone", "Phone", "Data", in_list_view=1),
                F("linked_supplier", "Linked Supplier", "Link", options="Supplier"),
            ],
        },
        {
            "name": "Labour Master", "module": "Benkas Core",
            "autoname": "LM-.#####", "title_field": "labour_name",
            "fields": [
                F("labour_name", "Labour Name", "Data", reqd=1, in_list_view=1),
                F("contractor", "Contractor", "Link", options="Contractor", in_list_view=1),
                F("category", "Category", "Select",
                  options="Skilled\nSemi-skilled\nUnskilled", in_list_view=1),
                F("status", "Status", "Select",
                  options="Active\nInactive\nExited", default="Active", in_list_view=1),
                CB("cb1"),
                F("id_proof_type", "ID Proof Type", "Select",
                  options="Aadhaar\nPAN\nVoter ID\nDriving License\nOther"),
                F("id_proof_no", "ID Proof No", "Data"),
                F("photo", "Photo", "Attach Image"),
                F("id_card_barcode", "ID Card Barcode", "Barcode"),
            ],
        },
        {
            "name": "Delay Reason", "module": "Benkas Core",
            "autoname": "field:reason", "naming_rule": "By fieldname",
            "fields": [
                F("reason", "Reason", "Data", reqd=1, unique=1, in_list_view=1),
            ],
        },
        {
            # Small editable master for the EOD status dropdown. Add/rename rows in
            # the list view — no code change needed. is_stopped drives the Stoppage
            # Analysis report; color drives the Section 360 / client-report chip.
            "name": "Progress Status", "module": "Benkas Core",
            "autoname": "field:status_name", "naming_rule": "By fieldname",
            "title_field": "status_name",
            "fields": [
                F("status_name", "Status", "Data", reqd=1, unique=1, in_list_view=1),
                F("is_stopped", "Is a Stoppage", "Check", default="0", in_list_view=1),
                F("color", "Colour", "Select", options="Green\nBlue\nRed\nOrange\nGrey",
                  default="Blue", in_list_view=1),
                F("display_order", "Display Order", "Int", default="0", in_list_view=1),
            ],
        },
        {
            "name": "Construction Activity", "module": "Benkas Core",
            "autoname": "field:activity_name", "naming_rule": "By fieldname",
            "title_field": "activity_name",
            "fields": [
                F("activity_name", "Activity Name", "Data", reqd=1, unique=1, in_list_view=1),
                F("sequence", "Sequence", "Int", in_list_view=1),
                F("default_weight", "Default Weight %", "Percent", in_list_view=1),
                F("is_active", "Is Active", "Check", default="1"),
            ],
        },
        {
            "name": "Generator Master", "module": "Site Safety Assets",
            "autoname": "field:generator_id", "naming_rule": "By fieldname",
            "fields": [
                F("generator_id", "Generator ID", "Data", reqd=1, unique=1, in_list_view=1),
                F("capacity", "Capacity (kVA)", "Data", in_list_view=1),
                F("plant_section", "Plant Section", "Link", options="Plant Section", in_list_view=1),
            ],
        },
        {
            "name": "Site Vehicle", "module": "Site Safety Assets",
            "autoname": "field:vehicle_no", "naming_rule": "By fieldname",
            "fields": [
                F("vehicle_no", "Vehicle No", "Data", reqd=1, unique=1, in_list_view=1),
                F("vehicle_type", "Vehicle Type", "Select",
                  options="Jeep\nPickup\nForklift\nCrane\nTempo\nTwo Wheeler\nOther", in_list_view=1),
                CB("cb1"),
                F("owner_type", "Owner Type", "Select", options="Company\nBenkas\nContractor"),
                F("assigned_driver", "Assigned Driver", "Data", in_list_view=1),
            ],
        },
        # ---------------- Manpower ----------------
        {
            "name": "Gate Entry PPE Item", "module": "Manpower", "istable": 1,
            "fields": [
                F("ppe_item", "PPE Item", "Data", in_list_view=1, columns=6),
                F("is_available", "Available", "Check", in_list_view=1, columns=2),
            ],
        },
        {
            "name": "Gate Pass", "module": "Site Safety Assets",
            "autoname": "GP-.YYYY.-.#####",
            "fields": [
                F("person_type", "Person Type", "Select", options=PERSON_TYPES, reqd=1, in_list_view=1),
                F("person", "Person", "Dynamic Link", options="person_type", reqd=1, in_list_view=1),
                F("plant_section", "Plant Section", "Link", options="Plant Section"),
                F("reason", "Reason", "Small Text"),
                F("destination", "Destination", "Data"),
                CB("cb1"),
                F("expected_out_time", "Expected Out Time", "Datetime"),
                F("expected_return_time", "Expected Return Time", "Datetime"),
                F("actual_out_time", "Actual Out Time", "Datetime"),
                F("actual_return_time", "Actual Return Time", "Datetime"),
                SB("sb_status"),
                F("pass_status", "Pass Status", "Select",
                  options="Requested\nApproved\nOut\nReturned\nOverdue",
                  default="Requested", read_only=1, in_list_view=1),
                F("barcode", "Barcode", "Barcode"),
            ],
        },
        {
            "name": "Gate Entry", "module": "Manpower",
            "autoname": "GE-.YYYY.-.#####",
            "fields": [
                F("person_type", "Person Type", "Select", options=PERSON_TYPES, reqd=1, in_list_view=1),
                F("person", "Person", "Dynamic Link", options="person_type", reqd=1, in_list_view=1),
                F("plant_section", "Plant Section", "Link", options="Plant Section", reqd=1, in_list_view=1),
                F("entry_type", "Entry Type", "Select", options="In\nOut", reqd=1, default="In", in_list_view=1),
                CB("cb1"),
                F("time_in", "Time In", "Datetime"),
                F("time_out", "Time Out", "Datetime"),
                F("override_reason", "Manual Override Reason", "Small Text"),
                F("vehicle_no", "Vehicle No", "Data"),
                F("gate_pass", "Gate Pass", "Link", options="Gate Pass"),
                SB("sb_work", "Work & Safety"),
                F("work_description", "Work Description", "Small Text"),
                F("photo", "Gate Photo", "Attach Image", reqd=1),
                F("ppe_checklist", "PPE Checklist", "Table", options="Gate Entry PPE Item"),
                SB("sb_ack", "Acknowledgement"),
                F("acknowledgement_status", "Acknowledgement Status", "Select",
                  options="Pending\nConfirmed\nDisputed", default="Pending", read_only=1, in_list_view=1),
                F("dispute_remarks", "Dispute Remarks", "Small Text"),
            ],
        },
        # ---------------- Site Safety Assets ----------------
        {
            "name": "Contractor Tools Register", "module": "Site Safety Assets",
            "autoname": "CTR-.YYYY.-.#####",
            "fields": [
                F("contractor", "Contractor", "Link", options="Contractor", reqd=1, in_list_view=1),
                F("tool_description", "Tool Description", "Small Text", in_list_view=1),
                F("qty", "Qty In", "Int"),
                F("qty_returned", "Qty Returned", "Int"),
                CB("cb1"),
                F("gate_entry_in", "Gate Entry In", "Link", options="Gate Entry"),
                F("gate_entry_out", "Gate Entry Out", "Link", options="Gate Entry"),
                F("status", "Status", "Select", options="In\nReturned\nMismatch",
                  default="In", read_only=1, in_list_view=1),
                F("photo", "Photo", "Attach Image"),
            ],
        },
        {
            "name": "Site Vehicle Log", "module": "Site Safety Assets",
            "autoname": "VL-.YYYY.-.#####",
            "fields": [
                F("vehicle", "Vehicle", "Link", options="Site Vehicle", reqd=1, in_list_view=1),
                F("driver", "Driver", "Data", in_list_view=1),
                F("plant_section", "Plant Section", "Link", options="Plant Section"),
                F("purpose", "Purpose", "Small Text"),
                CB("cb1"),
                F("time_out", "Time Out", "Datetime"),
                F("time_in", "Time In", "Datetime"),
                F("odometer_start", "Odometer Start", "Float"),
                F("odometer_end", "Odometer End", "Float"),
            ],
        },
        {
            "name": "Generator Log", "module": "Site Safety Assets",
            "autoname": "GL-.YYYY.-.#####",
            "fields": [
                F("generator", "Generator", "Link", options="Generator Master", reqd=1, in_list_view=1),
                F("plant_section", "Plant Section", "Link", options="Plant Section"),
                F("log_date", "Log Date", "Date", default="Today", in_list_view=1),
                F("shift", "Shift", "Select", options="Day\nNight\nGeneral"),
                CB("cb1"),
                F("start_time", "Start Time", "Datetime"),
                F("stop_time", "Stop Time", "Datetime"),
                F("running_hours", "Running Hours", "Float", read_only=1, in_list_view=1),
                SB("sb_fuel", "Fuel & Meter"),
                F("opening_meter", "Opening Meter", "Float"),
                F("closing_meter", "Closing Meter", "Float"),
                F("diesel_filled", "Diesel Filled (L)", "Float"),
                CB("cb2"),
                F("diesel_balance", "Diesel Balance (L)", "Float"),
                F("consumption_rate", "Consumption Rate (L/hr)", "Float", read_only=1),
                F("fuel_slip_photo", "Fuel Slip Photo", "Attach Image"),
            ],
        },
        {
            "name": "Power Consumption Log", "module": "Site Safety Assets",
            "autoname": "PCL-.YYYY.-.#####",
            "fields": [
                F("log_date", "Log Date", "Date", default="Today", in_list_view=1),
                F("shift", "Shift", "Select", options="Day\nNight\nGeneral"),
                F("plant_section", "Plant Section", "Link", options="Plant Section", in_list_view=1),
                F("reading_by", "Reading By", "Link", options="User"),
                CB("cb1"),
                F("r_phase", "R Phase (A)", "Float"),
                F("y_phase", "Y Phase (A)", "Float"),
                F("b_phase", "B Phase (A)", "Float"),
                F("voltage", "Voltage (V)", "Float"),
            ],
        },
        {
            "name": "Visitor Log", "module": "Site Safety Assets",
            "autoname": "VIS-.YYYY.-.#####", "title_field": "visitor_name",
            "fields": [
                F("visitor_name", "Visitor Name", "Data", reqd=1, in_list_view=1),
                F("company", "Company", "Data", in_list_view=1),
                F("purpose", "Purpose", "Small Text"),
                F("plant_section", "Plant Section", "Link", options="Plant Section"),
                F("host_person", "Host Person", "Link", options="User"),
                CB("cb1"),
                F("time_in", "Time In", "Datetime"),
                F("time_out", "Time Out", "Datetime"),
                F("photo", "Photo", "Attach Image"),
                F("visitor_slip", "Visitor Slip", "Barcode"),
                F("acknowledgement_status", "Acknowledgement Status", "Select",
                  options="Pending\nConfirmed\nDisputed", default="Pending"),
            ],
        },
        {
            "name": "Safety Violation Log", "module": "Site Safety Assets",
            "autoname": "SVL-.YYYY.-.#####",
            "fields": [
                F("violation_type", "Violation Type", "Select",
                  options="No Helmet\nNo Safety Shoes\nNo Harness\nUnsafe Act\nOther",
                  reqd=1, in_list_view=1),
                F("person_type", "Person Type", "Select", options=PERSON_TYPES),
                F("person", "Person", "Dynamic Link", options="person_type", in_list_view=1),
                F("plant_section", "Plant Section", "Link", options="Plant Section", in_list_view=1),
                CB("cb1"),
                F("violation_datetime", "Violation Datetime", "Datetime", default="now"),
                F("photo", "Photo", "Attach Image", reqd=1),
                F("corrective_action", "Corrective Action", "Small Text"),
                F("status", "Status", "Select", options="Open\nCorrected", default="Open", in_list_view=1),
            ],
        },
        {
            "name": "Safety Work Permit Worker", "module": "Site Safety Assets", "istable": 1,
            "fields": [
                F("worker_name", "Worker Name", "Data", in_list_view=1, columns=6),
                F("worker_role", "Role", "Data", in_list_view=1, columns=4),
            ],
        },
        {
            "name": "Safety Work Permit", "module": "Site Safety Assets",
            "autoname": "SWP-.YYYY.-.#####",
            "fields": [
                F("permit_type", "Permit Type", "Select",
                  options="Hot Work\nWork at Height\nConfined Space\nExcavation\nOther",
                  reqd=1, in_list_view=1),
                F("plant_section", "Plant Section", "Link", options="Plant Section", in_list_view=1),
                F("work_description", "Work Description", "Small Text"),
                F("workers_involved", "Workers Involved", "Table", options="Safety Work Permit Worker"),
                CB("cb1"),
                F("valid_from", "Valid From", "Datetime"),
                F("valid_to", "Valid To", "Datetime"),
                F("issuing_incharge", "Issuing Incharge", "Link", options="User"),
                F("approving_incharge", "Approving Incharge", "Link", options="User"),
                SB("sb_photos", "Mandatory Photos"),
                F("site_photo", "Site/Area Photo", "Attach Image", reqd=1),
                F("ppe_photo", "PPE-in-use Photo", "Attach Image", reqd=1),
                F("barricading_photo", "Barricading/Fire-watch Photo", "Attach Image"),
                SB("sb_status", "Status"),
                F("permit_status", "Permit Status", "Select", options=PERMIT_STATUS,
                  default="Requested", read_only=1, in_list_view=1),
                F("closing_confirmation", "Closing Confirmation", "Check"),
            ],
        },
        {
            "name": "Electrical Work Permit Job Log", "module": "Site Safety Assets", "istable": 1,
            "fields": [
                F("start_time", "Start Time", "Datetime", in_list_view=1, columns=3),
                F("end_time", "End Time", "Datetime", in_list_view=1, columns=3),
                F("handover_notes", "Handover Notes", "Small Text", in_list_view=1, columns=4),
            ],
        },
        {
            "name": "Electrical Work Permit", "module": "Site Safety Assets",
            "autoname": "EWP-.YYYY.-.#####",
            "fields": [
                F("job_description", "Job Description", "Small Text", reqd=1, in_list_view=1),
                F("plant_section", "Plant Section", "Link", options="Plant Section", in_list_view=1),
                F("equipment", "Equipment", "Data"),
                F("loto_confirmed", "LOTO Confirmed", "Check"),
                CB("cb1"),
                F("valid_from", "Valid From", "Datetime"),
                F("valid_to", "Valid To", "Datetime"),
                F("issuing_engineer", "Issuing Engineer", "Link", options="User"),
                F("receiving_engineer", "Receiving Engineer", "Link", options="User"),
                SB("sb_log", "Job Log"),
                F("job_log", "Job Log", "Table", options="Electrical Work Permit Job Log"),
                SB("sb_status", "Status"),
                F("permit_status", "Permit Status", "Select", options=PERMIT_STATUS,
                  default="Requested", read_only=1, in_list_view=1),
                F("closure_signoff", "Closure Sign-off (Re-energized)", "Check"),
            ],
        },
        # ---------------- Work Schedule ----------------
        {
            "name": "Daily Progress Photo", "module": "Work Schedule", "istable": 1,
            "fields": [
                F("image", "Image", "Attach Image", in_list_view=1, columns=5),
                F("activity_task", "Task", "Link", options="Task", in_list_view=1, columns=3,
                  description="Optional — tag the task this photo shows, so photos group by task."),
                F("caption", "Caption", "Data", in_list_view=1, columns=2),
            ],
        },
        {
            "name": "Daily Task Progress", "module": "Work Schedule", "istable": 1,
            "fields": [
                F("task", "Task", "Link", options="Task", reqd=1, in_list_view=1, columns=3),
                F("status", "Status", "Link", options="Progress Status", reqd=1, in_list_view=1, columns=2),
                F("percent_complete", "% Complete", "Percent", in_list_view=1, columns=2),
                F("work_description", "Work Description", "Small Text", reqd=1, in_list_view=1, columns=5,
                  description="What was done today — or, if stopped, why. Required, at least 15 characters."),
            ],
        },
        {
            "name": "Daily Worker Log", "module": "Work Schedule", "istable": 1,
            "fields": [
                F("person_type", "Type", "Select", options=PERSON_TYPES, reqd=1, in_list_view=1, columns=2),
                F("person", "Person", "Dynamic Link", options="person_type", reqd=1, in_list_view=1, columns=4),
                F("task", "Task", "Link", options="Task", in_list_view=1, columns=4),
                F("hours", "Hours", "Float", default="8", in_list_view=1, columns=1),
            ],
        },
        {
            "name": "Daily Material Consumed", "module": "Work Schedule", "istable": 1,
            "fields": [
                F("item", "Item", "Link", options="Item", reqd=1, in_list_view=1, columns=3),
                F("qty", "Qty", "Float", reqd=1, in_list_view=1, columns=1),
                F("uom", "UOM", "Link", options="UOM", in_list_view=1, columns=1),
                F("task", "Task", "Link", options="Task", in_list_view=1, columns=3),
                F("material_request", "Material Request", "Link", options="Material Request",
                  in_list_view=1, columns=2),
                F("no_material_request", "No MR", "Check", read_only=1, in_list_view=1, columns=1),
            ],
        },
        {
            "name": "Daily Progress Log", "module": "Work Schedule", "is_submittable": 1,
            "autoname": "DPL-.YYYY.-.#####",
            "fields": [
                F("plant_section", "Plant Section", "Link", options="Plant Section", reqd=1, in_list_view=1),
                F("log_date", "Log Date", "Date", default="Today", reqd=1, in_list_view=1),
                CB("cb1"),
                F("incharge", "Incharge", "Link", options="User", default="__user", in_list_view=1),
                F("stock_entry", "Auto Stock Entry", "Link", options="Stock Entry", read_only=1),
                F("no_work_today", "No Work Today", "Check", default="0",
                  description="Tick if nothing happened at this section today (holiday, full rain day, etc.)."),
                F("no_work_reason", "Reason (no work)", "Small Text",
                  depends_on="no_work_today", mandatory_depends_on="no_work_today"),
                SB("sb_progress", "Task Progress"),
                F("task_progress", "Task Progress", "Table", options="Daily Task Progress"),
                SB("sb_workers", "Workers Present"),
                F("workers_present", "Workers Present", "Table", options="Daily Worker Log"),
                SB("sb_material", "Material Consumed"),
                F("material_consumed", "Material Consumed", "Table", options="Daily Material Consumed"),
                SB("sb_photos", "Site Photos"),
                F("photos", "Photos", "Table", options="Daily Progress Photo"),
                F("remarks", "Remarks", "Small Text"),
            ],
        },
        # ---------------- Material ----------------
        {
            "name": "Quality Inspection Photo", "module": "Material", "istable": 1,
            "fields": [
                F("image", "Image", "Attach Image", reqd=1, in_list_view=1, columns=6),
                F("caption", "Caption", "Data", in_list_view=1, columns=4),
            ],
        },
    ]


def build():
    made, skipped = [], []
    for dt in doctypes():
        if frappe.db.exists("DocType", dt["name"]):
            skipped.append(dt["name"])
            continue
        payload = {
            "doctype": "DocType",
            "name": dt["name"],
            "module": dt["module"],
            "custom": 0,
            "istable": dt.get("istable", 0),
            "is_submittable": dt.get("is_submittable", 0),
            "editable_grid": 1,
            "track_changes": 1,
            "fields": dt["fields"],
            "permissions": [] if dt.get("istable") else DEFAULT_PERMS,
        }
        if dt.get("autoname"):
            payload["autoname"] = dt["autoname"]
        if dt.get("naming_rule"):
            payload["naming_rule"] = dt["naming_rule"]
        if dt.get("title_field"):
            payload["title_field"] = dt["title_field"]
        doc = frappe.get_doc(payload)
        doc.insert(ignore_permissions=True)
        made.append(dt["name"])
    frappe.db.commit()
    print("CREATED:", made)
    print("SKIPPED (already exist):", skipped)
    return {"created": made, "skipped": skipped}
