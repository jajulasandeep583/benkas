"""
Print formats for every stage (code-driven, idempotent):
ID cards, gate slip, gate pass, visitor slip, work permits and a daily
progress report. Self-contained HTML/Jinja; the unique code is printed so
each slip is usable immediately (a live QR can be layered on later).
"""

import frappe

CSS = """
<style>
.bk{font-family:Arial,Helvetica,sans-serif;color:#16324f;max-width:700px}
.bk .hd{background:#16324f;color:#fff;padding:10px 14px;border-radius:6px 6px 0 0;
  font-size:15px;font-weight:bold;display:flex;justify-content:space-between}
.bk .bd{border:1px solid #16324f;border-top:0;border-radius:0 0 6px 6px;padding:14px}
.bk .g{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;font-size:12px}
.bk .f b{display:inline-block;min-width:120px;color:#555}
.bk table.t{width:100%;border-collapse:collapse;margin-top:8px;font-size:12px}
.bk table.t th,.bk table.t td{border:1px solid #cbd5e1;padding:4px 6px;text-align:left}
.bk .code{margin-top:10px;text-align:center;font-family:monospace;font-size:14px;
  letter-spacing:2px;background:#f2f4f7;padding:6px;border-radius:4px}
.bk .ph{width:90px;height:110px;object-fit:cover;border:1px solid #999;float:right}
.bk .badge{padding:2px 8px;border-radius:10px;background:#e2e8f0;font-size:11px}
.bk-card{width:320px;border:2px solid #16324f;border-radius:10px;padding:14px;
  font-family:Arial;color:#16324f}
.bk-card .t{font-size:15px;font-weight:bold;text-align:center;border-bottom:1px solid #16324f;
  padding-bottom:6px;margin-bottom:8px}
.bk-card .row{display:flex;gap:10px}.bk-card img{width:90px;height:110px;object-fit:cover;border:1px solid #999}
.bk-card .field{font-size:12px;margin:2px 0}.bk-card .field b{display:inline-block;width:74px}
.bk-card .code{margin-top:8px;text-align:center;font-family:monospace;font-size:13px;
  letter-spacing:2px;background:#f2f4f7;padding:5px;border-radius:4px}
</style>
"""

STAFF = CSS + """
<div class="bk-card">
  <div class="t">RAMSHY BIO — SITE ID CARD</div>
  <div class="row">
    <img src="{{ doc.image or '/assets/frappe/images/ui/avatar.png' }}">
    <div>
      <div class="field"><b>Name</b> {{ doc.employee_name or doc.name }}</div>
      <div class="field"><b>Type</b> {{ doc.employment_type or 'Staff' }}</div>
      <div class="field"><b>Dept</b> {{ doc.department or '-' }}</div>
      <div class="field"><b>ID</b> {{ doc.name }}</div>
    </div>
  </div>
  <div style="text-align:center;margin-top:8px">
    <img src="{{ qr_data_uri(qr_key(doc.doctype, doc.name)) }}" style="width:120px;height:120px">
    <div class="code">{{ doc.id_card_barcode or doc.name }}</div>
  </div>
</div>
"""

LABOUR = CSS + """
<div class="bk-card">
  <div class="t">RAMSHY BIO — LABOUR ID CARD</div>
  <div class="row">
    <img src="{{ doc.photo or '/assets/frappe/images/ui/avatar.png' }}">
    <div>
      <div class="field"><b>Name</b> {{ doc.labour_name }}</div>
      <div class="field"><b>Category</b> {{ doc.category or '-' }}</div>
      <div class="field"><b>Contractor</b> {{ doc.contractor or '-' }}</div>
      <div class="field"><b>Status</b> {{ doc.status }}</div>
    </div>
  </div>
  <div style="text-align:center;margin-top:8px">
    <img src="{{ qr_data_uri(qr_key(doc.doctype, doc.name)) }}" style="width:120px;height:120px">
    <div class="code">{{ doc.id_card_barcode or doc.name }}</div>
  </div>
</div>
"""

GATE_ENTRY = CSS + """
<div class="bk">
  <div class="hd"><span>GATE ENTRY SLIP</span><span>{{ doc.name }}</span></div>
  <div class="bd">
    {% if doc.photo %}<img class="ph" src="{{ doc.photo }}">{% endif %}
    <div class="g">
      <div class="f"><b>Person Type</b> {{ doc.person_type }}</div>
      <div class="f"><b>Person</b> {{ doc.person }}</div>
      <div class="f"><b>Plant Section</b> {{ doc.plant_section }}</div>
      <div class="f"><b>Entry Type</b> {{ doc.entry_type }}</div>
      <div class="f"><b>Time In</b> {{ frappe.format(doc.time_in, {'fieldtype':'Datetime'}) }}</div>
      <div class="f"><b>Time Out</b> {{ frappe.format(doc.time_out, {'fieldtype':'Datetime'}) }}</div>
      <div class="f"><b>Vehicle</b> {{ doc.vehicle_no or '-' }}</div>
      <div class="f"><b>Acknowledgement</b> <span class="badge">{{ doc.acknowledgement_status }}</span></div>
    </div>
    <div class="f" style="font-size:12px;margin-top:6px"><b>Work</b> {{ doc.work_description or '-' }}</div>
    {% if doc.ppe_checklist %}
    <table class="t"><tr><th>PPE Item</th><th>Available</th></tr>
      {% for r in doc.ppe_checklist %}<tr><td>{{ r.ppe_item }}</td><td>{{ 'Yes' if r.is_available else 'No' }}</td></tr>{% endfor %}
    </table>{% endif %}
    <div style="text-align:center;margin-top:8px;clear:both">
      <img src="{{ qr_data_uri(doc.name) }}" style="width:100px;height:100px">
      <div class="code">{{ doc.name }}</div>
    </div>
  </div>
</div>
"""

GATE_PASS = CSS + """
<div class="bk">
  <div class="hd"><span>OUTWARD GATE PASS</span><span>{{ doc.name }}</span></div>
  <div class="bd">
    <div class="g">
      <div class="f"><b>Person</b> {{ doc.person }} ({{ doc.person_type }})</div>
      <div class="f"><b>Section</b> {{ doc.plant_section or '-' }}</div>
      <div class="f"><b>Destination</b> {{ doc.destination or '-' }}</div>
      <div class="f"><b>Status</b> <span class="badge">{{ doc.pass_status }}</span></div>
      <div class="f"><b>Expected Out</b> {{ frappe.format(doc.expected_out_time, {'fieldtype':'Datetime'}) }}</div>
      <div class="f"><b>Expected Return</b> {{ frappe.format(doc.expected_return_time, {'fieldtype':'Datetime'}) }}</div>
      <div class="f"><b>Actual Out</b> {{ frappe.format(doc.actual_out_time, {'fieldtype':'Datetime'}) }}</div>
      <div class="f"><b>Actual Return</b> {{ frappe.format(doc.actual_return_time, {'fieldtype':'Datetime'}) }}</div>
    </div>
    <div class="f" style="font-size:12px;margin-top:6px"><b>Reason</b> {{ doc.reason or '-' }}</div>
    <div style="text-align:center;margin-top:8px;clear:both">
      <img src="{{ qr_data_uri(qr_key('Gate Pass', doc.name)) }}" style="width:112px;height:112px">
      <div class="code">{{ doc.barcode or doc.name }}</div>
    </div>
    <div style="font-size:11px;margin-top:6px;color:#777">Approved digitally in ERP — approver login + timestamp is the authorised signature.</div>
  </div>
</div>
"""

VISITOR = CSS + """
<div class="bk">
  <div class="hd"><span>VISITOR SLIP</span><span>{{ doc.name }}</span></div>
  <div class="bd">
    {% if doc.photo %}<img class="ph" src="{{ doc.photo }}">{% endif %}
    <div class="g">
      <div class="f"><b>Visitor</b> {{ doc.visitor_name }}</div>
      <div class="f"><b>Company</b> {{ doc.company or '-' }}</div>
      <div class="f"><b>Host</b> {{ doc.host_person or '-' }}</div>
      <div class="f"><b>Section</b> {{ doc.plant_section or '-' }}</div>
      <div class="f"><b>Time In</b> {{ frappe.format(doc.time_in, {'fieldtype':'Datetime'}) }}</div>
      <div class="f"><b>Time Out</b> {{ frappe.format(doc.time_out, {'fieldtype':'Datetime'}) }}</div>
    </div>
    <div class="f" style="font-size:12px;margin-top:6px"><b>Purpose</b> {{ doc.purpose or '-' }}</div>
    <div style="text-align:center;margin-top:8px;clear:both">
      <img src="{{ qr_data_uri(qr_key('Visitor Log', doc.name)) }}" style="width:112px;height:112px">
      <div class="code">{{ doc.visitor_slip or doc.name }}</div>
    </div>
  </div>
</div>
"""

SAFETY_PERMIT = CSS + """
<div class="bk">
  <div class="hd"><span>SAFETY WORK PERMIT — {{ doc.permit_type }}</span><span>{{ doc.name }}</span></div>
  <div class="bd">
    <div class="g">
      <div class="f"><b>Section</b> {{ doc.plant_section }}</div>
      <div class="f"><b>Status</b> <span class="badge">{{ doc.permit_status }}</span></div>
      <div class="f"><b>Valid From</b> {{ frappe.format(doc.valid_from, {'fieldtype':'Datetime'}) }}</div>
      <div class="f"><b>Valid To</b> {{ frappe.format(doc.valid_to, {'fieldtype':'Datetime'}) }}</div>
      <div class="f"><b>Issuing Incharge</b> {{ doc.issuing_incharge or '-' }}</div>
      <div class="f"><b>Approving Incharge</b> {{ doc.approving_incharge or '-' }}</div>
    </div>
    <div class="f" style="font-size:12px;margin-top:6px"><b>Work</b> {{ doc.work_description or '-' }}</div>
    {% if doc.workers_involved %}
    <table class="t"><tr><th>Worker</th><th>Role</th></tr>
      {% for r in doc.workers_involved %}<tr><td>{{ r.worker_name }}</td><td>{{ r.worker_role }}</td></tr>{% endfor %}
    </table>{% endif %}
    <div style="font-size:12px;margin-top:8px">Closing Confirmation:
      <b>{{ 'YES' if doc.closing_confirmation else 'NO' }}</b></div>
    <div style="margin-top:8px">
      {% if doc.site_photo %}<img src="{{ doc.site_photo }}" style="width:120px;height:90px;object-fit:cover;border:1px solid #999;margin:3px">{% endif %}
      {% if doc.ppe_photo %}<img src="{{ doc.ppe_photo }}" style="width:120px;height:90px;object-fit:cover;border:1px solid #999;margin:3px">{% endif %}
      {% if doc.barricading_photo %}<img src="{{ doc.barricading_photo }}" style="width:120px;height:90px;object-fit:cover;border:1px solid #999;margin:3px">{% endif %}
    </div>
    <div style="text-align:center;margin-top:6px">
      <img src="{{ qr_data_uri(doc.name) }}" style="width:100px;height:100px">
      <div class="code">{{ doc.name }}</div>
    </div>
  </div>
</div>
"""

ELEC_PERMIT = CSS + """
<div class="bk">
  <div class="hd"><span>ELECTRICAL WORK PERMIT</span><span>{{ doc.name }}</span></div>
  <div class="bd">
    <div class="g">
      <div class="f"><b>Section/Equipment</b> {{ doc.plant_section }} / {{ doc.equipment or '-' }}</div>
      <div class="f"><b>Status</b> <span class="badge">{{ doc.permit_status }}</span></div>
      <div class="f"><b>LOTO Confirmed</b> {{ 'YES' if doc.loto_confirmed else 'NO' }}</div>
      <div class="f"><b>Closure Sign-off</b> {{ 'YES' if doc.closure_signoff else 'NO' }}</div>
      <div class="f"><b>Issuing Engineer</b> {{ doc.issuing_engineer or '-' }}</div>
      <div class="f"><b>Receiving Engineer</b> {{ doc.receiving_engineer or '-' }}</div>
    </div>
    <div class="f" style="font-size:12px;margin-top:6px"><b>Job</b> {{ doc.job_description }}</div>
    {% if doc.job_log %}
    <table class="t"><tr><th>Start</th><th>End</th><th>Handover Notes</th></tr>
      {% for r in doc.job_log %}<tr><td>{{ frappe.format(r.start_time, {'fieldtype':'Datetime'}) }}</td>
      <td>{{ frappe.format(r.end_time, {'fieldtype':'Datetime'}) }}</td><td>{{ r.handover_notes or '' }}</td></tr>{% endfor %}
    </table>{% endif %}
    <div style="text-align:center;margin-top:6px">
      <img src="{{ qr_data_uri(doc.name) }}" style="width:100px;height:100px">
      <div class="code">{{ doc.name }}</div>
    </div>
  </div>
</div>
"""

DAILY_PROGRESS = CSS + """
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

MATERIAL_REQUEST = CSS + """
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
    <div class="code">{{ doc.name }}</div>
  </div>
</div>
"""

FORMATS = [
    ("Staff ID Card", "Employee", "Benkas Core", STAFF),
    ("Labour ID Card", "Labour Master", "Benkas Core", LABOUR),
    ("Gate Entry Slip", "Gate Entry", "Manpower", GATE_ENTRY),
    ("Gate Pass Slip", "Gate Pass", "Site Safety Assets", GATE_PASS),
    ("Visitor Slip", "Visitor Log", "Site Safety Assets", VISITOR),
    ("Safety Work Permit Print", "Safety Work Permit", "Site Safety Assets", SAFETY_PERMIT),
    ("Electrical Work Permit Print", "Electrical Work Permit", "Site Safety Assets", ELEC_PERMIT),
    ("Daily Progress Report", "Daily Progress Log", "Work Schedule", DAILY_PROGRESS),
    ("Material Request Slip", "Material Request", "Material", MATERIAL_REQUEST),
]


def create():
    for name, dt, module, html in FORMATS:
        if not frappe.db.exists("DocType", dt):
            continue
        if frappe.db.exists("Print Format", name):
            # keep HTML in sync with code on every migrate
            pf = frappe.get_doc("Print Format", name)
            if pf.html != html:
                pf.html = html
                pf.save(ignore_permissions=True)
            continue
        frappe.get_doc({
            "doctype": "Print Format", "name": name, "doc_type": dt, "module": module,
            "standard": "Yes", "custom_format": 1, "print_format_type": "Jinja", "html": html,
        }).insert(ignore_permissions=True)
