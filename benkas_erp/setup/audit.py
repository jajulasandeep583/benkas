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

    # ---------------- Workspaces ----------------
    print("--- WORKSPACES ---")
    for name, (icon, color) in WS_EXPECT.items():
        if not frappe.db.exists("Workspace", name):
            print(f"  FAIL  {name:30} MISSING")
            continue
        w = frappe.get_doc("Workspace", name)
        broken = [s.link_to for s in w.shortcuts
                  if (s.type == "DocType" and not frappe.db.exists("DocType", s.link_to))
                  or (s.type == "Report" and not frappe.db.exists("Report", s.link_to))]
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
    for r in frappe.get_all("Report", filters={"module": ["in", MODULES]}, pluck="name"):
        try:
            res = run_report(r, filters={})
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

    custom_parents = frappe.get_all("DocType", filters={
        "module": ["in", MODULES], "istable": 0}, pluck="name")
    orphans = [d for d in custom_parents if d not in dt_homes]
    multi = {d: hs for d, hs in dt_homes.items() if d in custom_parents and len(hs) > 1}
    print(f"  {'PASS' if not orphans else 'FAIL'}  every custom DocType has a home shortcut "
          f"({len(custom_parents)} parents) {'' if not orphans else 'ORPHANS: ' + str(orphans)}")
    print(f"  {'PASS' if not multi else 'FAIL'}  each custom DocType home is exactly one workspace "
          f"{'' if not multi else 'MULTI: ' + str(multi)}")

    reports = frappe.get_all("Report", filters={"module": ["in", MODULES]}, pluck="name")
    unlinked = [r for r in reports if r not in rp_homes]
    print(f"  {'PASS' if not unlinked else 'FAIL'}  every report linked on a workspace "
          f"({len(reports)} reports) {'' if not unlinked else 'UNLINKED: ' + str(unlinked)}")
    print(f"  {'PASS' if icons_ok else 'FAIL'}  all 6 workspaces have a non-empty icon")

    # intro + onboarding blocks present
    import json as _json
    intro_bad, onb_bad = [], []
    for w in ws_names:
        blocks = _json.loads(frappe.db.get_value("Workspace", w, "content") or "[]")
        types = [b.get("type") for b in blocks]
        if "paragraph" not in types:
            intro_bad.append(w)
        if w != "Benkas MIS" and "onboarding" not in types:
            onb_bad.append(w)
    print(f"  {'PASS' if not intro_bad else 'FAIL'}  intro paragraph on every workspace "
          f"{'' if not intro_bad else 'MISSING: ' + str(intro_bad)}")
    print(f"  {'PASS' if not onb_bad else 'FAIL'}  onboarding block on 5 operational workspaces "
          f"{'' if not onb_bad else 'MISSING: ' + str(onb_bad)}")

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
