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
    "Manpower Manager": "blue", "Material and Purchase": "orange",
    "Work Schedule and Progress": "green", "Site Safety and Assets": "red",
    "Benkas Core": "gray", "Benkas MIS": "purple",
}

INTRO = {
    "Manpower Manager": "Track everyone entering the site — company staff, contractors and "
        "labour — with gate in/out, live photos and Incharge acknowledgement. Used every day "
        "by Gate Security and Section Incharges.",
    "Material and Purchase": "Receive material at the gate through weighbridge and quality "
        "check into section stores, then issue it to work. Used by Stores / Weighbridge "
        "Operators and Gate Security.",
    "Work Schedule and Progress": "Plan each section's work as tasks and log daily site "
        "progress — manpower, material and photos — in one place. Used daily by Section "
        "Incharges and the Project Manager.",
    "Site Safety and Assets": "Log visitors, safety violations, work permits, generator / "
        "vehicle usage and contractor tools here. Used daily by Section Incharges, the "
        "Safety Officer and Gate Security.",
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
    return names


# ------------------------- workspace specs -------------------------
def _workspaces():
    return [
        {"name": "Manpower Manager", "icon": "users",
         "roles": ["Gate Security", "Section Incharge", "Benkas Project Manager"],
         "shortcuts": [("DocType", "Gate Entry", "Gate Entry"), ("DocType", "Gate Pass", "Gate Pass"),
                       ("DocType", "Employee", "Employee"),
                       ("Report", "EOD Manpower MIS", "EOD Manpower MIS"),
                       ("Report", "Contractor-wise Labour Count", "Contractor-wise Labour Count"),
                       ("Report", "Late Entry and OT Report", "Late Entry and OT Report")],
         "cards": ["today_headcount", "pending_ack", "overdue_passes"],
         "charts": ["headcount_section", "ack_status"],
         "links": [("Workforce Masters", ["Labour Master", "Contractor", "Plant Section"])]},

        {"name": "Material and Purchase", "icon": "truck",
         "roles": ["Gate Security", "Stores Weighbridge Operator", "Benkas Project Manager"],
         "shortcuts": [("DocType", "Purchase Receipt", "Purchase Receipt"),
                       ("DocType", "Quality Inspection", "Quality Inspection"),
                       ("DocType", "Stock Entry", "Stock Entry"),
                       ("DocType", "Material Request", "Material Request"),
                       ("DocType", "Item", "Item"), ("DocType", "Supplier", "Supplier"),
                       ("Report", "Material Received vs Issued", "Material Received vs Issued"),
                       ("Report", "Material Section Stock Balance", "Material Section Stock Balance"),
                       ("Report", "QC Rejection Report", "QC Rejection Report")],
         "cards": ["qc_rejected", "weight_var", "matvalue_today"],
         "charts": ["stock_purpose", "qc_outcome"],
         "links": [("Reference", ["Plant Section"])]},

        {"name": "Work Schedule and Progress", "icon": "calendar",
         "roles": ["Section Incharge", "Benkas Project Manager"],
         "shortcuts": [("DocType", "Daily Progress Log", "Daily Progress Log"),
                       ("DocType", "Task", "Task"), ("DocType", "Project", "Project"),
                       ("Report", "Section Progress - Planned vs Actual", "Section Progress - Planned vs Actual"),
                       ("Report", "Section WBS Progress", "Section WBS Progress"),
                       ("Report", "Delay Analysis by Section", "Delay Analysis by Section"),
                       ("Report", "Weekly Section MIS", "Weekly Section MIS")],
         "cards": ["overall_progress", "active_sections"],
         "charts": ["delay_reasons"],
         "links": [("Reference", ["Construction Activity", "Delay Reason", "Plant Section"])]},

        {"name": "Site Safety and Assets", "icon": "shield",
         "roles": ["Section Incharge", "Safety Officer", "Generator Electrical Operator", "Benkas Project Manager"],
         "shortcuts": [("DocType", "Visitor Log", "Visitor Log"),
                       ("DocType", "Safety Violation Log", "Safety Violation Log"),
                       ("DocType", "Safety Work Permit", "Safety Work Permit"),
                       ("DocType", "Electrical Work Permit", "Electrical Work Permit"),
                       ("DocType", "Contractor Tools Register", "Contractor Tools Register"),
                       ("DocType", "Generator Master", "Generator Master"),
                       ("DocType", "Generator Log", "Generator Log"),
                       ("DocType", "Power Consumption Log", "Power Consumption Log"),
                       ("DocType", "Site Vehicle", "Site Vehicle"),
                       ("DocType", "Site Vehicle Log", "Site Vehicle Log"),
                       ("Report", "Safety Violations Summary", "Safety Violations Summary"),
                       ("Report", "Safety Violations by Contractor", "Safety Violations by Contractor"),
                       ("Report", "Generator Consumption MIS", "Generator Consumption MIS"),
                       ("Report", "Vehicle Utilisation", "Vehicle Utilisation")],
         "cards": ["open_violations", "active_permits", "tool_mismatch"],
         "charts": ["violations_section", "permit_status"],
         "links": [("Reference", ["Gate Pass", "Plant Section"])]},

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
         "shortcuts": [("URL", "Setup / Masters", "/app/benkas-core")],
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
    for (stype, label, link_to) in spec["shortcuts"]:
        if stype == "Report":
            if frappe.db.exists("Report", link_to):
                ws_shortcuts.append({"type": "Report", "label": label, "link_to": link_to,
                                     "report_ref_doctype": frappe.db.get_value("Report", link_to, "ref_doctype"),
                                     "color": "Grey"})
        elif stype == "URL":
            ws_shortcuts.append({"type": "URL", "label": label, "url": link_to, "color": "Green"})
        elif frappe.db.exists("DocType", link_to):
            ws_shortcuts.append({"type": "DocType", "label": label, "link_to": link_to, "color": "Blue"})

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
        for i, spec in enumerate(_workspaces(), start=1):
            _make_workspace(spec, card_ids, chart_ids, i)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: workspaces setup failed")

