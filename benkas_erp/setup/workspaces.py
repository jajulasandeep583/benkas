"""
Six role-scoped Workspaces for Benkas ERP (code-driven, idempotent).

Each workspace: icon + indicator colour, an intro paragraph, module onboarding
(operational ones), number cards, group-by charts, doctype/report shortcuts,
grouped reference links, and role-based visibility.

_make_workspace UPSERTS — icon/colour/title/content and all child blocks are
re-applied even when the workspace already exists, so edits always land.
"""

import json
import frappe
from benkas_erp.setup.onboarding import WORKSPACE_ONBOARDING

SM = "System Manager"

COLORS = {
    "Gate Management": "cyan",
    "Manpower Manager": "blue", "Material and Purchase": "orange",
    "Work Schedule and Progress": "green", "Site Safety and Assets": "red",
    "Benkas Core": "gray", "Benkas MIS": "purple",
}

INTRO = {
    "Gate Management": "Everything that enters or exits the site is recorded here — people, "
        "visitors, vehicles, tools, and gate passes. Gate Security works from this workspace "
        "all day; the Scan Station is the fastest way to log anyone in or out.",
    "Manpower Manager": "Workforce masters, attendance review and Incharge acknowledgements. "
        "Day-to-day gate operations (logging people in/out, visitors, passes) now live in the "
        "Gate Management workspace.",
    "Material and Purchase": "Receive material at the gate through weighbridge and quality "
        "check into section stores, then issue it to work. Used by Stores / Weighbridge "
        "Operators.",
    "Work Schedule and Progress": "Plan each section's work as tasks and log daily site "
        "progress — manpower, material and photos — in one place. Used daily by Section "
        "Incharges and the Project Manager.",
    "Site Safety and Assets": "Safety violations, work permits and generator / power "
        "monitoring. Used by Section Incharges, the Safety Officer and the Generator / "
        "Electrical Operator. (Visitors, tools and vehicle logs moved to Gate Management.)",
    "Benkas Core": "Set up the plant's master data — sections, contractors, labour, "
        "activities and delay reasons — before daily operations begin. Managed by the "
        "Project Manager.",
    "Benkas MIS": "The consolidated executive view across all 12 sections — overall "
        "progress, manpower, material and safety at a glance. For Benkas and Ramshy Bio "
        "management (read-only).",
}


def _project():
    return (frappe.db.get_value("Project", {"project_name": "Ramshy Bio Ethanol Plant"}, "name")
            or frappe.db.get_value("Project", {}, "name") or "")


# ------------------------- number cards -------------------------
def _cards():
    proj = _project()
    return [
        ("today_headcount", "Today's Headcount", "Gate Entry", "Count", None,
         [["Gate Entry", "entry_type", "=", "In"], ["Gate Entry", "time_in", "Timespan", "today"]]),
        ("pending_ack", "Pending Acknowledgements", "Gate Entry", "Count", None,
         [["Gate Entry", "acknowledgement_status", "=", "Pending"]]),
        ("overdue_passes", "Overdue Gate Passes", "Gate Pass", "Count", None,
         [["Gate Pass", "pass_status", "=", "Overdue"]]),
        ("weight_var", "Weight Variance Flags", "Purchase Receipt", "Count", None,
         [["Purchase Receipt", "weight_variance_flag", "=", 1]]),
        ("qc_rejected", "QC Rejections", "Quality Inspection", "Count", None,
         [["Quality Inspection", "status", "=", "Rejected"]]),
        ("matvalue_today", "Material Value Received (Today)", "Purchase Receipt", "Sum", "grand_total",
         [["Purchase Receipt", "posting_date", "Timespan", "today"], ["Purchase Receipt", "docstatus", "=", 1]]),
        ("overall_progress", "Overall % Complete", "Task", "Average", "progress",
         ([["Task", "project", "=", proj], ["Task", "is_group", "=", 0]] if proj else [["Task", "is_group", "=", 0]])),
        ("active_sections", "Active Plant Sections", "Plant Section", "Count", None,
         [["Plant Section", "is_active", "=", 1]]),
        ("open_violations", "Open Safety Violations", "Safety Violation Log", "Count", None,
         [["Safety Violation Log", "status", "=", "Open"]]),
        ("active_permits", "Active Safety Permits", "Safety Work Permit", "Count", None,
         [["Safety Work Permit", "permit_status", "=", "Work in Progress"]]),
        ("tool_mismatch", "Tool Mismatches", "Contractor Tools Register", "Count", None,
         [["Contractor Tools Register", "status", "=", "Mismatch"]]),
        # --- Gate Management ---
        ("people_on_site", "People On Site Now", "Gate Entry", "Count", None,
         [["Gate Entry", "entry_type", "=", "In"], ["Gate Entry", "time_out", "is", "not set"],
          ["Gate Entry", "time_in", "Timespan", "today"]]),
        ("visitors_on_site", "Visitors On Site Now", "Visitor Log", "Count", None,
         [["Visitor Log", "time_out", "is", "not set"], ["Visitor Log", "time_in", "Timespan", "today"]]),
        ("vehicles_out", "Vehicles Out", "Site Vehicle Log", "Count", None,
         [["Site Vehicle Log", "time_out", "is", "set"], ["Site Vehicle Log", "time_in", "is", "not set"]]),
        ("tools_pending", "Tools Pending Return", "Contractor Tools Register", "Count", None,
         [["Contractor Tools Register", "status", "=", "In"]]),
    ]


def _ensure_cards():
    names = {}
    for key, label, dt, func, agg, filters in _cards():
        if not frappe.db.exists("DocType", dt):
            continue
        existing = frappe.db.get_value("Number Card", {"label": label, "document_type": dt}, "name")
        if existing:
            names[key] = existing
            continue
        payload = {"doctype": "Number Card", "label": label, "type": "Document Type",
                   "document_type": dt, "function": func, "is_public": 1,
                   "show_percentage_stats": 0, "filters_json": json.dumps(filters)}
        if agg:
            payload["aggregate_function_based_on"] = agg
        names[key] = frappe.get_doc(payload).insert(ignore_permissions=True).name
    return names


# ------------------------- charts -------------------------
def _charts():
    return [
        ("headcount_section", "Benkas Headcount by Section", "Gate Entry", "plant_section", "Bar",
         [["Gate Entry", "entry_type", "=", "In"]], None),
        ("ack_status", "Benkas Acknowledgement Status", "Gate Entry", "acknowledgement_status", "Donut", [], None),
        ("stock_purpose", "Benkas Stock Movement by Purpose", "Stock Entry", "purpose", "Bar",
         [["Stock Entry", "docstatus", "=", 1]], None),
        ("qc_outcome", "Benkas QC Outcome", "Quality Inspection", "status", "Donut", [], None),
        ("delay_reasons", "Benkas Delay Reasons", "Daily Task Progress", "delay_reason", "Donut", [],
         "Daily Progress Log"),
        ("violations_section", "Benkas Violations by Section", "Safety Violation Log", "plant_section", "Bar", [], None),
        ("permit_status", "Benkas Permit Status", "Safety Work Permit", "permit_status", "Donut", [], None),
        ("entries_category", "Benkas Entries by Category", "Gate Entry", "person_type", "Donut",
         [["Gate Entry", "entry_type", "=", "In"]], None),
    ]


def _ensure_charts():
    names = {}
    for key, label, dt, based_on, ctype, filters, parent_dt in _charts():
        if not frappe.db.exists("DocType", dt):
            continue
        try:
            fj = json.dumps(filters)
            existing = frappe.db.get_value("Dashboard Chart", {"chart_name": label}, "name")
            if existing:
                doc = frappe.get_doc("Dashboard Chart", existing)
                if doc.document_type != dt or (doc.parent_document_type or None) != parent_dt:
                    frappe.delete_doc("Dashboard Chart", existing, force=1, ignore_permissions=True)
                else:
                    if (doc.group_by_based_on != based_on or doc.type != ctype
                            or (doc.filters_json or "[]") != fj):
                        doc.group_by_based_on = based_on
                        doc.type = ctype
                        doc.filters_json = fj
                        doc.save(ignore_permissions=True)
                    names[key] = existing
                    continue
            payload = {"doctype": "Dashboard Chart", "chart_name": label, "chart_type": "Group By",
                       "document_type": dt, "group_by_type": "Count", "group_by_based_on": based_on,
                       "type": ctype, "is_public": 1, "timeseries": 0, "filters_json": fj}
            if parent_dt:
                payload["parent_document_type"] = parent_dt
            names[key] = frappe.get_doc(payload).insert(ignore_permissions=True).name
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Benkas: chart {label} failed")
    names.update(_ensure_timeseries_charts())
    return names


def _ensure_timeseries_charts():
    """Count-timeseries chart: gate entries by hour (shows gate rush periods)."""
    names = {}
    label = "Benkas Gate Entries by Hour"
    if not frappe.db.exists("DocType", "Gate Entry"):
        return names
    existing = frappe.db.get_value("Dashboard Chart", {"chart_name": label}, "name")
    if existing:
        names["entries_hour"] = existing
        return names
    try:
        names["entries_hour"] = frappe.get_doc({
            "doctype": "Dashboard Chart", "chart_name": label, "chart_type": "Count",
            "document_type": "Gate Entry", "based_on": "time_in", "timeseries": 1,
            "time_interval": "Hourly", "timespan": "Last Week", "type": "Bar", "is_public": 1,
            "filters_json": json.dumps([["Gate Entry", "entry_type", "=", "In"]]),
        }).insert(ignore_permissions=True).name
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: hourly chart failed")
    return names


# ------------------------- workspace specs -------------------------
def _workspaces():
    return [
        {"name": "Gate Management", "icon": "door-open",
         "roles": ["Gate Security", "Section Incharge", "Benkas Project Manager"],
         "shortcuts": [("URL", "🔳 Scan Station — scan cards & slips here", "/app/benkas-scan"),
                       ("DocType", "Gate Entry", "Gate Entry"),
                       ("DocType", "Temporary Passes", "Gate Entry", {"is_temporary": 1}),
                       ("DocType", "Visitor Log", "Visitor Log"),
                       ("DocType", "Gate Pass", "Gate Pass"),
                       ("DocType", "Contractor Tools Register", "Contractor Tools Register"),
                       ("DocType", "Site Vehicle Log", "Site Vehicle Log"),
                       ("DocType", "Site Vehicle", "Site Vehicle"),
                       ("Report", "Gate Register", "Gate Register"),
                       ("Report", "Visitor Register Summary", "Visitor Register Summary"),
                       ("Report", "EOD Manpower MIS", "EOD Manpower MIS"),
                       ("Report", "Labour Attendance Register", "Labour Attendance Register"),
                       ("Report", "Staff Attendance Summary", "Staff Attendance Summary")],
         "cards": ["people_on_site", "visitors_on_site", "vehicles_out", "overdue_passes", "tools_pending"],
         "charts": ["entries_hour", "entries_category"],
         "links": [("Gate Reference", ["Plant Section", "Contractor"])]},

        {"name": "Manpower Manager", "icon": "users",
         "roles": ["Section Incharge", "Benkas Project Manager"],
         "shortcuts": [("DocType", "Gate Entry", "Gate Entry"), ("DocType", "Gate Pass", "Gate Pass"),
                       ("DocType", "Employee", "Employee"),
                       ("Report", "EOD Manpower MIS", "EOD Manpower MIS"),
                       ("Report", "Labour Attendance Register", "Labour Attendance Register"),
                       ("Report", "Staff Attendance Summary", "Staff Attendance Summary"),
                       ("Report", "Contractor-wise Labour Count", "Contractor-wise Labour Count"),
                       ("Report", "Late Entry and OT Report", "Late Entry and OT Report")],
         "cards": ["today_headcount", "pending_ack", "overdue_passes"],
         "charts": ["headcount_section", "ack_status"],
         "links": [("Workforce Masters", ["Labour Master", "Contractor", "Plant Section"])]},

        {"name": "Material and Purchase", "icon": "truck",
         "roles": ["Stores Weighbridge Operator", "Benkas Project Manager"],
         "shortcuts": [("DocType", "Purchase Receipt", "Purchase Receipt"),
                       ("DocType", "Quality Inspection", "Quality Inspection"),
                       ("DocType", "Stock Entry", "Stock Entry"),
                       ("DocType", "Material Request", "Material Request"),
                       ("DocType", "Item", "Item"), ("DocType", "Supplier", "Supplier"),
                       ("Report", "Material Received vs Issued", "Material Received vs Issued"),
                       ("Report", "Material Section Stock Balance", "Material Section Stock Balance"),
                       ("Report", "Material Consumption by Item", "Material Consumption by Item"),
                       ("Report", "QC Rejection Report", "QC Rejection Report")],
         "cards": ["qc_rejected", "weight_var", "matvalue_today"],
         "charts": ["stock_purpose", "qc_outcome"],
         "links": [("Reference", ["Plant Section"])]},

        {"name": "Work Schedule and Progress", "icon": "calendar",
         "roles": ["Section Incharge", "Benkas Project Manager"],
         "shortcuts": [("URL", "🧭 Section 360° — one section, everything", "/app/section-360"),
                       ("URL", "🗓️ Section Task Planner — set tentative dates", "/app/section-task-planner"),
                       ("DocType", "Daily Progress Log", "Daily Progress Log"),
                       ("DocType", "Task", "Task"), ("DocType", "Project", "Project"),
                       ("Report", "Section Progress - Planned vs Actual", "Section Progress - Planned vs Actual"),
                       ("Report", "Section WBS Progress", "Section WBS Progress"),
                       ("Report", "Delay Analysis by Section", "Delay Analysis by Section"),
                       ("Report", "Section Manpower & Work Log", "Section Manpower & Work Log"),
                       ("Report", "Weekly Section MIS", "Weekly Section MIS")],
         "cards": ["overall_progress", "active_sections"],
         "charts": ["delay_reasons"],
         "links": [("Reference", ["Construction Activity", "Delay Reason", "Plant Section"])]},

        {"name": "Site Safety and Assets", "icon": "shield",
         "roles": ["Section Incharge", "Safety Officer", "Generator Electrical Operator", "Benkas Project Manager"],
         "shortcuts": [("DocType", "Safety Violation Log", "Safety Violation Log"),
                       ("DocType", "Safety Work Permit", "Safety Work Permit"),
                       ("DocType", "Electrical Work Permit", "Electrical Work Permit"),
                       ("DocType", "Generator Master", "Generator Master"),
                       ("DocType", "Generator Log", "Generator Log"),
                       ("DocType", "Power Consumption Log", "Power Consumption Log"),
                       ("Report", "Safety Violations Summary", "Safety Violations Summary"),
                       ("Report", "Safety Violations by Contractor", "Safety Violations by Contractor"),
                       ("Report", "Generator Consumption MIS", "Generator Consumption MIS"),
                       ("Report", "Vehicle Utilisation", "Vehicle Utilisation")],
         "cards": ["open_violations", "active_permits", "tool_mismatch"],
         "charts": ["violations_section", "permit_status"],
         "links": [("Reference", ["Plant Section"])]},

        {"name": "Benkas Core", "icon": "settings",
         "roles": ["Benkas Project Manager"],
         "shortcuts": [("DocType", "Plant Section", "Plant Section"),
                       ("DocType", "Contractor", "Contractor"),
                       ("DocType", "Labour Master", "Labour Master"),
                       ("DocType", "Delay Reason", "Delay Reason"),
                       ("DocType", "Construction Activity", "Construction Activity")],
         "cards": ["active_sections"], "charts": [], "links": []},

        {"name": "Benkas MIS", "icon": "layout-dashboard",
         "roles": ["Ramshy Bio Management", "Benkas Project Manager"],
         # one navigation shortcut to the setup/masters workspace — Benkas Core
         # can't get its own /apps tile (v16 = one tile per installed app)
         "shortcuts": [("URL", "🧭 Section 360° — drill into any section", "/app/section-360"),
                       ("URL", "🗓️ Section Task Planner", "/app/section-task-planner"),
                       ("URL", "Setup / Masters", "/app/benkas-core")],
         "cards": ["overall_progress", "today_headcount", "open_violations", "pending_ack"],
         "charts": ["headcount_section", "violations_section"],
         "links": []},
    ]


def _content(spec, card_ids, chart_ids, ws_shortcuts):
    name = spec["name"]
    blocks = [{"id": "hdr", "type": "header",
               "data": {"text": f"<span class=\"h4\"><b>{name}</b></span>", "col": 12}},
              {"id": "intro", "type": "paragraph",
               "data": {"text": f"<p>{INTRO[name]}</p>", "col": 12}}]

    onb = WORKSPACE_ONBOARDING.get(name)
    if onb and frappe.db.exists("Module Onboarding", onb):
        blocks.append({"id": "onb", "type": "onboarding", "data": {"onboarding_name": onb, "col": 12}})

    for k in spec["cards"]:
        if card_ids.get(k):
            blocks.append({"id": "nc_" + k, "type": "number_card",
                           "data": {"number_card_name": card_ids[k], "col": 3}})
    for k in spec["charts"]:
        if chart_ids.get(k):
            blocks.append({"id": "ch_" + k, "type": "chart",
                           "data": {"chart_name": chart_ids[k], "col": 6}})
    for s in ws_shortcuts:
        blocks.append({"id": "sc_" + s["label"][:10], "type": "shortcut",
                       "data": {"shortcut_name": s["label"], "col": 3}})
    for (grp, _dts) in spec["links"]:
        blocks.append({"id": "cd_" + grp[:10], "type": "card", "data": {"card_name": grp, "col": 4}})
    return json.dumps(blocks)


def _make_workspace(spec, card_ids, chart_ids, seq):
    name = spec["name"]

    ws_shortcuts = []
    for sc in spec["shortcuts"]:
        stype, label, link_to = sc[0], sc[1], sc[2]
        extra = sc[3] if len(sc) > 3 else None
        if stype == "Report":
            if frappe.db.exists("Report", link_to):
                ws_shortcuts.append({"type": "Report", "label": label, "link_to": link_to,
                                     "report_ref_doctype": frappe.db.get_value("Report", link_to, "ref_doctype"),
                                     "color": "Grey"})
        elif stype == "URL":
            ws_shortcuts.append({"type": "URL", "label": label, "url": link_to, "color": "Green"})
        elif frappe.db.exists("DocType", link_to):
            row = {"type": "DocType", "label": label, "link_to": link_to, "color": "Blue"}
            if extra:  # pre-filtered list view (e.g. Temporary Passes)
                row["stats_filter"] = json.dumps(extra)
            ws_shortcuts.append(row)

    links = []
    for (grp, dts) in spec["links"]:
        links.append({"type": "Card Break", "label": grp})
        for dt in dts:
            if frappe.db.exists("DocType", dt):
                links.append({"type": "Link", "link_type": "DocType", "link_to": dt,
                              "label": dt, "onboard": 0, "is_query_report": 0})

    number_cards = [{"number_card_name": card_ids[k]} for k in spec["cards"] if card_ids.get(k)]
    charts = [{"chart_name": chart_ids[k], "label": chart_ids[k]} for k in spec["charts"] if chart_ids.get(k)]
    roles = [{"role": r} for r in (spec["roles"] + [SM]) if frappe.db.exists("Role", r)]
    content = _content(spec, card_ids, chart_ids, ws_shortcuts)

    fields = {"title": name, "label": name, "module": "Benkas Core", "public": 1,
              "icon": spec["icon"], "indicator_color": COLORS.get(name, "gray"),
              "sequence_id": seq, "content": content}

    if frappe.db.exists("Workspace", name):
        doc = frappe.get_doc("Workspace", name)
        doc.update(fields)
        doc.set("shortcuts", ws_shortcuts)
        doc.set("links", links)
        doc.set("number_cards", number_cards)
        doc.set("charts", charts)
        doc.set("roles", roles)
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": "Workspace", "name": name, **fields,
                        "shortcuts": ws_shortcuts, "links": links,
                        "number_cards": number_cards, "charts": charts, "roles": roles}
                       ).insert(ignore_permissions=True)


def create():
    try:
        card_ids = _ensure_cards()
        chart_ids = _ensure_charts()
        # Float sequence_ids below 1.0 keep the 7 Benkas workspaces grouped at the
        # very top of the sidebar (standard ERPNext/HRMS workspaces start at 1.0 and
        # are left fully intact below — nothing is hidden).
        for i, spec in enumerate(_workspaces(), start=1):
            _make_workspace(spec, card_ids, chart_ids, round(0.1 * i, 2))
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: workspaces setup failed")

