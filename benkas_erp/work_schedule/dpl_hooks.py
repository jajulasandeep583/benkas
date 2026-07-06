import frappe


def set_rollups(doc, method=None):
    """Auto-fetch manpower & material rollups for the section/date (aggregations,
    not a single-field fetch — so done server-side, not via fetch_from)."""
    if not (doc.plant_section and doc.log_date):
        return

    doc.manpower_deployed = frappe.db.count("Gate Entry", {
        "plant_section": doc.plant_section,
        "entry_type": "In",
        "time_in": ["between", [f"{doc.log_date} 00:00:00", f"{doc.log_date} 23:59:59"]],
    })

    value = frappe.db.sql(
        """
        SELECT COALESCE(SUM(sed.amount), 0)
        FROM `tabStock Entry` se
        JOIN `tabStock Entry Detail` sed ON sed.parent = se.name
        WHERE se.plant_section = %s
          AND se.purpose = 'Material Issue'
          AND se.posting_date = %s
          AND se.docstatus = 1
        """,
        (doc.plant_section, doc.log_date),
    )
    doc.material_consumed_value = value[0][0] if value else 0
