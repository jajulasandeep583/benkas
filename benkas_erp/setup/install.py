"""
Install / migrate orchestration for Benkas ERP.

Everything the app configures on the site (roles, custom fields, workflows,
notifications, reports, workspace, print formats) is created here in code so a
fresh `install-app` / `migrate` reproduces the full setup — nothing is hand
configured in the site.
"""

import frappe


def after_install():
    setup_all()


def after_migrate():
    setup_all()


def _doctypes_ready():
    # Custom DocTypes are materialised by setup.build_doctypes; until they
    # exist we can only safely create the roles.
    return bool(frappe.db.exists("DocType", "Gate Entry"))


def setup_all():
    from benkas_erp.setup import (
        roles, custom_fields, permissions, workflows, notifications,
        reports, workspaces, print_formats, activities, onboarding, field_help,
        attendance,
    )

    roles.create_roles()
    frappe.db.commit()

    if _doctypes_ready():
        from benkas_erp import scan
        for step in (custom_fields.create, field_help.apply, permissions.apply,
                     workflows.create_workflows, notifications.create_notifications,
                     reports.create_reports, activities.seed_activities,
                     onboarding.create, workspaces.create, print_formats.create,
                     scan.backfill_barcodes, attendance.ensure_shift_type):
            step()
            frappe.db.commit()
