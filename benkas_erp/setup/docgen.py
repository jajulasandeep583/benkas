"""
Generate / refresh the Benkas ERP Word documentation from the LIVE app.

Introspects DocTypes, fields, custom fields, workflows, roles, reports and
current record counts, then writes a formatted .docx. Re-run any time the app
changes to keep the document in sync.

    bench --site <site> execute benkas_erp.setup.docgen.build
"""

import frappe
from datetime import datetime

MODULES = ["Benkas Core", "Manpower", "Material", "Work Schedule", "Site Safety Assets"]
STD_DOCTYPES = ["Purchase Receipt", "Stock Entry", "Employee", "Quality Inspection"]

WIN_OUT = "/mnt/c/Users/jajul/Downloads/Benkas_ERP_System_Documentation.docx"

CHANGELOG = [
    ("2026-07-06", "Daily Progress Log -> single end-to-end site log", [
        "Restructured Daily Progress Log into one submittable site log per section/day "
        "with 3 child tables: Task Progress, Workers Present, Material Consumed.",
        "On submit (server-side): pushes % onto each Task.progress, accrues manpower-days, "
        "batches all material rows into ONE auto-submitted Stock Entry (Material Issue), "
        "consumes against a linked Material Request (flags rows with no MR), and recomputes "
        "Plant Section % complete.",
        "validate: >=1 photo; every worker must have a matching Gate Entry (In) for the "
        "section/date; else the log is blocked (audit-proof manpower).",
        "Fully REST-creatable (header + 3 tables + photos in one POST) — all logic is "
        "server-side hooks so a PWA client gets identical guarantees.",
        "Re-pointed Section Progress & Delay Analysis reports and the Delay Reasons chart "
        "to the new child tables; fixed workspace icons to valid Lucide names.",
    ]),
    ("2026-07-06", "Workspaces, reports & WBS expansion", [
        "Split navigation into 6 role-scoped workspaces (5 module + Benkas MIS exec view) with icons.",
        "Added 7 more MIS reports (Contractor labour, Late/OT, Stock Balance, QC Rejection, "
        "Delay Analysis, Section WBS Progress, Safety-by-Contractor) — 13 total.",
        "Added number cards + group-by charts across workspaces.",
        "Added Construction Activity master + per-section Work Breakdown Structure "
        "(civil→erection→wiring→installation→testing→commissioning); 108 sub-tasks generated.",
        "Added stage-wise print formats: Gate Entry Slip, Gate Pass, Visitor Slip, "
        "Safety/Electrical Work Permit, Daily Progress Report (+ ID cards).",
    ]),
    ("2026-07-06", "Initial build", [
        "Scaffolded custom app `benkas_erp` on ERPNext v16 + HRMS (site benkas.local).",
        "Created 5 modules and 22 custom DocTypes (code-first JSON).",
        "Added custom fields to Purchase Receipt, Stock Entry, Employee, Quality Inspection.",
        "Created 4 approval workflows, 7 roles with permissions, 6 MIS query reports.",
        "Built 'Benkas MIS' workspace with 4 number cards + headcount chart.",
        "Added validation/rollup hooks and an overdue-gate-pass scheduler.",
        "Seeded company, 12 Plant Sections (Warehouse+Task+Cost Center), delay reasons.",
        "Loaded UAT dummy data and passed end-to-end self-test (reports, workflow, validations).",
    ]),
]


def _p(doc, text, style=None, bold=False, size=None):
    from docx.shared import Pt
    para = doc.add_paragraph(style=style)
    run = para.add_run(text)
    run.bold = bold
    if size:
        run.font.size = Pt(size)
    return para


def _table(doc, headers, rows):
    from docx.shared import Pt
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = str(h)
        for para in c.paragraphs:
            for run in para.runs:
                run.bold = True
                run.font.size = Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if v is None else str(v)
            for para in cells[i].paragraphs:
                for run in para.runs:
                    run.font.size = Pt(9)
    return t


def _fields_rows(dt):
    rows = []
    for f in frappe.get_meta(dt).fields:
        if f.fieldtype in ("Section Break", "Column Break", "Tab Break"):
            continue
        flags = []
        if f.reqd:
            flags.append("required")
        if f.read_only:
            flags.append("read-only")
        if f.unique:
            flags.append("unique")
        rows.append([f.fieldname, f.label, f.fieldtype,
                     f.options or "", ", ".join(flags)])
    return rows


def build(path=None):
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # ---- Title page ----
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("Benkas ERP")
    r.bold = True
    r.font.size = Pt(30)
    r.font.color.rgb = RGBColor(0x16, 0x32, 0x4F)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = sub.add_run("Ethanol Plant Project Monitoring, Manpower & Material Management System")
    rs.font.size = Pt(13)
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(
        f"Custom app on ERPNext v16 + HRMS  |  Ramshy Bio Pvt. Ltd.  |  "
        f"Generated {datetime.now():%d %b %Y %H:%M}"
    ).font.size = Pt(10)
    doc.add_page_break()

    # ---- 1. Overview ----
    doc.add_heading("1. Solution Overview", level=1)
    _p(doc, "Benkas ERP (app: benkas_erp) is a custom Frappe/ERPNext v16 application that "
            "digitises Benkas Engineering's project-monitoring scope for the Ramshy Bio "
            "ethanol plant construction: manpower, material, work-schedule/MIS, and "
            "visitor/asset/utility/safety tracking. It is installed on top of standard "
            "ERPNext + HRMS and reuses standard components (Warehouse, Project/Task, "
            "Purchase Receipt, Quality Inspection, Stock Entry, Employee, Workflow, "
            "Dashboard) wherever possible, adding custom DocTypes only where ERPNext has "
            "no equivalent. Everything is code-first: DocTypes, custom fields, workflows, "
            "roles, reports and the dashboard are all reproduced from code on install/migrate "
            "— nothing is hand-configured in the site.")

    doc.add_heading("Environment & Access", level=2)
    _table(doc, ["Item", "Value"], [
        ["Site", "benkas.local"],
        ["URL (local)", "http://localhost:8003"],
        ["Login", "Administrator / admin"],
        ["Apps installed", ", ".join(frappe.get_installed_apps())],
        ["Company", frappe.db.get_value("Company", {}, "name") or "-"],
        ["Custom app", "benkas_erp (module folders: benkas_core, manpower, material, "
                       "work_schedule, site_safety_assets)"],
    ])

    # ---- 2. Modules & DocTypes ----
    doc.add_heading("2. Modules & Custom DocTypes", level=1)
    for m in MODULES:
        parents = frappe.get_all("DocType", filters={"module": m, "istable": 0},
                                 pluck="name", order_by="name")
        children = frappe.get_all("DocType", filters={"module": m, "istable": 1},
                                  pluck="name", order_by="name")
        if not parents and not children:
            continue
        doc.add_heading(f"Module: {m}", level=2)
        if parents:
            _p(doc, "Documents: " + ", ".join(parents))
        if children:
            _p(doc, "Child tables: " + ", ".join(children))

    # ---- 3. DocType field reference ----
    doc.add_heading("3. DocType Field Reference", level=1)
    all_parents = frappe.get_all("DocType", filters={"module": ["in", MODULES], "istable": 0},
                                 fields=["name", "module"], order_by="module, name")
    for d in all_parents:
        doc.add_heading(f"{d.name}  ({d.module})", level=2)
        submittable = frappe.db.get_value("DocType", d.name, "is_submittable")
        autoname = frappe.db.get_value("DocType", d.name, "autoname")
        _p(doc, f"Autoname: {autoname or '-'}    Submittable: {'Yes' if submittable else 'No'}",
           size=9)
        _table(doc, ["Fieldname", "Label", "Type", "Options", "Flags"], _fields_rows(d.name))

    # ---- 4. Custom fields on standard DocTypes ----
    doc.add_heading("4. Custom Fields on Standard ERPNext DocTypes", level=1)
    for dt in STD_DOCTYPES:
        cfs = frappe.get_all("Custom Field", filters={"dt": dt},
                             fields=["fieldname", "label", "fieldtype", "options", "reqd"],
                             order_by="idx")
        cfs = [c for c in cfs if c.fieldname and (c.fieldname.startswith(("plant_section",
               "benkas", "gross", "tare", "net", "weight", "supplier_invoice", "id_card",
               "inspection_photos")))]
        if not cfs:
            continue
        doc.add_heading(dt, level=2)
        _table(doc, ["Fieldname", "Label", "Type", "Options", "Required"],
               [[c.fieldname, c.label, c.fieldtype, c.options or "",
                 "Yes" if c.reqd else ""] for c in cfs])

    # ---- 5. Workflows ----
    doc.add_heading("5. Approval Workflows", level=1)
    wfs = frappe.get_all("Workflow", filters={"document_type": ["in",
                         ["Gate Entry", "Gate Pass", "Safety Work Permit", "Electrical Work Permit"]]},
                         fields=["name", "document_type", "workflow_state_field"])
    for w in wfs:
        doc.add_heading(f"{w.name}  (on {w.document_type})", level=2)
        trans = frappe.get_all("Workflow Transition", filters={"parent": w.name},
                               fields=["state", "action", "next_state", "allowed", "condition"],
                               order_by="idx")
        _table(doc, ["From", "Action", "To", "Allowed Role", "Condition"],
               [[t.state, t.action, t.next_state, t.allowed, t.condition or ""] for t in trans])

    # ---- 6. Roles & permissions ----
    doc.add_heading("6. Roles", level=1)
    roles = ["Gate Security", "Section Incharge", "Stores Weighbridge Operator",
             "Safety Officer", "Generator Electrical Operator", "Benkas Project Manager",
             "Ramshy Bio Management"]
    _table(doc, ["Role", "Exists"], [[r, "Yes" if frappe.db.exists("Role", r) else "No"] for r in roles])
    _p(doc, "Section-level data isolation for Section Incharge is applied with standard "
            "User Permissions on Plant Section (assign each incharge to their section).")

    # ---- 7. Reports & dashboard ----
    doc.add_heading("7. MIS Reports & Dashboard", level=1)
    reports = frappe.get_all("Report", filters={"module": ["in", MODULES]},
                             fields=["name", "ref_doctype", "report_type"], order_by="name")
    _table(doc, ["Report", "Based On", "Type"],
           [[r.name, r.ref_doctype, r.report_type] for r in reports])

    doc.add_heading("Workspaces (role-scoped)", level=2)
    ws = frappe.get_all("Workspace", filters={"module": "Benkas Core"},
                        fields=["name", "icon"], order_by="sequence_id")
    ws_rows = []
    for w in ws:
        wroles = frappe.get_all("Has Role", filters={"parent": w.name, "parenttype": "Workspace"},
                                pluck="role")
        ws_rows.append([w.name, w.icon or "", ", ".join(wroles) or "all"])
    _table(doc, ["Workspace", "Icon", "Visible to Roles"], ws_rows)

    doc.add_heading("Stage-wise Print Formats", level=2)
    pfs = frappe.get_all("Print Format", filters={"module": ["in", MODULES]},
                         fields=["name", "doc_type"], order_by="name")
    _table(doc, ["Print Format", "DocType"], [[p.name, p.doc_type] for p in pfs])

    # ---- 8. Automation ----
    doc.add_heading("8. Automation (hooks & scheduler)", level=1)
    _table(doc, ["Trigger", "DocType", "Action"], [
        ["validate", "Gate Entry", "Enforce photo; block inactive labour; auto-stamp time"],
        ["after_insert", "Gate Entry", "Notify section Incharge (bell notification)"],
        ["validate", "Purchase Receipt", "Enforce invoice photo; derive/flag weight variance"],
        ["before_save", "Daily Progress Log", "Auto-fetch manpower & material-consumed rollups"],
        ["before_save", "Contractor Tools Register", "Auto-set In / Returned / Mismatch status"],
        ["before_save", "Generator Log", "Compute running hours & diesel L/hr"],
        ["validate", "Safety/Electrical Work Permit", "Guard closure (confirmation / LOTO / sign-off)"],
        ["cron */30 min", "Gate Pass", "Flag overdue passes (Out → Overdue)"],
    ])

    # ---- 9. Seed & current data ----
    doc.add_heading("9. Seed & Current Data", level=1)
    _p(doc, "Plant Sections (12): " + ", ".join(
        frappe.get_all("Plant Section", pluck="section_name", order_by="creation")))
    acts = frappe.get_all("Construction Activity", fields=["activity_name", "default_weight"],
                          order_by="sequence")
    _p(doc, "Construction Activities (per-section WBS): " +
       ", ".join(f"{a.activity_name} ({a.default_weight}%)" for a in acts))
    _p(doc, f"Section sub-tasks generated (WBS): {frappe.db.count('Task', {'parent_task': ['!=', '']})}")
    count_dts = ["Plant Section", "Contractor", "Labour Master", "Employee", "Gate Entry",
                 "Gate Pass", "Daily Progress Log", "Generator Log", "Power Consumption Log",
                 "Site Vehicle Log", "Safety Violation Log", "Visitor Log",
                 "Contractor Tools Register", "Safety Work Permit", "Electrical Work Permit"]
    _table(doc, ["DocType", "Records"], [[dt, frappe.db.count(dt)] for dt in count_dts])

    # ---- 10. Reproduce / install ----
    doc.add_heading("10. Install / Reproduce", level=1)
    for step in [
        "bench get-app benkas_erp <repo-url>   # or copy apps/benkas_erp",
        "bench --site <site> install-app benkas_erp",
        "bench --site <site> execute benkas_erp.setup.build_doctypes.build",
        "bench --site <site> migrate            # runs after_migrate → full setup",
        "bench --site <site> execute benkas_erp.setup.seed.run        # masters",
        "bench --site <site> execute benkas_erp.setup.demo_data.run   # optional UAT data",
        "bench --site <site> execute benkas_erp.setup.selftest.run    # verify",
    ]:
        _p(doc, "•  " + step, size=10)

    # ---- 11. Change log ----
    doc.add_heading("11. Change Log", level=1)
    for date, title_, items in CHANGELOG:
        doc.add_heading(f"{date} — {title_}", level=2)
        for it in items:
            _p(doc, "•  " + it, size=10)

    out = path or WIN_OUT
    doc.save(out)

    # also keep a committed copy inside the app repo (docs/)
    try:
        import os
        app_docs = frappe.get_app_path("benkas_erp", "..", "docs")
        os.makedirs(app_docs, exist_ok=True)
        repo_copy = os.path.join(app_docs, "Benkas_ERP_System_Documentation.docx")
        doc.save(repo_copy)
        print("Repo copy written to:", repo_copy)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: repo docx copy failed")

    print("Documentation written to:", out)
    return out
