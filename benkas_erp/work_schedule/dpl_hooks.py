"""
Daily Progress Log = the single end-to-end site log per section per day.

All logic is server-side (hooks), so a mobile/PWA client POSTing straight to the
REST API gets the exact same validation and rollups as the desk UI.

The EOD form is deliberately simple — per task row: task, status, % complete,
work description. Photos are per LOG (>=1), optionally tagged per task.

validate (only what stops garbage):
  - work_description >= 15 chars, and a status, on every task row
  - a stopped status must not raise the task's % (warn, never block)
  - at least one site photo for the day (not one per task)
  - workers / material pointing at a task with no activity row -> friendly warning
  - every worker row must have a matching Gate Entry (In) for this section/date
  - "No Work Today" short-circuits everything (reason required, tables cleared)

on_submit:
  - push each Task row's typed % straight onto Task.progress (last log wins)
  - accrue manpower-days on Task from Worker rows
  - batch all Material Consumed rows into ONE submitted Stock Entry (Material
    Issue) for the section; consume against a Material Request where linked
  - accrue material value on Task and recompute the section % complete
"""

import frappe
from frappe import _
from frappe.utils import flt

MIN_DESC = 15


def _is_stopped(status):
    return bool(status) and bool(frappe.db.get_value("Progress Status", status, "is_stopped"))


def _section_task_set(section):
    parent = frappe.db.get_value("Plant Section", section, "project_task")
    if not parent:
        return set()
    return set(frappe.get_all("Task", filters={"parent_task": parent}, pluck="name")) | {parent}


def _warn_orphan_task(rows, logged_tasks, label):
    for r in (rows or []):
        if r.get("task") and r.task not in logged_tasks:
            frappe.msgprint(
                _("Heads up: a {0} row points at {1}, which has no task row today. "
                  "Add a task row for it so its progress is captured.").format(label, r.task),
                indicator="orange", alert=True)


# --------------------------------------------------------------------------
def validate(doc, method=None):
    if not doc.incharge:
        doc.incharge = frappe.session.user

    # "Nothing happened today" — reason required, then keep the log clean.
    if doc.no_work_today:
        if not (doc.no_work_reason or "").strip():
            frappe.throw(_("Tick 'No Work Today' means you must type a short reason."))
        doc.task_progress = []
        doc.workers_present = []
        doc.material_consumed = []
        return

    if not doc.task_progress:
        frappe.throw(_("Add at least one task row — or tick <b>No Work Today</b>."))

    section_tasks = _section_task_set(doc.plant_section)
    logged_tasks = set()
    for r in doc.task_progress:
        if not r.task:
            frappe.throw(_("Every task row needs a task selected."))
        if not r.status:
            frappe.throw(_("Row for {0}: pick a status.").format(r.task))
        if len((r.work_description or "").strip()) < MIN_DESC:
            frappe.throw(_("Row for {0}: describe the work in at least {1} characters "
                           "(what was done, or why it stopped).").format(r.task, MIN_DESC))
        if section_tasks and r.task not in section_tasks:
            frappe.msgprint(_("Heads up: {0} is not a task of section {1}.")
                            .format(r.task, doc.plant_section), indicator="orange", alert=True)
        if _is_stopped(r.status) and r.percent_complete is not None:
            cur = flt(frappe.db.get_value("Task", r.task, "progress"))
            if flt(r.percent_complete) > cur:
                frappe.msgprint(
                    _("Heads up: {0} is marked stopped but its % went up "
                      "({1}% → {2}%). Usually a stopped task stays at {1}%.")
                    .format(r.task, round(cur), round(flt(r.percent_complete))),
                    indicator="orange", alert=True)
        logged_tasks.add(r.task)

    # photos: at least one per LOG, not per task row
    if not doc.photos:
        frappe.throw(_("Add at least one site photo for the day "
                       "(you don't need one per task)."))

    _warn_orphan_task(doc.workers_present, logged_tasks, "worker")
    _warn_orphan_task(doc.material_consumed, logged_tasks, "material")

    _validate_workers(doc)

    for r in (doc.material_consumed or []):
        r.no_material_request = 0 if r.material_request else 1


def _validate_workers(doc):
    """Each worker must have a Gate Entry (In) for this section on this date."""
    start = f"{doc.log_date} 00:00:00"
    end = f"{doc.log_date} 23:59:59"
    for r in (doc.workers_present or []):
        if not r.person:
            continue
        exists = frappe.db.exists("Gate Entry", {
            "person_type": r.person_type, "person": r.person,
            "plant_section": doc.plant_section, "entry_type": "In",
            "time_in": ["between", [start, end]],
        })
        if not exists:
            frappe.throw(_("{0} has no gate entry for this section today "
                           "(section {1}, {2}).").format(r.person, doc.plant_section, doc.log_date))


# --------------------------------------------------------------------------
def on_submit(doc, method=None):
    if doc.no_work_today:
        return  # nothing to roll up on a no-work day
    _apply_task_progress(doc)
    _accrue_manpower(doc)
    _issue_material(doc)
    _recalc_section(doc.plant_section)


def _apply_task_progress(doc):
    for r in (doc.task_progress or []):
        if r.task and r.percent_complete is not None:
            frappe.db.set_value("Task", r.task, "progress", r.percent_complete)


def _accrue_manpower(doc):
    for r in (doc.workers_present or []):
        if not r.task:
            continue
        days = (r.hours or 0) / 8.0
        cur = frappe.db.get_value("Task", r.task, "manpower_days_logged") or 0
        frappe.db.set_value("Task", r.task, "manpower_days_logged", cur + days)


def _issue_material(doc):
    rows = [r for r in (doc.material_consumed or []) if r.item and r.qty]
    if not rows:
        return

    warehouse = frappe.db.get_value("Plant Section", doc.plant_section, "warehouse")
    if not warehouse:
        frappe.throw(_("Plant Section {0} has no warehouse set — cannot issue material.")
                     .format(doc.plant_section))
    company = frappe.defaults.get_defaults().get("company") or frappe.db.get_value("Company", {}, "name")

    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Issue"
    se.company = company
    se.posting_date = doc.log_date
    se.set_posting_time = 1
    # custom fields from the material customization
    se.plant_section = doc.plant_section
    se.benkas_task = rows[0].task or None

    for r in rows:
        item = {"item_code": r.item, "qty": r.qty, "s_warehouse": warehouse,
                "allow_zero_valuation_rate": 1}
        if r.uom:
            item["uom"] = r.uom
        if r.material_request:
            item["material_request"] = r.material_request
            mri = frappe.db.get_value("Material Request Item",
                                      {"parent": r.material_request, "item_code": r.item}, "name")
            if mri:
                item["material_request_item"] = mri
        se.append("items", item)

    se.insert(ignore_permissions=True)
    se.submit()
    doc.db_set("stock_entry", se.name)

    # flip each linked Material Request's benkas_status based on issued vs requested qty
    for mr_name in {r.material_request for r in rows if r.material_request}:
        _update_material_request_status(mr_name)

    # accrue material value per task from the submitted stock entry amounts
    amount_by_item = {}
    for sei in se.items:
        amount_by_item.setdefault(sei.item_code, 0)
        amount_by_item[sei.item_code] += (sei.amount or 0)
    task_value = {}
    for r in rows:
        if r.task:
            task_value.setdefault(r.task, 0)
            task_value[r.task] += amount_by_item.get(r.item, 0) * (r.qty / sum(
                x.qty for x in rows if x.item == r.item))
    for task, val in task_value.items():
        cur = frappe.db.get_value("Task", task, "material_consumed_value") or 0
        frappe.db.set_value("Task", task, "material_consumed_value", cur + val)


def _update_material_request_status(mr_name):
    """Set the Material Request's benkas_status from issued-vs-requested qty:
    Issued when every item is fully issued, else Partially Issued. Never
    overrides a manually Closed request. Issued qty is summed from the linked
    submitted Stock Entry rows (deterministic, not reliant on core side-effects)."""
    if not frappe.db.exists("Material Request", mr_name):
        return
    if not frappe.get_meta("Material Request").get_field("benkas_status"):
        return
    if frappe.db.get_value("Material Request", mr_name, "benkas_status") == "Closed":
        return

    items = frappe.get_all("Material Request Item", filters={"parent": mr_name},
                           fields=["name", "qty"])
    if not items:
        return

    fully, any_issued = True, False
    for it in items:
        issued = frappe.db.sql(
            """SELECT COALESCE(SUM(sed.qty), 0) FROM `tabStock Entry Detail` sed
               JOIN `tabStock Entry` se ON se.name = sed.parent
               WHERE sed.material_request_item = %s AND se.docstatus = 1""",
            it.name)[0][0] or 0
        if issued > 0:
            any_issued = True
        if issued < (it.qty or 0):
            fully = False

    new_status = "Issued" if fully else ("Partially Issued" if any_issued else None)
    if new_status:
        frappe.db.set_value("Material Request", mr_name, "benkas_status", new_status)


def _recalc_section(section):
    """Section % complete = task_weight-weighted average of its WBS sub-tasks'
    progress (falls back to a plain average when no weights are set)."""
    parent = frappe.db.get_value("Plant Section", section, "project_task")
    if not parent:
        return
    subs = frappe.get_all("Task", filters={"parent_task": parent},
                          fields=["progress", "task_weight"])
    if not subs:
        subs = [{"progress": frappe.db.get_value("Task", parent, "progress") or 0, "task_weight": 0}]
    tw = sum((s.get("task_weight") or 0) for s in subs)
    if tw > 0:
        pct = sum((s.get("progress") or 0) * (s.get("task_weight") or 0) for s in subs) / tw
    else:
        pct = sum((s.get("progress") or 0) for s in subs) / len(subs)
    if frappe.get_meta("Plant Section").get_field("section_percent_complete"):
        frappe.db.set_value("Plant Section", section, "section_percent_complete", round(pct, 1))
