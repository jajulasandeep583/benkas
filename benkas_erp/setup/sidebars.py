"""Workspace Sidebar records — the v16 app-centric LEFT sidebar for each workspace.

Frappe v16 renders the left sidebar from the 'Workspace Sidebar' doctype (keyed by
workspace title), NOT from Workspace.links. Without an explicit record a workspace
falls back to a sparse module auto-sidebar (or nothing). This builds one Workspace
Sidebar per Benkas workspace, mirroring that workspace's own link groups:

  Home (link to the workspace itself)
  ── <Section Break: group label>
       <indented links: DocType / Report / Page>
  ── <next group> ...

Idempotent — upserts every migrate. Runs after workspaces.create() so each
workspace's links table already exists to mirror.
"""

import frappe

BENKAS_WORKSPACES = [
    "Gate Management", "Manpower Manager", "Material and Purchase",
    "Work Schedule and Progress", "Site Safety and Assets",
    "Benkas Core", "Benkas MIS",
]

# Per-item Lucide icons (all verified to exist in Frappe's lucide sprite) so every
# sidebar row is iconed. Keyed by DocType / Page name; reports fall back to "table".
ICONS = {
    # gate
    "Gate Entry": "log-in", "Visitor Log": "user-check", "Gate Pass": "ticket",
    "Contractor Tools Register": "wrench", "Site Vehicle Log": "truck", "Site Vehicle": "car",
    # masters / people
    "Plant Section": "map-pin", "Contractor": "hard-hat", "Employee": "user",
    "Labour Master": "users", "Supplier": "store", "Item": "box",
    "Construction Activity": "hammer", "Delay Reason": "clock",
    # material
    "Material Request": "clipboard-list", "Purchase Receipt": "package-check",
    "Quality Inspection": "badge-check", "Stock Entry": "arrow-left-right",
    # work schedule
    "Daily Progress Log": "clipboard-check", "Task": "list-checks", "Project": "folder-kanban",
    # safety & assets
    "Safety Violation Log": "triangle-alert", "Safety Work Permit": "shield-check",
    "Electrical Work Permit": "zap", "Generator Master": "fuel", "Generator Log": "gauge",
    "Power Consumption Log": "plug-zap",
    # pages
    "benkas-scan": "scan-line", "section-360": "compass", "section-task-planner": "calendar-clock",
}


def _items_for(ws_name, icon):
    ws = frappe.get_doc("Workspace", ws_name)
    # leading "Home" entry linking back to the workspace itself
    items = [{"label": "Home", "type": "Link", "link_type": "Workspace",
              "link_to": ws_name, "icon": icon or "home", "idx": 1}]
    idx = 2
    in_section = False
    for lk in ws.links:
        if lk.type == "Card Break":
            items.append({"label": lk.label, "type": "Section Break", "idx": idx})
            in_section = True
        elif lk.type == "Link":
            it = {"label": lk.label, "type": "Link", "link_type": lk.link_type,
                  "link_to": lk.link_to, "idx": idx, "child": 1 if in_section else 0}
            it["icon"] = ICONS.get(lk.link_to) or ("table" if lk.link_type == "Report" else "file-text")
            items.append(it)
        idx += 1
    return items


def create():
    try:
        for ws_name in BENKAS_WORKSPACES:
            if not frappe.db.exists("Workspace", ws_name):
                continue
            icon = frappe.db.get_value("Workspace", ws_name, "icon")
            items = _items_for(ws_name, icon)
            fields = {"app": "benkas_erp", "standard": 1, "module": "Benkas Core",
                      "header_icon": icon}
            if frappe.db.exists("Workspace Sidebar", ws_name):
                doc = frappe.get_doc("Workspace Sidebar", ws_name)
                doc.update(fields)
                doc.set("items", items)
                doc.save(ignore_permissions=True)
            else:
                frappe.get_doc({"doctype": "Workspace Sidebar", "title": ws_name,
                                **fields, "items": items}).insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: workspace sidebars setup failed")
