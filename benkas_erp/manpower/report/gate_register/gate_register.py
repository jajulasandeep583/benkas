# Copyright (c) 2026, Benkas Engineering and contributors
# For license information, please see license.txt
"""Gate Register — every in/out event across the site (people, visitors, vehicles,
tools, gate passes) as one UNION. Script report so the optional filters (etype,
direction, section, contractor) can default safely: a Query Report crashes with
KeyError when the initial auto-run drops empty-valued optional filters."""

import frappe

COLUMNS = [
    {"label": "Date / Time", "fieldname": "ts", "fieldtype": "Datetime", "width": 165},
    {"label": "Type", "fieldname": "etype", "fieldtype": "Data", "width": 135},
    {"label": "Name / Description", "fieldname": "name_desc", "fieldtype": "Data", "width": 200},
    {"label": "Contractor", "fieldname": "contractor", "fieldtype": "Data", "width": 150},
    {"label": "Section", "fieldname": "section", "fieldtype": "Data", "width": 130},
    {"label": "Dir", "fieldname": "dir", "fieldtype": "Data", "width": 55},
    {"label": "Source", "fieldname": "source", "fieldtype": "Data", "width": 130},
    {"label": "Reference", "fieldname": "reference", "fieldtype": "Data", "width": 160},
    {"label": "Recorded By", "fieldname": "recorded_by", "fieldtype": "Data", "width": 150},
]

QUERY = """
SELECT
  x.ts          AS ts,
  x.etype       AS etype,
  x.name_desc   AS name_desc,
  x.contractor  AS contractor,
  x.section     AS section,
  x.direction   AS dir,
  x.source      AS source,
  x.reference   AS reference,
  x.recorded_by AS recorded_by
FROM (
  SELECT ge.time_in ts,
    CASE ge.person_type WHEN 'Employee' THEN 'Person-Staff' WHEN 'Labour Master' THEN 'Person-Labour'
      ELSE 'Person-Contractor' END etype,
    ge.person name_desc,
    (SELECT lm.contractor FROM `tabLabour Master` lm WHERE lm.name = ge.person) contractor,
    ge.plant_section section, 'IN' direction, 'Gate Entry' source, ge.name reference, ge.owner recorded_by
  FROM `tabGate Entry` ge WHERE ge.time_in IS NOT NULL
  UNION ALL
  SELECT ge.time_out,
    CASE ge.person_type WHEN 'Employee' THEN 'Person-Staff' WHEN 'Labour Master' THEN 'Person-Labour'
      ELSE 'Person-Contractor' END,
    ge.person, (SELECT lm.contractor FROM `tabLabour Master` lm WHERE lm.name = ge.person),
    ge.plant_section, 'OUT', 'Gate Entry', ge.name, ge.owner
  FROM `tabGate Entry` ge WHERE ge.time_out IS NOT NULL
  UNION ALL
  SELECT vl.time_in, 'Visitor', vl.visitor_name, vl.company, vl.plant_section, 'IN', 'Visitor Log', vl.name, vl.owner
  FROM `tabVisitor Log` vl WHERE vl.time_in IS NOT NULL
  UNION ALL
  SELECT vl.time_out, 'Visitor', vl.visitor_name, vl.company, vl.plant_section, 'OUT', 'Visitor Log', vl.name, vl.owner
  FROM `tabVisitor Log` vl WHERE vl.time_out IS NOT NULL
  UNION ALL
  SELECT svl.time_out, 'Vehicle-Site', svl.vehicle, svl.driver, svl.plant_section, 'OUT', 'Site Vehicle Log', svl.name, svl.owner
  FROM `tabSite Vehicle Log` svl WHERE svl.time_out IS NOT NULL
  UNION ALL
  SELECT svl.time_in, 'Vehicle-Site', svl.vehicle, svl.driver, svl.plant_section, 'IN', 'Site Vehicle Log', svl.name, svl.owner
  FROM `tabSite Vehicle Log` svl WHERE svl.time_in IS NOT NULL
  UNION ALL
  SELECT TIMESTAMP(pr.posting_date, pr.posting_time), 'Vehicle-Material',
    CONCAT(pr.supplier, CASE WHEN pr.weighbridge_slip_no IS NOT NULL AND pr.weighbridge_slip_no != ''
      THEN CONCAT(' / WB ', pr.weighbridge_slip_no) ELSE '' END),
    pr.supplier, pr.plant_section, 'IN', 'Purchase Receipt', pr.name, pr.owner
  FROM `tabPurchase Receipt` pr WHERE pr.docstatus < 2 AND pr.posting_date IS NOT NULL
  UNION ALL
  SELECT ctr.creation, 'Tools', ctr.tool_description, ctr.contractor, NULL, 'IN', 'Contractor Tools Register', ctr.name, ctr.owner
  FROM `tabContractor Tools Register` ctr
  UNION ALL
  SELECT ctr.modified, 'Tools', ctr.tool_description, ctr.contractor, NULL, 'OUT', 'Contractor Tools Register', ctr.name, ctr.owner
  FROM `tabContractor Tools Register` ctr WHERE ctr.status IN ('Returned', 'Mismatch')
  UNION ALL
  SELECT gp.actual_out_time, 'Gate Pass', gp.person, NULL, gp.plant_section, 'OUT', 'Gate Pass', gp.name, gp.owner
  FROM `tabGate Pass` gp WHERE gp.actual_out_time IS NOT NULL
  UNION ALL
  SELECT gp.actual_return_time, 'Gate Pass', gp.person, NULL, gp.plant_section, 'IN', 'Gate Pass', gp.name, gp.owner
  FROM `tabGate Pass` gp WHERE gp.actual_return_time IS NOT NULL
) x
WHERE x.ts IS NOT NULL
  AND DATE(x.ts) BETWEEN %(from_date)s AND %(to_date)s
  AND (%(etype)s = '' OR x.etype = %(etype)s)
  AND (%(direction)s = '' OR x.direction = %(direction)s)
  AND (%(section)s = '' OR x.section = %(section)s)
  AND (%(contractor)s = '' OR x.contractor = %(contractor)s)
ORDER BY x.ts DESC
"""


def execute(filters=None):
    filters = frappe._dict(filters or {})
    today = frappe.utils.today()
    params = {
        "from_date": filters.get("from_date") or today,
        "to_date": filters.get("to_date") or today,
        "etype": filters.get("etype") or "",
        "direction": filters.get("direction") or "",
        "section": filters.get("section") or "",
        "contractor": filters.get("contractor") or "",
    }
    return COLUMNS, frappe.db.sql(QUERY, params, as_dict=True)
