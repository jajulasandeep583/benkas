"""
Client Weekly MIS Pack — a presentation-grade A4 .docx the PM hands to the
client (Ramshy Bio) every week. Pulls only from live data (no new doctypes):

    cover · project scorecard · section-wise table · per-section detail (x12,
    each = task table with % + status, the week's work narrative, stoppage
    summary, material, photo captions) · manpower annex · material annex ·
    stoppage & exceptions page

    bench --site benkas.local execute benkas_erp.setup.client_mis.build
    bench --site benkas.local execute benkas_erp.setup.client_mis.build \
        --kwargs "{'week_ending':'2026-07-06'}"

A weekly scheduler (Monday) drops a fresh pack in the BENKAS PM folder.
"""

import frappe
from frappe.utils import getdate, today, add_days, flt, formatdate
from benkas_erp.section360 import _latest_progress

WIN_DIR = "/mnt/c/Users/jajul/Downloads/BENKAS PM"
NAVY = (0x16, 0x32, 0x4F)


# --------------------------------------------------------------------------
# docx helpers
# --------------------------------------------------------------------------
def _p(doc, text, bold=False, size=None, color=None, align=None, italic=False):
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    para = doc.add_paragraph()
    if align == "center":
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    if size:
        run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor(*color)
    return para


def _table(doc, headers, rows, widths=None):
    from docx.shared import Pt, RGBColor
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = str(h)
        for para in c.paragraphs:
            for run in para.runs:
                run.bold = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(*NAVY)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if v is None else str(v)
            for para in cells[i].paragraphs:
                for run in para.runs:
                    run.font.size = Pt(9)
    return t


def _money(v):
    return frappe.utils.fmt_money(flt(v), currency="INR")


# --------------------------------------------------------------------------
# data gathering (week-scoped)
# --------------------------------------------------------------------------
def _section_rows(week_start, week_end):
    """One summary row per section + a detail dict for the per-section pages."""
    sections = frappe.get_all(
        "Plant Section", fields=["name", "section_code", "section_name", "incharge",
                                 "project_task", "warehouse", "section_percent_complete"],
        order_by="section_code asc")
    out = []
    for s in sections:
        tasks = frappe.get_all("Task", filters={"parent_task": s.project_task},
                               fields=["name", "subject", "progress"],
                               order_by="subject asc") if s.project_task else []
        for t in tasks:
            t["latest_status"] = (_latest_progress(t.name).get("status") or "Not started")
        actual = flt(s.section_percent_complete)
        pdays = frappe.db.sql(
            """SELECT COALESCE(SUM(dwl.hours),0)/8 FROM `tabDaily Worker Log` dwl
               JOIN `tabDaily Progress Log` dpl ON dpl.name=dwl.parent
               WHERE dpl.plant_section=%s AND dpl.log_date BETWEEN %s AND %s""",
            (s.name, week_start, week_end))[0][0] or 0
        work = frappe.db.sql(
            """SELECT dtp.work_description, dtp.percent_complete, dtp.status, dpl.log_date
               FROM `tabDaily Task Progress` dtp JOIN `tabDaily Progress Log` dpl ON dpl.name=dtp.parent
               WHERE dpl.plant_section=%s AND dpl.log_date BETWEEN %s AND %s
                 AND IFNULL(dtp.work_description,'')<>'' ORDER BY dpl.log_date""",
            (s.name, week_start, week_end), as_dict=1)
        stoppages = frappe.db.sql(
            """SELECT dtp.status, COUNT(*) FROM `tabDaily Task Progress` dtp
               JOIN `tabDaily Progress Log` dpl ON dpl.name=dtp.parent
               JOIN `tabProgress Status` ps2 ON ps2.name=dtp.status AND ps2.is_stopped=1
               WHERE dpl.plant_section=%s AND dpl.log_date BETWEEN %s AND %s
               GROUP BY dtp.status ORDER BY 2 DESC""",
            (s.name, week_start, week_end))
        no_work = frappe.db.sql(
            """SELECT COUNT(*) FROM `tabDaily Progress Log`
               WHERE plant_section=%s AND no_work_today=1 AND log_date BETWEEN %s AND %s""",
            (s.name, week_start, week_end))[0][0] or 0
        material = frappe.db.sql(
            """SELECT dmc.item, SUM(dmc.qty), dmc.uom
               FROM `tabDaily Material Consumed` dmc JOIN `tabDaily Progress Log` dpl ON dpl.name=dmc.parent
               WHERE dpl.plant_section=%s AND dpl.log_date BETWEEN %s AND %s
               GROUP BY dmc.item, dmc.uom ORDER BY SUM(dmc.qty) DESC""",
            (s.name, week_start, week_end))
        photos = frappe.db.sql(
            """SELECT dpp.activity_task, dpl.log_date, dpp.caption
               FROM `tabDaily Progress Photo` dpp JOIN `tabDaily Progress Log` dpl ON dpl.name=dpp.parent
               WHERE dpl.plant_section=%s AND dpl.log_date BETWEEN %s AND %s AND IFNULL(dpp.image,'')<>''
               ORDER BY dpl.log_date""", (s.name, week_start, week_end), as_dict=1)
        visitors = frappe.db.sql(
            """SELECT COUNT(*) FROM `tabVisitor Log` WHERE plant_section=%s
               AND DATE(time_in) BETWEEN %s AND %s""", (s.name, week_start, week_end))[0][0] or 0
        stopped_days = sum(r[1] for r in stoppages) + no_work
        status = "Attention" if stopped_days else "On Track"
        out.append({
            "section": s.name, "code": s.section_code, "name": s.section_name,
            "incharge": s.incharge, "actual": actual, "status": status,
            "pdays": round(pdays, 1), "tasks": tasks, "work": work,
            "stoppages": stoppages, "no_work": no_work, "stopped_days": stopped_days,
            "material": material, "photos": photos, "visitors": visitors,
        })
    return out


def _manpower_annex(week_start, week_end):
    by_contractor = frappe.db.sql(
        """SELECT COALESCE(lm.contractor, dwl.person_type) grp, ROUND(SUM(dwl.hours)/8,1)
           FROM `tabDaily Worker Log` dwl JOIN `tabDaily Progress Log` dpl ON dpl.name=dwl.parent
           LEFT JOIN `tabLabour Master` lm ON lm.name=dwl.person
           WHERE dpl.log_date BETWEEN %s AND %s GROUP BY grp ORDER BY 2 DESC""",
        (week_start, week_end))
    by_category = frappe.db.sql(
        """SELECT dwl.person_type, ROUND(SUM(dwl.hours)/8,1)
           FROM `tabDaily Worker Log` dwl JOIN `tabDaily Progress Log` dpl ON dpl.name=dwl.parent
           WHERE dpl.log_date BETWEEN %s AND %s GROUP BY dwl.person_type ORDER BY 2 DESC""",
        (week_start, week_end))
    return by_contractor, by_category


def _material_annex(week_start, week_end):
    received = frappe.db.sql(
        """SELECT COALESCE(pr.plant_section,'(unassigned)'), ROUND(SUM(pri.amount),0)
           FROM `tabPurchase Receipt Item` pri JOIN `tabPurchase Receipt` pr ON pr.name=pri.parent
           WHERE pr.docstatus=1 AND pr.posting_date BETWEEN %s AND %s
           GROUP BY pr.plant_section ORDER BY 2 DESC""", (week_start, week_end))
    issued = frappe.db.sql(
        """SELECT COALESCE(se.plant_section,'(unassigned)'), ROUND(SUM(sed.amount),0)
           FROM `tabStock Entry Detail` sed JOIN `tabStock Entry` se ON se.name=sed.parent
           WHERE se.docstatus=1 AND se.purpose='Material Issue' AND se.posting_date BETWEEN %s AND %s
           GROUP BY se.plant_section ORDER BY 2 DESC""", (week_start, week_end))
    return received, issued


def _stoppage_annex(week_start, week_end):
    """Stopped section-days across the week, by reason and by section."""
    by_reason = frappe.db.sql(
        """SELECT dtp.status, COUNT(*) FROM `tabDaily Task Progress` dtp
           JOIN `tabDaily Progress Log` dpl ON dpl.name=dtp.parent
           JOIN `tabProgress Status` ps2 ON ps2.name=dtp.status AND ps2.is_stopped=1
           WHERE dpl.log_date BETWEEN %s AND %s
           GROUP BY dtp.status ORDER BY 2 DESC""", (week_start, week_end))
    return by_reason


def _exceptions(week_start, week_end):
    violations = frappe.get_all("Safety Violation Log", filters={"status": "Open"},
                                fields=["plant_section", "violation_type", "person", "violation_datetime"],
                                order_by="violation_datetime desc", limit=25)
    overdue_passes = frappe.get_all("Gate Pass",
                                    filters={"pass_status": ["in", ["Out", "Overdue"]],
                                             "expected_return_time": ["<", frappe.utils.now()]},
                                    fields=["name", "person", "expected_return_time"], limit=25)
    return violations, overdue_passes


# --------------------------------------------------------------------------
# builder
# --------------------------------------------------------------------------
def build(week_ending=None, path=None):
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    week_end = getdate(week_ending) if week_ending else getdate(today())
    week_start = add_days(week_end, -6)
    rows = _section_rows(week_start, week_end)

    n = len(rows) or 1
    overall_actual = round(sum(r["actual"] for r in rows) / n, 1)
    total_pdays = round(sum(r["pdays"] for r in rows), 1)
    on_track = sum(1 for r in rows if r["status"] == "On Track")
    attention_sections = n - on_track if rows else 0
    total_stopped_days = sum(r["stopped_days"] for r in rows)

    doc = Document()
    for section in doc.sections:
        section.page_height, section.page_width = Inches(11.69), Inches(8.27)  # A4
        section.left_margin = section.right_margin = Inches(0.8)

    # ---- Cover ----
    doc.add_paragraph("\n\n")
    _p(doc, "RAMSHY BIO PVT. LTD.", bold=True, size=16, color=NAVY, align="center")
    _p(doc, "Ethanol Plant — Construction Progress", bold=True, size=26, color=NAVY, align="center")
    _p(doc, "Weekly Management Information Report", size=15, align="center")
    _p(doc, f"Week ending {formatdate(week_end, 'dd MMMM yyyy')}", size=13, align="center", italic=True)
    doc.add_paragraph("\n")
    _p(doc, f"Overall completion: {overall_actual}%", bold=True, size=13, align="center")
    _p(doc, f"{on_track} of {n} sections on track  ·  {total_pdays} person-days this week"
            f"  ·  {total_stopped_days} stopped section-days", size=12, align="center")
    doc.add_paragraph("\n\n")
    _p(doc, "Prepared by Benkas Engineering — Project Monitoring Cell", size=10, align="center", italic=True)
    doc.add_page_break()

    # ---- 1. Project scorecard ----
    doc.add_heading("1. Project Scorecard", level=1)
    _table(doc, ["Metric", "Value"], [
        ["Overall completion", f"{overall_actual}%"],
        ["Sections on track", f"{on_track} of {n}"],
        ["Sections needing attention", str(attention_sections)],
        ["Person-days this week", str(total_pdays)],
        ["Stopped section-days this week", str(total_stopped_days)],
        ["Report window", f"{formatdate(week_start,'dd MMM')} – {formatdate(week_end,'dd MMM yyyy')}"],
    ])

    # ---- 2. Section-wise summary ----
    doc.add_heading("2. Section-wise Progress", level=1)
    _table(doc, ["Code", "Section", "Incharge", "Complete", "Status", "P-days (wk)", "Stopped days"],
           [[r["code"], r["name"], r["incharge"] or "—", f"{r['actual']}%",
             r["status"], r["pdays"], r["stopped_days"]] for r in rows])

    # ---- 3. Per-section detail ----
    doc.add_page_break()
    doc.add_heading("3. Section Detail", level=1)
    for r in rows:
        doc.add_heading(f"{r['code']} — {r['name']}", level=2)
        _p(doc, f"Incharge: {r['incharge'] or '—'}   |   {r['actual']}% complete  ·  {r['status']}"
                f"   |   {r['pdays']} person-days this week   |   {r['visitors']} visitor(s)", size=10)
        _table(doc, ["Task", "% Complete", "Latest Status"],
               [[t["subject"], f"{round(flt(t.get('progress')))}%", t["latest_status"]] for t in r["tasks"]]
               or [["No sub-tasks", "", ""]])
        if r["work"]:
            _p(doc, "What happened this week:", bold=True, size=10)
            for w in r["work"][:14]:
                pct = f"  ({round(flt(w.percent_complete))}%)" if w.percent_complete is not None else ""
                _p(doc, f"• {formatdate(w.log_date,'dd MMM')} [{w.status or '—'}]: {w.work_description}{pct}", size=9)
        if r["stoppages"] or r["no_work"]:
            _p(doc, "Stoppages this week:", bold=True, size=10)
            srows = [[st[0], st[1]] for st in r["stoppages"]]
            if r["no_work"]:
                srows.append(["No-work days", r["no_work"]])
            _table(doc, ["Reason", "Days"], srows)
        if r["material"]:
            _p(doc, "Material consumed this week:", bold=True, size=10)
            _table(doc, ["Item", "Qty", "UOM"], [[m[0], m[1], m[2] or ""] for m in r["material"]])
        if r["photos"]:
            _p(doc, f"Photos logged this week ({len(r['photos'])}):", bold=True, size=10)
            _table(doc, ["Task", "Date", "Caption"],
                   [[p.activity_task or "—", formatdate(p.log_date, "dd MMM"), p.caption or ""]
                    for p in r["photos"][:20]])
        doc.add_paragraph("")

    # ---- 4. Manpower annex ----
    doc.add_page_break()
    doc.add_heading("4. Manpower Annex (this week)", level=1)
    by_contractor, by_category = _manpower_annex(week_start, week_end)
    _p(doc, "Person-days by contractor / team", bold=True, size=11)
    _table(doc, ["Contractor / Team", "Person-days"],
           [[c[0], c[1]] for c in by_contractor] or [["No manpower logged", ""]])
    _p(doc, "Person-days by category", bold=True, size=11)
    _table(doc, ["Category", "Person-days"],
           [[c[0], c[1]] for c in by_category] or [["No manpower logged", ""]])

    # ---- 5. Material annex ----
    doc.add_heading("5. Material Annex (this week)", level=1)
    received, issued = _material_annex(week_start, week_end)
    _p(doc, "Material received (by section)", bold=True, size=11)
    _table(doc, ["Section", "Value received"],
           [[m[0], _money(m[1])] for m in received] or [["Nothing received", ""]])
    _p(doc, "Material issued to work (by section)", bold=True, size=11)
    _table(doc, ["Section", "Value issued"],
           [[m[0], _money(m[1])] for m in issued] or [["Nothing issued", ""]])

    # ---- 6. Stoppages & exceptions ----
    doc.add_page_break()
    doc.add_heading("6. Stoppages & Attention Required", level=1)
    by_reason = _stoppage_annex(week_start, week_end)
    _p(doc, "Stopped section-days by reason (whole project)", bold=True, size=11)
    _table(doc, ["Reason", "Section-days"],
           [[b[0], b[1]] for b in by_reason] or [["None", "No stoppages this week"]])
    violations, overdue_passes = _exceptions(week_start, week_end)
    _p(doc, "Open safety violations", bold=True, size=11)
    _table(doc, ["Section", "Type", "Person", "When"],
           [[v.plant_section, v.violation_type, v.person, formatdate(v.violation_datetime, "dd MMM")]
            for v in violations] or [["None", "No open violations", "", ""]])
    _p(doc, "Overdue gate passes (tools/material not returned)", bold=True, size=11)
    _table(doc, ["Gate Pass", "Person", "Expected Return"],
           [[g.name, g.person, g.expected_return_time] for g in overdue_passes] or [["None", "", ""]])

    doc.add_paragraph("")
    _p(doc, "— End of report —  Generated by Benkas ERP on "
            + formatdate(today(), "dd MMM yyyy"), size=9, align="center", italic=True)

    # ---- save ----
    import os
    fname = f"Client_Weekly_MIS_{week_end}.docx"
    saved = []
    out = path or os.path.join(WIN_DIR, fname)
    try:
        doc.save(out)
        saved.append(out)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: client MIS win save failed")
    # committed sample in the app repo
    try:
        app_docs = frappe.get_app_path("benkas_erp", "..", "docs")
        os.makedirs(app_docs, exist_ok=True)
        sample = os.path.join(app_docs, "Sample_Client_Weekly_MIS.docx")
        doc.save(sample)
        saved.append(sample)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: client MIS sample save failed")
    print("Client MIS written:", saved)
    return {"saved": saved, "sections": n, "overall_actual": overall_actual}


def weekly_scheduler():
    """hooks.scheduler_events['weekly'] entry — build a fresh pack every week."""
    try:
        build()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: weekly client MIS scheduler failed")
