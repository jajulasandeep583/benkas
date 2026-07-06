import frappe


def extend_bootinfo(bootinfo):
    """Add a second /apps desktop tile for 'Benkas Core'.

    Frappe v16 renders the app grid from bootinfo.app_data, which boot.py builds
    with exactly ONE entry per installed app (apps[0] of add_to_apps_screen). A
    second add_to_apps_screen entry for the same app is silently dropped, so we
    inject the extra tile here, after boot has built app_data.
    """
    app_data = getattr(bootinfo, "app_data", None)
    if not app_data:
        return
    if any((a.get("app_name") == "benkas_core") for a in app_data):
        return
    if not frappe.db.exists("Workspace", "Benkas Core"):
        return

    logo = app_data[0].get("app_logo_url") or "/assets/frappe/images/frappe-framework-logo.svg"
    app_data.append({
        "app_name": "benkas_core",
        "app_title": "Benkas Core",
        "app_route": "/desk/benkas-core",
        "app_logo_url": logo,
        "modules": [],
        "workspaces": ["Benkas Core"],
    })
