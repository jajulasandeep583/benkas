"""
Complete Benkas ERP User Guide generator.

Introspects the LIVE site (workspaces, doctypes, fields + help text, reports,
pages, print formats) so the structural inventory and every field table are
provably complete and cannot drift, then wraps that skeleton in curated,
site-staff-level walkthroughs. Produces one docx with a Word TOC field.

    bench --site <site> execute benkas_erp.setup.userguide.build

Returns the covered-item lists so audit.py can assert completeness.
"""

import os

import frappe
from frappe.utils import today, formatdate

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

WIN_DIR = "/mnt/c/Users/jajul/Downloads/BENKAS PM"
NAVY = RGBColor(0x16, 0x32, 0x4F)
GREY = RGBColor(0x55, 0x60, 0x6A)
MODULES = ["Benkas Core", "Manpower", "Material", "Work Schedule", "Site Safety Assets"]
SKIP_FT = {"Section Break", "Column Break", "Tab Break", "HTML", "Fold", "Heading", "Button"}

# ----------------------------------------------------------------------------
# CURATED CONTENT (the human explanations; structure/fields come from the site)
# ----------------------------------------------------------------------------
# doctype -> dict(about, on_submit, errors=[(message, meaning)], tip)
DOC = {
    "Gate Entry": {
        "about": "The record of one person (staff, contractor or labour) entering or leaving a "
                 "plant section. Normally created automatically by the Scan Station, but can be "
                 "filled by hand. It is the source of truth for who was on site — attendance, "
                 "manpower reports and the Daily Progress Log's worker check all read from it.",
        "on_submit": "Gate Entry is not submitted (workflows are off) — it saves as a record. "
                     "For staff, a matching HRMS Employee Checkin is created so attendance is "
                     "calculated. A QR key (EMP-/LAB-…) is stamped so the next scan finds it.",
        "errors": [("Photo is mandatory", "Every gate IN needs a live photo — snap it, or use "
                    "'Log IN without photo' only if the camera is broken."),
                   ("No open entry to close", "You scanned OUT for someone with no open IN today "
                    "— they never scanned in, so there is nothing to close.")],
        "tip": "Use the Scan Station for everyday gate work; open Gate Entry directly only to "
               "review or correct a record.",
    },
    "Daily Progress Log": {
        "about": "THE end-of-day site log — one per section per day. It captures what each task "
                 "achieved (with a status and %), who worked, and what material was used. This is "
                 "the single most important daily entry: everything on the dashboards flows from it.",
        "on_submit": "On Submit the system does all of this for you, automatically:\n"
                     "• writes each task row's typed % onto the Task (last log of the day wins);\n"
                     "• recalculates the section's overall % complete;\n"
                     "• adds the worker hours as manpower-days onto each task;\n"
                     "• creates and submits ONE Stock Entry (Material Issue) for every material "
                     "row, so stock drops — you never open Stock Entry yourself;\n"
                     "• if a material row was linked to a Material Request, moves that request to "
                     "Partially Issued / Issued.",
        "errors": [("Add at least one task row — or tick No Work Today",
                    "A working-day log needs at least one task row. If truly nothing happened, "
                    "tick No Work Today and give a reason instead."),
                   ("Row for <task>: describe the work in at least 15 characters",
                    "The Work Description is too short. Say what was actually done, or why it "
                    "stopped."),
                   ("Row for <task>: pick a status", "Every task row needs a status "
                    "(Work Done / Work in Progress / a Stopped reason)."),
                   ("Add at least one site photo for the day",
                    "At least one photo is required per log (not per task). Tick No Work Today to "
                    "skip photos on an idle day."),
                   ("<person> has no gate entry for this section today",
                    "You added a worker who never scanned in to this section today. Only people "
                    "with a gate entry can be counted — deliberate, so manpower stays honest."),
                   ("Heads up: <task> is marked stopped but its % went up",
                    "A friendly WARNING, not a block. A stopped task usually keeps the same %.")],
        "tip": "On a phone, staff file this from the Benkas PWA 'Daily EOD' tile — same fields, "
               "same rules.",
    },
    "Material Request": {
        "about": "A request for material to be issued to your section's work. Standard ERPNext "
                 "Material Request, extended with Plant Section, Task and a Benkas status so it "
                 "fits the site flow.",
        "on_submit": "On Submit it becomes 'Requested'. After approval set the Benkas status to "
                     "'Approved'; the daily log then issues stock against it and moves it to "
                     "Partially Issued / Issued. The PM closes it when done.",
        "errors": [("Warehouse is mandatory for stock item",
                    "A stockable item needs the section warehouse on its row.")],
        "tip": "Statuses: Requested → Approved → Partially Issued → Issued → Closed.",
    },
    "Purchase Receipt": {
        "about": "The Goods Receipt Note (GRN) — records material arriving at the gate from a "
                 "supplier, with weighbridge readings and the mandatory supplier-invoice photo.",
        "on_submit": "On Submit stock is added to the section warehouse. A large gap between the "
                     "weighbridge net weight and the invoice quantity raises a Weight Variance "
                     "flag for the Incharge to review.",
        "errors": [("Invoice / delivery-challan photo is mandatory",
                    "The GRN will not save without the supplier document photo — it is your proof "
                    "the material and paperwork arrived together.")],
        "tip": "Fill the weighbridge slip number and gross/tare/net weights when a truck is "
               "weighed.",
    },
    "Quality Inspection": {
        "about": "The accept / reject / partial decision on received material, with photos of the "
                 "goods. Standard ERPNext Quality Inspection.",
        "on_submit": "A 'Rejected' inspection feeds the QC Rejection Report so bad material is "
                     "tracked back to the supplier and the Purchase Receipt.",
        "errors": [], "tip": "Attach at least one photo of the inspected material.",
    },
    "Stock Entry": {
        "about": "Standard stock movement. On this site you rarely open it by hand — the Daily "
                 "Progress Log creates the Material Issue entries for you.",
        "on_submit": "Moves stock in/out of warehouses.", "errors": [],
        "tip": "Look here to audit an auto-created Material Issue from a daily log.",
    },
    "Safety Work Permit": {
        "about": "A permit to do a high-risk job (hot work, height, confined space, excavation) "
                 "with the workers involved and mandatory site/PPE photos.",
        "on_submit": "Not submitted — the Permit Status field is set by hand for now (workflows "
                     "are OFF; see the Admin appendix). A photo of the site area and PPE-in-use "
                     "is mandatory.",
        "errors": [("Site/Area photo and PPE-in-use photo are mandatory",
                    "A safety permit cannot be raised without both photos.")],
        "tip": "Statuses run Requested → Approved → Work in Progress → Closed (set manually).",
    },
    "Electrical Work Permit": {
        "about": "A permit for electrical work, with LOTO (lock-out/tag-out) confirmation and a "
                 "job log of start/stop and handover notes.",
        "on_submit": "Not submitted — Permit Status set by hand for now. Tick LOTO Confirmed only "
                     "when isolation is verified.",
        "errors": [], "tip": "Close-out requires the 'Re-energized' sign-off tick.",
    },
    "Safety Violation Log": {
        "about": "A logged safety breach (no helmet, unsafe act…) with a mandatory photo and the "
                 "corrective action taken. Feeds the safety reports and the exceptions page.",
        "on_submit": "Not submitted. An 'Open' violation shows on dashboards until you set it to "
                     "'Corrected'.",
        "errors": [("Photo is mandatory", "A violation must have a photo — it is the evidence.")],
        "tip": "Repeat offenders roll up by contractor in the 'Safety Violations by Contractor' "
               "report.",
    },
    "Gate Pass": {
        "about": "Permission for a person to leave site during working hours (and return). The "
                 "gate scans the pass out and back in.",
        "on_submit": "Not submitted. Pass Status moves Requested → Approved → Out → Returned; a "
                     "scheduler flags passes as Overdue when the expected return time passes.",
        "errors": [("PASS NOT APPROVED", "The pass is still Requested — the person's Incharge "
                    "must Approve it before they can leave.")],
        "tip": "Print the Gate Pass Slip (QR) so the gate can scan it.",
    },
    "Visitor Log": {
        "about": "A site visitor with their company, host, purpose and photo. The gate signs them "
                 "in and out.",
        "on_submit": "Not submitted. Print the Visitor Slip (QR) for sign-out at the gate.",
        "errors": [], "tip": "Visitors still on site (no time-out) show in the Visitor Register "
                             "Summary.",
    },
    "Contractor Tools Register": {
        "about": "Tools a contractor brings in, with quantity and photo. The gate scans them out "
                 "and the returned quantity must match.",
        "on_submit": "Status auto-flips In → Returned, or 'Mismatch' when the returned quantity "
                     "differs from what came in.",
        "errors": [], "tip": "A 'Mismatch' means hold the person and call the Incharge.",
    },
    "Site Vehicle Log": {
        "about": "A trip for a site vehicle — driver, purpose, out/in times and odometer.",
        "on_submit": "Not submitted. Feeds the Vehicle Utilisation report.",
        "errors": [], "tip": "Fill odometer start/end to get distance in the report.",
    },
    "Generator Log": {
        "about": "A generator run — start/stop, meter and diesel readings; running hours and "
                 "consumption are computed.",
        "on_submit": "Running hours and litres-per-hour are calculated on save from your times "
                     "and meter readings.",
        "errors": [], "tip": "Feeds the Generator Consumption MIS.",
    },
    "Power Consumption Log": {
        "about": "A phase-current and voltage reading for a section, per shift.",
        "on_submit": "Saved as a reading.", "errors": [], "tip": "Log by shift for trend tracking.",
    },
    "Labour Master": {
        "about": "A contract labourer's record — name, contractor, category, ID proof and photo. "
                 "The QR ID card prints from here.",
        "on_submit": "A QR key (LAB-…) is stamped for the Scan Station. An 'Inactive'/'Exited' "
                     "labourer is blocked at the gate.",
        "errors": [], "tip": "Print the Labour ID Card (80mm thermal, with photo + QR).",
    },
    "Contractor": {
        "about": "A labour/works agency — licence, agreement validity, contact and linked "
                 "Supplier. Labour and billing group under the contractor.",
        "on_submit": "Saved as a master.", "errors": [], "tip": "Set Agreement Valid Upto so "
                     "expiries can be tracked.",
    },
    "Plant Section": {
        "about": "One area of the plant (Distillation, Fermentation…). Each section links a "
                 "Warehouse, a parent Project Task (its WBS) and a Cost Center, and carries the "
                 "rolled-up section % complete.",
        "on_submit": "Saved as a master. Its Project Task holds the section's activity sub-tasks.",
        "errors": [], "tip": "The 12 sections are seeded — you rarely add new ones.",
    },
    "Construction Activity": {
        "about": "A standard activity in the build sequence (Civil → Erection → … → Commissioning) "
                 "with a default duration and weight. Used to generate each section's task list.",
        "on_submit": "Saved as a master. Running the WBS generator creates these activities as "
                     "sub-tasks under every section.",
        "errors": [], "tip": "See the Admin appendix to regenerate section tasks after changing "
                     "activities.",
    },
    "Progress Status": {
        "about": "The small editable list behind the EOD status dropdown — Work Done, Work in "
                 "Progress and the Stopped reasons. Each row has a colour (for the chips) and an "
                 "'Is a Stoppage' tick (which drives the Stoppage Analysis report).",
        "on_submit": "Saved as a master. Add or rename a status here anytime — no code change "
                     "needed; the EOD form and reports pick it up.",
        "errors": [], "tip": "Tick 'Is a Stoppage' on any status that means work did not progress.",
    },
    "Delay Reason": {
        "about": "A short master list of delay reasons (kept for reference/history).",
        "on_submit": "Saved as a master.", "errors": [],
        "tip": "Day-to-day stoppages are now captured by the task Status; this list is legacy.",
    },
    "Generator Master": {"about": "A generator on site — its ID, capacity and section.",
                         "on_submit": "Saved as a master.", "errors": [], "tip": ""},
    "Site Vehicle": {"about": "A site vehicle — number, type, owner and driver.",
                     "on_submit": "Saved as a master.", "errors": [], "tip": ""},
    "Employee": {"about": "Standard HRMS Employee — your permanent staff. Their gate scans create "
                          "Employee Checkins and attendance.",
                 "on_submit": "Saved. A QR key (EMP-…) is stamped for the Scan Station.",
                 "errors": [], "tip": "Print the Staff ID Card (QR)."},
    "Task": {"about": "Standard Frappe Task — one activity under a section. Its % is set by the "
                      "daily log or edited inline on Section 360. PMs can add/rename tasks under a "
                      "section's parent task and they appear everywhere automatically.",
             "on_submit": "Progress and status feed the section rollup and the WBS reports.",
             "errors": [], "tip": "Plan tentative dates in the Section Task Planner."},
    "Project": {"about": "Standard Frappe Project — the whole plant build. The 12 sections' parent "
                         "tasks live under it.", "on_submit": "Saved.", "errors": [], "tip": ""},
    "Item": {"about": "Standard ERPNext Item — the materials master.", "on_submit": "Saved.",
             "errors": [], "tip": ""},
    "Supplier": {"about": "Standard ERPNext Supplier — material vendors.", "on_submit": "Saved.",
                 "errors": [], "tip": ""},
}

# report -> dict(q=question it answers, read=how to read it)
REP = {
    "Gate Register": {"q": "Every in/out event across the whole site (people, visitors, vehicles, "
                      "tools, gate passes, material trucks) in one timeline.",
                      "read": "Date range + optional Type / Direction / Section / Contractor "
                      "filters. Each row links back to its source record."},
    "EOD Manpower MIS": {"q": "How many people were on each section, by category, per day — with "
                         "acknowledgement gaps.", "read": "Group by date + section + category."},
    "Labour Attendance Register": {"q": "Per-labourer daily in/out, hours and OT from gate scans.",
                                   "read": "One row per labourer per day."},
    "Staff Attendance Summary": {"q": "Staff attendance (from HRMS Attendance) — status, in/out, "
                                 "hours, late flag.", "read": "One row per employee per day."},
    "Contractor-wise Labour Count": {"q": "How many labourers each contractor has, by skill and "
                                     "active status.", "read": "One row per contractor."},
    "Late Entry and OT Report": {"q": "Who came in late and who did overtime.",
                                 "read": "Late flag when first-in is after 09:00."},
    "Material Received vs Issued": {"q": "Per section: material received vs issued value.",
                                    "read": "Compare Received Qty against Issued Qty/Value."},
    "Material Section Stock Balance": {"q": "On-hand quantity and value in each section's stores.",
                                       "read": "One row per section warehouse."},
    "Material Consumption by Item": {"q": "Which items were consumed at site (from the daily log), "
                                     "by section.", "read": "Sorted by quantity consumed."},
    "QC Rejection Report": {"q": "Every rejected quality inspection with its reference.",
                            "read": "Trace a rejection back to the Purchase Receipt."},
    "Safety Violations Summary": {"q": "Violations by section, type and person, with open counts.",
                                  "read": "Sorted by frequency."},
    "Safety Violations by Contractor": {"q": "Which contractor's people breach safety most.",
                                        "read": "Rolls violations up to the contractor."},
    "Generator Consumption MIS": {"q": "Generator running hours, diesel and litres/hour per day.",
                                  "read": "One row per generator per day."},
    "Vehicle Utilisation": {"q": "Trips, hours out and distance per site vehicle.",
                            "read": "One row per vehicle."},
    "Visitor Register Summary": {"q": "Visitor counts per section, distinct companies/visitors and "
                                 "who is still on site.", "read": "Still-On-Site = no time-out."},
    "Section Manpower & Work Log": {"q": "Per section per day (last 30 days): workers, person-days "
                                    "and the actual work descriptions.",
                                    "read": "The narrative of what each section did."},
    "Section Progress - Planned vs Actual": {"q": "Each section's task progress vs latest reported "
                                             "%.", "read": "Compare Task Progress to Reported."},
    "Section WBS Progress": {"q": "Every section activity with status, progress and planned dates.",
                             "read": "The full work-breakdown at a glance."},
    "Stoppage Analysis": {"q": "Stopped section-days by reason and by section/task across a week — "
                          "this is where 'rain cost us 6 section-days' comes from.",
                          "read": "Date range + optional section. Sorted by most stopped days."},
    "Weekly Section MIS": {"q": "One summary row per section for the last 7 days — logs filed, "
                           "latest %, open material requests.", "read": "The weekly one-glance."},
    "Weekly Section Report": {"q": "Pick a section + week and see everything: each task's latest "
                              "%, status, days worked/stopped, the work narrative, person-days, "
                              "material and photo count.",
                              "read": "Section + From/To date filters. The deep per-section view."},
}

# desk page -> walkthrough (list of steps)
PAGE = {
    "benkas-scan": {
        "title": "Scan Station (Gate Scan Station)",
        "about": "The gate's home screen. A USB barcode scanner or the device camera reads a QR "
                 "on an ID card / slip and the station does the right thing automatically — "
                 "supermarket style. The input box is always focused so a USB scanner just works.",
        "steps": [
            "Keep the page open at the gate. The scan box stays focused — a USB scanner types the "
            "code and hits Enter for you; or tap the camera button to scan with the device camera.",
            "PERSON IN: scan an ID card (EMP-/LAB-/staff). The station finds the person, shows "
            "their PHOTO + name + contractor, pre-fills the section, opens the camera to snap a "
            "live IN photo, and creates the Gate Entry (In). A big banner confirms who and what.",
            "PERSON OUT: scan the same card again — the station finds today's open IN and closes "
            "it (sets time-out). No typing.",
            "TEMP PASS: tap 'Temp Pass' to quick-register a one-day labourer (or reuse a "
            "lost-card master) and print a Temporary Gate Slip (TMP- QR). Next day that slip is "
            "rejected as expired.",
            "TOOLS IN: tap 'Tools In' to open the Contractor Tools Register and print a "
            "Contractor Tools Slip (TOOL- QR) for scanning out later.",
            "GATE PASS: scan a Gate Pass Slip — if Approved it marks the person Out; scan again on "
            "return to mark Returned. A red 'PASS NOT APPROVED' means send them back to approve.",
            "VISITOR: scan a Visitor Slip to sign the visitor out.",
            "Read the RESULT BANNER after every scan (green = done, red = blocked, e.g. "
            "'…is Exited — ENTRY BLOCKED'). The recent-scans list shows the last events, each with "
            "a 'Print Slip' button.",
        ],
    },
    "section-360": {
        "title": "Section 360°",
        "about": "One screen that shows everything about a section: progress, the task checklist, "
                 "manpower, material and recent activity. The PM can edit a task's % right here.",
        "steps": [
            "Pick a section in the box at the top. The whole 360° view loads.",
            "HEADER: section % complete, tasks done / total, how many tasks are Stopped, and an "
            "overall On-Track / Attention pill.",
            "TASK CHECKLIST: every task with an editable % box (type a new number and it saves + "
            "rolls the section up), a coloured status chip (green = done, blue = in progress, "
            "red = stopped), the last work description, and the photos tagged to that task.",
            "MANPOWER: on-site-today headcount, person-days (7-day and total), and breakdowns by "
            "category and contractor.",
            "MATERIAL: consumed value, top items issued, and open material requests.",
            "RECENT ACTIVITY: the last daily logs with photo, status and %.",
        ],
    },
    "section-task-planner": {
        "title": "Section Task Planner",
        "about": "Set the tentative start/end dates (and optional weight) for each activity in a "
                 "section, so 'Delayed' can be detected and the client report has a schedule.",
        "steps": [
            "Pick a section. Its activities load with any dates already set.",
            "Either set a Section Start Date and click 'Re-fill dates from start' to cascade dates "
            "down the list by weight, or type each Tentative Start / Tentative End by hand.",
            "Weight is optional — the section % works as a plain average if you leave weights at 0. "
            "If you use weights, the Total turns green at 1.00.",
            "Click 'Save Plan'. You'll see 'Saved N tasks' and the dates persist.",
        ],
    },
}

# print format -> when it prints
PF = {
    "Gate Entry Slip": "After a gate IN — an 80mm thermal slip with the entry QR.",
    "Temporary Gate Slip": "For a one-day temp labourer — TMP- QR, valid the same day only.",
    "Gate Pass Slip": "For an approved gate pass — GP- QR for scan-out/return.",
    "Visitor Slip": "For a visitor — VIS- QR for sign-out.",
    "Contractor Tools Slip": "When tools are logged in — TOOL- QR to scan out.",
    "Staff ID Card": "A staff ID card — 80mm, photo + EMP- QR.",
    "Labour ID Card": "A labourer ID card — 80mm, photo + LAB- QR.",
    "Material Request Slip": "A printable copy of a material request (A4).",
    "Daily Progress Report": "The full daily site log — tasks, workers, material, photos (A4).",
    "Safety Work Permit Print": "The safety permit document with workers and photos (A4).",
    "Electrical Work Permit Print": "The electrical permit with LOTO and job log (A4).",
}

ROLES = [
    ("Gate Security", "Scan every person/vehicle in and out at the Scan Station; snap IN photos; "
     "issue temp slips and tool slips; sign visitors out.", "—",
     "Hand over the gate; make sure every open IN has been closed."),
    ("Section Incharge", "Acknowledge your section's gate entries (bell); raise Material Requests.",
     "Supervise work; keep Safety Violation Log current.",
     "File the Daily Progress Log (EOD) — task rows with status/%/description, workers, material, "
     "photos; or tick No Work Today. On a phone use the PWA 'Daily EOD' tile."),
    ("Stores / Weighbridge", "Receive trucks: create the Purchase Receipt (GRN) with weighbridge "
     "weights and the mandatory invoice photo.", "Run Quality Inspection on received material.",
     "Reconcile Material Received vs Issued."),
    ("Safety Officer", "Issue Safety / Electrical Work Permits with photos.",
     "Log every Safety Violation with a photo and corrective action.",
     "Review open violations on the dashboard."),
    ("Project Manager", "Scan the MIS dashboard and EOD compliance (which sections filed today).",
     "Edit task % on Section 360; plan dates in the Task Planner; approve material requests.",
     "Generate / read the Weekly Section Report, Stoppage Analysis and the Client Weekly MIS pack."),
    ("Ramshy Bio Management", "Open Benkas MIS for the executive dashboard.", "—",
     "Read the Client Weekly MIS pack."),
]

FAQ = [
    ("A person's photo won't upload / the camera is blank at the gate.",
     "Use 'Log IN without photo' so the queue isn't held up, then check the browser's camera "
     "permission and lighting. The live photo is your dispute proof, so fix the camera soon."),
    ("The Scan Station says 'ENTRY BLOCKED (… is Exited/Inactive)'.",
     "That ID card is deactivated. Refuse entry and send the person to their Incharge / the PM."),
    ("The Scan Station shows red 'PASS NOT APPROVED'.",
     "The gate pass is still Requested. Send the person back to their Incharge to Approve it."),
    ("A temp slip is rejected the next morning as 'EXPIRED TEMP SLIP'.",
     "Temporary Gate Slips are valid the same day only. Issue a fresh temp slip."),
    ("Tools show 'Mismatch' when scanning out.",
     "The returned quantity doesn't match what came in. Hold the person and call the Incharge."),
    ("My Daily Progress Log won't save: 'Add at least one task row'.",
     "A working-day log needs at least one task row. If nothing happened, tick 'No Work Today' and "
     "type a reason."),
    ("'describe the work in at least 15 characters'.",
     "The Work Description is too short — say what was done, or why it stopped (15+ characters)."),
    ("'<person> has no gate entry for this section today'.",
     "You added a worker who never scanned in to this section today. Only people with a gate entry "
     "can be counted — this keeps manpower honest."),
    ("A task is marked stopped but I get a 'went up' warning.",
     "It's only a warning, not a block. A stopped task normally keeps the same %; adjust if you "
     "really moved work, otherwise leave it and submit."),
    ("What are the EOD statuses and which count as a stoppage?",
     "Work Done, Work in Progress, and five 'Stopped —' reasons. Any status ticked 'Is a Stoppage' "
     "in the Progress Status master feeds the Stoppage Analysis report."),
    ("How do I file the EOD from my phone?",
     "Open the Benkas PWA, tap 'Daily EOD', pick the section, add task rows (task/status/%/"
     "description), snap photos, submit. Same rules as the desk."),
    ("The section % isn't updating.",
     "Section % comes from the Daily Progress Log task rows ON SUBMIT. Make sure the log was "
     "submitted (not left as a draft), or edit the task % directly on Section 360."),
    ("Dates I set in the Task Planner disappear after saving.",
     "Fixed — they now display correctly. If you're on an older build, pull the latest and run "
     "bench build + clear-cache."),
    ("Slips print too big / not on the thermal roll.",
     "Gate/ID slips are formatted for an 80mm thermal roll; the DPR and Material Request are A4. "
     "Pick the matching printer."),
    ("Where do I print an ID card?",
     "Open the Employee (Staff ID Card) or Labour Master (Labour ID Card) and Print — both are "
     "80mm with photo + QR."),
    ("The GRN won't save.",
     "The supplier invoice / delivery-challan photo is mandatory on the Purchase Receipt."),
    ("What is the Weight Variance flag?",
     "When the weighbridge net weight differs a lot from the invoice quantity, the GRN flags it "
     "for the Incharge to review; it also appears in the weekly exceptions."),
    ("Why can't I submit a Safety/Electrical Permit through a workflow?",
     "Approval workflows are currently OFF (see the Admin appendix). For now set the Permit Status "
     "field by hand. They'll be switched on at go-live."),
    ("Who receives a notification and when?",
     "Section Incharges get a bell alert when someone scans into their section; approval and "
     "status-change alerts follow the configured Notifications."),
    ("How do I add a new task to a section?",
     "Open Task, set its Parent Task to the section's Project Task. It then shows in Section 360, "
     "the Task Planner, the daily log dropdown and the WBS reports automatically."),
    ("How do I regenerate a section's activity tasks?",
     "See the Admin appendix — the WBS generator recreates the standard activities under each "
     "section (idempotent)."),
    ("How do I produce the client's weekly report?",
     "It builds automatically every week, or run it on demand (Admin appendix). It lands in the "
     "BENKAS PM folder and the app's docs/."),
    ("A report opens empty.",
     "Most reports default to a recent date window — widen the From/To dates. Section-scoped "
     "reports need data logged for that section in the window."),
    ("What does 'Attention' vs 'On Track' mean on Section 360?",
     "'Attention' shows when any task in the section is currently in a Stopped status; otherwise "
     "'On Track'."),
    ("Can two people file the same section's EOD on the same day?",
     "Yes, but the last submitted log wins for each task's %. Agree who files to avoid confusion."),
]


# ----------------------------------------------------------------------------
# docx helpers
# ----------------------------------------------------------------------------
def _run(p, text, bold=False, italic=False, size=None, color=None):
    r = p.add_run(text)
    r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = color
    return r


def _p(doc, text="", bold=False, italic=False, size=None, color=None, align=None, style=None):
    p = doc.add_paragraph(style=style)
    if align == "center": p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if text: _run(p, text, bold, italic, size, color)
    return p


def _bullets(doc, items):
    for it in items:
        doc.add_paragraph(str(it), style="List Bullet")


def _numbered(doc, items):
    for it in items:
        doc.add_paragraph(str(it), style="List Number")


def _table(doc, headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.LEFT
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = str(h)
        for para in c.paragraphs:
            for r in para.runs:
                r.bold = True; r.font.size = Pt(9); r.font.color.rgb = NAVY
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if v is None else str(v)
            for para in cells[i].paragraphs:
                for r in para.runs:
                    r.font.size = Pt(9)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    return t


def _callout(doc, label, text):
    p = doc.add_paragraph()
    _run(p, f"{label}: ", bold=True, color=NAVY)
    _run(p, text)


def _toc(doc):
    p = doc.add_paragraph()
    run = p.add_run()
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText"); instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    sep = OxmlElement("w:fldChar"); sep.set(qn("w:fldCharType"), "separate")
    txt = OxmlElement("w:t"); txt.text = "Right-click here and choose 'Update Field' to build the contents."
    end = OxmlElement("w:fldChar"); end.set(qn("w:fldCharType"), "end")
    run._r.append(b); run._r.append(instr); run._r.append(sep); run._r.append(txt); run._r.append(end)


def _img_if(doc, path, width=6.2):
    try:
        if path and os.path.exists(path):
            doc.add_picture(path, width=Inches(width))
            return True
    except Exception:
        pass
    return False


# ----------------------------------------------------------------------------
# introspection
# ----------------------------------------------------------------------------
def _benkas_workspaces():
    ws = frappe.get_all("Workspace", filters={"public": 1},
                        fields=["name", "sequence_id"], order_by="sequence_id asc")
    return [w.name for w in ws if (w.sequence_id or 9) < 1]


def _hint(df):
    """Generated 'what to enter' when there's no help text."""
    ft = df.fieldtype
    if df.description:
        return df.description
    if ft == "Select":
        return "Choose one of: " + ", ".join((df.options or "").split("\n")[:8])
    if ft in ("Link", "Dynamic Link"):
        return f"Pick a {df.options or 'record'}."
    if ft == "Date":
        return "Pick a date."
    if ft == "Datetime":
        return "Pick date and time."
    if ft == "Check":
        return "Tick if it applies."
    if ft in ("Attach Image", "Attach"):
        return "Attach a photo / file."
    if ft == "Table":
        return f"Line items — add rows ({df.options})."
    if ft in ("Currency", "Float", "Int", "Percent"):
        return "Enter a number."
    return "Type the value."


def _field_rows(doctype):
    meta = frappe.get_meta(doctype)
    rows, tables = [], []
    for df in meta.fields:
        if df.fieldtype in SKIP_FT or df.hidden:
            continue
        if df.reqd:
            req = "Yes"
        elif getattr(df, "mandatory_depends_on", None):
            req = "Sometimes"
        elif df.read_only:
            req = "Auto"
        else:
            req = "No"
        rows.append((df.label or df.fieldname, df.fieldtype, req, _hint(df)))
        if df.fieldtype == "Table" and df.options:
            tables.append(df.options)
    return rows, tables


# ----------------------------------------------------------------------------
# builders
# ----------------------------------------------------------------------------
def _custom_field_rows(dt):
    """Only the Benkas-added custom fields on a standard doctype."""
    rows = []
    for cf in frappe.get_all("Custom Field", filters={"dt": dt},
                             fields=["label", "fieldname", "fieldtype", "reqd", "description",
                                     "options", "read_only", "mandatory_depends_on"],
                             order_by="idx"):
        if cf.fieldtype in SKIP_FT:
            continue
        req = "Yes" if cf.reqd else ("Sometimes" if cf.mandatory_depends_on else
                                     ("Auto" if cf.read_only else "No"))
        rows.append((cf.label or cf.fieldname, cf.fieldtype, req,
                     cf.description or _hint(frappe._dict(cf))))
    return rows


def _doctype_section(doc, dt, is_standard, covered, child_seen, level=3):
    doc.add_heading(dt + ("  (standard form)" if is_standard else ""), level=level)
    info = DOC.get(dt, {})
    _p(doc, info.get("about", f"Records for {dt}."))

    if is_standard:
        cfs = _custom_field_rows(dt)
        if cfs:
            doc.add_heading("Benkas additions to this standard form", level=level + 1)
            _p(doc, "This is the standard ERPNext/HRMS form. Benkas adds the fields below — fill "
                    "these; the rest of the form works as usual.")
            _table(doc, ["Field", "Type", "Required?", "What to enter"],
                   [[r[0], r[1], r[2], r[3]] for r in cfs], widths=[1.7, 1.0, 0.9, 3.0])
        else:
            _p(doc, "Standard ERPNext/HRMS form — no Benkas-specific fields; use it as normal.")
    else:
        doc.add_heading("Fields — what to enter", level=level + 1)
        rows, tables = _field_rows(dt)
        _table(doc, ["Field", "Type", "Required?", "What to enter"],
               [[r[0], r[1], r[2], r[3]] for r in rows], widths=[1.7, 1.0, 0.9, 3.0])
        for tbl in tables:
            child_seen.add(tbl)
            doc.add_heading(f"Line items: {tbl}", level=level + 1)
            crows, _ = _field_rows(tbl)
            _table(doc, ["Column", "Type", "Required?", "What to enter"],
                   [[r[0], r[1], r[2], r[3]] for r in crows], widths=[1.7, 1.0, 0.9, 3.0])

    if info.get("on_submit"):
        doc.add_heading("What happens on save / submit", level=level + 1)
        for line in info["on_submit"].split("\n"):
            _p(doc, line)
    if info.get("errors"):
        doc.add_heading("Common messages & what to do", level=level + 1)
        _table(doc, ["Message", "What it means / what to do"],
               [[m, w] for m, w in info["errors"]], widths=[2.6, 3.9])
    if info.get("tip"):
        _callout(doc, "Tip", info["tip"])
    covered["doctypes"].append(dt)


def _report_section(doc, rep, level=3):
    doc.add_heading(f"Report — {rep}", level=level)
    meta = frappe.db.get_value("Report", rep, ["report_type", "ref_doctype"], as_dict=1) or {}
    info = REP.get(rep, {})
    _p(doc, info.get("q", f"A report over {meta.get('ref_doctype') or 'the data'}."))
    _callout(doc, "How to read it", info.get("read", "Open it, set any filters at the top, and "
             "read the columns. Use Menu → Export for Excel/PDF."))
    _p(doc, f"Type: {meta.get('report_type', 'Query Report')} · Based on: {meta.get('ref_doctype', '—')}",
       italic=True, size=9, color=GREY)


# ----------------------------------------------------------------------------
def build(path=None, only_path=False):
    covered = {"doctypes": [], "reports": [], "pages": [], "print_formats": [], "child_tables": set()}
    documented = set()
    child_seen = set()

    ws_names = _benkas_workspaces()
    all_reports = {r.name: r for r in frappe.get_all(
        "Report", filters={"module": ["in", MODULES]}, fields=["name", "module", "report_type", "ref_doctype"])}
    all_pf = {p.name: p for p in frappe.get_all(
        "Print Format", filters={"module": ["in", MODULES]}, fields=["name", "doc_type"])}

    doc = Document()
    for s in doc.sections:
        s.page_height, s.page_width = Inches(11.69), Inches(8.27)
        s.left_margin = s.right_margin = Inches(0.85)

    # ---------- Cover ----------
    doc.add_paragraph("\n\n\n")
    _p(doc, "BENKAS ENGINEERING", bold=True, size=15, color=NAVY, align="center")
    _p(doc, "Benkas ERP", bold=True, size=34, color=NAVY, align="center")
    _p(doc, "Complete Step-by-Step User Guide", size=18, align="center")
    _p(doc, "Ramshy Bio Pvt. Ltd. — Ethanol Plant Construction Monitoring", size=12,
       align="center", italic=True)
    doc.add_paragraph("\n")
    _p(doc, f"Generated from the live site on {formatdate(today(), 'dd MMMM yyyy')}",
       size=11, align="center")
    _p(doc, "This guide is generated by introspecting the running app, so its inventory and "
            "every field list are complete and always match the system.", size=10, align="center",
       italic=True, color=GREY)
    doc.add_page_break()

    # ---------- Contents ----------
    doc.add_heading("Contents", level=1)
    _toc(doc)
    doc.add_page_break()

    # ================= Chapter 1 =================
    doc.add_heading("1.  What Benkas ERP is", level=1)
    _p(doc, "Benkas ERP monitors the construction of the Ramshy Bio ethanol plant. It keeps five "
            "things honest and in one place:")
    _bullets(doc, [
        "PEOPLE — who came through the gate (staff, contractors, labour), attendance and manpower.",
        "MATERIAL — what was requested, received (with weighbridge + invoice proof), quality-checked "
        "and consumed at site.",
        "PROGRESS — each section's tasks, their % complete and the daily site log behind them.",
        "SAFETY & ASSETS — permits, violations, generators and power.",
        "GATE — the single scan point that feeds attendance and proves who was really on site.",
    ])
    doc.add_heading("The daily rhythm", level=2)
    _p(doc, "One simple loop runs every day:")
    _table(doc, ["Step", "What happens", "Where"],
           [["1. Gate scan", "People scan IN (photo) and OUT at the Scan Station.", "Gate Management"],
            ["2. Work", "The section does its work; material is issued as needed.", "site"],
            ["3. EOD log", "The Incharge files the Daily Progress Log (task %, workers, material, "
             "photos) — from desk or phone.", "Work Schedule"],
            ["4. Roll-up", "Task % and section % update automatically; stock is issued.", "automatic"],
            ["5. Read", "PM & client read the dashboards and weekly reports.", "Benkas MIS"]],
           widths=[1.2, 4.2, 1.3])
    doc.add_heading("How it all connects", level=2)
    _p(doc, "(Shown as a text flow — this guide uses precise textual walkthroughs rather than "
            "screenshots so it can be regenerated from the live app without drift.)", italic=True,
       size=9, color=GREY)
    for line in [
        "GATE SCAN --> Gate Entry (who is on site) --> feeds --> Attendance & Manpower reports",
        "     |",
        "     '--> Daily Progress Log (EOD) --> writes --> Task %  --> rolls up --> Section %",
        "                     |                                              |",
        "                     |--> issues --> Stock Entry (material consumed) |",
        "                     '--> photos + status ----------------> Section 360 / Benkas MIS",
        "",
        "MATERIAL:  Material Request --> Purchase Receipt (GRN) --> Quality Inspection --> stock",
        "                                                   '--> consumed in the Daily Progress Log",
    ]:
        mp = doc.add_paragraph()
        r = mp.add_run(line)
        r.font.name = "Consolas"
        r.font.size = Pt(8.5)

    # ================= Chapter 2 : inventory =================
    doc.add_page_break()
    doc.add_heading("2.  The map — everything that exists", level=1)
    _p(doc, "This inventory is generated from the live site, so it is complete.")

    doc.add_heading("2.1  Workspaces (sidebar order)", level=2)
    WS_PURPOSE = {
        "Gate Management": "The gate's home — scanning, gate entries, passes, visitors, tools, "
        "vehicles and the gate registers.",
        "Manpower Manager": "Workforce masters, gate-driven attendance and manpower reports.",
        "Material and Purchase": "Requests, GRN receipts, quality, stock and material reports.",
        "Work Schedule and Progress": "Planning, the Daily Progress Log, Section 360 and progress "
        "reports.",
        "Site Safety and Assets": "Permits, violations, generators and power.",
        "Benkas Core": "The master data — sections, contractors, labour, activities, statuses.",
        "Benkas MIS": "The executive dashboard and the client weekly report.",
    }
    _table(doc, ["#", "Workspace", "Purpose"],
           [[i + 1, w, WS_PURPOSE.get(w, "")] for i, w in enumerate(ws_names)], widths=[0.4, 2.0, 4.1])

    doc.add_heading("2.2  Doctypes (what each records)", level=2)
    DT_ONE = {
        "Plant Section": "One plant area, its warehouse, WBS task and % complete.",
        "Contractor": "A labour/works agency.",
        "Labour Master": "A contract labourer (ID card prints here).",
        "Delay Reason": "Legacy delay-reason list.",
        "Construction Activity": "A standard build activity used to generate section tasks.",
        "Progress Status": "The EOD status list (Work Done / stopped reasons) + colours.",
        "Gate Entry": "One person's IN or OUT at a section.",
        "Gate Pass": "Permission to leave site during the day.",
        "Visitor Log": "A site visitor's sign-in/out.",
        "Contractor Tools Register": "Tools brought in and returned.",
        "Site Vehicle": "A site vehicle master.",
        "Site Vehicle Log": "A vehicle trip.",
        "Daily Progress Log": "THE end-of-day site log per section.",
        "Safety Work Permit": "A high-risk work permit.",
        "Electrical Work Permit": "An electrical work permit (LOTO).",
        "Safety Violation Log": "A logged safety breach.",
        "Generator Master": "A generator master.",
        "Generator Log": "A generator run.",
        "Power Consumption Log": "A phase/voltage reading.",
        "Employee": "Standard staff master (attendance).",
        "Task": "One section activity (has a %).",
        "Project": "The whole plant build.",
        "Item": "Material master.",
        "Supplier": "Vendor master.",
        "Material Request": "A request to issue material.",
        "Purchase Receipt": "Goods receipt (GRN) with weighbridge + invoice.",
        "Quality Inspection": "Accept/reject received material.",
        "Stock Entry": "Stock movement (auto-created by the daily log).",
    }
    for m in MODULES:
        dts = frappe.get_all("DocType", filters={"module": m, "custom": 0, "istable": 0},
                             fields=["name"], order_by="name")
        if not dts:
            continue
        doc.add_heading(m, level=3)
        _table(doc, ["Doctype", "What it records"],
               [[d.name, DT_ONE.get(d.name, "—")] for d in dts], widths=[2.2, 3.9])
    # child tables (inventory only)
    child = frappe.get_all("DocType", filters={"module": ["in", MODULES], "custom": 0, "istable": 1},
                           fields=["name"], order_by="name")
    doc.add_heading("Child tables (line-item grids inside the above)", level=3)
    _p(doc, ", ".join(c.name for c in child) + ".")
    for c in child:
        covered["child_tables"].add(c.name)

    doc.add_heading("2.3  Pages", level=2)
    _table(doc, ["Page", "What it does"],
           [["Scan Station", "The gate scan screen."],
            ["Section 360°", "Everything about one section on one screen."],
            ["Section Task Planner", "Set tentative task dates per section."]], widths=[2.2, 3.9])

    doc.add_heading("2.4  Reports (the question each answers)", level=2)
    _table(doc, ["Report", "Answers"],
           [[r, REP.get(r, {}).get("q", "—")] for r in sorted(all_reports)], widths=[2.4, 3.7])

    doc.add_heading("2.5  Print formats (when each prints)", level=2)
    _table(doc, ["Print format", "Doctype", "When it prints"],
           [[p, all_pf[p].doc_type, PF.get(p, "—")] for p in sorted(all_pf)], widths=[2.0, 1.8, 2.3])

    doc.add_heading("2.6  Where do I find X?", level=2)
    FIND = [
        ["Scan a person in/out", "Gate Management", "Scan Station"],
        ["File the end-of-day log", "Work Schedule and Progress", "Daily Progress Log / PWA Daily EOD"],
        ["Request material", "Material and Purchase", "Material Request"],
        ["Receive a truck (GRN)", "Material and Purchase", "Purchase Receipt"],
        ["See a section's full picture", "Work Schedule / Benkas MIS", "Section 360°"],
        ["Plan task dates", "Work Schedule and Progress", "Section Task Planner"],
        ["Log a safety violation", "Site Safety and Assets", "Safety Violation Log"],
        ["Print an ID card", "Manpower / Benkas Core", "Employee / Labour Master → Print"],
        ["The client weekly pack", "Benkas MIS", "Client Weekly MIS"],
        ["Every gate event", "Gate Management", "Gate Register report"],
        ["Why work stopped this week", "Work Schedule / Benkas MIS", "Stoppage Analysis"],
    ]
    _table(doc, ["I want to…", "Workspace", "Open"], FIND, widths=[2.4, 2.0, 1.7])

    # ================= Chapters 3+ : one per workspace =================
    planner_img = "/mnt/c/Users/jajul/pw-e2e/planner-fixed.png"
    for wi, wname in enumerate(ws_names):
        doc.add_page_break()
        doc.add_heading(f"{wi + 3}.  {wname}", level=1)
        wdoc = frappe.get_doc("Workspace", wname)

        # --- what's on this workspace ---
        doc.add_heading("What's on this workspace", level=2)
        _p(doc, WS_PURPOSE.get(wname, ""))
        cards = [c.label for c in getattr(wdoc, "number_cards", []) if c.label]
        charts = [(c.label or c.chart_name) for c in getattr(wdoc, "charts", [])
                  if (c.label or c.chart_name)]
        shortcuts = [(s.type, s.label or "", s.link_to or s.url or "") for s in wdoc.shortcuts]
        if cards:
            _callout(doc, "Number cards (live counts)", ", ".join(cards) + ".")
        if charts:
            _callout(doc, "Charts", ", ".join(charts) + ".")
        _p(doc, "Shortcut tiles on this workspace:")
        _table(doc, ["Tile", "Type", "Opens"],
               [[s[1], s[0], s[2]] for s in shortcuts], widths=[2.4, 1.2, 2.5])

        # ordered list of items from shortcuts then links (dedup)
        order = []
        for s in wdoc.shortcuts:
            order.append((s.type, s.link_to or s.url))
        for l in wdoc.links:
            if l.type in ("DocType", "Report", "Page"):
                order.append((l.type, l.link_to))
        seen_here = set()

        # --- pages first ---
        doc.add_heading("Pages, doctypes and reports on this workspace — one by one", level=2)
        for typ, key in order:
            if (typ, key) in seen_here:
                continue
            seen_here.add((typ, key))
            if typ == "Page":
                if key in documented:
                    continue
                documented.add(key)
                pinfo = PAGE.get(key)
                if pinfo:
                    doc.add_heading("Page — " + pinfo["title"], level=3)
                    _p(doc, pinfo["about"])
                    doc.add_heading("Step by step", level=4)
                    _numbered(doc, pinfo["steps"])
                    if key == "section-task-planner":
                        if _img_if(doc, planner_img):
                            _p(doc, "Section Task Planner (live screenshot).", italic=True, size=9,
                               color=GREY)
                    covered["pages"].append(key)
            elif typ == "DocType":
                if key in documented:
                    _p(doc, f"• {key} — see its full chapter where it first appears.", size=9,
                       color=GREY)
                    continue
                documented.add(key)
                is_std = not frappe.db.get_value("DocType", key, "custom") and \
                    frappe.db.get_value("DocType", key, "module") not in MODULES
                _doctype_section(doc, key, is_std, covered, child_seen)
            elif typ == "Report":
                if key in documented:
                    continue
                documented.add(key)
                _report_section(doc, key)
                covered["reports"].append(key)

    # ================= EOD compliance note on Work Schedule already covered; add MIS pack =================
    # Client MIS pack is part of Benkas MIS chapter — add explicit how-to
    doc.add_page_break()
    doc.add_heading("Client Weekly MIS pack — how to produce it", level=2)
    _p(doc, "The client-facing weekly report (cover scorecard, section-wise table, per-section "
            "detail, manpower & material annexes, stoppage & exceptions) builds automatically every "
            "week and lands in the BENKAS PM folder and the app's docs/. To build one on demand:")
    _p(doc, "bench --site <site> execute benkas_erp.setup.client_mis.build", size=10)
    _p(doc, "Or for a specific week ending:")
    _p(doc, "bench --site <site> execute benkas_erp.setup.client_mis.build --kwargs "
            "\"{'week_ending':'2026-07-06'}\"", size=10)

    # ================= Role cheat-sheets =================
    doc.add_page_break()
    n = len(ws_names) + 3
    doc.add_heading(f"{n}.  Daily / weekly routine — one page per role", level=1)
    for role, morning, during, evening in ROLES:
        doc.add_heading(role, level=2)
        _table(doc, ["When", "Do this"],
               [["Morning", morning], ["During the day", during], ["Evening / weekly", evening]],
               widths=[1.4, 5.0])

    # ================= FAQ =================
    doc.add_page_break()
    doc.add_heading(f"{n + 1}.  Troubleshooting & FAQ", level=1)
    for i, (q, a) in enumerate(FAQ, 1):
        _p(doc, f"Q{i}. {q}", bold=True, color=NAVY)
        _p(doc, a)

    # ================= Admin appendix =================
    doc.add_page_break()
    doc.add_heading(f"{n + 2}.  Admin appendix (for future-you)", level=1)
    doc.add_heading("Regenerate this guide & the other docs", level=2)
    _bullets(doc, [
        "This guide: bench --site <site> execute benkas_erp.setup.userguide.build",
        "System documentation: benkas_erp.setup.docgen.build",
        "Role quick-refs: benkas_erp.setup.usermanual.build_all",
        "Client weekly pack: benkas_erp.setup.client_mis.build",
    ])
    doc.add_heading("Reseed / regenerate data", level=2)
    _bullets(doc, [
        "Masters + 12 sections + WBS tasks: benkas_erp.setup.seed.run (idempotent).",
        "Progress Status list only: benkas_erp.setup.seed.seed_progress_statuses.",
        "Regenerate section activity tasks: benkas_erp.setup.activities.generate_section_tasks.",
        "Demo/UAT data: benkas_erp.setup.demo_data.reset then .run.",
        "Full health check: benkas_erp.setup.audit.run (expect 0 FAIL).",
    ])
    doc.add_heading("Deferred go-live items (not yet on)", level=2)
    _bullets(doc, [
        "Approval WORKFLOWS are OFF (WORKFLOWS_ACTIVE=False). Permit/request statuses are set by "
        "hand for now; flip the flag + migrate to enforce approvals at go-live.",
        "USER PERMISSIONS: restrict each Section Incharge to their own Plant Section — to be "
        "applied on the real site.",
        "required_apps (erpnext, hrms) is set; complete the ERPNext setup wizard before seeding on "
        "a fresh site.",
    ])

    _p(doc, "")
    _p(doc, "— End of guide —  Generated by Benkas ERP on " + formatdate(today(), "dd MMM yyyy"),
       size=9, align="center", italic=True, color=GREY)

    # ---------- save ----------
    covered["child_tables"] = sorted(covered["child_tables"])
    fname = "Benkas_ERP_Complete_User_Guide.docx"
    out = path or os.path.join(WIN_DIR, fname)
    saved = []
    try:
        doc.save(out); saved.append(out)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Benkas: user guide win save failed")
    if not only_path:
        try:
            app_docs = frappe.get_app_path("benkas_erp", "..", "docs")
            os.makedirs(app_docs, exist_ok=True)
            repo = os.path.join(app_docs, fname)
            doc.save(repo); saved.append(repo)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Benkas: user guide repo save failed")

    print("User guide written:", saved)
    print("Covered: %d doctypes, %d reports, %d pages, %d child tables"
          % (len(covered["doctypes"]), len(covered["reports"]), len(covered["pages"]),
             len(covered["child_tables"])))
    return {"saved": saved, "covered": covered}


def _docx_text(path):
    d = Document(path)
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


def verify(path=None):
    """Cross-check the generated guide against the live site: every parent doctype,
    child table, report, page and print format must appear in the document. The
    ONLY allowed omission is a child table having no top-level chapter (it appears
    inside its parent instead) — but its NAME must still be present."""
    import tempfile
    out = path or os.path.join(tempfile.gettempdir(), "benkas_userguide_verify.docx")
    build(path=out, only_path=True)
    text = _docx_text(out)

    live = {
        "parent doctypes": [d.name for d in frappe.get_all(
            "DocType", filters={"module": ["in", MODULES], "custom": 0, "istable": 0})],
        "child tables": [d.name for d in frappe.get_all(
            "DocType", filters={"module": ["in", MODULES], "custom": 0, "istable": 1})],
        "reports": [r.name for r in frappe.get_all("Report", filters={"module": ["in", MODULES]})],
        "print formats": [p.name for p in frappe.get_all(
            "Print Format", filters={"module": ["in", MODULES]})],
        "pages": ["Scan Station", "Section 360", "Section Task Planner"],
    }
    missing = {}
    for cat, names in live.items():
        miss = [n for n in names if n not in text]
        if miss:
            missing[cat] = miss
    ok = not missing
    print("=== USER GUIDE COMPLETENESS ===")
    for cat, names in live.items():
        miss = missing.get(cat, [])
        print(f"  {'PASS' if not miss else 'FAIL'}  {cat}: {len(names)} live, "
              f"{len(names) - len(miss)} in guide" + (f"  MISSING {miss}" if miss else ""))
    print(f"  RESULT: {'ALL PRESENT' if ok else 'GAPS FOUND'}")
    return {"ok": ok, "missing": missing, "counts": {k: len(v) for k, v in live.items()}}
