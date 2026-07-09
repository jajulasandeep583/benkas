frappe.pages['section-task-planner'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper, title: 'Section Task Planner', single_column: true,
	});
	new SectionTaskPlanner(page);
};

class SectionTaskPlanner {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
		this.section = null;
		this.rows = [];
		this.render();
		this.add_section_field();
	}

	render() {
		this.$body.html(`
		<style>
			.stp{max-width:1000px;margin:0 auto}
			.stp .bar{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;margin-bottom:14px}
			.stp .hint{color:#667;font-size:13px;margin:2px 0 14px}
			.stp table{width:100%;border-collapse:collapse;background:var(--card-bg,#fff)}
			.stp th,.stp td{border:1px solid var(--border-color,#e2e6ea);padding:7px 9px;font-size:13px;text-align:left;vertical-align:middle}
			.stp th{background:#16324f;color:#fff;font-weight:600}
			.stp td input{border:1px solid #cdd5dd;border-radius:5px;padding:5px 7px;font-size:13px;width:100%}
			.stp td.subj{font-weight:600;color:#16324f;min-width:220px}
			.stp .chip{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11px;font-weight:700}
			.stp .chip.Completed{background:#e7f7ec;color:#1a7d3c}
			.stp .chip.Delayed{background:#fdeaea;color:#c0271e}
			.stp .chip.In.Progress,.stp .chip.InProgress{background:#fff4e0;color:#a86400}
			.stp .chip.Not.Started,.stp .chip.NotStarted{background:#eef1f4;color:#556}
			.stp .actions{margin-top:16px;display:flex;gap:10px}
			.stp .empty{color:#889;padding:40px;text-align:center}
			.stp .wsum{font-weight:700}
		</style>
		<div class="stp">
			<div class="bar">
				<div class="section-slot"></div>
				<div class="start-slot"></div>
				<button class="btn btn-default btn-sm btn-refill">Re-fill dates from start</button>
			</div>
			<div class="hint">Set the <b>tentative start &amp; end date</b> and <b>weight</b> for each activity in
				the chosen section. These pre-fill from the section start date but are yours to adjust.
				A task whose end date has passed while below 100% shows as <b>Delayed</b>.</div>
			<div class="grid"><div class="empty">Pick a section above to plan its tasks.</div></div>
			<div class="actions" style="display:none">
				<button class="btn btn-primary btn-save">Save Plan</button>
				<span class="save-status" style="align-self:center;color:#1a7d3c"></span>
			</div>
		</div>`);
		this.$grid = this.$body.find('.grid');
		this.$actions = this.$body.find('.actions');
		this.$body.find('.btn-save').on('click', () => this.save());
		this.$body.find('.btn-refill').on('click', () => this.refill_dates());
	}

	add_section_field() {
		this.section_field = frappe.ui.form.make_control({
			df: {fieldtype: 'Link', options: 'Plant Section', label: 'Section', reqd: 1,
				change: () => { this.section = this.section_field.get_value(); this.load(); }},
			parent: this.$body.find('.section-slot'), render_input: true,
		});
		this.section_field.refresh();
		this.start_field = frappe.ui.form.make_control({
			df: {fieldtype: 'Date', label: 'Section Start Date'},
			parent: this.$body.find('.start-slot'), render_input: true,
		});
		this.start_field.refresh();
	}

	load() {
		if (!this.section) return;
		frappe.call('benkas_erp.section360.get_section_tasks', {section: this.section})
			.then(r => {
				this.rows = (r.message || {}).tasks || [];
				if (r.message && r.message.section_start_date)
					this.start_field.set_value(r.message.section_start_date);
				this.draw();
			});
	}

	draw() {
		if (!this.rows.length) {
			this.$grid.html('<div class="empty">This section has no planned sub-tasks yet. Run a migrate to generate them.</div>');
			this.$actions.hide();
			return;
		}
		let body = this.rows.map((t, i) => `
			<tr data-i="${i}">
				<td class="subj">${frappe.utils.escape_html(t.subject)}</td>
				<td><input type="date" class="f-start" value="${(t.exp_start_date || '').slice(0, 10)}"></td>
				<td><input type="date" class="f-end" value="${(t.exp_end_date || '').slice(0, 10)}"></td>
				<td style="width:90px"><input type="number" step="0.01" min="0" max="1" class="f-weight" value="${t.task_weight != null ? t.task_weight : ''}"></td>
				<td style="width:70px;text-align:right">${Math.round(t.progress || 0)}%</td>
				<td style="width:110px"><span class="chip ${(t.chip||'').replace(/ /g,'')}">${t.chip || ''}</span></td>
			</tr>`).join('');
		this.$grid.html(`
			<table>
				<thead><tr><th>Activity</th><th>Tentative Start</th><th>Tentative End</th>
					<th>Weight</th><th>Progress</th><th>Status</th></tr></thead>
				<tbody>${body}</tbody>
				<tfoot><tr><td colspan="3" style="text-align:right">Total weight</td>
					<td class="wsum"></td><td colspan="2"></td></tr></tfoot>
			</table>`);
		this.$grid.find('.f-weight').on('input', () => this.update_sum());
		this.update_sum();
		this.$actions.show();
	}

	update_sum() {
		let s = 0;
		this.$grid.find('.f-weight').each((_, el) => { s += parseFloat(el.value) || 0; });
		const $w = this.$grid.find('.wsum');
		$w.text(s.toFixed(2));
		$w.css('color', Math.abs(s - 1) < 0.001 ? '#1a7d3c' : '#c0271e');
	}

	refill_dates() {
		const start = this.start_field.get_value();
		if (!start) { frappe.msgprint('Set a Section Start Date first.'); return; }
		let cursor = frappe.datetime.str_to_obj(start);
		this.$grid.find('tbody tr').each((_, tr) => {
			const $tr = $(tr);
			const w = parseFloat($tr.find('.f-weight').val()) || 0.05;
			const dur = Math.max(Math.round(w * 140), 3); // heuristic when re-filling
			const s = frappe.datetime.obj_to_str(cursor).slice(0, 10);
			const endObj = frappe.datetime.add_days(cursor, dur - 1);
			const e = frappe.datetime.obj_to_str(endObj).slice(0, 10);
			$tr.find('.f-start').val(s);
			$tr.find('.f-end').val(e);
			cursor = frappe.datetime.add_days(endObj, 1);
		});
	}

	save() {
		const rows = [];
		this.$grid.find('tbody tr').each((_, tr) => {
			const $tr = $(tr);
			const i = $tr.data('i');
			rows.push({
				name: this.rows[i].name,
				exp_start_date: $tr.find('.f-start').val() || null,
				exp_end_date: $tr.find('.f-end').val() || null,
				task_weight: parseFloat($tr.find('.f-weight').val()) || 0,
			});
		});
		frappe.call('benkas_erp.section360.save_section_tasks', {
			section: this.section, rows: JSON.stringify(rows),
			section_start_date: this.start_field.get_value() || null,
		}).then(r => {
			const n = (r.message || {}).updated || 0;
			this.$body.find('.save-status').text(`Saved ${n} task${n === 1 ? '' : 's'}.`);
			setTimeout(() => this.$body.find('.save-status').text(''), 4000);
			this.load();
		});
	}
}
