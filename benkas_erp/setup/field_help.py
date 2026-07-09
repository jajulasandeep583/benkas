"""
Plain-language help text (grey text under the field) for the fields a human
fills by hand. Applied as Property Setters so it works on both the app's own
DocTypes and customised standard ones, and reproduces on migrate.
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

FIELD_HELP = {
    "Gate Entry": {
        "person_type": "Is this a company Employee, a Contractor firm, or an individual Labour?",
        "person": "Scan the ID card or pick the person entering the gate.",
        "plant_section": "Which plant area they are working in today.",
        "entry_type": "In when they arrive, Out when they leave.",
        "photo": "Take a live photo at the gate to confirm who actually entered.",
        "override_reason": "If you typed the time by hand instead of scanning, say why.",
        "ppe_checklist": "Tick the safety gear the person is actually wearing before letting them in.",
        "acknowledgement_status": "Set by the Section Incharge once they confirm the person reported for work.",
    },
    "Daily Progress Log": {
        "plant_section": "The plant area this day's log is for.",
        "log_date": "The date the work actually happened.",
        "incharge": "Defaults to you — the person responsible for this section today.",
        "no_work_today": "Tick if nothing happened here today — then just type the reason and submit.",
        "no_work_reason": "Why there was no work (holiday, full rain day, etc.).",
        "photos": "Attach at least one site photo for the day (you don't need one per task).",
        "remarks": "Anything worth noting about the day.",
    },
    "Daily Task Progress": {
        "task": "The specific sub-task worked on today (only tasks under this section are shown).",
        "status": "Work Done, Work in Progress, or one of the Stopped reasons.",
        "percent_complete": "How complete this task is now, as a percentage (you type it).",
        "work_description": "What was actually done today — or, if stopped, why. At least 15 characters.",
    },
    "Daily Progress Photo": {
        "activity_task": "Optional — tag the task this photo shows so photos group by task.",
    },
    "Daily Worker Log": {
        "person_type": "Employee, Contractor or Labour.",
        "person": "Who worked today. They must already have a gate entry for this section today, or the log won't save.",
        "task": "Which sub-task they worked on (optional).",
        "hours": "Hours worked. Defaults to 8 (a full day).",
    },
    "Daily Material Consumed": {
        "item": "The material used from section stores.",
        "qty": "How much was used.",
        "uom": "Unit of measure (e.g. Nos, Kg, Bags).",
        "task": "Which sub-task it was used for.",
        "material_request": "Link the request this was issued against, if there was one.",
        "no_material_request": "Ticked automatically if this item wasn't formally requested first — used for tracking, doesn't block the entry.",
    },
    "Gate Pass": {
        "reason": "Why the person needs to leave site during working hours.",
        "destination": "Where they are going.",
        "expected_out_time": "When they plan to leave.",
        "expected_return_time": "When they are expected back — used to flag overdue passes.",
        "pass_status": "Moves Requested → Approved → Out → Returned as the pass is used.",
    },
    "Safety Work Permit": {
        "permit_type": "The kind of high-risk job (hot work, height, confined space, etc.).",
        "valid_from": "Start of the window this permit is valid for.",
        "valid_to": "End of the validity window.",
        "site_photo": "Photo of the work area before starting (required).",
        "ppe_photo": "Photo showing workers in the required safety gear (required).",
        "barricading_photo": "Photo of the barricading / fire-watch arrangement.",
        "closing_confirmation": "Tick only after you've physically checked the job is finished and the area is safe — required before the permit can be closed.",
    },
    "Electrical Work Permit": {
        "loto_confirmed": "Tick only after the equipment is locked out, tagged out and verified dead — required before this permit can be approved.",
        "closure_signoff": "Tick only after the equipment has been safely re-energized and handed back — required before closing.",
        "job_log": "Record start/stop times and any hand-over during the job.",
    },
    "Safety Violation Log": {
        "violation_type": "What was seen (no helmet, no shoes, unsafe act, etc.).",
        "person": "Who committed the violation (leave blank if unknown).",
        "photo": "Photo evidence of the violation (required).",
        "corrective_action": "What was done about it on the spot.",
        "status": "Open until the issue is fixed, then set to Corrected.",
    },
    "Visitor Log": {
        "visitor_name": "Name of the person visiting.",
        "company": "Who they represent.",
        "purpose": "Why they are here.",
        "host_person": "The person or section they are here to see.",
        "photo": "Live photo of the visitor at the gate.",
    },
    "Material Request": {
        "material_request_type": "Choose 'Material Issue' for material going out to site work.",
    },
}


def apply():
    for doctype, fields in FIELD_HELP.items():
        if not frappe.db.exists("DocType", doctype):
            continue
        meta = frappe.get_meta(doctype)
        for fieldname, text in fields.items():
            if not meta.get_field(fieldname):
                continue
            make_property_setter(doctype, fieldname, "description", text, "Text",
                                 validate_fields_for_doctype=False)
