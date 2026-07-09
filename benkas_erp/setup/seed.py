"""
Go-live seed data for Benkas ERP.

Creates the company (if the site has none), a fiscal year, the master Project,
12 Plant Sections each wired to a Warehouse + Task + Cost Center, plus Delay
Reasons and the two Employment Types. Idempotent — safe to re-run.

    bench --site <site> execute benkas_erp.setup.seed.run
"""

import frappe

COMPANY_NAME = "Ramshy Bio Pvt. Ltd."
COMPANY_ABBR = "RBPL"
PROJECT_NAME = "Ramshy Bio Ethanol Plant"

SECTIONS = [
    ("Power Plant", "PP"),
    ("Milling Section", "MILL"),
    ("Liquefaction Section", "LIQ"),
    ("Fermentation Section", "FERM"),
    ("Distillation Section", "DIST"),
    ("MSDH", "MSDH"),
    ("Evaporation Section", "EVAP"),
    ("Dryer Section", "DRY"),
    ("ETP", "ETP"),
    ("WTP", "WTP"),
    ("CO2 Plant", "CO2"),
    ("Warehouse Stores", "WHS"),
]

DELAY_REASONS = ["Manpower Shortage", "Material Delay", "Design/Approval Pending",
                 "Weather", "Rework", "Other"]

# EOD task status master — (name, is_stopped, colour, order). Editable later in
# the Progress Status list without any code change.
PROGRESS_STATUSES = [
    ("Work Done", 0, "Green", 1),
    ("Work in Progress", 0, "Blue", 2),
    ("Stopped — Rain / Natural Cause", 1, "Red", 3),
    ("Stopped — Material Not Available", 1, "Red", 4),
    ("Stopped — Manpower Shortage", 1, "Red", 5),
    ("Stopped — Awaiting Approval/Drawing", 1, "Red", 6),
    ("Stopped — Other", 1, "Red", 7),
]

EMPLOYMENT_TYPES = ["Ramshy Bio Staff", "Benkas Staff"]


def seed_progress_statuses():
    """Idempotent — creates the 7 default EOD statuses, keeps flags/colour in sync."""
    for name, stopped, color, order in PROGRESS_STATUSES:
        if frappe.db.exists("Progress Status", name):
            frappe.db.set_value("Progress Status", name,
                                {"is_stopped": stopped, "color": color, "display_order": order})
            continue
        frappe.get_doc({"doctype": "Progress Status", "status_name": name,
                        "is_stopped": stopped, "color": color, "display_order": order}
                       ).insert(ignore_permissions=True)


def _ensure_company():
    company = frappe.defaults.get_defaults().get("company") or \
        frappe.db.get_value("Company", {}, "name")
    if company:
        return company
    # Only reached when the site has NO company (e.g. ERPNext setup wizard not run).
    # Company creation makes a "Goods In Transit" warehouse that needs the standard
    # "Transit" Warehouse Type, which the wizard would have seeded — ensure it so a
    # bare-site seed doesn't fail with LinkValidationError.
    if not frappe.db.exists("Warehouse Type", "Transit"):
        frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"}).insert(
            ignore_permissions=True, ignore_if_duplicate=True)
    doc = frappe.get_doc({
        "doctype": "Company",
        "company_name": COMPANY_NAME,
        "abbr": COMPANY_ABBR,
        "default_currency": "INR",
        "country": "India",
        "create_chart_of_accounts_based_on": "Standard Template",
        "chart_of_accounts": "Standard",
    }).insert(ignore_permissions=True)
    frappe.db.set_default("company", doc.name)
    return doc.name


def _ensure_fiscal_year():
    if frappe.db.exists("Fiscal Year", {"disabled": 0}):
        return
    from datetime import date
    today = date.today()
    start_year = today.year if today.month >= 4 else today.year - 1
    frappe.get_doc({
        "doctype": "Fiscal Year",
        "year": f"{start_year}-{start_year + 1}",
        "year_start_date": f"{start_year}-04-01",
        "year_end_date": f"{start_year + 1}-03-31",
    }).insert(ignore_permissions=True)


def _root(doctype, company):
    return frappe.db.get_value(doctype, {"company": company, "is_group": 1},
                               "name", order_by="lft asc")


def run():
    company = _ensure_company()
    _ensure_fiscal_year()

    for et in EMPLOYMENT_TYPES:
        if not frappe.db.exists("Employment Type", et):
            frappe.get_doc({"doctype": "Employment Type", "employee_type_name": et}
                           ).insert(ignore_permissions=True)

    for r in DELAY_REASONS:
        if not frappe.db.exists("Delay Reason", r):
            frappe.get_doc({"doctype": "Delay Reason", "reason": r}).insert(ignore_permissions=True)

    seed_progress_statuses()

    if not frappe.db.exists("Project", PROJECT_NAME):
        project = frappe.get_doc({"doctype": "Project", "project_name": PROJECT_NAME}
                                 ).insert(ignore_permissions=True).name
    else:
        project = PROJECT_NAME

    root_wh = _root("Warehouse", company)
    root_cc = _root("Cost Center", company)

    made = []
    for name, code in SECTIONS:
        if frappe.db.exists("Plant Section", code):
            continue

        wh = frappe.db.get_value("Warehouse", {"warehouse_name": name, "company": company}, "name")
        if not wh:
            wh = frappe.get_doc({
                "doctype": "Warehouse", "warehouse_name": name, "company": company,
                "parent_warehouse": root_wh,
            }).insert(ignore_permissions=True).name

        task = frappe.db.get_value("Task", {"subject": name, "project": project}, "name")
        if not task:
            task = frappe.get_doc({
                "doctype": "Task", "subject": name, "project": project,
            }).insert(ignore_permissions=True).name

        cc = frappe.db.get_value("Cost Center", {"cost_center_name": name, "company": company}, "name")
        if not cc:
            cc = frappe.get_doc({
                "doctype": "Cost Center", "cost_center_name": name, "company": company,
                "parent_cost_center": root_cc, "is_group": 0,
            }).insert(ignore_permissions=True).name

        frappe.get_doc({
            "doctype": "Plant Section",
            "section_name": name, "section_code": code,
            "warehouse": wh, "project_task": task, "cost_center": cc, "is_active": 1,
        }).insert(ignore_permissions=True)
        made.append(code)

    frappe.db.commit()

    # construction activity master + per-section WBS sub-tasks
    from benkas_erp.setup import activities
    activities.seed_activities()
    wbs = activities.generate_section_tasks()

    print("Company:", company)
    print("Plant Sections created:", made)
    print("WBS sub-tasks:", wbs)
    return {"company": company, "sections": made, "wbs": wbs}
