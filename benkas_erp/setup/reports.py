"""Standard Query Reports for Benkas ERP MIS (code-driven, idempotent).

Created with is_standard = Yes so, in developer mode, each report is written
to its module folder as version-controlled files.
"""

import frappe

REPORTS = [
    {
        "name": "EOD Manpower MIS", "ref_doctype": "Gate Entry", "module": "Manpower",
        "query": """
SELECT
  DATE(ge.time_in)            AS "Date:Date:100",
  ps.section_name            AS "Section:Data:150",
  ge.person_type             AS "Category:Data:120",
  COUNT(DISTINCT ge.person)  AS "Headcount:Int:100",
  SUM(ge.acknowledgement_status = 'Pending')  AS "Not Ack:Int:90",
  SUM(ge.acknowledgement_status = 'Disputed') AS "Disputed:Int:90"
FROM `tabGate Entry` ge
LEFT JOIN `tabPlant Section` ps ON ps.name = ge.plant_section
WHERE ge.entry_type = 'In'
GROUP BY DATE(ge.time_in), ps.section_name, ge.person_type
ORDER BY DATE(ge.time_in) DESC
""",
    },
    {
        "name": "Material Received vs Issued", "ref_doctype": "Stock Entry", "module": "Material",
        "query": """
SELECT
  ps.section_name AS "Section:Data:160",
  SUM(CASE WHEN se.purpose = 'Material Receipt' THEN sed.qty ELSE 0 END) AS "Received Qty:Float:120",
  SUM(CASE WHEN se.purpose = 'Material Issue'   THEN sed.qty ELSE 0 END) AS "Issued Qty:Float:120",
  SUM(CASE WHEN se.purpose = 'Material Issue'   THEN sed.amount ELSE 0 END) AS "Issue Value:Currency:140"
FROM `tabStock Entry` se
JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
LEFT JOIN `tabPlant Section` ps ON ps.name = se.plant_section
WHERE se.docstatus = 1
GROUP BY ps.section_name
ORDER BY ps.section_name
""",
    },
    {
        "name": "Section Progress - Planned vs Actual", "ref_doctype": "Daily Progress Log",
        "module": "Work Schedule",
        "query": """
SELECT
  ps.section_name AS "Section:Data:160",
  t.subject       AS "Task:Data:160",
  t.progress      AS "Task Progress:Percent:130",
  MAX(dtp.percent_complete) AS "Reported:Percent:120",
  MAX(dpl.log_date)         AS "Last Update:Date:110"
FROM `tabPlant Section` ps
LEFT JOIN `tabTask` t ON t.name = ps.project_task
LEFT JOIN `tabDaily Progress Log` dpl ON dpl.plant_section = ps.name AND dpl.docstatus = 1
LEFT JOIN `tabDaily Task Progress` dtp ON dtp.parent = dpl.name
GROUP BY ps.name
ORDER BY ps.section_name
""",
    },
    {
        "name": "Safety Violations Summary", "ref_doctype": "Safety Violation Log",
        "module": "Site Safety Assets",
        "query": """
SELECT
  ps.section_name     AS "Section:Data:150",
  svl.violation_type  AS "Violation Type:Data:150",
  svl.person          AS "Person:Data:150",
  COUNT(*)            AS "Count:Int:80",
  SUM(svl.status = 'Open') AS "Open:Int:80"
FROM `tabSafety Violation Log` svl
LEFT JOIN `tabPlant Section` ps ON ps.name = svl.plant_section
GROUP BY ps.section_name, svl.violation_type, svl.person
ORDER BY COUNT(*) DESC
""",
    },
    {
        "name": "Generator Consumption MIS", "ref_doctype": "Generator Log",
        "module": "Site Safety Assets",
        "query": """
SELECT
  g.generator            AS "Generator:Data:150",
  g.log_date             AS "Date:Date:100",
  SUM(g.running_hours)   AS "Running Hrs:Float:110",
  SUM(g.diesel_filled)   AS "Diesel Filled (L):Float:130",
  CASE WHEN SUM(g.running_hours) > 0
       THEN SUM(g.diesel_filled) / SUM(g.running_hours) ELSE 0 END AS "L / hr:Float:90"
FROM `tabGenerator Log` g
GROUP BY g.generator, g.log_date
ORDER BY g.log_date DESC
""",
    },
    {
        "name": "Vehicle Utilisation", "ref_doctype": "Site Vehicle Log",
        "module": "Site Safety Assets",
        "query": """
SELECT
  vl.vehicle AS "Vehicle:Data:150",
  COUNT(*)   AS "Trips:Int:80",
  ROUND(SUM(TIMESTAMPDIFF(MINUTE, vl.time_out, vl.time_in)) / 60, 1) AS "Hours Out:Float:110",
  SUM(vl.odometer_end - vl.odometer_start) AS "Distance:Float:110"
FROM `tabSite Vehicle Log` vl
WHERE vl.time_out IS NOT NULL AND vl.time_in IS NOT NULL
GROUP BY vl.vehicle
ORDER BY COUNT(*) DESC
""",
    },
    {
        "name": "Contractor-wise Labour Count", "ref_doctype": "Labour Master", "module": "Manpower",
        "query": """
SELECT
  lm.contractor AS "Contractor:Link/Contractor:190",
  COUNT(*)                        AS "Total:Int:80",
  SUM(lm.status = 'Active')       AS "Active:Int:80",
  SUM(lm.category = 'Skilled')    AS "Skilled:Int:90",
  SUM(lm.category = 'Semi-skilled') AS "Semi:Int:80",
  SUM(lm.category = 'Unskilled')  AS "Unskilled:Int:100"
FROM `tabLabour Master` lm
GROUP BY lm.contractor
ORDER BY COUNT(*) DESC
""",
    },
    {
        "name": "Late Entry and OT Report", "ref_doctype": "Gate Entry", "module": "Manpower",
        "query": """
SELECT
  DATE(ge.time_in)  AS "Date:Date:100",
  ge.person         AS "Person:Data:150",
  ge.person_type    AS "Type:Data:110",
  ps.section_name   AS "Section:Data:140",
  TIME(MIN(ge.time_in)) AS "First In:Data:90",
  TIME(MAX(COALESCE(ge.time_out, ge.time_in))) AS "Last Out:Data:90",
  CASE WHEN TIME(MIN(ge.time_in)) > '09:00:00' THEN 'LATE' ELSE '' END AS "Late:Data:70"
FROM `tabGate Entry` ge
LEFT JOIN `tabPlant Section` ps ON ps.name = ge.plant_section
WHERE ge.time_in IS NOT NULL
GROUP BY DATE(ge.time_in), ge.person, ge.person_type, ps.section_name
ORDER BY DATE(ge.time_in) DESC
""",
    },
    {
        "name": "Material Section Stock Balance", "ref_doctype": "Plant Section", "module": "Material",
        "query": """
SELECT
  ps.section_name AS "Section:Data:170",
  b.warehouse     AS "Warehouse:Link/Warehouse:180",
  SUM(b.actual_qty)   AS "On Hand Qty:Float:120",
  SUM(b.stock_value)  AS "Stock Value:Currency:140"
FROM `tabPlant Section` ps
JOIN `tabBin` b ON b.warehouse = ps.warehouse
GROUP BY ps.section_name, b.warehouse
ORDER BY ps.section_name
""",
    },
    {
        "name": "QC Rejection Report", "ref_doctype": "Quality Inspection", "module": "Material",
        "query": """
SELECT
  qi.item_code       AS "Item:Data:150",
  qi.status          AS "Status:Data:100",
  qi.reference_type  AS "Ref Type:Data:130",
  qi.reference_name  AS "Reference:Data:150",
  qi.report_date     AS "Date:Date:100"
FROM `tabQuality Inspection` qi
WHERE qi.status = 'Rejected'
ORDER BY qi.report_date DESC
""",
    },
    {
        "name": "Delay Analysis by Section", "ref_doctype": "Daily Progress Log", "module": "Work Schedule",
        "query": """
SELECT
  ps.section_name   AS "Section:Data:170",
  dtp.delay_reason  AS "Delay Reason:Link/Delay Reason:200",
  COUNT(*)          AS "Occurrences:Int:120"
FROM `tabDaily Progress Log` dpl
JOIN `tabDaily Task Progress` dtp ON dtp.parent = dpl.name
LEFT JOIN `tabPlant Section` ps ON ps.name = dpl.plant_section
WHERE dtp.delay_reason IS NOT NULL AND dtp.delay_reason != ''
GROUP BY ps.section_name, dtp.delay_reason
ORDER BY COUNT(*) DESC
""",
    },
    {
        "name": "Section WBS Progress", "ref_doctype": "Task", "module": "Work Schedule",
        "query": """
SELECT
  parent.subject AS "Section Task:Data:150",
  t.subject      AS "Activity:Data:230",
  t.status       AS "Status:Data:100",
  t.progress     AS "Progress:Percent:110",
  t.exp_start_date AS "Planned Start:Date:110",
  t.exp_end_date   AS "Planned End:Date:110"
FROM `tabTask` t
JOIN `tabTask` parent ON parent.name = t.parent_task
WHERE t.parent_task IN (SELECT project_task FROM `tabPlant Section` WHERE project_task IS NOT NULL)
ORDER BY parent.subject, t.subject
""",
    },
    {
        "name": "Safety Violations by Contractor", "ref_doctype": "Safety Violation Log",
        "module": "Site Safety Assets",
        "query": """
SELECT
  COALESCE(lm.contractor, svl.person) AS "Contractor / Person:Data:200",
  svl.violation_type AS "Violation Type:Data:150",
  COUNT(*)           AS "Count:Int:80",
  SUM(svl.status = 'Open') AS "Open:Int:80"
FROM `tabSafety Violation Log` svl
LEFT JOIN `tabLabour Master` lm ON lm.name = svl.person AND svl.person_type = 'Labour Master'
GROUP BY COALESCE(lm.contractor, svl.person), svl.violation_type
ORDER BY COUNT(*) DESC
""",
    },
]


def create_reports():
    for r in REPORTS:
        q = r["query"].strip()
        if frappe.db.exists("Report", r["name"]):
            # keep query / ref_doctype in sync with code on every migrate
            doc = frappe.get_doc("Report", r["name"])
            changed = False
            if (doc.query or "").strip() != q:
                doc.query = q
                changed = True
            if doc.ref_doctype != r["ref_doctype"]:
                doc.ref_doctype = r["ref_doctype"]
                changed = True
            if changed:
                doc.save(ignore_permissions=True)
            continue
        frappe.get_doc({
            "doctype": "Report",
            "report_name": r["name"],
            "ref_doctype": r["ref_doctype"],
            "module": r["module"],
            "report_type": "Query Report",
            "is_standard": "Yes",
            "query": q,
        }).insert(ignore_permissions=True)
