frappe.pages['benkas-scan'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Gate Scan Station',
		single_column: true,
	});
	new BenkasScanStation(page);
};

class BenkasScanStation {
	constructor(page) {
		this.page = page;
		this.$body = $(page.body);
		this.pending = null; // pending IN scan awaiting photo
		this.render();
		this.bind();
		this.load_sections();
		this.focus();
	}

	render() {
		this.$body.html(`
		<style>
			.bk-scan{max-width:760px;margin:0 auto}
			.bk-scan .scanbox{display:flex;gap:10px;margin:8px 0 16px}
			.bk-scan input.code{flex:1;font-size:22px;padding:12px 14px;border:2px solid #16324f;border-radius:8px}
			.bk-scan .status{border-radius:12px;padding:22px;text-align:center;min-height:230px;
				display:flex;flex-direction:column;align-items:center;justify-content:center;transition:.15s}
			.bk-scan .status.idle{background:#f2f4f7;color:#667}
			.bk-scan .status.ok{background:#e7f7ec;border:3px solid #1a9e4b}
			.bk-scan .status.err{background:#fdeaea;border:3px solid #d33}
			.bk-scan .status img.photo{width:150px;height:180px;object-fit:cover;border:3px solid #16324f;border-radius:8px;margin-bottom:10px}
			.bk-scan .status .name{font-size:30px;font-weight:800;color:#16324f}
			.bk-scan .status .sub{font-size:18px;color:#334}
			.bk-scan .status .meta{font-size:14px;color:#667;margin-top:2px}
			.bk-scan .status .action{margin-top:12px;font-size:26px;font-weight:800;letter-spacing:1px}
			.bk-scan .status.ok .action{color:#1a7d3c}
			.bk-scan .status.err .action{color:#c0271e}
			.bk-scan .in-panel{margin-top:14px;padding:14px;border:2px dashed #16324f;border-radius:10px;background:#fff}
			.bk-scan .in-panel select{font-size:18px;padding:8px;border-radius:6px;min-width:240px}
			.bk-scan video,.bk-scan canvas{width:260px;border-radius:8px;background:#000}
			.bk-scan .big-btn{font-size:20px;font-weight:700;padding:12px 22px;border-radius:8px;border:0;cursor:pointer}
			.bk-scan .snap{background:#1a9e4b;color:#fff}
			.bk-scan .camscan{background:#16324f;color:#fff}
			.bk-scan .muted{color:#889;font-size:13px}
		</style>
		<div class="bk-scan">
			<div class="scanbox">
				<input class="code" type="text" autocomplete="off" spellcheck="false"
					placeholder="Scan a QR / ID card here…  (USB scanner types automatically)">
				<button class="big-btn camscan">📷 Camera scan</button>
			</div>
			<div class="status idle" id="bk-status">
				<div class="action">Ready — scan a card or slip</div>
				<div class="muted">USB scanner: just scan. No mouse, no typing.</div>
			</div>
			<div class="in-panel" id="bk-inpanel" style="display:none"></div>
			<div id="bk-cam" style="display:none;text-align:center;margin-top:12px"></div>
		</div>`);
		this.$input = this.$body.find('input.code');
		this.$status = this.$body.find('#bk-status');
		this.$inpanel = this.$body.find('#bk-inpanel');
		this.$cam = this.$body.find('#bk-cam');
	}

	bind() {
		this.$input.on('keydown', (e) => {
			if (e.which === 13) {
				const v = this.$input.val().trim();
				this.$input.val('');
				if (v) this.do_scan(v);
			}
		});
		// keep the input focused for the HID scanner
		this.$input.on('blur', () => setTimeout(() => this.focus(), 150));
		this.$body.find('.camscan').on('click', () => this.camera_scan());
	}

	focus() { this.$input.trigger('focus'); }

	load_sections() {
		frappe.db.get_list('Plant Section', { filters: { is_active: 1 }, fields: ['name', 'section_name'], limit: 0 })
			.then(rows => { this.sections = rows || []; });
	}

	do_scan(code) {
		this.close_in_panel();
		frappe.call({
			method: 'benkas_erp.scan.scan',
			args: { code },
			callback: (r) => this.handle(code, r.message || {}),
		});
	}

	handle(code, res) {
		const p = res.person || {};
		const cls = res.ok ? 'ok' : 'err';
		const label = {
			IN: 'READY — LOG IN', OUT: '✓ OUT RECORDED', IN_DONE: '✓ IN LOGGED',
			GATE_PASS_OUT: '✓ GATE PASS — OUT', GATE_PASS_RETURN: '✓ RETURNED',
			VISITOR_OUT: '✓ VISITOR OUT', ERROR: '✕ ' + (res.message || 'ERROR'),
		}[res.action] || (res.message || '');

		this.$status.attr('class', 'status ' + cls).html(`
			${p.photo ? `<img class="photo" src="${frappe.utils.escape_html(p.photo)}">` : ''}
			${p.name ? `<div class="name">${frappe.utils.escape_html(p.name)}</div>` : ''}
			${p.sub ? `<div class="sub">${frappe.utils.escape_html(p.sub)}</div>` : ''}
			${p.meta ? `<div class="meta">${frappe.utils.escape_html(p.meta)}</div>` : ''}
			<div class="action">${frappe.utils.escape_html(label)}</div>
			${res.ok && res.action !== 'IN' ? `<div class="muted">${frappe.utils.escape_html(res.message || '')}</div>` : ''}`);

		if (res.ok && res.action === 'IN') {
			this.open_in_panel(code, res.prefill || {}, p);
		} else {
			this.focus();
		}
	}

	open_in_panel(code, prefill, person) {
		const opts = (this.sections || []).map(s =>
			`<option value="${s.name}" ${s.name === prefill.plant_section ? 'selected' : ''}>${frappe.utils.escape_html(s.section_name)}</option>`).join('');
		this.$inpanel.html(`
			<b>Confirm section &amp; capture live photo:</b><br>
			<div style="margin:8px 0">Plant Section:
				<select id="bk-sec">${opts}</select></div>
			<div id="bk-invideo" style="margin:8px 0"></div>
			<button class="big-btn snap" id="bk-snap">📸 Snap &amp; Log IN</button>
			<button class="big-btn" id="bk-skip" style="background:#eee">Log IN without photo</button>
		`).show();
		this.pending = { code, prefill };
		this.start_camera('#bk-invideo');
		this.$inpanel.find('#bk-snap').on('click', () => this.submit_in(true));
		this.$inpanel.find('#bk-skip').on('click', () => this.submit_in(false));
	}

	submit_in(with_photo) {
		const section = this.$inpanel.find('#bk-sec').val();
		let image = null;
		if (with_photo && this.video && this.video.videoWidth) {
			const c = document.createElement('canvas');
			c.width = this.video.videoWidth; c.height = this.video.videoHeight;
			c.getContext('2d').drawImage(this.video, 0, 0);
			image = c.toDataURL('image/jpeg', 0.7);
		}
		frappe.call({
			method: 'benkas_erp.scan.create_gate_in',
			args: { code: this.pending.code, plant_section: section, image },
			callback: (r) => { this.close_in_panel(); this.handle(this.pending.code, r.message || {}); },
		});
	}

	close_in_panel() {
		this.stop_camera();
		this.$inpanel.hide().empty();
		this.$cam.hide().empty();
		this.pending = null;
	}

	// ---- camera: live photo for IN ----
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

	// ---- camera-based QR scanning (native BarcodeDetector, no external lib) ----
	async camera_scan() {
		if (!('BarcodeDetector' in window)) {
			frappe.msgprint('This browser has no built-in QR scanner. Use the USB scanner, or Chrome/Edge for camera scan.');
			return;
		}
		if (!navigator.mediaDevices) return;
		const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
		const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } }).catch(() => null);
		if (!stream) return;
		const video = document.createElement('video');
		video.autoplay = true; video.playsInline = true; video.srcObject = stream;
		this.$cam.empty().append(video).append('<div class="muted">Point the camera at the QR…</div>').show();
		const stop = () => { stream.getTracks().forEach(t => t.stop()); this.$cam.hide().empty(); };
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
