import frappe
from frappe.utils import time_diff_in_hours


def compute(doc, method=None):
    """Derive running hours (from times or meter) and diesel consumption rate."""
    if doc.start_time and doc.stop_time:
        doc.running_hours = round(time_diff_in_hours(doc.stop_time, doc.start_time), 2)
    elif doc.opening_meter is not None and doc.closing_meter is not None \
            and doc.closing_meter >= doc.opening_meter:
        doc.running_hours = round(doc.closing_meter - doc.opening_meter, 2)

    if doc.running_hours and doc.diesel_filled:
        doc.consumption_rate = round(doc.diesel_filled / doc.running_hours, 2)

    if doc.generator and not doc.plant_section:
        doc.plant_section = frappe.db.get_value("Generator Master", doc.generator, "plant_section")
