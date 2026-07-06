frappe.pages['benkas-scan'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper, title: 'Gate Scan Station', single_column: true,
	});
	page.set_primary_action('Temp Pass', () => station.temp_pass_dialog(), 'add');
	page.set_secondary_action('Tools In', () => frappe.new_doc('Contractor Tools Register'));
	const station = new BenkasScanStation(page);
};

class BenkasScanStation {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
		this.recent = [];
		this.render();
		this.bind();
		this.load_sections();
		this.focus();
	}

	render() {
		this.$body.html(`
		<style>
			.bk-scan{max-width:820px;margin:0 auto}
			.bk-scan .scanbox{display:flex;gap:10px;margin:6px 0 14px}
			.bk-scan input.code{flex:1;font-size:22px;padding:12px 14px;border:2px solid #16324f;border-radius:8px}
			.bk-scan .big-btn{font-size:18px;font-weight:700;padding:12px 20px;border-radius:8px;border:0;cursor:pointer}
			.bk-scan .camscan{background:#16324f;color:#fff}
			.bk-scan .snap{background:#1a9e4b;color:#fff}
			.bk-scan .status{border-radius:12px;padding:20px;min-height:210px;display:flex;gap:18px;align-items:center}
			.bk-scan .status.idle{background:#f2f4f7;color:#667;justify-content:center;text-align:center}
			.bk-scan .status.ok{background:#e7f7ec;border:3px solid #1a9e4b}
			.bk-scan .status.err{background:#fdeaea;border:3px solid #d33}
			.bk-scan .status img.photo{width:140px;height:170px;object-fit:cover;border:3px solid #16324f;border-radius:8px}
			.bk-scan .status .name{font-size:30px;font-weight:800;color:#16324f;line-height:1.05}
			.bk-scan .status .sub{font-size:18px;color:#334}
			.bk-scan .status .meta{font-size:14px;color:#667}
			.bk-scan .status .action{margin-top:8px;font-size:26px;font-weight:800}
			.bk-scan .status.ok .action{color:#1a7d3c}.bk-scan .status.err .action{color:#c0271e}
			.bk-scan .status a.rec{display:inline-block;margin-top:6px;font-size:15px;font-weight:700;text-decoration:underline}
			.bk-scan .rowbtns{margin-top:10px;display:flex;gap:10px;flex-wrap:wrap}
			.bk-scan .in-panel{margin-top:14px;padding:14px;border:2px dashed #16324f;border-radius:10px;background:#fff}
			.bk-scan .in-panel .frappe-control{max-width:340px}
			.bk-scan .in-panel input{font-size:18px!important;height:auto!important;padding:10px!important}
			.bk-scan video{width:250px;border-radius:8px;background:#000}
			.bk-scan .recent{margin-top:18px}
			.bk-scan .recent h5{margin:0 0 6px}
			.bk-scan .recent table{width:100%;border-collapse:collapse;font-size:13px}
			.bk-scan .recent td{border-bottom:1px solid #eee;padding:5px 6px}
			.bk-scan .pill{padding:1px 8px;border-radius:10px;font-size:12px;font-weight:700}
			.bk-scan .pill.in{background:#e7f7ec;color:#1a7d3c}.bk-scan .pill.out{background:#eef;color:#3355aa}
			.bk-scan .pill.err{background:#fdeaea;color:#c0271e}.bk-scan .pill.act{background:#f4ecd9;color:#946}
			.bk-scan .muted{color:#889;font-size:13px}
		</style>
		<div class="bk-scan">
			<div class="scanbox">
				<input class="code" type="text" autocomplete="off" spellcheck="false"
					placeholder="Scan a card / slip QR here…  (USB scanner types automatically)">
				<button class="big-btn camscan">📷 Camera scan</button>
			</div>
			<div class="status idle" id="bk-status">
				<div><div class="action">Ready — scan a card or slip</div>
				<div class="muted">Temp Pass / Tools In are the buttons top-right.</div></div>
			</div>
			<div class="in-panel" id="bk-inpanel" style="display:none"></div>
			<div class="recent"><h5>Recent activity (this session)</h5>
				<table id="bk-recent"><tr><td class="muted">No scans yet.</td></tr></table></div>
		</div>`);
		this.$input = this.$body.find('input.code');
		this.$status = this.$body.find('#bk-status');
		this.$inpanel = this.$body.find('#bk-inpanel');
		this.$recent = this.$body.find('#bk-recent');
	}

	bind() {
		this.$input.on('keydown', (e) => {
			if (e.which === 13) {
				const v = this.$input.val().trim();
				this.$input.val('');
				if (v) this.do_scan(v);
			}
		});
		this.$input.on('blur', () => setTimeout(() => this.focus(), 150));
		this.$body.find('.camscan').on('click', () => this.camera_scan());
	}

	focus() { this.$input.trigger('focus'); }

	load_sections() {
		frappe.db.get_list('Plant Section', { filters: { is_active: 1 }, fields: ['name'], limit: 0 })
			.then(rows => { this.sections = (rows || []).map(r => r.name); });
	}

	do_scan(code) {
		this.close_in_panel();
		frappe.call({ method: 'benkas_erp.scan.scan', args: { code },
			callback: (r) => this.handle(code, r.message || {}) });
	}

	rec_link(res) {
		const map = { OUT: 'Gate Entry', IN_DONE: 'Gate Entry', TEMP_ISSUED: 'Gate Entry',
			GATE_PASS_OUT: 'Gate Pass', GATE_PASS_RETURN: 'Gate Pass',
			VISITOR_OUT: 'Visitor Log', TOOLS: 'Contractor Tools Register' };
		const dt = map[res.action];
		if (res.reference && dt) return `/app/${frappe.router.slug(dt)}/${res.reference}`;
		return null;
	}

	handle(code, res) {
		const p = res.person || {};
		const cls = res.ok ? 'ok' : 'err';
		const label = {
			IN: 'READY — LOG IN', OUT: '✓ OUT RECORDED', IN_DONE: '✓ IN RECORDED',
			TEMP_ISSUED: '✓ TEMP PASS ISSUED', GATE_PASS_OUT: '✓ GATE PASS — OUT',
			GATE_PASS_RETURN: '✓ RETURNED', VISITOR_OUT: '✓ VISITOR OUT',
			TOOLS: 'TOOLS REGISTER', ERROR: '✕ ' + (res.message || 'ERROR'),
		}[res.action] || (res.message || '');
		const link = this.rec_link(res);

		this.$status.attr('class', 'status ' + cls).html(`
			${p.photo ? `<img class="photo" src="${frappe.utils.escape_html(p.photo)}">` : ''}
			<div>
				${p.name ? `<div class="name">${frappe.utils.escape_html(p.name)}</div>` : ''}
				${p.sub ? `<div class="sub">${frappe.utils.escape_html(p.sub)}</div>` : ''}
				${p.meta ? `<div class="meta">${frappe.utils.escape_html(p.meta)}</div>` : ''}
				<div class="action">${frappe.utils.escape_html(label)}</div>
				${res.ok && res.action !== 'IN' ? `<div class="muted">${frappe.utils.escape_html(res.message || '')}</div>` : ''}
				${link ? `<a class="rec" href="${link}">Open ${frappe.utils.escape_html(res.reference)}</a>` : ''}
				<div class="rowbtns" id="bk-actbtns"></div>
			</div>`);

		const $btns = this.$status.find('#bk-actbtns');
		if (res.action === 'IN_DONE') this._print_btn($btns, 'Gate Entry', res.reference, 'Gate Entry Slip');
		if (res.action === 'TEMP_ISSUED') this._print_btn($btns, 'Gate Entry', res.reference, 'Temporary Gate Slip');
		if (res.action === 'TOOLS' && res.route)
			$btns.append($(`<button class="big-btn camscan">Open register</button>`).on('click', () => frappe.set_route(res.route.replace('/app/', ''))));

		this.push_recent(res, p);
		if (res.ok && res.action === 'IN') this.open_in_panel(code, res.prefill || {});
		else this.focus();
	}

	_print_btn($parent, dt, name, fmt) {
		$parent.append($(`<button class="big-btn snap">🖨 Print Slip</button>`).on('click', () => {
			const u = `/printview?doctype=${encodeURIComponent(dt)}&name=${encodeURIComponent(name)}`
				+ `&format=${encodeURIComponent(fmt)}&trigger_print=1&no_letterhead=1&_lang=en`;
			window.open(u, '_blank');
		}));
	}

	push_recent(res, p) {
		const pill = { IN_DONE: ['in', 'IN'], OUT: ['out', 'OUT'], TEMP_ISSUED: ['in', 'TEMP'],
			GATE_PASS_OUT: ['out', 'GP OUT'], GATE_PASS_RETURN: ['in', 'GP RET'],
			VISITOR_OUT: ['out', 'VIS OUT'], TOOLS: ['act', 'TOOLS'], ERROR: ['err', 'ERR'] }[res.action]
			|| ['act', res.action];
		if (res.action === 'IN') return; // not final yet
		this.recent.unshift({ t: frappe.datetime.now_time(), name: (p.name || '—'), pill });
		this.recent = this.recent.slice(0, 10);
		this.$recent.html(this.recent.map(r =>
			`<tr><td style="width:70px" class="muted">${r.t}</td>
			<td>${frappe.utils.escape_html(r.name)}</td>
			<td style="width:80px"><span class="pill ${r.pill[0]}">${r.pill[1]}</span></td></tr>`).join(''));
	}

	open_in_panel(code, prefill) {
		this.$inpanel.html(`<b>Confirm section &amp; capture photo:</b>
			<div id="bk-secwrap" style="margin:8px 0"></div>
			<div id="bk-invideo" style="margin:8px 0"></div>
			<button class="big-btn snap" id="bk-snap">📸 Snap &amp; Log IN</button>
			<button class="big-btn" id="bk-skip" style="background:#eee">Log IN without photo</button>`).show();
		this.pending = { code };
		this.section_control = frappe.ui.form.make_control({
			df: { fieldtype: 'Link', options: 'Plant Section', label: 'Plant Section',
				placeholder: 'Search section…', reqd: 1,
				get_query: () => ({ filters: { is_active: 1 } }) },
			parent: this.$inpanel.find('#bk-secwrap'), render_input: true,
		});
		this.section_control.set_value(prefill.plant_section || '');
		this.start_camera('#bk-invideo');
		this.$inpanel.find('#bk-snap').on('click', () => this.submit_in(true));
		this.$inpanel.find('#bk-skip').on('click', () => this.submit_in(false));
	}

	submit_in(with_photo) {
		const section = this.section_control ? this.section_control.get_value() : null;
		if (!section) { frappe.show_alert({ message: 'Pick a section', indicator: 'red' }); return; }
		let image = null;
		if (with_photo && this.video && this.video.videoWidth) {
			const c = document.createElement('canvas');
			c.width = this.video.videoWidth; c.height = this.video.videoHeight;
			c.getContext('2d').drawImage(this.video, 0, 0);
			image = c.toDataURL('image/jpeg', 0.7);
		}
		frappe.call({ method: 'benkas_erp.scan.create_gate_in',
			args: { code: this.pending.code, plant_section: section, image },
			callback: (r) => { this.close_in_panel(); this.handle(this.pending.code, r.message || {}); } });
	}

	temp_pass_dialog() {
		const d = new frappe.ui.Dialog({
			title: 'Temporary Gate Pass',
			fields: [
				{ fieldtype: 'Data', fieldname: 'name1', label: 'Person name (new/one-day worker)' },
				{ fieldtype: 'Link', fieldname: 'contractor', label: 'Contractor (if labour)', options: 'Contractor' },
				{ fieldtype: 'Column Break' },
				{ fieldtype: 'Link', fieldname: 'person', label: 'OR existing person (card lost)', options: 'Labour Master' },
				{ fieldtype: 'Section Break' },
				{ fieldtype: 'Link', fieldname: 'plant_section', label: 'Plant Section', options: 'Plant Section', reqd: 1,
					get_query: () => ({ filters: { is_active: 1 } }) },
			],
			primary_action_label: 'Issue &amp; Print',
			primary_action: (v) => {
				frappe.call({
					method: 'benkas_erp.scan.create_temp_pass',
					args: {
						name: v.name1, person: v.person, contractor: v.contractor,
						person_type: v.person ? 'Labour Master' : 'Labour Master',
						plant_section: v.plant_section,
					},
					callback: (r) => { d.hide(); this.handle('', r.message || {}); },
				});
			},
		});
		d.show();
	}

	close_in_panel() {
		this.stop_camera();
		this.$inpanel.hide().empty();
		this.section_control = null; this.pending = null;
	}

	start_camera(sel) {
		if (!navigator.mediaDevices) return;
		navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } }).then(stream => {
			this.stream = stream;
			this.video = document.createElement('video');
			this.video.autoplay = true; this.video.playsInline = true; this.video.srcObject = stream;
			$(sel).empty().append(this.video);
		}).catch(() => { $(sel).html('<span class="muted">Camera unavailable — use "Log IN without photo".</span>'); });
	}

	stop_camera() {
		if (this.stream) { this.stream.getTracks().forEach(t => t.stop()); this.stream = null; }
		this.video = null;
	}

	async camera_scan() {
		if (!('BarcodeDetector' in window)) {
			frappe.msgprint('No built-in QR scanner in this browser. Use the USB scanner, or Chrome/Edge.');
			return;
		}
		if (!navigator.mediaDevices) return;
		const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
		const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } }).catch(() => null);
		if (!stream) return;
		const video = document.createElement('video');
		video.autoplay = true; video.playsInline = true; video.srcObject = stream;
		this.$inpanel.empty().append(video).append('<div class="muted">Point at the QR…</div>').show();
		const stop = () => { stream.getTracks().forEach(t => t.stop()); this.$inpanel.hide().empty(); };
		const tick = async () => {
			if (!stream.active) return;
			try {
				const codes = await detector.detect(video);
				if (codes && codes.length) { stop(); this.do_scan(codes[0].rawValue.trim()); return; }
			} catch (e) { /* keep trying */ }
			requestAnimationFrame(tick);
		};
		video.onloadedmetadata = () => requestAnimationFrame(tick);
		setTimeout(() => { if (stream.active) stop(); }, 20000);
	}
}
