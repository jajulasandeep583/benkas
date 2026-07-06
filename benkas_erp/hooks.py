app_name = "benkas_erp"
app_title = "Benkas ERP"
app_publisher = "Benkas Engineering"
app_description = "Custom app for Ramshy Bio Ethanol Plant project monitoring"
app_email = "aimidhunatech@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "benkas_erp",
# 		"logo": "/assets/benkas_erp/logo.png",
# 		"title": "Benkas ERP",
# 		"route": "/benkas_erp",
# 		"has_permission": "benkas_erp.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/benkas_erp/css/benkas_erp.css"
# app_include_js = "/assets/benkas_erp/js/benkas_erp.js"

# include js, css files in header of web template
# web_include_css = "/assets/benkas_erp/css/benkas_erp.css"
# web_include_js = "/assets/benkas_erp/js/benkas_erp.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "benkas_erp/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "benkas_erp/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "benkas_erp.utils.jinja_methods",
# 	"filters": "benkas_erp.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "benkas_erp.install.before_install"
# after_install = "benkas_erp.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "benkas_erp.uninstall.before_uninstall"
# after_uninstall = "benkas_erp.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "benkas_erp.utils.before_app_install"
# after_app_install = "benkas_erp.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "benkas_erp.utils.before_app_uninstall"
# after_app_uninstall = "benkas_erp.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "benkas_erp.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "benkas_erp.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"benkas_erp.tasks.all"
# 	],
# 	"daily": [
# 		"benkas_erp.tasks.daily"
# 	],
# 	"hourly": [
# 		"benkas_erp.tasks.hourly"
# 	],
# 	"weekly": [
# 		"benkas_erp.tasks.weekly"
# 	],
# 	"monthly": [
# 		"benkas_erp.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "benkas_erp.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "benkas_erp.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "benkas_erp.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "benkas_erp.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["benkas_erp.utils.before_request"]
# after_request = ["benkas_erp.utils.after_request"]

# Job Events
# ----------
# before_job = ["benkas_erp.utils.before_job"]
# after_job = ["benkas_erp.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"benkas_erp.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# ==================== Benkas ERP configuration ====================

after_install = "benkas_erp.setup.install.after_install"
after_migrate = "benkas_erp.setup.install.after_migrate"

doc_events = {
    "Gate Entry": {
        "validate": "benkas_erp.manpower.gate_entry_hooks.validate",
        "after_insert": "benkas_erp.manpower.gate_entry_hooks.notify_incharge",
    },
    "Purchase Receipt": {
        "validate": "benkas_erp.material.purchase_receipt_hooks.validate",
    },
    "Daily Progress Log": {
        "validate": "benkas_erp.work_schedule.dpl_hooks.validate",
        "on_submit": "benkas_erp.work_schedule.dpl_hooks.on_submit",
    },
    "Contractor Tools Register": {
        "before_save": "benkas_erp.site_safety_assets.tools_hooks.set_status",
    },
    "Generator Log": {
        "before_save": "benkas_erp.site_safety_assets.generator_hooks.compute",
    },
    "Safety Work Permit": {
        "validate": "benkas_erp.site_safety_assets.permit_hooks.validate_safety_permit",
    },
    "Safety Violation Log": {
        "validate": "benkas_erp.site_safety_assets.permit_hooks.validate_safety_violation",
    },
    "Electrical Work Permit": {
        "validate": "benkas_erp.site_safety_assets.permit_hooks.validate_electrical_permit",
    },
}

scheduler_events = {
    "cron": {
        "*/30 * * * *": [
            "benkas_erp.site_safety_assets.gate_pass_scheduler.flag_overdue_passes"
        ]
    }
}

# App tile on the /apps screen.
# NOTE: Frappe v16 supports only ONE tile per installed app — boot.py builds
# bootinfo.app_data from apps[0] of this hook, so a second entry for the same
# app is silently dropped. Benkas Core is reached instead via a "Setup /
# Masters" shortcut on the Benkas MIS landing workspace (see setup/workspaces.py).
add_to_apps_screen = [
    {
        "name": "benkas_erp",
        "logo": "/assets/frappe/images/frappe-framework-logo.svg",
        "title": "Benkas ERP",
        "route": "/app/benkas-mis",
    },
]

# Expose helpers to Jinja (print formats)
jinja = {"methods": ["benkas_erp.utils.qr_data_uri"]}
