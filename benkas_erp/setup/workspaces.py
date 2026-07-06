"""
Six role-scoped Workspaces for Benkas ERP (code-driven, idempotent):
5 module workspaces + a slim cross-module 'Benkas MIS' exec view. Each carries
an icon, number cards, group-by charts, report + doctype shortcuts, grouped
links, and role-based visibility.

All number cards / charts are created here too, so the whole navigation layer
travels with the app on a fresh install.
"""

import json
import frappe

SM = "System Manager"

COLORS = {
    "Manpower Manager": "blue",
    "Material and Purchase": "orange",
    "Work Schedule and Progress": "green",
    "Site Safety and Assets": "red",
    "Benkas Core": "gray",
    "Benkas MIS": "purple",
}


def _project():
    return (frappe.db.get_value("Project", {"project_name": "Ramshy Bio Ethanol Plant"}, "name")
            or frappe.db.get_value("Project", {}, "name") or "")


# ------------------------- number cards -------------------------
def _cards():
    proj = _project()
    return [
        # key, label, doctype, function, agg_field, filters
        ("today_headcount", "Today's Headcount", "Gate Entry", "Count", None,
         [["Gate Entry", "entry_type", "=", "In"], ["Gate Entry", "time_in", "Timespan", "today"]]),
        ("pending_ack", "Pending Acknowledgements", "Gate Entry", "Count", None,
         [["Gate Entry", "acknowledgement_status", "=", "Pending"]]),
        ("overdue_passes", "Overdue Gate Passes", "Gate Pass", "Count", None,
         [["Gate Pass", "pass_status", "=", "Overdue"]]),
        ("passes_out", "Gate Passes Out", "Gate Pass", "Count", None,
         [["Gate Pass", "pass_status", "=", "Out"]]),
        ("weight_var", "Weight Variance Flags", "Purchase Receipt", "Count", None,
         [["Purchase Receipt", "weight_variance_flag", "=", 1]]),
        ("qc_rejected", "QC Rejections", "Quality Inspection", "Count", None,
         [["Quality Inspection", "status", "=", "Rejected"]]),
        ("matvalue_today", "Material Value Received (Today)", "Purchase Receipt", "Sum", "grand_total",
         [["Purchase Receipt", "posting_date", "Timespan", "today"], ["Purchase Receipt", "docstatus", "=", 1]]),
        ("overall_progress", "Overall % Complete", "Task", "Average", "progress",
         ([["Task", "project", "=", proj], ["Task", "is_group", "=", 0]] if proj else [["Task", "is_group", "=", 0]])),
        ("open_violations", "Open Safety Violations", "Safety Violation Log", "Count", None,
         [["Safety Violation Log", "status", "=", "Open"]]),
        ("active_permits", "Active Safety Permits", "Safety Work Permit", "Count", None,
         [["Safety Work Permit", "permit_status", "=", "Work in Progress"]]),
        ("tool_mismatch", "Tool Mismatches", "Contractor Tools Register", "Count", None,
         [["Contractor Tools Register", "status", "=", "Mismatch"]]),
        ("active_sections", "Active Plant Sections", "Plant Section", "Count", None,
         [["Plant Section", "is_active", "=", 1]]),
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
        payload = {
            "doctype": "Number Card", "label": label, "type": "Document Type",
            "document_type": dt, "function": func, "is_public": 1,
            "show_percentage_stats": 0, "filters_json": json.dumps(filters),
        }
        if agg:
            payload["aggregate_function_based_on"] = agg
        names[key] = frappe.get_doc(payload).insert(ignore_permissions=True).name
    return names


# ------------------------- charts -------------------------
def _charts():
    # key, label, doctype, group_by_field, chart_type, filters, parent_doctype
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
                # document_type is set-only-once -> delete & recreate if it changed
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
            payload = {
                "doctype": "Dashboard Chart", "chart_name": label, "chart_type": "Group By",
                "document_type": dt, "group_by_type": "Count", "group_by_based_on": based_on,
                "type": ctype, "is_public": 1, "timeseries": 0, "filters_json": fj,
            }
            if parent_dt:
                payload["parent_document_type"] = parent_dt
            names[key] = frappe.get_doc(payload).insert(ignore_permissions=True).name
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Benkas: chart {label} failed")
    return names


# ------------------------- workspaces -------------------------
# (name, icon, [roles], [(shortcut_type, label, link_to)], [card_keys], [chart_keys],
#  [(card_label, [doctypes])])
def _workspaces():
    return [
        ("Manpower Manager", "users",
         ["Gate Security", "Section Incharge", "Benkas Project Manager"],
         [("DocType", "Gate Entry", "Gate Entry"), ("DocType", "Gate Pass", "Gate Pass"),
          ("DocType", "Labour Master", "Labour Master"), ("DocType", "Contractor", "Contractor"),
          ("DocType", "Employee", "Employee"),
          ("Report", "EOD Manpower MIS", "EOD Manpower MIS"),
          ("Report", "Contractor-wise Labour Count", "Contractor-wise Labour Count"),
          ("Report", "Late Entry and OT Report", "Late Entry and OT Report")],
         ["today_headcount", "pending_ack", "overdue_passes"],
         ["headcount_section", "ack_status"],
         [("Workforce", ["Gate Entry", "Gate Pass", "Labour Master", "Contractor"])]),

        ("Material and Purchase", "truck",
         ["Gate Security", "Stores Weighbridge Operator", "Benkas Project Manager"],
         [("DocType", "Purchase Receipt", "Purchase Receipt"),
          ("DocType", "Quality Inspection", "Quality Inspection"),
          ("DocType", "Stock Entry", "Stock Entry"), ("DocType", "Item", "Item"),
          ("DocType", "Supplier", "Supplier"),
          ("Report", "Material Received vs Issued", "Material Received vs Issued"),
          ("Report", "Material Section Stock Balance", "Material Section Stock Balance"),
          ("Report", "QC Rejection Report", "QC Rejection Report")],
         ["qc_rejected", "weight_var", "matvalue_today"],
         ["stock_purpose", "qc_outcome"],
         [("Material Flow", ["Purchase Receipt", "Quality Inspection", "Stock Entry"])]),

        ("Work Schedule and Progress", "calendar",
         ["Section Incharge", "Benkas Project Manager"],
         [("DocType", "Daily Progress Log", "Daily Progress Log"),
          ("DocType", "Task", "Task"), ("DocType", "Project", "Project"),
          ("DocType", "Construction Activity", "Construction Activity"),
          ("DocType", "Delay Reason", "Delay Reason"),
          ("Report", "Section Progress - Planned vs Actual", "Section Progress - Planned vs Actual"),
          ("Report", "Section WBS Progress", "Section WBS Progress"),
          ("Report", "Delay Analysis by Section", "Delay Analysis by Section")],
         ["overall_progress", "active_sections"],
         ["delay_reasons"],
         [("Planning", ["Daily Progress Log", "Task", "Construction Activity", "Delay Reason"])]),

        ("Site Safety and Assets", "shield",
         ["Section Incharge", "Safety Officer", "Generator Electrical Operator", "Benkas Project Manager"],
         [("DocType", "Visitor Log", "Visitor Log"),
          ("DocType", "Safety Violation Log", "Safety Violation Log"),
          ("DocType", "Safety Work Permit", "Safety Work Permit"),
          ("DocType", "Electrical Work Permit", "Electrical Work Permit"),
          ("DocType", "Contractor Tools Register", "Contractor Tools Register"),
          ("DocType", "Generator Log", "Generator Log"),
          ("DocType", "Site Vehicle Log", "Site Vehicle Log"),
          ("DocType", "Power Consumption Log", "Power Consumption Log"),
          ("Report", "Safety Violations by Contractor", "Safety Violations by Contractor"),
          ("Report", "Vehicle Utilisation", "Vehicle Utilisation"),
          ("Report", "Generator Consumption MIS", "Generator Consumption MIS")],
         ["open_violations", "active_permits", "tool_mismatch"],
         ["violations_section", "permit_status"],
         [("Safety", ["Safety Violation Log", "Safety Work Permit", "Electrical Work Permit"]),
          ("Assets & Utility", ["Generator Log", "Power Consumption Log", "Site Vehicle Log",
                                "Contractor Tools Register", "Visitor Log"])]),

        ("Benkas Core", "settings",
         ["Benkas Project Manager"],
         [("DocType", "Plant Section", "Plant Section"), ("DocType", "Contractor", "Contractor"),
          ("DocType", "Labour Master", "Labour Master"),
          ("DocType", "Construction Activity", "Construction Activity"),
          ("DocType", "Delay Reason", "Delay Reason"),
          ("DocType", "Generator Master", "Generator Master"),
          ("DocType", "Site Vehicle", "Site Vehicle")],
         ["active_sections"], [],
         [("Masters", ["Plant Section", "Contractor", "Labour Master", "Construction Activity",
                       "Delay Reason", "Generator Master", "Site Vehicle"])]),

        ("Benkas MIS", "layout-dashboard",
         ["Ramshy Bio Management", "Benkas Project Manager"],
         [("Report", "Section Progress - Planned vs Actual", "Section Progress - Planned vs Actual"),
          ("Report", "EOD Manpower MIS", "EOD Manpower MIS"),
          ("Report", "Material Section Stock Balance", "Material Section Stock Balance"),
          ("Report", "Safety Violations by Contractor", "Safety Violations by Contractor")],
         ["overall_progress", "today_headcount", "open_violations", "pending_ack"],
         ["headcount_section", "violations_section"],
         []),
    ]


def _content(card_ids, chart_ids, card_keys, chart_keys, shortcuts, link_groups, header):
    blocks = [{"id": "hdr", "type": "header",
               "data": {"text": f"<span class=\"h4\"><b>{header}</b></span>", "col": 12}}]
    for k in card_keys:
        if card_ids.get(k):
            blocks.append({"id": "nc_" + k, "type": "number_card",
                           "data": {"number_card_name": card_ids[k], "col": 3}})
    for k in chart_keys:
        if chart_ids.get(k):
            blocks.append({"id": "ch_" + k, "type": "chart",
                           "data": {"chart_name": chart_ids[k], "col": 6}})
    for s in shortcuts:
        label = s["label"]
        blocks.append({"id": "sc_" + label[:8], "type": "shortcut",
                       "data": {"shortcut_name": label, "col": 3}})
    for (grp, _dts) in link_groups:
        blocks.append({"id": "cd_" + grp[:8], "type": "card",
                       "data": {"card_name": grp, "col": 4}})
    return json.dumps(blocks)


def _make_workspace(name, icon, roles, shortcuts, card_keys, chart_keys, link_groups,
                    card_ids, chart_ids, seq):
    if frappe.db.exists("Workspace", name):
        return

    ws_shortcuts = []
    for (stype, label, link_to) in shortcuts:
        if stype == "Report":
            if not frappe.db.exists("Report", link_to):
                continue
            ws_shortcuts.append({"type": "Report", "label": label, "link_to": link_to,
                                 "report_ref_doctype": frappe.db.get_value("Report", link_to, "ref_doctype"),
                                 "color": "Grey"})
        else:
            if not frappe.db.exists("DocType", link_to):
                continue
            ws_shortcuts.append({"type": "DocType", "label": label, "link_to": link_to, "color": "Blue"})

    links = []
    for (grp, dts) in link_groups:
        links.append({"type": "Card Break", "label": grp})
        for dt in dts:
            if frappe.db.exists("DocType", dt):
                links.append({"type": "Link", "link_type": "DocType", "link_to": dt,
                              "label": dt, "onboard": 0, "is_query_report": 0})

    number_cards = [{"number_card_name": card_ids[k]} for k in card_keys if card_ids.get(k)]
    charts = [{"chart_name": chart_ids[k], "label": chart_ids[k]} for k in chart_keys if chart_ids.get(k)]
    ws_roles = [{"role": r} for r in (roles + [SM]) if frappe.db.exists("Role", r)]

    frappe.get_doc({
        "doctype": "Workspace", "name": name, "title": name, "label": name,
        "module": "Benkas Core", "public": 1, "icon": icon,
        "indicator_color": COLORS.get(name, "gray"), "sequence_id": seq,
        "content": _content(card_ids, chart_ids, card_keys, chart_keys, ws_shortcuts, link_groups, name),
        "number_cards": number_cards, "charts": charts, "shortcuts": ws_shortcuts,
        "links": links, "roles": ws_roles,
    }).insert(ignore_permissions=True)


def create():
    try:
        card_ids = _ensure_cards()
        chart_ids = _ensure_charts()
        for i, (name, icon, roles, shortcuts, ckeys, chkeys, lgroups) in enumerate(_workspaces(), start=1):
            _make_workspace(name, icon, roles, shortcuts, ckeys, chkeys, lgroups,
                            card_ids, chart_ids, i)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: workspaces setup failed")


