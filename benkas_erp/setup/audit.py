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
    "Benkas Core": ("setting", "gray"),
    "Benkas MIS": ("dashboard", "purple"),
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
