"""
Human-facing User & Operations Manual for Benkas ERP (generated from code so it
never drifts from the app). Produces:
  - Benkas_ERP_User_Manual.docx        (full manual, role by role)
  - Benkas_QuickRef_Gate_Security.docx  (one-page laminate card)
  - Benkas_QuickRef_Section_Incharge.docx

    bench --site <site> execute benkas_erp.setup.usermanual.build_all
"""

import os
from datetime import datetime
import frappe

WIN_DIR = "/mnt/c/Users/jajul/Downloads/BENKAS PM"
VERSION = "1.0"

SCAN_URL = "/app/benkas-scan"


# --------------------------------------------------------------------------
# docx helpers
# --------------------------------------------------------------------------
def _doc():
    from docx import Document
    from docx.shared import Pt
    d = Document()
    style = d.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    return d


def _title_page(doc, title, subtitle):
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(title)
    r.bold = True
    r.font.size = Pt(30)
    r.font.color.rgb = RGBColor(0x16, 0x32, 0x4F)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.add_run(subtitle).font.size = Pt(13)
    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.add_run(f"Ramshy Bio Pvt. Ltd. — Ethanol Plant  |  Version {VERSION}  |  "
               f"{datetime.now():%d %b %Y}").font.size = Pt(10)


def _steps(doc, items):
    for i, it in enumerate(items, 1):
        p = doc.add_paragraph(style="List Number")
        p.add_run(it)


def _bullets(doc, items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


def _p(doc, text, bold=False, italic=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = bold
    r.italic = italic
    return p


def _callout(doc, label, text):
    from docx.shared import Pt
    p = doc.add_paragraph()
    r = p.add_run(f"{label}: ")
    r.bold = True
    p.add_run(text)
    for run in p.runs:
        run.font.size = Pt(10)


def _table(doc, headers, rows):
    from docx.shared import Pt
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = str(h)
        for para in c.paragraphs:
            for run in para.runs:
                run.bold = True
                run.font.size = Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = "" if v is None else str(v)
            for para in cells[i].paragraphs:
                for run in para.runs:
                    run.font.size = Pt(9)
    return t


# --------------------------------------------------------------------------
# FULL MANUAL
# --------------------------------------------------------------------------
def build(path=None):
    from docx import Document  # noqa
    doc = _doc()
    _title_page(doc, "Benkas ERP", "User & Operations Manual")
    doc.add_page_break()

    _intro(doc)
    doc.add_page_break()
    _ch_gate_security(doc)
    doc.add_page_break()
    _ch_section_incharge(doc)
    doc.add_page_break()
    _ch_stores(doc)
    doc.add_page_break()
    _ch_safety_officer(doc)
    doc.add_page_break()
    _ch_pm(doc)
    doc.add_page_break()
    _ch_management(doc)
    doc.add_page_break()
    _ch_qr_system(doc)
    doc.add_page_break()
    _ch_daily_chain(doc)
    doc.add_page_break()
    _ch_troubleshooting(doc)

    out = path or os.path.join(WIN_DIR, "Benkas_ERP_User_Manual.docx")
    doc.save(out)
    _repo_copy(doc, "Benkas_ERP_User_Manual.docx")
    print("User manual written to:", out)
    return out


def _intro(doc):
    doc.add_heading("Getting started", level=1)
    _p(doc, "Benkas ERP is the system Benkas Engineering uses to run and monitor the "
            "Ramshy Bio ethanol-plant construction — who is on site, what material moved, "
            "how each section is progressing, and site safety. This manual walks each role "
            "through their real day, step by step.")
    doc.add_heading("Logging in", level=2)
    _steps(doc, [
        "Open the site in a browser (your supervisor will give you the address, e.g. the "
        "plant server or the Frappe Cloud link).",
        "Enter your username (usually your email) and password. If you don't have a login, "
        "ask the Benkas Project Manager to create one and assign your role.",
        "After login you land on the app screen. Tap the Benkas ERP tile for the dashboard, "
        "or Benkas Core for master setup. Your role decides which screens you can see.",
    ])
    _callout(doc, "Roles", "Gate Security, Section Incharge, Stores/Weighbridge Operator, "
             "Safety Officer, Generator/Electrical Operator, Benkas Project Manager, and "
             "Ramshy Bio Management. You only see what your role needs.")


def _ch_gate_security(doc):
    doc.add_heading("1.  Gate Security — your day", level=1)
    _p(doc, "Your workspace is Gate Management — it's your ONE sidebar entry with everything "
            "gate-related: the Scan Station, Gate Entries, Visitors, Gate Passes, Contractor "
            "Tools, Site Vehicle logs, and the Gate Register. You don't need any other "
            "workspace. Almost everything you do is a scan — keep the Scan Station open all day.")
    doc.add_heading("The Gate Register (your logbook)", level=2)
    _p(doc, "Open 'Gate Register' from Gate Management to see every in/out event in one "
            "chronological list — people, visitors, vehicles, material trucks, tools and gate "
            "passes together, exactly like the physical gate register book. Filter by date, "
            "type, section, direction or contractor. This is the report to open to answer "
            "'who or what was on site at 3 pm last Tuesday' — each row links to its record.")

    doc.add_heading("Morning setup", level=2)
    _steps(doc, [
        "Log in and open the Scan Station: go to " + SCAN_URL + " (bookmark it). You'll see "
        "one big input box and a large status panel.",
        "Plug in the USB barcode scanner. It behaves like a keyboard — it types the code and "
        "presses Enter for you. Do NOT click anywhere; the input box stays focused on its own.",
        "Optional: if you're on a tablet with no USB scanner, use the '📷 Camera scan' "
        "button instead (works in Chrome/Edge).",
    ])

    doc.add_heading("Scanning a person IN", level=2)
    _steps(doc, [
        "Person shows their ID card. Scan the QR.",
        "The screen instantly shows their PHOTO, name and contractor. Look at the photo and "
        "confirm it's the same person standing in front of you.",
        "The section they usually work in is pre-filled. Change it only if they're working "
        "somewhere else today.",
        "The camera preview opens. Tap '📸 Snap & Log IN' to capture their live photo and "
        "record the entry. That's it — zero typing.",
        "If the camera isn't available, tap 'Log IN without photo' (use only if you must).",
    ])
    _callout(doc, "Why the photo", "The live gate photo proves who actually entered today, "
             "next to their card photo. It is what protects you if there's ever a dispute "
             "about who was on site.")

    doc.add_heading("Scanning the same person OUT", level=2)
    _steps(doc, [
        "When they leave, scan the same card again.",
        "The system finds their open entry for today and closes it — big green 'OUT "
        "RECORDED'. No photo, no typing.",
    ])

    doc.add_heading("The result card & printing a slip", level=2)
    _bullets(doc, [
        "After every scan a big banner shows: the person's photo & name, what happened "
        "('IN RECORDED', 'OUT RECORDED', etc.), and a link to open the record. It stays on "
        "screen until the next scan — you won't miss it.",
        "For an IN, a '🖨 Print Slip' button appears — one tap prints that person's gate slip "
        "on the thermal printer (80 mm roll). All gate slips are the same size.",
        "A 'Recent activity' list at the bottom shows your last ~10 scans (time, name, "
        "IN/OUT) so you can confirm it recorded and spot a double-scan.",
    ])

    doc.add_heading("Someone has no card (temporary pass)", level=2)
    _steps(doc, [
        "Tap the 'Temp Pass' button (top-right of the Scan Station).",
        "For a brand-new / one-day worker: type their name (and contractor if labour) + "
        "section. The system quick-registers them and issues a Temporary Gate Slip.",
        "For someone whose card is lost: pick them in the 'existing person' box instead — the "
        "temp slip links to their real record so their history stays continuous.",
        "Print the Temporary Gate Slip and hand it over. Its QR works for the rest of the day "
        "exactly like a card — scan it at exit to sign them out.",
        "It expires at end of day: scanning it the next day shows 'EXPIRED TEMP SLIP — issue "
        "a new one'.",
    ])

    doc.add_heading("A blocked or unknown card", level=2)
    _bullets(doc, [
        "Red 'ENTRY BLOCKED' (labour is Inactive/Exited): their contract ended or they were "
        "deactivated. Do not allow entry — send them to their Incharge or the PM.",
        "'Not found' / 'EXPIRED TEMP SLIP': damaged card or yesterday's temp slip. Issue a "
        "fresh Temporary Pass or send to the PM for a re-issue.",
    ])

    doc.add_heading("Material vehicle arrival", level=2)
    _p(doc, "When a supplier truck arrives with material, that's the Stores/Weighbridge "
            "Operator's GRN process (Chapter 3). Your job: note the vehicle, direct it to the "
            "weighbridge, and let the stores operator take over.")

    doc.add_heading("Visitor arrival + slip", level=2)
    _steps(doc, [
        "Create a new Visitor Log: fill visitor name, company, purpose, who they're visiting "
        "(host), and the section. Take their photo.",
        "Save. Print the Visitor Slip (Print → Visitor Slip) and hand it to the visitor — it "
        "carries a QR.",
        "When the visitor leaves, scan the slip at the Scan Station → the log closes "
        "automatically ('VISITOR OUT').",
    ])

    doc.add_heading("Contractor tools in / out", level=2)
    _steps(doc, [
        "When a contractor brings tools, tap 'Tools In' (top-right) — it opens a new "
        "Contractor Tools Register. Enter contractor, tool description, quantity, photo "
        "optional. Save, then print the Contractor Tools Slip (thermal) and hand it over.",
        "At exit, scan the tools slip QR. The register opens showing the item list — tick / "
        "enter what's actually going out (Qty Returned), then save.",
        "If returned quantity differs from what came in, the status auto-flags 'Mismatch' — "
        "hold the person and call the Incharge.",
    ])

    doc.add_heading("Gate Pass verification at exit", level=2)
    _steps(doc, [
        "Anyone leaving during working hours must show a Gate Pass. Scan its QR.",
        "GREEN 'GATE PASS — OUT': approved, let them go; the time is recorded.",
        "RED 'PASS NOT APPROVED': do NOT let them out. Send them back to their Incharge to "
        "get the pass approved.",
        "On return, scan again → 'RETURNED'. This closes the loop so no one is marked as "
        "still-out overnight.",
    ])

    doc.add_heading("End of day", level=2)
    _bullets(doc, [
        "Scan out anyone still inside as they leave.",
        "Any gate pass left 'Out' past its return time turns 'Overdue' automatically and "
        "shows on the manpower report — flag those to the PM.",
    ])

    doc.add_heading("Error messages — what they mean", level=2)
    _table(doc, ["Message on screen", "What to do"], [
        ["ENTRY BLOCKED (…is Exited/Inactive)", "Card deactivated — refuse entry, send to Incharge/PM."],
        ["PASS NOT APPROVED", "Send the person back to their Incharge to approve the gate pass."],
        ["Visitor already signed out", "The slip was already scanned out — no action needed."],
        ["Gate pass already returned", "Loop already closed — no action needed."],
        ["… not found", "Damaged/foreign card — send to PM for re-issue."],
        ["Unrecognised code", "That QR isn't a Benkas card/slip — ignore."],
    ])


def _ch_section_incharge(doc):
    doc.add_heading("2.  Section Incharge — your day", level=1)
    _p(doc, "You own one plant section. You confirm who really worked, log the day's "
            "progress, request material, and keep your section safe.")

    doc.add_heading("Morning: acknowledge gate entries", level=2)
    _steps(doc, [
        "Open your notifications (bell icon) — each person logged into your section this "
        "morning raises a pending acknowledgement.",
        "Open the Gate Entry list filtered to your section, status 'Pending'.",
        "For each: if the person actually reported to you and the work matches, click "
        "'Confirm'. If they never showed up or were redirected, click 'Dispute' and add a "
        "remark.",
    ])
    _callout(doc, "Why", "Confirmed vs Disputed is what makes contractor-labour billing "
             "honest — you're signing that the person was really there.")

    doc.add_heading("Raising a Material Request", level=2)
    _steps(doc, [
        "New Material Request. Set type = 'Material Issue' (material going out to your work).",
        "Fill Plant Section (yours) and the Task it's for, then add item lines with quantity.",
        "Submit. It goes to 'Requested'. Once approved it becomes 'Approved' and can be "
        "issued against by the daily log.",
    ])

    doc.add_heading("The Daily Progress Log (your main job)", level=2)
    _p(doc, "One log per section per day captures everything: task progress, who worked, and "
            "material used. When you submit it, the system updates task %, section %, and "
            "issues the material automatically.")
    _steps(doc, [
        "New Daily Progress Log. Section and date are pre-set; you are the Incharge.",
        "Task Progress table: add a row per sub-task worked on. Pick the task (only tasks "
        "under your section show), set % complete, write one line of activity, and a Delay "
        "Reason only if it fell behind.",
        "Workers Present table: add each person who worked, their task and hours (default 8). "
        "Note: a worker who has no gate entry for your section today CANNOT be added — the "
        "log will refuse to save with a clear message. That's deliberate: only people who "
        "actually came through the gate count.",
        "Material Consumed table: add item, quantity, unit, task, and (if it was requested) "
        "link the Material Request. Leave the request blank if there wasn't one — it's just "
        "flagged 'No MR' for visibility, it won't block you.",
        "Site Photos: attach at least one photo of the day's work (required).",
        "Submit.",
    ])
    _p(doc, "What happens automatically on submit:", bold=True)
    _bullets(doc, [
        "Each task's % is updated from your Task Progress rows.",
        "One Stock Entry (Material Issue) is created and submitted for all your material rows "
        "— stock drops automatically. You never touch Stock Entry.",
        "If a Material Request was linked, its status moves to Partially Issued or Issued.",
        "Manpower-days and material value are added onto the tasks; your section % is "
        "recalculated and flows to the dashboard.",
    ])

    doc.add_heading("Logging a safety violation", level=2)
    _steps(doc, [
        "New Safety Violation Log. Pick the violation type, the person, your section.",
        "Attach a photo (required) and note the corrective action taken.",
        "Leave status 'Open' until fixed, then set 'Corrected'.",
    ])

    doc.add_heading("Approving gate passes", level=2)
    _p(doc, "When someone in your section needs to step out, they (or you) raise a Gate Pass. "
            "Open it and click 'Approve'. Only then will the gate let them out. Your login + "
            "the timestamp is the authorised signature.")


def _ch_stores(doc):
    doc.add_heading("3.  Stores / Weighbridge Operator — your day", level=1)
    doc.add_heading("Receiving material (gate to stores)", level=2)
    _steps(doc, [
        "Truck arrives → weighbridge. Note gross and tare weight.",
        "New Purchase Receipt (GRN): supplier, item, quantity, the section warehouse it's "
        "going to, and the weighbridge fields (gross/tare — net is worked out).",
        "Upload the supplier invoice / delivery-challan photo. This is MANDATORY — the GRN "
        "will not save without it. That photo is your proof the material and paperwork "
        "matched at the gate.",
        "If net weight differs from the ordered quantity by more than a little, the system "
        "sets a 'Weight Variance' flag for the Incharge to review.",
        "Save. For items that need inspection, a Quality Inspection is required before the "
        "material is accepted (Chapter 4 / the Safety-and-quality flow).",
    ])
    doc.add_heading("Issuing against a Material Request", level=2)
    _p(doc, "You normally don't issue material by hand — the Section Incharge's Daily "
            "Progress Log issues it automatically against their Material Request. Your job is "
            "to keep stock accurate: make sure every GRN is entered so the section warehouse "
            "balance is right. Check the 'Material Section Stock Balance' report anytime.")
    doc.add_heading("Quality inspection handoff", level=2)
    _bullets(doc, [
        "Items flagged 'inspection required' force a Quality Inspection before the GRN can "
        "be completed.",
        "The Benkas Incharge records Accept / Reject / Partial and can attach photos of the "
        "material condition.",
        "Rejected material shows on the 'QC Rejection Report'.",
    ])


def _ch_safety_officer(doc):
    doc.add_heading("4.  Safety Officer — your day", level=1)
    doc.add_heading("Work permits lifecycle", level=2)
    _p(doc, "High-risk jobs (hot work, height, confined space, excavation, electrical) need "
            "a permit before work starts.")
    _steps(doc, [
        "New Safety Work Permit (or Electrical Work Permit). Set the permit type, section, "
        "work description, workers involved, and the validity window.",
        "Attach the mandatory photos: site/area photo and PPE-in-use photo (and barricading "
        "where relevant). The permit won't progress without them.",
        "Approve → the state moves Requested → Approved.",
        "When work starts, move it to 'Work in Progress'.",
        "To Close: you must tick 'Closing Confirmation' — that means you have physically "
        "checked the job is finished and the area is safe. Only then can it be closed. For "
        "electrical permits, LOTO must be confirmed before approval and the re-energized "
        "sign-off before closing.",
    ])
    doc.add_heading("Violation log & PPE review", level=2)
    _bullets(doc, [
        "Maintain the Safety Violation Log (photo mandatory). Repeat offenders by contractor "
        "show on the 'Safety Violations by Contractor' report — use it in contractor reviews.",
        "Gate entries carry a PPE checklist the guard ticks; spot-check compliance.",
    ])


def _ch_pm(doc):
    doc.add_heading("5.  Benkas Project Manager — your day", level=1)
    doc.add_heading("Master data", level=2)
    _bullets(doc, [
        "Plant Sections, Contractors, Labour, Delay Reasons, Construction Activities live in "
        "the Benkas Core workspace.",
        "Issue/re-issue ID cards from Employee and Labour Master (Print → ID Card). "
        "Deactivating a Labour (status Inactive/Exited) instantly blocks their card at the "
        "gate.",
    ])
    doc.add_heading("Adding a new Plant Section and its tasks", level=2)
    _steps(doc, [
        "Create the Plant Section (a Warehouse, Task and Cost Center get wired to it during "
        "seeding; for a brand-new one set these links).",
        "To break the section into standard construction activities (civil, erection, "
        "wiring, installation, testing, commissioning…), run the WBS generator: it creates a "
        "sub-task per active Construction Activity under the section's task.",
        "Edit the Construction Activity master to add/remove activities, then regenerate to "
        "pick up new ones.",
    ])
    _callout(doc, "Command", "Regenerate WBS sub-tasks with "
             "benkas_erp.setup.activities.generate_section_tasks (or the full "
             "setup_activities).")

    doc.add_heading("Planning tentative dates & weights (Section Task Planner)", level=2)
    _p(doc, "Every section sub-task carries a tentative start date, end date and a weight "
            "(its share of the section). These pre-fill automatically from the section's "
            "Section Start Date plus each activity's standard duration, and you tune them in one "
            "place — the Section Task Planner page.")
    _steps(doc, [
        "Open Work Schedule and Progress → 'Section Task Planner' (or /app/section-task-planner).",
        "Pick the section. Set its Section Start Date, then click 'Re-fill dates from start' to "
        "cascade tentative windows across the 9 activities.",
        "Adjust any start/end date or weight by hand. The weight total turns green when it adds "
        "up to 1.00 (100%).",
        "Click Save Plan. Any task whose end date has passed while it is still below 100% shows "
        "as Delayed — on the planner, on Section 360, and in the client pack.",
    ])
    _callout(doc, "Tip", "Weights drive the section's roll-up %: a task at 60% with weight 0.15 "
             "contributes 9% to the section. Keep weights summing to 1.00 for a true percentage.")

    doc.add_heading("Section 360° — one section, everything (Section 360 page)", level=2)
    _p(doc, "The Section 360 page is your single drill-down for any section: schedule position, "
            "task checklist, manpower, material and recent site activity — no hunting across "
            "reports.")
    _bullets(doc, [
        "Open it from Work Schedule and Progress or Benkas MIS ('Section 360°'), or /app/section-360.",
        "Header shows Actual vs Planned % and an On Track / Delayed badge (with rough days behind).",
        "Task checklist lists all 9 activities with their planned window, progress and status. "
        "'Mark Done' sets a task to 100% and instantly rolls the section % up.",
        "Manpower block: on-site today, person-days this week / total, split by category and "
        "contractor. Material block: value consumed, top items issued, open requests. Activity "
        "block: recent daily-log photos and work descriptions, visitor and open-safety counts.",
    ])

    doc.add_heading("Reports", level=2)
    _p(doc, "Every workspace carries its reports. The full list:")
    _table(doc, ["Report", "Answers"], [
        ["EOD Manpower MIS", "Headcount by section & category, ack reconciliation."],
        ["Contractor-wise Labour Count", "How many labour each contractor has, by skill."],
        ["Late Entry and OT Report", "First-in / last-out and late arrivals."],
        ["Material Received vs Issued", "Section-wise received vs issued quantity/value."],
        ["Material Section Stock Balance", "On-hand stock per section warehouse."],
        ["QC Rejection Report", "Rejected quality inspections."],
        ["Section Progress - Planned vs Actual", "Task progress vs reported progress."],
        ["Section WBS Progress", "Every activity sub-task's status & %."],
        ["Section Manpower & Work Log", "Per-section, per-day workers, person-days and the "
         "actual work description logged."],
        ["Delay Analysis by Section", "Delay reasons tallied by section."],
        ["Weekly Section MIS", "Weekly logs, latest %, open material requests per section."],
        ["Material Consumption by Item", "Per-item, per-section quantity consumed at site."],
        ["Visitor Register Summary", "Visits, companies and who's still on site, by section."],
        ["Safety Violations Summary / by Contractor", "Violations by section / by contractor."],
        ["Generator Consumption MIS", "Running hours & diesel per generator."],
        ["Vehicle Utilisation", "Trips, hours, distance per site vehicle."],
    ])
    doc.add_heading("Staff attendance (HR)", level=2)
    _bullets(doc, [
        "Every Employee gate scan also creates an HR Employee Checkin (IN/OUT). A default "
        "'Site General Shift' (09:00-18:00, auto-attendance) turns those checkins into HRMS "
        "Attendance automatically.",
        "See it in 'Staff Attendance Summary' (from HRMS Attendance) and 'Labour Attendance "
        "Register' (labour, from gate entries — the contractor-billing backbone).",
    ])
    doc.add_heading("The weekly client MIS pack", level=2)
    _p(doc, "Every week the system builds a presentation-grade Word document you hand to Ramshy "
            "Bio — cover with the project scorecard, section-wise progress table, a detail page "
            "per section (task checklist, work done, material consumed), manpower and material "
            "annexes, and an exceptions page (delayed tasks, open safety issues, overdue gate "
            "passes, weighbridge variances).")
    _bullets(doc, [
        "It is generated automatically every week and dropped in the 'BENKAS PM' folder as "
        "Client_Weekly_MIS_<date>.docx.",
        "Build one on demand for any week-ending date with "
        "benkas_erp.setup.client_mis.build (kwargs {'week_ending':'YYYY-MM-DD'}).",
        "A committed sample lives in the app's docs/ folder (Sample_Client_Weekly_MIS.docx).",
        "For a live on-screen view, the Section 360 page and Benkas MIS dashboard show the same "
        "numbers in real time.",
    ])

    doc.add_heading("BEFORE GO-LIVE checklist", level=2)
    _bullets(doc, [
        "Approval workflows are currently OFF (Gate Entry, Gate Pass, Safety/Electrical "
        "Permits, Material Request) so basic operations aren't blocked during build-out. The "
        "status fields are normal editable selects for now. To re-enable enforcement before "
        "go-live: set WORKFLOWS_ACTIVE = True in setup/workflows.py and run migrate — a "
        "one-line change.",
        "Finalise roles and users, then apply User Permissions (restrict each Incharge to "
        "their section) and required_apps — deferred to the real-site setup.",
        "Confirm the thermal printer roll width (default 80 mm; change ROLL_WIDTH_MM in "
        "setup/print_formats.py for 58 mm).",
    ])


def _ch_management(doc):
    doc.add_heading("6.  Ramshy Bio Management — reading the dashboard", level=1)
    _p(doc, "You have read-only access to the Benkas MIS dashboard. Open the Benkas ERP tile "
            "→ Benkas MIS. In one page:")
    _table(doc, ["What you see", "What it tells you"], [
        ["Overall % Complete", "Weighted average progress across all 12 sections."],
        ["Today's Headcount", "People on site right now (from gate scans)."],
        ["Open Safety Violations", "Unresolved safety issues."],
        ["Pending Acknowledgements", "Gate entries an Incharge hasn't yet confirmed."],
        ["Headcount by Section chart", "Where the workforce is deployed today."],
        ["Violations by Section chart", "Where safety attention is needed."],
    ])
    _p(doc, "Every number traces back to the gate — see the next chapter, 'The daily chain'.")


def _ch_qr_system(doc):
    doc.add_heading("7.  The QR system explained", level=1)
    _p(doc, "Every ID card and slip carries a QR code. Scanning it is how the plant runs "
            "hands-free at the gate.")
    doc.add_heading("What each QR encodes", level=2)
    _table(doc, ["Document", "QR content", "Example"], [
        ["Staff ID card (Employee)", "EMP-<employee id>", "EMP-HR-EMP-00001"],
        ["Labour ID card (Labour Master)", "LAB-<labour id>", "LAB-LM-00001"],
        ["Gate Pass slip", "GP-<gate pass no>", "GP-GP-2026-00012"],
        ["Visitor slip", "VIS-<visitor log no>", "VIS-VIS-2026-00034"],
    ])
    _p(doc, "The prefix tells the Scan Station what kind of document it is; the rest is the "
            "record's ID. The station reads it and does the right thing automatically.")
    doc.add_heading("Issuing & re-issuing cards", level=2)
    _bullets(doc, [
        "Register the person (Employee or Labour Master), then Print → ID Card. The QR is "
        "generated from their record — no manual entry.",
        "Lost/damaged card: just reprint. The QR stays the same because it's tied to their "
        "record ID.",
        "Deactivating a Labour (status Inactive/Exited) makes their card fail at the gate "
        "immediately — no need to collect the physical card.",
    ])
    doc.add_heading("Scanner hardware", level=2)
    _bullets(doc, [
        "Any USB 2D barcode/QR scanner in 'HID keyboard' mode works — it types the code and "
        "presses Enter. No drivers, no brand lock-in. This is the primary, fastest path.",
        "A tablet/phone camera also works via the '📷 Camera scan' button (Chrome/Edge, which "
        "have the built-in QR reader). Good as a backup or for roaming checks.",
        "Print cards at a size where the QR is ~3 cm — the app already renders them large "
        "with error-correction so a smudge or slight angle still scans.",
    ])


def _ch_daily_chain(doc):
    doc.add_heading("8.  The daily chain — from gate to client report", level=1)
    _p(doc, "This is how a single scan at the gate becomes a number on the client's weekly "
            "report. Anyone can use it to trace any figure back to its source.")
    for line in [
        "① Gate scan  →  Gate Entry (In) with live photo",
        "② Incharge Confirms the entry  →  the person counts as really present",
        "③ Daily Progress Log (Incharge) records: task % + workers + material used",
        "④ On submit  →  Stock Entry auto-issues the material (stock drops)",
        "⑤ Task.progress updates  →  Section % recalculated",
        "⑥ Section % + headcount + material  →  Benkas MIS dashboard",
        "⑦ Weekly Section MIS report  →  shared with Ramshy Bio management",
    ]:
        p = doc.add_paragraph()
        r = p.add_run(line)
        r.bold = True
    _p(doc, "So if management asks 'why is Distillation at 60%?', you trace: dashboard → "
            "Section WBS Progress report → the Daily Progress Logs that set those task % → the "
            "gate entries and material behind them. Every figure is auditable to a scan and a "
            "photo.")


def _ch_troubleshooting(doc):
    doc.add_heading("9.  Troubleshooting & FAQ", level=1)
    _table(doc, ["Situation", "What to do"], [
        ["Forgot to scan someone out", "Open their Gate Entry and set Time Out manually; or scan the card now."],
        ["Scanned IN but it says OUT", "They already had an open entry today — the scan closed it. Scan once more to open a fresh IN if needed."],
        ["Photo won't upload / camera blank", "Use 'Log IN without photo' to not hold up the queue; check browser camera permission and lighting."],
        ["Worker not appearing in the Daily Log dropdown", "They have no gate entry for your section today. They must be scanned in at the gate first."],
        ["'…has no gate entry for this section today'", "Same as above — the log blocks workers who didn't come through the gate. Scan them in, then add them."],
        ["Material Request not showing to consume", "It must be Approved (not just Requested). Approve it, or check you picked the right section."],
        ["Section % not updating", "Progress comes from the Daily Progress Log's Task Progress rows on submit. Make sure the log was submitted, not left as draft."],
        ["Stock went negative when submitting a log", "The section warehouse has no stock for that item — enter the GRN (Purchase Receipt) first, then log consumption."],
        ["'PASS NOT APPROVED' at the gate", "The gate pass is still Requested. The person's Incharge must Approve it."],
        ["Gate pass shows Overdue", "It was scanned Out but not scanned back in by the expected time. Find the person; scan Return when they're back."],
        ["Card says ENTRY BLOCKED", "The labour is Inactive/Exited. If that's wrong, the PM sets status back to Active."],
        ["QR won't scan", "Reprint the card larger; clean the scanner window; try the camera-scan button; check the card isn't creased across the QR."],
        ["Invoice photo blocks my GRN", "That's intentional — attach the supplier invoice/challan photo to proceed."],
        ["Can't close a work permit", "Tick the Closing Confirmation (and for electrical, the re-energized sign-off) first."],
        ["I don't see a workspace/report", "Your role doesn't include it. Ask the PM if you should have access."],
        ["Two people share one card", "Never allow it — each person needs their own card so the gate photo and record are theirs."],
    ])


# --------------------------------------------------------------------------
# QUICK-REFERENCE CARDS (one page each)
# --------------------------------------------------------------------------
def build_quickref():
    outs = []
    outs.append(_qr_gate_security())
    outs.append(_qr_section_incharge())
    return outs


def _qr_card(title, subtitle):
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    doc = _doc()
    for s in doc.sections:
        s.top_margin = Inches(0.5)
        s.bottom_margin = Inches(0.5)
        s.left_margin = Inches(0.6)
        s.right_margin = Inches(0.6)
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run(title)
    r.bold = True
    r.font.size = Pt(20)
    r.font.color.rgb = RGBColor(0x16, 0x32, 0x4F)
    sp = doc.add_paragraph()
    sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sp.add_run(subtitle).font.size = Pt(11)
    return doc


def _qr_gate_security():
    from docx.shared import Pt
    doc = _qr_card("GATE SCAN — QUICK CARD", "Gate Security  ·  keep the Scan Station open")
    def step(n, t):
        p = doc.add_paragraph()
        b = p.add_run(f"{n}  ")
        b.bold = True
        b.font.size = Pt(13)
        p.add_run(t).font.size = Pt(12)
    step("IN", "Scan card → check PHOTO matches → pick/confirm section → 📸 Snap & Log IN → 🖨 Print Slip.")
    step("OUT", "Person leaves → scan same card → 'OUT RECORDED'. Done.")
    step("NO CARD", "Tap 'Temp Pass' → name + section (or pick lost-card person) → print Temp Slip. Works today only.")
    step("GATE PASS", "Scan slip. GREEN = let out. RED 'NOT APPROVED' = send back to Incharge.")
    step("RETURN", "Scan the gate pass again when they come back → 'RETURNED'.")
    step("VISITOR", "New Visitor Log + photo → print slip. Scan slip at exit to close.")
    step("TOOLS", "Tap 'Tools In' → list items → print Tools Slip. At exit scan it, tick qty out. Mismatch = hold & call Incharge.")
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.add_run("RED SCREEN = STOP. ").bold = True
    p.add_run("ENTRY BLOCKED = deactivated card, refuse. NOT APPROVED = no exit. "
              "EXPIRED TEMP SLIP = yesterday's slip, issue a new one.")
    p2 = doc.add_paragraph()
    p2.add_run("Every scan shows a big banner with photo + what happened + a Print button, and "
               "adds to the Recent Activity list. It stays until your next scan.").italic = True
    out = os.path.join(WIN_DIR, "Benkas_QuickRef_Gate_Security.docx")
    doc.save(out)
    _repo_copy(doc, "Benkas_QuickRef_Gate_Security.docx")
    print("Quick-ref (Gate Security) written to:", out)
    return out


def _qr_section_incharge():
    from docx.shared import Pt
    doc = _qr_card("DAILY LOG — QUICK CARD", "Section Incharge  ·  one log per section per day")
    def step(n, t):
        p = doc.add_paragraph()
        b = p.add_run(f"{n}  ")
        b.bold = True
        b.font.size = Pt(13)
        p.add_run(t).font.size = Pt(12)
    step("1", "Morning: open pending Gate Entries → Confirm the real ones, Dispute no-shows.")
    step("2", "Need material? New Material Request (type Material Issue) → section + task + items → Submit → Approve.")
    step("3", "New Daily Progress Log. Add Task Progress rows (task, %, delay reason if behind).")
    step("4", "Add Workers Present. A worker with no gate entry today WON'T save — scan them in first.")
    step("5", "Add Material Consumed (item, qty, task; link the Material Request if there was one).")
    step("6", "Attach at least one site photo → Submit. Stock issues itself; % updates itself.")
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.add_run("Safety issue? ").bold = True
    p.add_run("New Safety Violation Log with a photo. Gate pass to approve? Open it → Approve.")
    out = os.path.join(WIN_DIR, "Benkas_QuickRef_Section_Incharge.docx")
    doc.save(out)
    _repo_copy(doc, "Benkas_QuickRef_Section_Incharge.docx")
    print("Quick-ref (Section Incharge) written to:", out)
    return out


def _repo_copy(doc, filename):
    try:
        app_docs = frappe.get_app_path("benkas_erp", "..", "docs")
        os.makedirs(app_docs, exist_ok=True)
        doc.save(os.path.join(app_docs, filename))
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Benkas: repo copy {filename} failed")


def build_all():
    build()
    build_quickref()
    return "ok"
