frappe.pages['section-360'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper, title: 'Section 360', single_column: true,
	});
	new Section360(page);
};

class Section360 {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
		this.section = frappe.get_route()[1] || null;
		this.render();
		this.add_section_field();
		if (this.section) { this.section_field.set_value(this.section); }
	}

	render() {
		this.$body.html(`
		<style>
			.s360{max-width:1080px;margin:0 auto}
			.s360 .bar{margin-bottom:16px;max-width:360px}
			.s360 .hdr{background:linear-gradient(120deg,#16324f,#1f4e79);color:#fff;border-radius:14px;padding:20px 22px;margin-bottom:18px}
			.s360 .hdr h2{margin:0 0 4px;font-size:24px;font-weight:800}
			.s360 .hdr .who{opacity:.85;font-size:14px}
			.s360 .hdr .bars{display:flex;gap:26px;margin-top:14px;flex-wrap:wrap}
			.s360 .hdr .stat .n{font-size:30px;font-weight:800;line-height:1}
			.s360 .hdr .stat .l{font-size:12px;opacity:.8;text-transform:uppercase;letter-spacing:.5px}
			.s360 .pill{display:inline-block;padding:3px 12px;border-radius:12px;font-size:13px;font-weight:800}
			.s360 .pill.OnTrack{background:#e7f7ec;color:#1a7d3c}
			.s360 .pill.Attention{background:#fdeaea;color:#c0271e}
			.s360 .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
			@media(max-width:800px){.s360 .grid2{grid-template-columns:1fr}}
			.s360 .card{background:var(--card-bg,#fff);border:1px solid var(--border-color,#e4e8ec);border-radius:12px;padding:16px;margin-bottom:16px}
			.s360 .card h3{margin:0 0 12px;font-size:15px;color:#16324f;font-weight:800;display:flex;justify-content:space-between}
			.s360 table{width:100%;border-collapse:collapse}
			.s360 th,.s360 td{padding:6px 8px;font-size:13px;border-bottom:1px solid #eef1f4;text-align:left;vertical-align:top}
			.s360 th{color:#667;font-weight:600;font-size:11px;text-transform:uppercase}
			.s360 td.r,.s360 th.r{text-align:right}
			.s360 .chip{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11px;font-weight:700}
			.s360 .chip.Green{background:#e7f7ec;color:#1a7d3c}
			.s360 .chip.Blue{background:#e7eefc;color:#2456c0}
			.s360 .chip.Red{background:#fdeaea;color:#c0271e}
			.s360 .chip.Orange{background:#fff4e0;color:#a86400}
			.s360 .chip.Grey{background:#eef1f4;color:#556}
			.s360 .pct-in{width:64px;padding:3px 6px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;text-align:right}
			.s360 .mini{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px}
			.s360 .mini .b{background:#f4f6f9;border-radius:9px;padding:9px 14px;min-width:96px}
			.s360 .mini .b .n{font-size:20px;font-weight:800;color:#16324f}
			.s360 .mini .b .l{font-size:11px;color:#778}
			.s360 .thumb{width:44px;height:44px;object-fit:cover;border-radius:6px;border:1px solid #dde;margin:1px}
			.s360 .desc{color:#334;font-size:12px}
			.s360 .empty{color:#8a94a0;text-align:center;padding:60px}
			.s360 .kv{color:#556;font-size:12px}
		</style>
		<div class="s360">
			<div class="bar"><div class="section-slot"></div></div>
			<div class="content"><div class="empty">Pick a plant section to open its 360° view.</div></div>
		</div>`);
		this.$content = this.$body.find('.content');
	}

	add_section_field() {
		this.section_field = frappe.ui.form.make_control({
			df: {fieldtype: 'Link', options: 'Plant Section', label: 'Section', reqd: 1,
				change: () => { this.section = this.section_field.get_value(); this.load(); }},
			parent: this.$body.find('.section-slot'), render_input: true,
		});
		this.section_field.refresh();
	}

	load() {
		if (!this.section) return;
		frappe.set_route('section-360', this.section);
		this.$content.html('<div class="empty">Loading…</div>');
		frappe.call('benkas_erp.section360.get_section_360', {section: this.section})
			.then(r => this.draw(r.message)).catch(() => this.$content.html('<div class="empty">Could not load this section.</div>'));
	}

	esc(s) { return frappe.utils.escape_html(s == null ? '' : String(s)); }

	draw(d) {
		if (!d) { this.$content.html('<div class="empty">No data.</div>'); return; }
		const h = d.header;
		const tasks = (d.tasks || []).map(t => {
			const photos = (t.photos || []).map(p =>
				`<img class="thumb" src="${this.esc(p.image)}" title="${this.esc(p.caption || p.date)}">`).join('');
			return `
			<tr>
				<td><b>${this.esc(t.subject)}</b></td>
				<td class="r"><input type="number" min="0" max="100" class="pct-in" value="${Math.round(t.percent || 0)}" data-task="${this.esc(t.name)}"></td>
				<td><span class="chip ${this.esc(t.color || 'Grey')}">${this.esc(t.latest_status)}</span></td>
				<td><div class="desc">${this.esc(t.last_description) || '<span class="kv">—</span>'}</div>
					${t.last_date ? `<div class="kv">${t.last_date}</div>` : ''}</td>
				<td>${photos || '<span class="kv">—</span>'}</td>
			</tr>`; }).join('');
		const mp = d.manpower, mat = d.material, act = d.activity;
		const cat = (mp.by_category || []).map(x => `<tr><td>${this.esc(x.k)}</td><td class="r">${x.v}</td></tr>`).join('') || '<tr><td colspan="2" class="kv">No data</td></tr>';
		const con = (mp.by_contractor || []).map(x => `<tr><td>${this.esc(x.k)}</td><td class="r">${x.v}</td></tr>`).join('') || '<tr><td colspan="2" class="kv">No data</td></tr>';
		const items = (mat.top_items || []).map(x => `<tr><td>${this.esc(x.item)}</td><td class="r">${x.qty}</td><td class="r">${format_currency(x.value)}</td></tr>`).join('') || '<tr><td colspan="3" class="kv">No issues logged</td></tr>';
		const mrs = (mat.open_requests || []).map(x => `<tr><td><a href="/app/material-request/${encodeURIComponent(x.name)}">${this.esc(x.name)}</a></td><td>${this.esc(x.benkas_status)}</td><td class="kv">${x.transaction_date||''}</td></tr>`).join('') || '<tr><td colspan="3" class="kv">None open</td></tr>';
		const logs = (act.logs || []).map(l => `
			<tr>
				<td class="kv" style="white-space:nowrap">${l.date}</td>
				<td>${l.photo ? `<img class="thumb" src="${this.esc(l.photo)}">` : ''}</td>
				<td>${l.status ? `<span class="kv">${this.esc(l.status)}</span> ` : ''}${this.esc(l.text)}</td>
				<td class="r">${l.pct != null ? Math.round(l.pct) + '%' : ''}</td>
			</tr>`).join('') || '<tr><td colspan="4" class="kv">No progress logs yet</td></tr>';

		this.$content.html(`
			<div class="hdr">
				<h2>${this.esc(h.section_name || h.section)}</h2>
				<div class="who">Section Incharge: <b>${this.esc(h.incharge || '—')}</b>
					${h.start_date ? ' · Start ' + h.start_date : ''}</div>
				<div class="bars">
					<div class="stat"><div class="n">${Math.round(h.percent_complete)}%</div><div class="l">Complete</div></div>
					<div class="stat"><div class="n">${h.done}/${h.total_tasks}</div><div class="l">Tasks Done</div></div>
					<div class="stat"><div class="n">${h.stopped}</div><div class="l">Stopped</div></div>
					<div class="stat"><div class="n"><span class="pill ${h.status.replace(/ /g,'')}">${h.status}</span></div><div class="l">Status</div></div>
				</div>
			</div>

			<div class="card">
				<h3>Task Checklist <a class="kv" href="/app/section-task-planner">plan dates ›</a></h3>
				<table><thead><tr><th>Task</th><th class="r">% Complete</th><th>Latest Status</th><th>Last Update</th><th>Photos</th></tr></thead>
				<tbody>${tasks || '<tr><td colspan="5" class="kv">No sub-tasks</td></tr>'}</tbody></table>
			</div>

			<div class="grid2">
				<div class="card">
					<h3>Manpower</h3>
					<div class="mini">
						<div class="b"><div class="n">${mp.today}</div><div class="l">On site today</div></div>
						<div class="b"><div class="n">${mp.person_days_week}</div><div class="l">Person-days (7d)</div></div>
						<div class="b"><div class="n">${mp.person_days_total}</div><div class="l">Person-days total</div></div>
					</div>
					<table><thead><tr><th>By Category</th><th class="r">P-days</th></tr></thead><tbody>${cat}</tbody></table>
					<table style="margin-top:8px"><thead><tr><th>By Contractor</th><th class="r">P-days</th></tr></thead><tbody>${con}</tbody></table>
				</div>
				<div class="card">
					<h3>Material</h3>
					<div class="mini">
						<div class="b"><div class="n">${format_currency(mat.total_value)}</div><div class="l">Consumed value</div></div>
						<div class="b"><div class="n">${(mat.open_requests||[]).length}</div><div class="l">Open requests</div></div>
					</div>
					<table><thead><tr><th>Top Items Issued</th><th class="r">Qty</th><th class="r">Value</th></tr></thead><tbody>${items}</tbody></table>
					<table style="margin-top:8px"><thead><tr><th>Open Requests</th><th>Status</th><th class="r">Date</th></tr></thead><tbody>${mrs}</tbody></table>
				</div>
			</div>

			<div class="card">
				<h3>Recent Activity
					<span class="kv">${act.visitors} visitor log(s) · ${act.open_violations} open safety issue(s)</span></h3>
				<table><thead><tr><th>Date</th><th>Photo</th><th>Work Done / Note</th><th class="r">%</th></tr></thead><tbody>${logs}</tbody></table>
			</div>`);

		this.$content.find('.pct-in').on('change', e => {
			const $in = $(e.currentTarget);
			const task = $in.data('task');
			let val = parseFloat($in.val());
			if (isNaN(val)) return;
			val = Math.max(0, Math.min(100, val));
			$in.val(Math.round(val));
			frappe.call('benkas_erp.section360.set_task_percent', {task, percent: val}).then(() => {
				frappe.show_alert({message: 'Progress saved', indicator: 'green'});
				this.load();
			});
		});
	}
}
