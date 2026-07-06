"""
Print formats (code-driven, idempotent).

Everything printed AT THE GATE (ID cards + slips) uses ONE thermal size — an
80 mm receipt roll, ~72 mm printable, monochrome, single column, big centred QR
(~30 mm). Change ROLL_WIDTH_MM once to switch to 58 mm.

Office documents (Daily Progress Report, Material Request Slip) stay A4.
"""

import frappe

# ---- single source of truth for the thermal printer ----
ROLL_WIDTH_MM = 80          # standard 80 mm receipt roll (set 58 for a 58 mm printer)
PRINT_W_MM = ROLL_WIDTH_MM - 8   # printable width
QR_MM = 30                   # QR size on the slip

THERMAL_CSS = f"""
<style>
@page {{ size: {ROLL_WIDTH_MM}mm auto; margin: 2mm; }}
.tk, .tk * {{ color: #000 !important; background: #fff !important; box-shadow: none !important; }}
.tk {{ width: {PRINT_W_MM}mm; margin: 0 auto; font-family: Arial, Helvetica, sans-serif;
       text-align: center; }}
.tk .hdr {{ font-weight: bold; font-size: 11pt; border-bottom: 1px solid #000;
            padding-bottom: 2mm; margin-bottom: 2mm; }}
.tk .name {{ font-size: 17pt; font-weight: bold; margin: 2mm 0 1mm; line-height: 1.1; }}
.tk .big {{ font-size: 15pt; font-weight: bold; margin: 2mm 0; }}
.tk .f {{ font-size: 10pt; margin: 0.5mm 0; }}
.tk .ph {{ width: 24mm; height: 30mm; object-fit: cover; border: 1px solid #000;
           display: block; margin: 2mm auto; }}
.tk .qr {{ margin: 2mm 0 1mm; }}
.tk .qr img {{ width: {QR_MM}mm; height: {QR_MM}mm; image-rendering: pixelated; }}
.tk .code {{ font-family: monospace; font-size: 9pt; letter-spacing: 1px; margin-bottom: 2mm; }}
.tk table {{ width: 100%; border-collapse: collapse; font-size: 9pt; margin: 2mm 0; }}
.tk th, .tk td {{ border: 1px solid #000; padding: 1mm; text-align: left; }}
.tk .foot {{ font-size: 8pt; margin-top: 2mm; border-top: 1px dashed #000; padding-top: 1mm; }}
</style>
"""

STAFF = THERMAL_CSS + """
<div class="tk">
  <div class="hdr">RAMSHY BIO — STAFF ID</div>
  <img class="ph" src="{{ doc.image or '/assets/frappe/images/ui/avatar.png' }}">
  <div class="name">{{ doc.employee_name or doc.name }}</div>
  <div class="f">{{ doc.employment_type or 'Staff' }}{% if doc.department %} · {{ doc.department }}{% endif %}</div>
  <div class="qr"><img src="{{ qr_data_uri(qr_key(doc.doctype, doc.name)) }}"></div>
  <div class="code">{{ qr_key(doc.doctype, doc.name) }}</div>
</div>
"""

LABOUR = THERMAL_CSS + """
<div class="tk">
  <div class="hdr">RAMSHY BIO — LABOUR ID</div>
  <img class="ph" src="{{ doc.photo or '/assets/frappe/images/ui/avatar.png' }}">
  <div class="name">{{ doc.labour_name }}</div>
  <div class="f">{{ doc.category or '' }}{% if doc.contractor %} · {{ doc.contractor }}{% endif %}</div>
  <div class="f">Status: {{ doc.status }}</div>
  <div class="qr"><img src="{{ qr_data_uri(qr_key(doc.doctype, doc.name)) }}"></div>
  <div class="code">{{ qr_key(doc.doctype, doc.name) }}</div>
</div>
"""

GATE_ENTRY = THERMAL_CSS + """
<div class="tk">
  <div class="hdr">GATE ENTRY SLIP</div>
  <div class="name">{{ doc.person }}</div>
  <div class="f">{{ doc.person_type }} · {{ doc.plant_section }}</div>
  <div class="f">In: {{ frappe.format(doc.time_in, {'fieldtype':'Datetime'}) }}</div>
  {% if doc.time_out %}<div class="f">Out: {{ frappe.format(doc.time_out, {'fieldtype':'Datetime'}) }}</div>{% endif %}
  <div class="qr"><img src="{{ qr_data_uri(doc.name) }}"></div>
  <div class="code">{{ doc.name }}</div>
</div>
"""

TEMP = THERMAL_CSS + """
<div class="tk">
  <div class="hdr">TEMPORARY GATE SLIP</div>
  <div class="name">{{ doc.person }}</div>
  <div class="f">{{ doc.person_type }} · {{ doc.plant_section }}</div>
  <div class="f">Issued: {{ frappe.format(doc.time_in, {'fieldtype':'Datetime'}) }}</div>
  <div class="qr"><img src="{{ qr_data_uri('TMP-' + doc.name) }}"></div>
  <div class="code">TMP-{{ doc.name }}</div>
  <div class="foot">Valid for TODAY only. Scan at exit to sign out.</div>
</div>
"""

GATE_PASS = THERMAL_CSS + """
<div class="tk">
  <div class="hdr">OUTWARD GATE PASS</div>
  <div class="name">{{ doc.person }}</div>
  <div class="f">{{ doc.person_type }} · {{ doc.plant_section or '-' }}</div>
  <div class="big">{{ doc.pass_status }}</div>
  <div class="f">Reason: {{ doc.reason or '-' }}</div>
  <div class="f">Dest: {{ doc.destination or '-' }}</div>
  <div class="f">Out by: {{ frappe.format(doc.expected_out_time, {'fieldtype':'Datetime'}) }}</div>
  <div class="f">Back by: {{ frappe.format(doc.expected_return_time, {'fieldtype':'Datetime'}) }}</div>
  <div class="qr"><img src="{{ qr_data_uri(qr_key('Gate Pass', doc.name)) }}"></div>
  <div class="code">{{ qr_key('Gate Pass', doc.name) }}</div>
  <div class="foot">Approved in ERP — approver login + time = signature.</div>
</div>
"""

VISITOR = THERMAL_CSS + """
<div class="tk">
  <div class="hdr">VISITOR SLIP</div>
  <img class="ph" src="{{ doc.photo or '/assets/frappe/images/ui/avatar.png' }}">
  <div class="name">{{ doc.visitor_name }}</div>
  <div class="f">{{ doc.company or '' }}</div>
  <div class="f">Host: {{ doc.host_person or '-' }} · {{ doc.plant_section or '-' }}</div>
  <div class="f">In: {{ frappe.format(doc.time_in, {'fieldtype':'Datetime'}) }}</div>
  <div class="qr"><img src="{{ qr_data_uri(qr_key('Visitor Log', doc.name)) }}"></div>
  <div class="code">{{ qr_key('Visitor Log', doc.name) }}</div>
  <div class="foot">Scan at exit to close the visit.</div>
</div>
"""

TOOLS = THERMAL_CSS + """
<div class="tk">
  <div class="hdr">CONTRACTOR TOOLS SLIP</div>
  <div class="name">{{ doc.contractor }}</div>
  <div class="f">Status: {{ doc.status }}</div>
  <table><tr><th>Tools</th><th>Qty In</th></tr>
    <tr><td>{{ doc.tool_description or '-' }}</td><td>{{ doc.qty or 0 }}</td></tr>
  </table>
  <div class="qr"><img src="{{ qr_data_uri('TOOL-' + doc.name) }}"></div>
  <div class="code">TOOL-{{ doc.name }}</div>
  <div class="foot">Scan at exit; qty out must match qty in.</div>
</div>
"""

# ---- office documents stay A4 ----
A4_CSS = """
<style>
.bk{font-family:Arial,Helvetica,sans-serif;color:#16324f;max-width:700px}
.bk .hd{background:#16324f;color:#fff;padding:10px 14px;border-radius:6px 6px 0 0;
  font-size:15px;font-weight:bold;display:flex;justify-content:space-between}
.bk .bd{border:1px solid #16324f;border-top:0;border-radius:0 0 6px 6px;padding:14px}
.bk .g{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;font-size:12px}
.bk .f b{display:inline-block;min-width:120px;color:#555}
.bk table.t{width:100%;border-collapse:collapse;margin-top:8px;font-size:12px}
.bk table.t th,.bk table.t td{border:1px solid #cbd5e1;padding:4px 6px;text-align:left}
.bk .badge{padding:2px 8px;border-radius:10px;background:#e2e8f0;font-size:11px}
</style>
"""

DAILY_PROGRESS = A4_CSS + """
<div class="bk">
  <div class="hd"><span>DAILY SITE LOG</span><span>{{ doc.name }}</span></div>
  <div class="bd">
    <div class="g">
      <div class="f"><b>Section</b> {{ doc.plant_section }}</div>
      <div class="f"><b>Date</b> {{ frappe.format(doc.log_date, {'fieldtype':'Date'}) }}</div>
      <div class="f"><b>Incharge</b> {{ doc.incharge or '-' }}</div>
      <div class="f"><b>Stock Entry</b> {{ doc.stock_entry or '-' }}</div>
    </div>
    <div style="font-weight:bold;margin-top:10px">Task Progress</div>
    <table class="t"><tr><th>Task</th><th>% Complete</th><th>Activity</th><th>Delay Reason</th></tr>
      {% for r in doc.task_progress %}<tr><td>{{ r.task }}</td><td>{{ r.percent_complete }}%</td>
      <td>{{ r.activity_description or '' }}</td><td>{{ r.delay_reason or '' }}</td></tr>{% endfor %}
      {% if not doc.task_progress %}<tr><td colspan="4">—</td></tr>{% endif %}
    </table>
    <div style="font-weight:bold;margin-top:10px">Workers Present</div>
    <table class="t"><tr><th>Type</th><th>Person</th><th>Task</th><th>Hours</th></tr>
      {% for r in doc.workers_present %}<tr><td>{{ r.person_type }}</td><td>{{ r.person }}</td>
      <td>{{ r.task or '' }}</td><td>{{ r.hours }}</td></tr>{% endfor %}
      {% if not doc.workers_present %}<tr><td colspan="4">—</td></tr>{% endif %}
    </table>
    <div style="font-weight:bold;margin-top:10px">Material Consumed</div>
    <table class="t"><tr><th>Item</th><th>Qty</th><th>UOM</th><th>Task</th><th>MR</th></tr>
      {% for r in doc.material_consumed %}<tr><td>{{ r.item }}</td><td>{{ r.qty }}</td>
      <td>{{ r.uom or '' }}</td><td>{{ r.task or '' }}</td>
      <td>{{ r.material_request or ('NO MR' if r.no_material_request else '') }}</td></tr>{% endfor %}
      {% if not doc.material_consumed %}<tr><td colspan="5">—</td></tr>{% endif %}
    </table>
    <div class="f" style="font-size:12px;margin-top:8px"><b>Remarks</b> {{ doc.remarks or '-' }}</div>
    {% if doc.photos %}<div style="margin-top:8px">
      {% for p in doc.photos %}{% if p.image %}<img src="{{ p.image }}" style="width:120px;height:90px;object-fit:cover;border:1px solid #999;margin:3px">{% endif %}{% endfor %}
    </div>{% endif %}
  </div>
</div>
"""

MATERIAL_REQUEST = A4_CSS + """
<div class="bk">
  <div class="hd"><span>MATERIAL REQUEST SLIP</span><span>{{ doc.name }}</span></div>
  <div class="bd">
    <div class="g">
      <div class="f"><b>Plant Section</b> {{ doc.plant_section or '-' }}</div>
      <div class="f"><b>Task</b> {{ doc.benkas_task or '-' }}</div>
      <div class="f"><b>Type</b> {{ doc.material_request_type }}</div>
      <div class="f"><b>Status</b> <span class="badge">{{ doc.benkas_status or '-' }}</span></div>
      <div class="f"><b>Requested By</b> {{ doc.owner }}</div>
      <div class="f"><b>Request Date</b> {{ frappe.format(doc.transaction_date, {'fieldtype':'Date'}) }}</div>
    </div>
    <table class="t"><tr><th>Item</th><th>Qty</th><th>UOM</th><th>Required By</th><th>Warehouse</th></tr>
      {% for r in doc.items %}<tr><td>{{ r.item_code }}</td><td>{{ r.qty }}</td>
      <td>{{ r.uom or r.stock_uom or '' }}</td>
      <td>{{ frappe.format(r.schedule_date, {'fieldtype':'Date'}) }}</td>
      <td>{{ r.warehouse or '' }}</td></tr>{% endfor %}
    </table>
    <div style="margin-top:26px;display:flex;justify-content:space-between;font-size:12px">
      <div>Requested by: __________________</div>
      <div>Approved by (Incharge): __________________</div>
    </div>
  </div>
</div>
"""

# (name, doctype, module, html, print_format_type_A4?)
FORMATS = [
    ("Staff ID Card", "Employee", "Benkas Core", STAFF),
    ("Labour ID Card", "Labour Master", "Benkas Core", LABOUR),
    ("Gate Entry Slip", "Gate Entry", "Manpower", GATE_ENTRY),
    ("Temporary Gate Slip", "Gate Entry", "Manpower", TEMP),
    ("Gate Pass Slip", "Gate Pass", "Site Safety Assets", GATE_PASS),
    ("Visitor Slip", "Visitor Log", "Site Safety Assets", VISITOR),
    ("Contractor Tools Slip", "Contractor Tools Register", "Site Safety Assets", TOOLS),
    ("Daily Progress Report", "Daily Progress Log", "Work Schedule", DAILY_PROGRESS),
    ("Material Request Slip", "Material Request", "Material", MATERIAL_REQUEST),
]

THERMAL_FORMATS = {"Staff ID Card", "Labour ID Card", "Gate Entry Slip", "Temporary Gate Slip",
                   "Gate Pass Slip", "Visitor Slip", "Contractor Tools Slip"}


def create():
    for name, dt, module, html in FORMATS:
        if not frappe.db.exists("DocType", dt):
            continue
        if frappe.db.exists("Print Format", name):
            pf = frappe.get_doc("Print Format", name)
            if pf.html != html:
                pf.html = html
                pf.save(ignore_permissions=True)
            continue
        frappe.get_doc({
            "doctype": "Print Format", "name": name, "doc_type": dt, "module": module,
            "standard": "Yes", "custom_format": 1, "print_format_type": "Jinja", "html": html,
        }).insert(ignore_permissions=True)
