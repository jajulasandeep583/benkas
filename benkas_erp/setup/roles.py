import frappe

ROLES = [
    "Gate Security",
    "Section Incharge",
    "Stores Weighbridge Operator",
    "Safety Officer",
    "Generator Electrical Operator",
    "Benkas Project Manager",
    "Ramshy Bio Management",
]


def create_roles():
    for role in ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role,
                "desk_access": 1,
            }).insert(ignore_permissions=True)
