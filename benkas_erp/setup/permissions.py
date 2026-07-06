"""Role permissions for Benkas ERP DocTypes (code-driven, idempotent)."""

import frappe
from frappe.permissions import add_permission, update_permission_property

# role -> { doctype: {perm: value, ...} }
PERM_MAP = {
    "Gate Security": {
        "Gate Entry": {"read": 1, "write": 1, "create": 1},
        "Visitor Log": {"read": 1, "write": 1, "create": 1},
        "Contractor Tools Register": {"read": 1, "write": 1, "create": 1},
        "Site Vehicle Log": {"read": 1, "write": 1, "create": 1},
        "Gate Pass": {"read": 1, "write": 1},
    },
    "Section Incharge": {
        "Gate Entry": {"read": 1, "write": 1},
        "Daily Progress Log": {"read": 1, "write": 1, "create": 1},
        "Safety Violation Log": {"read": 1, "write": 1, "create": 1},
        "Gate Pass": {"read": 1, "write": 1},
        "Plant Section": {"read": 1},
    },
    "Stores Weighbridge Operator": {
        "Contractor Tools Register": {"read": 1},
        "Plant Section": {"read": 1},
    },
    "Safety Officer": {
        "Safety Work Permit": {"read": 1, "write": 1, "create": 1},
        "Electrical Work Permit": {"read": 1, "write": 1, "create": 1},
        "Safety Violation Log": {"read": 1, "write": 1, "create": 1},
    },
    "Generator Electrical Operator": {
        "Generator Log": {"read": 1, "write": 1, "create": 1},
        "Power Consumption Log": {"read": 1, "write": 1, "create": 1},
        "Electrical Work Permit": {"read": 1, "write": 1, "create": 1},
    },
    "Benkas Project Manager": {
        "Plant Section": {"read": 1, "write": 1, "create": 1, "delete": 1},
        "Contractor": {"read": 1, "write": 1, "create": 1, "delete": 1},
        "Labour Master": {"read": 1, "write": 1, "create": 1, "delete": 1},
        "Delay Reason": {"read": 1, "write": 1, "create": 1, "delete": 1},
        "Generator Master": {"read": 1, "write": 1, "create": 1, "delete": 1},
        "Site Vehicle": {"read": 1, "write": 1, "create": 1, "delete": 1},
        "Gate Entry": {"read": 1, "write": 1, "create": 1},
        "Gate Pass": {"read": 1, "write": 1, "create": 1},
        "Daily Progress Log": {"read": 1, "write": 1, "create": 1},
        "Visitor Log": {"read": 1, "write": 1, "create": 1},
        "Generator Log": {"read": 1, "write": 1, "create": 1},
        "Power Consumption Log": {"read": 1, "write": 1, "create": 1},
        "Contractor Tools Register": {"read": 1, "write": 1, "create": 1},
        "Site Vehicle Log": {"read": 1, "write": 1, "create": 1},
        "Safety Violation Log": {"read": 1, "write": 1, "create": 1},
        "Safety Work Permit": {"read": 1, "write": 1, "create": 1},
        "Electrical Work Permit": {"read": 1, "write": 1, "create": 1},
    },
    "Ramshy Bio Management": {
        "Plant Section": {"read": 1},
        "Gate Entry": {"read": 1},
        "Daily Progress Log": {"read": 1},
        "Safety Violation Log": {"read": 1},
        "Safety Work Permit": {"read": 1},
        "Electrical Work Permit": {"read": 1},
    },
}

# roles that get report/export on everything they can read
REPORT_ROLES = {"Benkas Project Manager", "Ramshy Bio Management"}


def apply():
    for role, dts in PERM_MAP.items():
        if not frappe.db.exists("Role", role):
            continue
        for dt, perms in dts.items():
            if not frappe.db.exists("DocType", dt):
                continue
            add_permission(dt, role, 0)
            for ptype, val in perms.items():
                update_permission_property(dt, role, 0, ptype, val, validate=False)
            if role in REPORT_ROLES:
                for ptype in ("report", "export", "print", "email"):
                    update_permission_property(dt, role, 0, ptype, 1, validate=False)
