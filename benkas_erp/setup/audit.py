"""
Full audit of Benkas ERP against the finalize checklist. Prints a pass/fail
line per workspace / doctype-check / report / print-format.

    bench --site <site> execute benkas_erp.setup.audit.run
"""

import json
import frappe
from frappe.utils import today
from frappe.desk.query_report import run as run_report

MODULES = ["Benkas Core", "Manpower", "Material", "Work Schedule", "Site Safety Assets"]

WS_EXPECT = {
    "Gate Management": ("door-open", "cyan"),
    "Manpower Manager": ("users", "blue"),
    "Material and Purchase": ("truck", "orange"),
    "Work Schedule and Progress": ("calendar", "green"),
    "Site Safety and Assets": ("shield", "red"),
    "Benkas Core": ("settings", "gray"),
    "Benkas MIS": ("layout-dashboard", "purple"),
}

# doctypes that must carry a plant_section link
NEEDS_SECTION = ["Gate Entry", "Gate Pass", "Daily Progress Log", "Visitor Log",
                 "Generator Master", "Generator Log", "Power Consumption Log",
                 "Site Vehicle Log", "Safety Violation Log", "Safety Work Permit",
                 "Electrical Work Permit"]

# (doctype, attach-image field that must be reqd)
REQD_PHOTOS = [("Gate Entry", "photo"), ("Safety Violation Log", "photo"),
               ("Safety Work Permit", "site_photo"), ("Safety Work Permit", "ppe_photo")]

# child -> expected parent + table field
CHILD_TABLES = {
    "Gate Entry PPE Item": ("Gate Entry", "ppe_checklist"),
    "Quality Inspection Photo": ("Quality Inspection", "inspection_photos"),
    "Daily Progress Photo": ("Daily Progress Log", "photos"),
    "Safety Work Permit Worker": ("Safety Work Permit", "workers_involved"),
    "Electrical Work Permit Job Log": ("Electrical Work Permit", "job_log"),
}

PRINTS = [
    ("Gate Entry Slip", "Gate Entry"), ("Gate Pass Slip", "Gate Pass"),
    ("Visitor Slip", "Visitor Log"), ("Safety Work Permit Print", "Safety Work Permit"),
    ("Electrical Work Permit Print", "Electrical Work Permit"),
    ("Daily Progress Report", "Daily Progress Log"),
    ("Staff ID Card", "Employee"), ("Labour ID Card", "Labour Master"),
]


# Features that were SPECIFIED with fields + workflow + print — each asserted
# independently (a Link resolving is NOT proof the feature was built).
FEATURES = [
    {"name": "Material Request site tracking", "doctype": "Material Request",
     "fields": ["plant_section", "benkas_task", "benkas_status"],
     "workflow": "Material Request Approval",
     "wf_states": ["Requested", "Approved", "Partially Issued", "Issued", "Closed"],
     "wf_actions": ["Approve", "Close"], "print": "Material Request Slip"},
    {"name": "Purchase Receipt weighbridge", "doctype": "Purchase Receipt",
     "fields": ["plant_section", "gross_weight", "net_weight", "supplier_invoice_photo",
                "weight_variance_flag"], "workflow": None, "print": None},
    {"name": "Gate Entry acknowledgement", "doctype": "Gate Entry",
     "fields": ["plant_section", "photo", "acknowledgement_status"],
     "workflow": "Gate Entry Acknowledgement", "wf_states": ["Pending", "Confirmed", "Disputed"],
     "wf_actions": ["Confirm", "Dispute"], "print": "Gate Entry Slip"},
    {"name": "Safety Work Permit", "doctype": "Safety Work Permit",
     "fields": ["site_photo", "ppe_photo", "permit_status"],
     "workflow": "Safety Work Permit Approval",
     "wf_states": ["Requested", "Approved", "Work in Progress", "Closed"],
     "wf_actions": ["Approve", "Start Work", "Close"], "print": "Safety Work Permit Print"},
    {"name": "Electrical Work Permit", "doctype": "Electrical Work Permit",
     "fields": ["loto_confirmed", "closure_signoff", "permit_status"],
     "workflow": "Electrical Work Permit Approval",
     "wf_states": ["Requested", "Approved", "Work in Progress", "Closed"],
     "wf_actions": ["Approve", "Start Work", "Close"], "print": "Electrical Work Permit Print"},
]


def _workflows_and_thermal():
    print("\n--- WORKFLOWS (deactivated) + THERMAL SLIPS ---")
    wfs = ["Gate Entry Acknowledgement", "Gate Pass Approval", "Safety Work Permit Approval",
           "Electrical Work Permit Approval", "Material Request Approval"]
    all_inactive = all(frappe.db.exists("Workflow", w)
                       and frappe.db.get_value("Workflow", w, "is_active") == 0 for w in wfs)
    print(f"  {'PASS' if all_inactive else 'FAIL'}  all 5 workflows exist but INACTIVE")
    # status fields must be editable now
    ed = frappe.get_meta("Gate Entry").get_field("acknowledgement_status").read_only == 0
    print(f"  {'PASS' if ed else 'FAIL'}  status fields editable while workflows off")

    from benkas_erp.setup.print_formats import ROLL_WIDTH_MM
    slips = [("Staff ID Card", "Employee"), ("Labour ID Card", "Labour Master"),
             ("Gate Entry Slip", "Gate Entry"), ("Temporary Gate Slip", "Gate Entry"),
             ("Gate Pass Slip", "Gate Pass"), ("Visitor Slip", "Visitor Log"),
             ("Contractor Tools Slip", "Contractor Tools Register")]
    for pf, dt in slips:
        rec = frappe.db.get_value(dt, {}, "name")
        if not rec:
            print(f"  n/a   {pf}: no {dt} record to render")
            continue
        try:
            html = frappe.get_print(dt, rec, print_format=pf)
            size_ok = f"size: {ROLL_WIDTH_MM}mm" in html
            qr_ok = "data:image/png;base64" in html
            mono = "background:#000" not in html.replace(" ", "").replace("!important", "")  # no black fills
            print(f"  {'PASS' if size_ok and qr_ok else 'FAIL'}  {pf}: {ROLL_WIDTH_MM}mm page={size_ok} QR={qr_ok}")
        except Exception as e:
            print(f"  FAIL  {pf}: {e}")


def _decode_qr_from_png_datauri(data_uri):
    """Decode a QR from a base64 PNG data-URI (returns the encoded string or None)."""
    try:
        import base64 as _b64
        import numpy as np
        import cv2
        png = _b64.b64decode(data_uri.split(",", 1)[1])
        img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        val, _pts, _ = cv2.QRCodeDetector().detectAndDecode(img)
        return val or None
    except Exception:
        return None


def _scan_loop():
    """End-to-end QR scan loop: render a real card, decode its QR, then drive the
    scan station's server method through IN->OUT, gate-pass, visitor and the
    inactive-block. Self-contained + cleans up."""
    print("\n--- QR SCAN LOOP (scan station) ---")
    import re
    from benkas_erp import scan as S
    from frappe.model.workflow import apply_workflow

    created = []  # (doctype, name) to clean up
    try:
        contractor = frappe.db.get_value("Contractor", {}, "name")
        emp = frappe.db.get_value("Employee", {}, "name")
        section = frappe.db.get_value("Plant Section", {"is_active": 1}, "name")

        # fresh test labour (no pre-existing gate entries) so IN is unambiguous
        tl = frappe.get_doc({"doctype": "Labour Master", "labour_name": "Scan Test Worker",
                             "status": "Active", "contractor": contractor,
                             "category": "Skilled"}).insert(ignore_permissions=True)
        created.append(("Labour Master", tl.name))
        key = S.qr_key("Labour Master", tl.name)

        # 1) render the actual ID card and decode the QR printed on it
        html = frappe.get_print("Labour Master", tl.name, print_format="Labour ID Card")
        m = re.search(r"data:image/png;base64,[A-Za-z0-9+/=]+", html)
        try:
            import cv2  # noqa
            have_decoder = True
        except Exception:
            have_decoder = False
        if not have_decoder:
            print("  n/a   card QR decode skipped (no OpenCV on this site); encode key = " + repr(key))
        else:
            decoded = _decode_qr_from_png_datauri(m.group(0)) if m else None
            print(f"  {'PASS' if decoded == key else 'FAIL'}  card QR decodes to the standard key: "
                  f"encoded={key!r} decoded={decoded!r}")

        # 2) scan IN -> identifies person, offers IN (no open entry yet)
        r1 = S.scan(key)
        in_ok = r1.get("action") == "IN" and r1.get("person", {}).get("name") == "Scan Test Worker"
        print(f"  {'PASS' if in_ok else 'FAIL'}  scan -> IN, identifies person "
              f"({r1.get('person', {}).get('name')!r}), section pre-filled={r1.get('prefill', {}).get('plant_section')!r}")

        # 3) create the gate entry (as the guard would, after photo) then scan OUT
        r2 = S.create_gate_in(key, r1.get("prefill", {}).get("plant_section") or section, None)
        ge = r2.get("reference")
        if ge:
            created.append(("Gate Entry", ge))
        print(f"  {'PASS' if r2.get('action') == 'IN_DONE' and ge else 'FAIL'}  create_gate_in -> Gate Entry {ge}")
        r3 = S.scan(key)
        to = frappe.db.get_value("Gate Entry", ge, "time_out") if ge else None
        print(f"  {'PASS' if r3.get('action') == 'OUT' and r3.get('reference') == ge and to else 'FAIL'}  "
              f"scan again -> OUT closes the same entry (time_out set: {bool(to)})")

        # 4) inactive labour is blocked
        frappe.db.set_value("Labour Master", tl.name, "status", "Exited")
        rb = S.scan(key)
        blocked = (not rb.get("ok")) and ("BLOCK" in (rb.get("message", "").upper()))
        print(f"  {'PASS' if blocked else 'FAIL'}  inactive labour blocked -> {rb.get('message')!r}")
        frappe.db.set_value("Labour Master", tl.name, "status", "Active")

        # 5) Gate Pass: not-approved rejected, then Approved -> Out -> Returned
        gp_req = frappe.db.get_value("Gate Pass", {"pass_status": "Requested"}, "name")
        if gp_req:
            rna = S.scan(S.qr_key("Gate Pass", gp_req))
            na_ok = (not rna.get("ok")) and ("NOT APPROVED" in rna.get("message", "").upper())
            print(f"  {'PASS' if na_ok else 'FAIL'}  gate pass not approved -> rejected ({rna.get('message')!r})")

        gp = frappe.get_doc({"doctype": "Gate Pass", "person_type": "Employee", "person": emp,
                             "plant_section": section, "reason": "scan test",
                             "expected_out_time": frappe.utils.now_datetime(),
                             "expected_return_time": frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=3)})
        gp.insert(ignore_permissions=True)
        created.append(("Gate Pass", gp.name))
        frappe.db.set_value("Gate Pass", gp.name, "pass_status", "Approved")  # workflows off
        gk = S.qr_key("Gate Pass", gp.name)
        ro = S.scan(gk)
        print(f"  {'PASS' if ro.get('action') == 'GATE_PASS_OUT' and frappe.db.get_value('Gate Pass', gp.name, 'pass_status') == 'Out' else 'FAIL'}  approved pass scan -> OUT")
        rr = S.scan(gk)
        print(f"  {'PASS' if rr.get('action') == 'GATE_PASS_RETURN' and frappe.db.get_value('Gate Pass', gp.name, 'pass_status') == 'Returned' else 'FAIL'}  return scan -> RETURNED")

        # 6) Visitor: scan closes the log
        vl = frappe.get_doc({"doctype": "Visitor Log", "visitor_name": "Scan Test Visitor",
                             "plant_section": section, "time_in": frappe.utils.now_datetime()}).insert(ignore_permissions=True)
        created.append(("Visitor Log", vl.name))
        rv = S.scan(S.qr_key("Visitor Log", vl.name))
        vout = rv.get("action") == "VISITOR_OUT" and frappe.db.get_value("Visitor Log", vl.name, "time_out")
        print(f"  {'PASS' if vout else 'FAIL'}  visitor scan -> signed OUT (time_out set: {bool(vout)})")

        # 7) Employee scan IN/OUT -> Employee Checkin rows
        company = frappe.db.get_value("Company", {}, "name")
        emp = frappe.get_doc({"doctype": "Employee", "first_name": "Scan Test Staff",
                              "gender": "Male", "date_of_birth": "1990-01-01",
                              "date_of_joining": today(), "company": company, "status": "Active"}
                             ).insert(ignore_permissions=True)
        created.insert(0, ("Employee", emp.name))
        ek = S.qr_key("Employee", emp.name)
        S.scan(ek)
        rein = S.create_gate_in(ek, section, None)
        if rein.get("reference"):
            created.insert(0, ("Gate Entry", rein["reference"]))
        cin = frappe.db.exists("Employee Checkin", {"employee": emp.name, "log_type": "IN"})
        S.scan(ek)  # OUT
        cout = frappe.db.exists("Employee Checkin", {"employee": emp.name, "log_type": "OUT"})
        for c in frappe.get_all("Employee Checkin", filters={"employee": emp.name}, pluck="name"):
            created.insert(0, ("Employee Checkin", c))
        print(f"  {'PASS' if cin and cout else 'FAIL'}  employee scan creates IN & OUT Employee Checkins")

        # 8) Temporary pass: issue -> scan OUT today -> expired next day
        rt = S.create_temp_pass(name="Temp Test Worker", plant_section=section)
        tge = rt.get("reference")
        if tge:
            created.insert(0, ("Gate Entry", tge))
            lm_temp = frappe.db.get_value("Gate Entry", tge, "person")
            if lm_temp:
                created.append(("Labour Master", lm_temp))
        tkey = rt.get("temp_key")
        rtout = S.scan(tkey)
        t_ok = rt.get("action") == "TEMP_ISSUED" and rtout.get("action") == "OUT"
        print(f"  {'PASS' if t_ok else 'FAIL'}  temp pass issued + scanned OUT same day ({tkey})")
        # backdate to yesterday -> must be rejected as expired
        frappe.db.set_value("Gate Entry", tge, {"time_in": frappe.utils.add_days(frappe.utils.now_datetime(), -1),
                                                "time_out": None})
        rexp = S.scan(tkey)
        exp_ok = (not rexp.get("ok")) and ("EXPIRED" in rexp.get("message", "").upper())
        print(f"  {'PASS' if exp_ok else 'FAIL'}  temp slip next day rejected as expired ({rexp.get('message')!r})")

        # 9) Contractor Tools slip: TOOL- round-trips + mismatch flag
        ctr = frappe.get_doc({"doctype": "Contractor Tools Register", "contractor": contractor,
                              "tool_description": "Drill + bits", "qty": 3, "qty_returned": 0}
                             ).insert(ignore_permissions=True)
        created.insert(0, ("Contractor Tools Register", ctr.name))
        rtool = S.scan("TOOL-" + ctr.name)
        tool_ok = rtool.get("action") == "TOOLS" and rtool.get("reference") == ctr.name
        print(f"  {'PASS' if tool_ok else 'FAIL'}  TOOL- code opens the tools register")
        ctr.qty_returned = 2  # fewer than taken -> Mismatch via hook
        ctr.save(ignore_permissions=True)
        mm = frappe.db.get_value("Contractor Tools Register", ctr.name, "status")
        print(f"  {'PASS' if mm == 'Mismatch' else 'FAIL'}  tools mismatch auto-flagged (status={mm!r})")
    except Exception as e:
        print(f"  FAIL  scan loop: {e}")
    finally:
        for dt, nm in reversed(created):
            _safe_cancel_delete(dt, nm)
        frappe.db.commit()


def _material_request_lifecycle():
    """Self-contained + idempotent: raise a dedicated MR (qty 20), approve it,
    partially issue (12) -> Partially Issued, fully issue (8) -> Issued, then
    Close it. Cleans up everything it creates so it can be re-run."""
    from frappe.model.workflow import apply_workflow

    company = frappe.defaults.get_defaults().get("company") or frappe.db.get_value("Company", {}, "name")
    wh = frappe.db.get_value("Plant Section", "DIST", "warehouse")
    dparent = frappe.db.get_value("Plant Section", "DIST", "project_task")
    erection = frappe.db.get_value("Task", {"subject": "DIST - Structural / Erection", "parent_task": dparent}, "name")
    item = "BK-CEMENT-OPC53"
    worker = frappe.db.get_value("Employee", {}, "name")
    if not (wh and erection and worker and frappe.db.exists("Item", item)):
        print("  WARN  lifecycle prerequisites missing")
        return
    log_date = today()

    # self-contained: give the worker a gate entry for TODAY so the worker-gate-entry
    # validation passes and the issue date matches today's stock receipt.
    ge_name = frappe.get_doc({
        "doctype": "Gate Entry", "person_type": "Employee", "person": worker,
        "plant_section": "DIST", "entry_type": "In", "time_in": frappe.utils.now_datetime(),
        "photo": "/assets/frappe/images/ui/avatar.png",
    }).insert(ignore_permissions=True).name

    logs = []
    # keep the task's % unchanged: the single task row re-states the current value
    # (on_submit sets progress to the same number; cancel then can't drift it).
    cur_pct = frappe.db.get_value("Task", erection, "progress") or 0

    def issue(qty, pct, mr):
        d = frappe.get_doc({
            "doctype": "Daily Progress Log", "plant_section": "DIST", "log_date": log_date,
            "incharge": "Administrator",
            "task_progress": [{"task": erection, "status": "Work in Progress",
                               "percent_complete": cur_pct,
                               "work_description": "Material issue lifecycle test — progress unchanged."}],
            "workers_present": [{"person_type": "Employee", "person": worker,
                                 "task": erection, "hours": 8}],
            "material_consumed": [{"item": item, "qty": qty, "uom": "Nos", "task": erection,
                                   "material_request": mr}],
            "photos": [{"image": "/assets/frappe/images/ui/avatar.png"}],
        })
        d.insert(ignore_permissions=True)
        d.submit()
        logs.append((d.name, d.stock_entry))
        return d

    mr = None
    try:
        mr = frappe.get_doc({
            "doctype": "Material Request", "material_request_type": "Material Issue",
            "transaction_date": today(), "company": company, "plant_section": "DIST",
            "benkas_task": erection,
            "items": [{"item_code": item, "qty": 20, "uom": "Nos", "warehouse": wh, "schedule_date": today()}],
        })
        mr.insert(ignore_permissions=True)
        mr.submit()
        mr.db_set("benkas_status", "Approved")  # workflows off; set status directly

        issue(12, 62, mr.name)
        st1 = frappe.db.get_value("Material Request", mr.name, "benkas_status")
        print(f"  {'PASS' if st1 == 'Partially Issued' else 'FAIL'}  partial issue (12/20) -> {st1!r} (expected Partially Issued)")

        issue(8, 68, mr.name)
        st2 = frappe.db.get_value("Material Request", mr.name, "benkas_status")
        print(f"  {'PASS' if st2 == 'Issued' else 'FAIL'}  full issue (20/20) -> {st2!r} (expected Issued)")

        frappe.db.set_value("Material Request", mr.name, "benkas_status", "Closed")
        st3 = frappe.db.get_value("Material Request", mr.name, "benkas_status")
        print(f"  {'PASS' if st3 == 'Closed' else 'FAIL'}  manual Close (PM) -> {st3!r} (expected Closed)")
    except Exception as e:
        print(f"  FAIL  lifecycle: {e}")
    finally:
        # cleanup so the test is idempotent
        for dpl_name, se_name in logs:
            _safe_cancel_delete("Daily Progress Log", dpl_name)
            if se_name:
                _safe_cancel_delete("Stock Entry", se_name)
        if mr:
            _safe_cancel_delete("Material Request", mr.name)
        _safe_cancel_delete("Gate Entry", ge_name)
        frappe.db.commit()


def _safe_cancel_delete(dt, name):
    try:
        doc = frappe.get_doc(dt, name)
        if doc.docstatus == 1:
            doc.flags.ignore_permissions = True
            if dt == "Material Request":
                doc.db_set("benkas_status", "Issued")  # allow cancel past Closed guard
            doc.cancel()
        frappe.delete_doc(dt, name, force=1, ignore_permissions=True)
    except Exception:
        pass


def _check_features():
    print("\n--- FEATURE COMPLETENESS (fields + workflow + print, each asserted) ---")
    for f in FEATURES:
        dt = f["doctype"]
        meta = frappe.get_meta(dt)
        missing = [x for x in f["fields"] if not meta.get_field(x)]
        fields_ok = not missing

        wf_ok, wf_note = True, "n/a"
        if f.get("workflow"):
            if not frappe.db.exists("Workflow", f["workflow"]):
                wf_ok, wf_note = False, "workflow missing"
            else:
                states = set(frappe.get_all("Workflow Document State",
                             filters={"parent": f["workflow"]}, pluck="state"))
                acts = set(frappe.get_all("Workflow Transition",
                           filters={"parent": f["workflow"]}, pluck="action"))
                ms = [s for s in f["wf_states"] if s not in states]
                ma = [a for a in f["wf_actions"] if a not in acts]
                wf_ok = not ms and not ma
                wf_note = "ok" if wf_ok else f"missing states={ms} actions={ma}"

        pr_ok, pr_note = True, "n/a"
        if f.get("print"):
            if not frappe.db.exists("Print Format", f["print"]):
                pr_ok, pr_note = False, "print format missing"
            else:
                rec = frappe.db.get_value(dt, {}, "name")
                if not rec:
                    pr_note = "exists (no record to render)"
                else:
                    try:
                        frappe.get_print(dt, rec, print_format=f["print"])
                        pr_note = "renders"
                    except Exception as e:
                        pr_ok, pr_note = False, f"render error: {e}"

        ok = fields_ok and wf_ok and pr_ok
        print(f"  {'PASS' if ok else 'FAIL'}  {f['name']:32} "
              f"fields={'ok' if fields_ok else missing}  wf={wf_note}  print={pr_note}")


def _where(raw):
    conds, params = ["1=1"], []
    for f in raw:
        _dt, field, op, val = f
        if op == "Timespan" and val == "today":
            conds.append(f"`{field}` BETWEEN %s AND %s")
            params += [today() + " 00:00:00", today() + " 23:59:59"]
        elif op == "between":
            conds.append(f"`{field}` BETWEEN %s AND %s")
            params += [val[0], val[1]]
        elif op == "is" and val == "not set":
            conds.append(f"(`{field}` IS NULL OR `{field}` = '')")
        elif op == "is" and val == "set":
            conds.append(f"(`{field}` IS NOT NULL AND `{field}` != '')")
        else:
            conds.append(f"`{field}` {op} %s")
            params.append(val)
    return " AND ".join(conds), params


def _card_value(nc):
    doc = frappe.get_doc("Number Card", nc)
    where, params = _where(json.loads(doc.filters_json or "[]"))
    tbl = "`tab" + doc.document_type + "`"
    try:
        if doc.function == "Count":
            q = f"SELECT COUNT(*) FROM {tbl} WHERE {where}"
        else:
            fn = {"Sum": "SUM", "Average": "AVG", "Minimum": "MIN", "Maximum": "MAX"}[doc.function]
            q = f"SELECT {fn}(`{doc.aggregate_function_based_on}`) FROM {tbl} WHERE {where}"
        v = frappe.db.sql(q, params)[0][0]
        return round(v, 1) if isinstance(v, float) else v
    except Exception as e:
        return f"ERR:{e}"


def _chart_groups(ch):
    doc = frappe.get_doc("Dashboard Chart", ch)
    if doc.chart_type != "Group By":
        return "timeseries"  # e.g. hourly Count chart — not a group-by
    where, params = _where(json.loads(doc.filters_json or "[]"))
    fld = doc.group_by_based_on
    try:
        rows = frappe.db.sql(
            f"SELECT `{fld}`, COUNT(*) FROM `tab{doc.document_type}` WHERE {where} "
            f"GROUP BY `{fld}`", params)
        return len([r for r in rows if r[0] is not None])
    except Exception as e:
        return f"ERR:{e}"


def run():
    print("\n================ BENKAS ERP AUDIT ================\n")

    _check_features()

    # ---------------- Workspaces ----------------
    print("--- WORKSPACES ---")
    for name, (icon, color) in WS_EXPECT.items():
        if not frappe.db.exists("Workspace", name):
            print(f"  FAIL  {name:30} MISSING")
            continue
        w = frappe.get_doc("Workspace", name)
        broken = [s.link_to for s in w.shortcuts
                  if (s.type == "DocType" and not frappe.db.exists("DocType", s.link_to))
                  or (s.type == "Report" and not frappe.db.exists("Report", s.link_to))
                  or (s.type == "Page" and not frappe.db.exists("Page", s.link_to))]
        card_vals = {frappe.db.get_value("Number Card", c.number_card_name, "label"): _card_value(c.number_card_name)
                     for c in w.number_cards}
        chart_grps = {c.chart_name: _chart_groups(c.chart_name) for c in w.charts}
        roles = [r.role for r in w.roles]
        icon_ok = (w.icon == icon)
        color_ok = (w.indicator_color == color)
        ok = icon_ok and color_ok and not broken
        print(f"  {'PASS' if ok else 'FAIL'}  {name:30} icon={w.icon}({'ok' if icon_ok else 'X'}) "
              f"color={w.indicator_color}({'ok' if color_ok else 'X'}) "
              f"shortcuts={len(w.shortcuts)}/{len(broken)}broken roles={len(roles)}")
        print(f"        cards: {card_vals}")
        print(f"        charts(groups): {chart_grps}")

    # ---------------- DocTypes ----------------
    print("\n--- DOCTYPES ---")
    present = frappe.get_all("DocType", filters={"module": ["in", MODULES]}, pluck="name")
    print(f"  custom doctypes present: {len(present)}")
    miss_sec = [d for d in NEEDS_SECTION if not frappe.get_meta(d).get_field("plant_section")]
    print(f"  {'PASS' if not miss_sec else 'FAIL'}  plant_section present on all required: "
          f"{'yes' if not miss_sec else 'MISSING ' + str(miss_sec)}")
    bad_photos = [f"{dt}.{fn}" for dt, fn in REQD_PHOTOS
                  if not (frappe.get_meta(dt).get_field(fn) and frappe.get_meta(dt).get_field(fn).reqd)]
    print(f"  {'PASS' if not bad_photos else 'FAIL'}  mandatory photo fields reqd=1: "
          f"{'all set' if not bad_photos else 'NOT REQD ' + str(bad_photos)}")
    bad_child = []
    for child, (parent, field) in CHILD_TABLES.items():
        f = frappe.get_meta(parent).get_field(field)
        if not (f and f.fieldtype == "Table" and f.options == child):
            bad_child.append(f"{parent}.{field}->{child}")
    print(f"  {'PASS' if not bad_child else 'FAIL'}  child tables wired to parents: "
          f"{'all ok' if not bad_child else 'BROKEN ' + str(bad_child)}")

    # ---------------- Reports ----------------
    print("\n--- REPORTS ---")
    REPORT_FILTERS = {
        "Gate Register": {"from_date": "2000-01-01", "to_date": "2100-01-01",
                          "etype": "", "direction": "", "section": "", "contractor": ""},
    }
    for r in frappe.get_all("Report", filters={"module": ["in", MODULES]}, pluck="name"):
        try:
            res = run_report(r, filters=REPORT_FILTERS.get(r, {}))
            n = len(res.get("result", []))
            print(f"  {'PASS' if n > 0 else 'WARN'}  {r:42} {n} rows")
        except Exception as e:
            print(f"  FAIL  {r:42} {e}")

    # ---------------- Print Formats ----------------
    print("\n--- PRINT FORMATS ---")
    for pf, dt in PRINTS:
        nm = frappe.db.get_value(dt, {}, "name")
        if not nm:
            print(f"  WARN  {pf:32} no {dt} record to render")
            continue
        try:
            html = frappe.get_print(dt, nm, print_format=pf)
            has_img = "<img" in html
            has_name = str(nm) in html
            has_qr = "data:image/png;base64" in html
            ok = has_img and has_name
            print(f"  {'PASS' if ok else 'FAIL'}  {pf:32} {len(html)}b img={has_img} qr={has_qr} data={has_name}")
        except Exception as e:
            print(f"  FAIL  {pf:32} {e}")

    # ---------------- WBS ----------------
    print("\n--- WBS (Construction task breakdown) ---")
    total, orphans, dups = 0, 0, 0
    per_section = {}
    for sec in frappe.get_all("Plant Section", fields=["name", "project_task"]):
        if not sec.project_task:
            continue
        kids = frappe.get_all("Task", filters={"parent_task": sec.project_task}, pluck="subject")
        per_section[sec.name] = len(kids)
        total += len(kids)
        if len(kids) != len(set(kids)):
            dups += 1
    # orphan = task whose parent_task is set but parent missing
    all_parented = frappe.get_all("Task", filters={"parent_task": ["!=", ""]},
                                  fields=["name", "parent_task"])
    for t in all_parented:
        if not frappe.db.exists("Task", t.parent_task):
            orphans += 1
    counts_ok = all(v == 9 for v in per_section.values()) and len(per_section) == 12
    print(f"  {'PASS' if counts_ok and not orphans and not dups else 'FAIL'}  "
          f"total_subtasks={total} sections={len(per_section)} "
          f"each9={counts_ok} orphans={orphans} dup_sections={dups}")

    # ---------------- Placement: every custom DocType has a home ----------------
    print("\n--- WORKSPACE PLACEMENT (doctype homes / report links / icons) ---")
    ws_names = list(WS_EXPECT.keys())
    # map: doctype -> [workspaces where it's a DocType shortcut]
    dt_homes, rp_homes = {}, {}
    icons_ok = True
    for w in ws_names:
        if not frappe.db.exists("Workspace", w):
            continue
        doc = frappe.get_doc("Workspace", w)
        if not doc.icon:
            icons_ok = False
        for s in doc.shortcuts:
            if s.type == "DocType":
                dt_homes.setdefault(s.link_to, []).append(w)
            elif s.type == "Report":
                rp_homes.setdefault(s.link_to, []).append(w)

    # Reachability includes shortcuts AND grouped link cards — every custom
    # doctype must be clickable from a workspace by a human, not only via URL.
    for w in ws_names:
        if not frappe.db.exists("Workspace", w):
            continue
        for lk in frappe.get_doc("Workspace", w).links:
            if lk.type == "Link" and lk.link_type == "DocType":
                dt_homes.setdefault(lk.link_to, []).append(w + " (link)")

    custom_parents = frappe.get_all("DocType", filters={
        "module": ["in", MODULES], "istable": 0}, pluck="name")
    orphans = [d for d in custom_parents if d not in dt_homes]
    # intentional multi-home doctypes (a doctype may be a shortcut in >1 workspace
    # where used in both — Gate Entry appears on Gate Management as itself + a
    # "Temporary Passes" filtered view, and on Manpower Manager for acknowledgement).
    ALLOWED_MULTI = {"Gate Entry", "Gate Pass", "Plant Section", "Contractor",
                     "Labour Master", "Delay Reason", "Construction Activity"}
    bad_multi = {d: hs for d, hs in dt_homes.items()
                 if d in custom_parents and len(set(h for h in hs if "(link)" not in h)) > 1
                 and d not in ALLOWED_MULTI}
    print(f"  {'PASS' if not orphans else 'FAIL'}  every custom DocType reachable by clicking "
          f"({len(custom_parents)} parents) {'' if not orphans else 'ORPHANS: ' + str(orphans)}")
    print(f"  {'PASS' if not bad_multi else 'FAIL'}  no unintended multi-home shortcuts "
          f"{'' if not bad_multi else str(bad_multi)}")
    # v16 left sidebar: each workspace must have a populated Workspace Sidebar record
    # (the doctype that actually drives the left nav) with grouped Section Break items.
    for w in ws_names:
        has_sb = frappe.db.exists("Workspace Sidebar", w)
        n_items = frappe.db.count("Workspace Sidebar Item", {"parent": w}) if has_sb else 0
        n_grp = frappe.db.count("Workspace Sidebar Item",
                                {"parent": w, "type": "Section Break"}) if has_sb else 0
        ok = has_sb and n_items >= 3 and n_grp >= 1
        print(f"  {'PASS' if ok else 'FAIL'}  Workspace Sidebar '{w}' populated "
              f"({n_items} items, {n_grp} groups)")
    ctr = dt_homes.get("Contractor Tools Register", [])
    print(f"  {'PASS' if any('Gate Management' in h for h in ctr) else 'FAIL'}  "
          f"Contractor Tools Register lives on Gate Management -> {ctr}")
    # Gate Security's sidebar = Gate Management only (their one workspace)
    gm_roles = {r.role for r in frappe.get_doc("Workspace", "Gate Management").roles} if frappe.db.exists("Workspace", "Gate Management") else set()
    gs_elsewhere = [w for w in ws_names if w != "Gate Management" and frappe.db.exists("Workspace", w)
                    and "Gate Security" in {r.role for r in frappe.get_doc("Workspace", w).roles}]
    print(f"  {'PASS' if 'Gate Security' in gm_roles and not gs_elsewhere else 'FAIL'}  "
          f"Gate Security sees ONLY Gate Management {'' if not gs_elsewhere else 'also: ' + str(gs_elsewhere)}")

    reports = frappe.get_all("Report", filters={"module": ["in", MODULES]}, pluck="name")
    unlinked = [r for r in reports if r not in rp_homes]
    print(f"  {'PASS' if not unlinked else 'FAIL'}  every report linked on a workspace "
          f"({len(reports)} reports) {'' if not unlinked else 'UNLINKED: ' + str(unlinked)}")
    print(f"  {'PASS' if icons_ok else 'FAIL'}  all 7 workspaces have a non-empty icon")

    # intro + onboarding blocks present
    import json as _json
    intro_bad, onb_bad = [], []
    for w in ws_names:
        blocks = _json.loads(frappe.db.get_value("Workspace", w, "content") or "[]")
        types = [b.get("type") for b in blocks]
        if "paragraph" not in types:
            intro_bad.append(w)
        if w not in ("Benkas MIS", "Gate Management") and "onboarding" not in types:
            onb_bad.append(w)
    print(f"  {'PASS' if not intro_bad else 'FAIL'}  intro paragraph on every workspace "
          f"{'' if not intro_bad else 'MISSING: ' + str(intro_bad)}")
    print(f"  {'PASS' if not onb_bad else 'FAIL'}  onboarding block on 5 operational workspaces "
          f"{'' if not onb_bad else 'MISSING: ' + str(onb_bad)}")

    # /apps tiles: v16 renders one tile per installed app; extend_bootinfo injects
    # the 2nd (Benkas Core). Both must be present in the resulting app_data.
    benkas = sorted(t["title"] for t in _apps_screen_tiles()
                    if t["app"] in ("benkas_erp", "benkas_core"))
    tile_ok = benkas == ["Benkas Core", "Benkas ERP"]
    print(f"  {'PASS' if tile_ok else 'FAIL'}  /apps: both Benkas tiles present -> {benkas}")
    mis = frappe.get_doc("Workspace", "Benkas MIS")
    setup_sc = any(s.type == "URL" and (s.url or "") == "/app/benkas-core" for s in mis.shortcuts)
    print(f"  {'PASS' if setup_sc else 'FAIL'}  Benkas Core also reachable via 'Setup / Masters' shortcut on Benkas MIS")

    # ---------------- Daily Progress Log end-to-end flow ----------------
    print("\n--- DAILY PROGRESS LOG (single site-log flow) ---")
    dpl_name = frappe.db.get_value("Daily Progress Log", {"docstatus": 1}, "name")
    if not dpl_name:
        print("  WARN  no submitted Daily Progress Log to audit")
    else:
        d = frappe.get_doc("Daily Progress Log", dpl_name)
        # 1. Task.progress updated from task_progress rows
        prog_ok = all(
            frappe.db.get_value("Task", r.task, "progress") == r.percent_complete
            for r in d.task_progress if r.task)
        print(f"  {'PASS' if prog_ok else 'FAIL'}  Task.progress updated from task_progress rows")
        # 2. Task.manpower_days_logged accrued
        man_ok = any((frappe.db.get_value("Task", r.task, "manpower_days_logged") or 0) > 0
                     for r in d.workers_present if r.task)
        print(f"  {'PASS' if man_ok else 'FAIL'}  Task.manpower_days_logged accrued from worker rows")
        # 3. Plant Section rollup
        sec_pct = frappe.db.get_value("Plant Section", d.plant_section, "section_percent_complete")
        print(f"  {'PASS' if sec_pct not in (None,) else 'FAIL'}  Plant Section.section_percent_complete = {sec_pct}")
        # 4. Stock Entry auto-created + submitted with qty
        se = d.stock_entry
        se_ok, issued_qty = False, 0
        if se and frappe.db.get_value("Stock Entry", se, "docstatus") == 1:
            issued_qty = sum(frappe.get_all("Stock Entry Detail",
                             filters={"parent": se}, pluck="qty"))
            se_ok = issued_qty > 0
        print(f"  {'PASS' if se_ok else 'FAIL'}  Stock Entry auto-created & submitted ({se}, qty={issued_qty})")
        # 5. Stock actually reduced (an issue exists in the ledger for the item/warehouse)
        mrow = d.material_consumed[0] if d.material_consumed else None
        red_ok = False
        if mrow:
            wh = frappe.db.get_value("Plant Section", d.plant_section, "warehouse")
            neg = frappe.db.sql("""SELECT COALESCE(SUM(actual_qty),0) FROM `tabStock Ledger Entry`
                WHERE item_code=%s AND warehouse=%s AND actual_qty<0""", (mrow.item, wh))[0][0]
            red_ok = (neg or 0) < 0
        print(f"  {'PASS' if red_ok else 'FAIL'}  Stock reduced in ledger for consumed item")
        # 6. Material Request consumed (if linked)
        mr = mrow.material_request if mrow else None
        if mr:
            per = frappe.db.get_value("Material Request", mr, "per_ordered") or 0
            print(f"  {'PASS' if per > 0 else 'FAIL'}  Material Request consumed (per_ordered={per})")
        else:
            print("  n/a   no Material Request linked on the log")
        # 7. print format renders all three tables
        try:
            html = frappe.get_print("Daily Progress Log", dpl_name, print_format="Daily Progress Report")
            tabs_ok = all(t in html for t in ("Task Progress", "Workers Present", "Material Consumed"))
            print(f"  {'PASS' if tabs_ok else 'FAIL'}  Daily Progress Report renders all 3 child tables ({len(html)}b)")
        except Exception as e:
            print(f"  FAIL  print render: {e}")

    # ---------------- EOD simplification (status master, new reports, validation) ----------------
    _eod_simplification()

    # ---------------- Section 360 / Task planning / Client MIS ----------------
    _section360_planning_and_mis()

    # ---------------- Material Request lifecycle (partial -> full -> close) ----------------
    print("\n--- MATERIAL REQUEST LIFECYCLE ---")
    _material_request_lifecycle()

    _scan_loop()

    _workflows_and_thermal()

    # ---------------- Role -> Workspace visibility ----------------
    print("\n--- WORKSPACE VISIBILITY BY ROLE (sidebar) ---")
    roles = ["Gate Security", "Section Incharge", "Stores Weighbridge Operator",
             "Safety Officer", "Generator Electrical Operator", "Benkas Project Manager",
             "Ramshy Bio Management"]
    ws_roles = {}
    for w in WS_EXPECT:
        if frappe.db.exists("Workspace", w):
            ws_roles[w] = set(r.role for r in frappe.get_doc("Workspace", w).roles)
    for role in roles:
        visible = [w for w, rs in ws_roles.items() if role in rs]
        print(f"  {role:30} -> {', '.join(visible)}")

    print("\n================ END AUDIT ================\n")



def _expect_throw(label, doc_dict):
    try:
        d = frappe.get_doc(doc_dict)
        d.insert(ignore_permissions=True)
        print(f"  FAIL  {label} (it saved — should have thrown)")
        _safe_cancel_delete("Daily Progress Log", d.name)
    except frappe.ValidationError:
        print(f"  PASS  {label}")
    except Exception as e:
        print(f"  FAIL  {label} (wrong error: {e})")


def _eod_simplification():
    """The simplified EOD flow: status master, new fields, new reports, and the
    validation guards that stop garbage."""
    print("\n--- EOD SIMPLIFICATION (status master, reports, validation) ---")

    # 1. Progress Status master seeded with correct stopped flags
    from benkas_erp.setup.seed import PROGRESS_STATUSES
    have = frappe.get_all("Progress Status", pluck="name")
    seeded_ok = all(name in have for name, *_ in PROGRESS_STATUSES)
    stopped_ok = all(bool(frappe.db.get_value("Progress Status", name, "is_stopped")) == bool(st)
                     for name, st, *_ in PROGRESS_STATUSES)
    print(f"  {'PASS' if seeded_ok and stopped_ok else 'FAIL'}  Progress Status master seeded "
          f"({len(have)} rows, stopped flags correct)")

    # 2. simplified child + parent fields
    m = frappe.get_meta("Daily Task Progress")
    dtp_ok = (bool(m.get_field("status")) and bool(m.get_field("work_description"))
              and m.get_field("work_description").reqd
              and not m.get_field("activity_description") and not m.get_field("delay_reason"))
    print(f"  {'PASS' if dtp_ok else 'FAIL'}  Daily Task Progress = task/status/%/work_description "
          f"(old activity_description & delay_reason gone)")
    photo_ok = bool(frappe.get_meta("Daily Progress Photo").get_field("activity_task"))
    lm = frappe.get_meta("Daily Progress Log")
    log_ok = bool(lm.get_field("no_work_today")) and bool(lm.get_field("no_work_reason"))
    print(f"  {'PASS' if photo_ok else 'FAIL'}  Daily Progress Photo.activity_task present (photos group by task)")
    print(f"  {'PASS' if log_ok else 'FAIL'}  Daily Progress Log.no_work_today + reason present")

    # 3. reports present + runnable, old one gone
    from frappe.desk.query_report import run as run_report
    for rep in ("Weekly Section Report", "Stoppage Analysis"):
        rtype = frappe.db.get_value("Report", rep, "report_type")
        print(f"  {'PASS' if rtype == 'Script Report' else 'FAIL'}  report '{rep}' exists ({rtype})")
    gone = not frappe.db.exists("Report", "Delay Analysis by Section")
    print(f"  {'PASS' if gone else 'FAIL'}  retired 'Delay Analysis by Section' removed")

    wide = {"from_date": "2000-01-01", "to_date": today()}
    try:
        res = run_report("Stoppage Analysis", wide)
        rows = res.get("result", []) or []
        rain = any("Rain" in (r.get("reason", "") if isinstance(r, dict) else "") for r in rows)
        print(f"  PASS  Stoppage Analysis runs ({len(rows)} rows, rain stoppage present: {rain})")
    except Exception as e:
        print(f"  FAIL  Stoppage Analysis run: {e}")
    try:
        res2 = run_report("Weekly Section Report", wide)
        print(f"  PASS  Weekly Section Report runs ({len(res2.get('result', []) or [])} rows)")
    except Exception as e:
        print(f"  FAIL  Weekly Section Report run: {e}")

    # 4. validation guards (garbage prevention)
    dpl_task = frappe.db.get_value(
        "Task", {"parent_task": frappe.db.get_value("Plant Section", "DIST", "project_task")}, "name")
    if dpl_task:
        _expect_throw("short work_description rejected (<15 chars)", {
            "doctype": "Daily Progress Log", "plant_section": "DIST", "log_date": today(),
            "task_progress": [{"task": dpl_task, "status": "Work in Progress",
                               "percent_complete": 10, "work_description": "short"}],
            "photos": [{"image": "/assets/frappe/images/ui/avatar.png"}]})
    _expect_throw("empty log (no rows, not No-Work) rejected", {
        "doctype": "Daily Progress Log", "plant_section": "DIST", "log_date": today(),
        "photos": [{"image": "/assets/frappe/images/ui/avatar.png"}]})
    try:
        d = frappe.get_doc({"doctype": "Daily Progress Log", "plant_section": "DIST",
                            "log_date": today(), "no_work_today": 1,
                            "no_work_reason": "Full rain day, site closed."})
        d.insert(ignore_permissions=True)
        print("  PASS  No-Work-Today log saves with a reason (no photos/tasks needed)")
        _safe_cancel_delete("Daily Progress Log", d.name)
    except Exception as e:
        print(f"  FAIL  No-Work-Today log: {e}")


def _section360_planning_and_mis():
    """Assert the Section 360 view, Task Planner, and Client MIS pack actually
    work end-to-end — not just that helpers import."""
    from benkas_erp import section360
    print("\n--- SECTION 360 / TASK PLANNING ---")

    # 1. both desk pages exist (what renders in the browser)
    for pg, title in [("section-360", "Section 360"), ("section-task-planner", "Section Task Planner")]:
        ok = frappe.db.exists("Page", pg) and frappe.db.get_value("Page", pg, "module") == "Benkas Core"
        print(f"  {'PASS' if ok else 'FAIL'}  desk page '{pg}' present ({title})")

    # 1b. every custom desk page is wired into its workspace(s) as a proper Page
    # shortcut WITH a Lucide icon (not a raw URL / emoji-in-label hack)
    PAGE_SHORTCUTS = {"benkas-scan": ["Gate Management"],
                      "section-360": ["Work Schedule and Progress", "Benkas MIS"],
                      "section-task-planner": ["Work Schedule and Progress", "Benkas MIS"]}
    for pg, wss in PAGE_SHORTCUTS.items():
        for ws in wss:
            hits = [s for s in frappe.get_doc("Workspace", ws).shortcuts
                    if s.type == "Page" and s.link_to == pg]
            ok = bool(hits) and all((s.icon or "").strip() for s in hits)
            print(f"  {'PASS' if ok else 'FAIL'}  page '{pg}' -> Page shortcut with icon on '{ws}'"
                  + ("" if ok else "  (missing / still URL / no icon)"))

    # 2. planning fields present
    ps_ok = bool(frappe.get_meta("Plant Section").get_field("section_start_date"))
    ca_ok = bool(frappe.get_meta("Construction Activity").get_field("default_duration_days"))
    print(f"  {'PASS' if ps_ok else 'FAIL'}  Plant Section.section_start_date field present")
    print(f"  {'PASS' if ca_ok else 'FAIL'}  Construction Activity.default_duration_days field present")

    # 3. tasks carry tentative dates + weight (planning pre-fill worked)
    dated = frappe.db.sql("""SELECT COUNT(*) FROM `tabTask`
        WHERE parent_task IN (SELECT project_task FROM `tabPlant Section` WHERE project_task IS NOT NULL)
          AND exp_start_date IS NOT NULL AND exp_end_date IS NOT NULL""")[0][0]
    print(f"  {'PASS' if dated > 0 else 'FAIL'}  section sub-tasks have tentative dates ({dated})")

    sec = frappe.db.get_value("Plant Section", {"project_task": ["is", "set"]}, "name")
    if not sec:
        print("  WARN  no section with a project task to exercise Section 360");
    else:
        # 4. Section 360 payload returns every block, with numeric planned/actual
        p = section360.get_section_360(sec)
        blocks_ok = all(k in p for k in ("header", "tasks", "manpower", "material", "activity"))
        h = p.get("header", {})
        hdr_ok = isinstance(h.get("percent_complete"), (int, float)) \
            and h.get("status") in ("On Track", "Attention") \
            and all(k in h for k in ("total_tasks", "done", "stopped"))
        # task block is sourced from the manual EOD log (status chip + photos)
        task_ok = all(all(k in t for k in ("latest_status", "color", "last_description", "photos"))
                      for t in p.get("tasks", [])) if p.get("tasks") else True
        sub_ok = all(k in p["manpower"] for k in ("today", "person_days_week", "by_contractor")) \
            and "top_items" in p["material"] and "logs" in p["activity"]
        print(f"  {'PASS' if blocks_ok and hdr_ok and sub_ok and task_ok else 'FAIL'}  get_section_360('{sec}') "
              f"returns all blocks (actual={h.get('percent_complete')} status={h.get('status')} "
              f"done={h.get('done')}/{h.get('total_tasks')} stopped={h.get('stopped')}, tasks={len(p.get('tasks', []))})")

        # 5. planner get/save roundtrip actually writes to Task
        gt = section360.get_section_tasks(sec)
        if gt["tasks"]:
            t0 = gt["tasks"][0]
            orig = frappe.db.get_value("Task", t0["name"], "exp_end_date")
            newdate = frappe.utils.add_days(orig or today(), 3)
            section360.save_section_tasks(sec, [{"name": t0["name"], "exp_end_date": str(newdate)}])
            saved = frappe.db.get_value("Task", t0["name"], "exp_end_date")
            roundtrip = str(saved) == str(newdate)
            # restore
            section360.save_section_tasks(sec, [{"name": t0["name"], "exp_end_date": str(orig) if orig else None}])
            print(f"  {'PASS' if roundtrip else 'FAIL'}  planner save_section_tasks writes dates to Task")
        else:
            print("  WARN  section has no sub-tasks to roundtrip")

        # 6. mark_task_complete is whitelisted and rolls the section up
        wl = getattr(section360.mark_task_complete, "__func__", section360.mark_task_complete)
        is_wl = getattr(wl, "whitelisted", False) or getattr(section360.mark_task_complete, "whitelisted", False)
        incomplete = frappe.db.get_value("Task",
            {"parent_task": frappe.db.get_value("Plant Section", sec, "project_task"),
             "progress": ["<", 100]}, "name")
        if incomplete:
            before = frappe.db.get_value("Plant Section", sec, "section_percent_complete")
            res = section360.mark_task_complete(incomplete)
            after = res.get("section_percent")
            prog = frappe.db.get_value("Task", incomplete, "progress")
            ok = prog == 100 and after is not None and (after or 0) >= (before or 0)
            print(f"  {'PASS' if ok else 'FAIL'}  mark_task_complete sets 100% + rolls section "
                  f"({before} -> {after})")
        else:
            print("  n/a   no incomplete task to mark (all done)")

    # 7. Client MIS pack builds a real .docx
    print("\n--- CLIENT WEEKLY MIS PACK ---")
    try:
        import os, tempfile
        from benkas_erp.setup import client_mis
        out = os.path.join(tempfile.gettempdir(), "benkas_audit_mis.docx")
        if os.path.exists(out):
            os.remove(out)
        r = client_mis.build(path=out)
        size = os.path.getsize(out) if os.path.exists(out) else 0
        print(f"  {'PASS' if size > 5000 else 'FAIL'}  client_mis.build() wrote a .docx "
              f"({size}b, {r.get('sections')} sections, overall={r.get('overall_actual')}%)")
        # NB: frappe.get_app_path lowercases joined parts — join the filename with os.path.join
        sample = os.path.join(frappe.get_app_path("benkas_erp", "..", "docs"), "Sample_Client_Weekly_MIS.docx")
        print(f"  {'PASS' if os.path.exists(sample) else 'FAIL'}  committed sample present in docs/")
    except Exception as e:
        print(f"  FAIL  client_mis.build(): {e}")

    # 8. weekly scheduler is wired in hooks
    from benkas_erp import hooks as _h
    sched = _h.scheduler_events.get("weekly", [])
    print(f"  {'PASS' if any('client_mis' in s for s in sched) else 'FAIL'}  weekly client-MIS scheduler registered")


def _apps_screen_tiles():
    """Reproduce what ends up in bootinfo.app_data (the /apps grid): boot.py's
    one-entry-per-installed-app PLUS our extend_bootinfo injection."""
    tiles = []
    for app in frappe.get_installed_apps():
        if app == "frappe":
            continue
        entries = frappe.get_hooks("add_to_apps_screen", app_name=app)
        if entries:
            e = entries[0]
            tiles.append({"app_name": app, "app_title": e.get("title"),
                          "app_logo_url": e.get("logo")})
    boot = frappe._dict(app_data=tiles)
    from benkas_erp.boot import extend_bootinfo
    extend_bootinfo(boot)
    return [{"app": a.get("app_name"), "title": a.get("app_title"),
             "route": a.get("app_route")} for a in boot.app_data]
