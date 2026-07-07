"""Desktop Icon records — the branded badge shown in the sidebar header and on the
/apps desktop for each Benkas workspace.

v16 renders a workspace's header/desktop badge from a Desktop Icon record: when the
record has `app` set and an SVG exists at
`assets/<app>/icons/desktop_icons/<style>/<scrub(label)>.svg` it uses that glyph,
otherwise it falls back to the first-letter alphabet badge. We ship both style
variants (subtle/solid) under public/icons/desktop_icons and register one standard
Desktop Icon per workspace here (idempotent, upserts every migrate)."""

import frappe

BENKAS_WORKSPACES = [
    "Gate Management", "Manpower Manager", "Material and Purchase",
    "Work Schedule and Progress", "Site Safety and Assets",
    "Benkas Core", "Benkas MIS",
]


def create():
    try:
        for ws in BENKAS_WORKSPACES:
            if not frappe.db.exists("Workspace", ws):
                continue
            icon = frappe.db.get_value("Workspace", ws, "icon")
            fields = {"label": ws, "icon_type": "Link", "link_type": "Workspace Sidebar",
                      "link_to": ws, "icon": icon, "app": "benkas_erp", "standard": 1}
            # de-dupe any earlier per-user / non-standard icon for this workspace
            for stale in frappe.get_all("Desktop Icon",
                                        filters={"label": ws, "standard": 0}, pluck="name"):
                frappe.delete_doc("Desktop Icon", stale, force=1, ignore_permissions=True)
            if frappe.db.exists("Desktop Icon", ws):
                doc = frappe.get_doc("Desktop Icon", ws)
                doc.update(fields)
                doc.save(ignore_permissions=True)
            else:
                frappe.get_doc({"doctype": "Desktop Icon", **fields}).insert(
                    ignore_permissions=True, ignore_if_duplicate=True)
        frappe.cache.delete_key("desktop_icons")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: desktop icons setup failed")
