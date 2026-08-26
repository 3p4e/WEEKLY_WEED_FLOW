/* analytics-view.js — cross-week trends for managers and executives.
   Data: GET /reports/analytics (weekly Fri→Thu buckets; deliberately
   hour-free — counts of tasks and logged sessions, never durations).

   Charts are inline SVG/HTML, CSP-clean, themed via --ch-a/--ch-b chart
   tokens (validated pair per theme — see app.css). Two-series identity is
   carried by the legend + direct hover titles, never color alone.

   Same full-page-view pattern as facility/approvals; guard = every role
   above base USER (mirrors the endpoint's 403). */

(function () {
  GF.WWF._ana = { data: null, loading: false, error: null, weeks: 8 };
  // Yield-domain band (harvest lots). Its own store + loader: the task-domain
  // analytics come from /reports/analytics (weekly buckets), the yield band from
  // the per-lot harvest register (GET /cultivation/yield's sibling
  // /cultivation/harvests), so the two load and fail independently.
  GF.WWF._anaY = { data: null, loading: false, error: null };

  GF.WWF.loadAnalytics = async () => {
    const st = GF.WWF._ana;
    st.loading = true; st.error = null;
    const my = (st.lseq = (st.lseq || 0) + 1);
    try {
      const data = await GF.API.analytics(st.weeks);
      if (my !== st.lseq) return;
      st.data = data;
    } catch (e) {
      if (my !== st.lseq) return;
      st.error = e.message;
    }
    if (my !== st.lseq) return;
    st.loading = false;
    if (GF.state.view === 'analytics') GF.render.all();
  };

  // Real per-lot harvest rows — every field below is read verbatim from
  // /cultivation/harvests (backend/app/api/harvest.py `list_harvests` /
  // `_harvest_out`). No metric here is synthesised; anything the register does
  // not carry (wattage → g/W, cost → cost/g, graded A/B/C quality) is omitted,
  // not invented.
  GF.WWF.loadAnaYield = async () => {
    const yst = GF.WWF._anaY;
    yst.loading = true; yst.error = null;
    const my = (yst.lseq = (yst.lseq || 0) + 1);
    try {
      const data = await GF.API.harvests();
      if (my !== yst.lseq) return;
      yst.data = data;
    } catch (e) {
      if (my !== yst.lseq) return;
      yst.error = e.message;
    }
    if (my !== yst.lseq) return;
    yst.loading = false;
    if (GF.state.view === 'analytics') GF.render.all();
  };

  GF.WWF.anaRange = (n) => {
    GF.WWF._ana.weeks = n;
    GF.WWF._ana.data = null;
    GF.WWF.loadAnalytics();
    GF.render.all();
  };

  const wkLbl = (iso) => {
    const d = new Date(iso + 'T00:00:00');
    return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}`;
  };

  // Bar with a 4px-rounded data end and a square baseline (mark spec).
  const barPath = (x, y, w, h, r = 4) => {
    if (h <= r) return `M${x} ${y + h}h${w}v${-h}h${-w}Z`;
    return `M${x} ${y + h}v${-(h - r)}q0 ${-r} ${r} ${-r}h${w - 2 * r}q${r} 0 ${r} ${r}v${h - r}Z`;
  };

  const nice = (m) => { // clean y-axis max
    if (m <= 5) return 5;
    const pow = Math.pow(10, Math.floor(Math.log10(m)));
    for (const k of [1, 2, 5, 10]) if (k * pow >= m) return k * pow;
    return 10 * pow;
  };

  /* Chart A — created vs completed per week (grouped bars, 2 series). */
  const chartFlow = (weeks) => {
    const W = 560, H = 180, padL = 30, padB = 20, padT = 12;
    const n = weeks.length;
    const maxV = nice(Math.max(1, ...weeks.map((w) => Math.max(w.created, w.completed))));
    const slot = (W - padL) / n;
    const bw = Math.min(14, (slot - 8) / 2); // ≤24px, air in the band
    const y = (v) => padT + (H - padB - padT) * (1 - v / maxV);
    const grid = [0, 0.5, 1].map((f) => {
      const gy = y(maxV * f);
      return `<line x1="${padL}" y1="${gy}" x2="${W}" y2="${gy}" class="ana-grid"/>
        <text x="${padL - 5}" y="${gy + 3}" class="ana-tick" text-anchor="end">${Math.round(maxV * f)}</text>`;
    }).join('');
    const bars = weeks.map((w, i) => {
      const x0 = padL + i * slot + (slot - 2 * bw - 2) / 2;
      const lbl = (n <= 8 || i % 2 === (n - 1) % 2)
        ? `<text x="${x0 + bw + 1}" y="${H - 6}" class="ana-tick" text-anchor="middle">${wkLbl(w.week_start)}</text>` : '';
      const cap = i === n - 1 && w.created > 0
        ? `<text x="${x0 + bw / 2}" y="${y(w.created) - 4}" class="ana-cap" text-anchor="middle">${w.created}</text>` : '';
      const cap2 = i === n - 1 && w.completed > 0
        ? `<text x="${x0 + bw + 2 + bw / 2}" y="${y(w.completed) - 4}" class="ana-cap" text-anchor="middle">${w.completed}</text>` : '';
      return `<g><title>${wkLbl(w.week_start)} · ${AL('created', 'креирани')} ${w.created} · ${AL('completed', 'завршени')} ${w.completed}</title>
        <path d="${barPath(x0, y(w.created), bw, (H - padB) - y(w.created))}" fill="var(--ch-a)"/>
        <path d="${barPath(x0 + bw + 2, y(w.completed), bw, (H - padB) - y(w.completed))}" fill="var(--ch-b)"/>
        ${cap}${cap2}${lbl}</g>`;
    }).join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${AL('Created vs completed per week', 'Креирани наспроти завршени по недела')}">${grid}${bars}</svg>
      <div class="ana-legend">
        <span><i style="background:var(--ch-a)"></i>${AL('Created', 'Креирани')}</span>
        <span><i style="background:var(--ch-b)"></i>${AL('Completed', 'Завршени')}</span>
      </div>`;
  };

  /* Chart B — on-time completion % per week (single line, fixed 0–100). */
  const chartOnTime = (weeks) => {
    const W = 560, H = 140, padL = 34, padB = 20, padT = 10;
    const n = weeks.length;
    const slot = (W - padL) / n;
    const y = (v) => padT + (H - padB - padT) * (1 - v / 100);
    const pts = weeks.map((w, i) => w.completed > 0
      ? { x: padL + i * slot + slot / 2, y: y(Math.round(100 * w.on_time / w.completed)), v: Math.round(100 * w.on_time / w.completed), w } : null);
    const line = pts.filter(Boolean);
    const grid = [0, 50, 100].map((v) =>
      `<line x1="${padL}" y1="${y(v)}" x2="${W}" y2="${y(v)}" class="ana-grid"/>
       <text x="${padL - 5}" y="${y(v) + 3}" class="ana-tick" text-anchor="end">${v}%</text>`).join('');
    if (!line.length) return `<svg viewBox="0 0 ${W} ${H}">${grid}</svg>
      <div class="ana-note">${AL('No completions in this range yet.', 'Сè уште нема завршувања во овој опсег.')}</div>`;
    const path = line.map((p, i) => `${i ? 'L' : 'M'}${p.x} ${p.y}`).join('');
    const area = `M${line[0].x} ${H - padB}${line.map((p) => `L${p.x} ${p.y}`).join('')}L${line[line.length - 1].x} ${H - padB}Z`;
    const last = line[line.length - 1];
    const dots = line.map((p) =>
      `<circle cx="${p.x}" cy="${p.y}" r="4" fill="var(--ch-b)" stroke="var(--surface)" stroke-width="2">
         <title>${wkLbl(p.w.week_start)} · ${p.v}% (${p.w.on_time}/${p.w.completed})</title></circle>`).join('');
    const labels = weeks.map((w, i) => (n <= 8 || i % 2 === (n - 1) % 2)
      ? `<text x="${padL + i * slot + slot / 2}" y="${H - 6}" class="ana-tick" text-anchor="middle">${wkLbl(w.week_start)}</text>` : '').join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${AL('On-time completion rate', 'Стапка на навремено завршување')}">${grid}
      <path d="${area}" fill="var(--ch-b)" opacity="0.1"/>
      <path d="${path}" fill="none" stroke="var(--ch-b)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
      ${dots}<text x="${last.x + 8}" y="${last.y + 3}" class="ana-cap">${last.v}%</text>${labels}</svg>`;
  };

  /* Horizontal HTML bar (dept / type rows). */
  const hbar = (frac) =>
    `<div class="ana-hb"><div class="ana-hb-f" style="width:${Math.max(2, Math.round(100 * frac))}%"></div></div>`;

  const deptName = (d) => (GF.state.lang === 'mk' && d.name_mk) ? d.name_mk : d.name;

  /* ── Yield-domain band ──────────────────────────────────────────────────
     Sourced ENTIRELY from GET /cultivation/harvests (per dried lot). Fields
     used, all real: dry_flower_g, dry_trim_g, dry_waste_g, dry_total_g,
     wet_weight_g, plants_harvested, batch_code, cultivar_code, room_name,
     dried_on/harvested_on, status. */

  const kg = (g) => (g / 1000).toFixed(g >= 100000 ? 0 : 1); // grams → kg string

  // Monday (ISO week start) of an ISO date, as a YYYY-MM-DD key — the bucket a
  // dried lot's yield is counted in for the week-over-week delta.
  const weekMon = (iso) => {
    const d = new Date(iso + 'T00:00:00');
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };

  // Horizontal bar with an explicit (dynamic, per-row) fill colour — the tinted
  // sibling of hbar(). Colour is a per-element value, so it stays inline.
  const hbarC = (frac, color) =>
    `<div class="ana-hb"><div class="ana-hb-f" style="width:${Math.max(2, Math.round(100 * frac))}%${color ? `;background:${color}` : ''}"></div></div>`;

  // Single-series bar chart — dry-flower kg per cycle (batch). Reuses barPath()
  // and nice() from the task charts above; same mark spec, one series.
  const chartCycle = (cycles) => {
    const W = 560, H = 190, padL = 34, padB = 22, padT = 16;
    const n = cycles.length;
    const maxV = nice(Math.max(1, ...cycles.map((c) => c.kg)));
    const slot = (W - padL) / n;
    const bw = Math.max(6, Math.min(30, slot - 12));
    const y = (v) => padT + (H - padB - padT) * (1 - v / maxV);
    const grid = [0, 0.5, 1].map((f) => {
      const gy = y(maxV * f);
      return `<line x1="${padL}" y1="${gy}" x2="${W}" y2="${gy}" class="ana-grid"/>
        <text x="${padL - 5}" y="${gy + 3}" class="ana-tick" text-anchor="end">${(maxV * f).toFixed(maxV < 10 ? 1 : 0)}</text>`;
    }).join('');
    const bars = cycles.map((c, i) => {
      const x0 = padL + i * slot + (slot - bw) / 2;
      const bh = (H - padB) - y(c.kg);
      const lbl = (n <= 10 || i % 2 === (n - 1) % 2)
        ? `<text x="${x0 + bw / 2}" y="${H - 7}" class="ana-tick" text-anchor="middle">${GF.esc(c.code)}</text>` : '';
      return `<g><title>${GF.esc(c.code)} · ${c.kg.toFixed(1)} kg</title>
        <path d="${barPath(x0, y(c.kg), bw, bh)}" fill="var(--ch-a)"/>
        <text x="${x0 + bw / 2}" y="${y(c.kg) - 4}" class="ana-cap" text-anchor="middle">${c.kg.toFixed(1)}</text>${lbl}</g>`;
    }).join('');
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${AL('Dry-flower yield per cycle', 'Принос суво соцветие по циклус')}">${grid}${bars}</svg>`;
  };

  // Reusable label/bar/value row, matching the task-domain .ana-row grid.
  const yRow = (label, frac, val, color) =>
    `<div class="ana-row"><div class="ana-rl" title="${GF.esc(label)}">${GF.esc(label)}</div>${hbarC(frac, color)}<div class="ana-rv">${GF.esc(val)}</div><div class="ana-rx"></div></div>`;

  const yieldSection = () => {
    const yst = GF.WWF._anaY;
    const head = `<div class="ana-sec">${GF.icon('leaf', 'icon ana-sec-ic')}
      <h3>${AL('Yield & harvest', 'Принос и берба')}</h3>
      <span class="ana-sec-note">${AL('Dry weights from recorded harvest lots', 'Суви тежини од евидентирани лотови')}</span></div>`;

    if (yst.error) {
      return head + `<div class="panel ana-panel" style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(yst.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadAnaYield()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    if (yst.loading && !yst.data) {
      return head + `<div class="mw-skel" style="height:70px;margin-bottom:10px"></div>
        <div class="mw-skel" style="height:200px"></div>`;
    }
    if (!yst.data) return head + `<div class="ana-note">${AL('Loading…', 'Се вчитува…')}</div>`;

    const lots = yst.data.harvests || [];
    const dried = lots.filter((l) => l.dry_flower_g != null);
    if (!dried.length) {
      return head + `<div class="panel ana-panel"><div class="ana-note">${AL(
        'No dried harvest lots yet — yield metrics appear once lots are dried.',
        'Сè уште нема исушени лотови — метриките се појавуваат откако лотовите ќе се исушат.')}</div></div>`;
    }

    const sum = (arr, f) => arr.reduce((s, x) => s + (f(x) || 0), 0);
    const flowerG = sum(dried, (l) => l.dry_flower_g);
    const trimG = sum(dried, (l) => l.dry_trim_g);
    const wasteG = sum(dried, (l) => l.dry_waste_g);
    const dryTotalG = flowerG + trimG + wasteG;
    const plantsDried = sum(dried, (l) => l.plants_harvested);
    const wetDried = sum(dried.filter((l) => l.wet_weight_g != null), (l) => l.wet_weight_g);
    const avgGPlant = plantsDried > 0 ? flowerG / plantsDried : null;
    const lossPct = wetDried > 0 ? (wetDried - dryTotalG) / wetDried * 100 : null;
    const cycleCodes = new Set(dried.map((l) => l.batch_code));
    const openLots = lots.filter((l) => l.status !== 'closed').length;

    // Week-over-week delta on dry-flower yield — only when the data actually
    // spans two harvest weeks (else the delta would be meaningless). Compares
    // the two most recent weeks that carry a dried lot.
    const wkMap = new Map();
    for (const l of dried) {
      const dt = l.dried_on || l.harvested_on;
      if (!dt) continue;
      const k = weekMon(dt);
      wkMap.set(k, (wkMap.get(k) || 0) + (l.dry_flower_g || 0));
    }
    const wks = [...wkMap.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1));
    let wow = null;
    if (wks.length >= 2) {
      const prev = wks[wks.length - 2][1], curw = wks[wks.length - 1][1];
      if (prev > 0) wow = { pct: (curw - prev) / prev * 100 };
    }

    const tile = GF.kpiTile;
    const wowSub = wow
      ? `${wow.pct >= 0 ? '▲' : '▼'} ${Math.abs(wow.pct).toFixed(1)}% ${AL('vs prev. harvest week', 'во однос на претходната недела')}`
      : `${dried.length} ${AL('lots', 'лотови')} · ${cycleCodes.size} ${AL('cycles', 'циклуси')}`;
    const kpis = `<div class="ana-tiles">
      ${tile(AL('Dry-flower yield', 'Принос суво соцветие'), kg(flowerG) + ' kg', wowSub,
             wow ? (wow.pct >= 0 ? 'good' : 'bad') : undefined)}
      ${tile(AL('Avg yield / plant', 'Просечен принос / растение'),
             avgGPlant == null ? '—' : avgGPlant.toFixed(1) + ' g',
             plantsDried > 0 ? `${AL('across', 'од')} ${plantsDried} ${AL('plants', 'растенија')}` : '')}
      ${tile(AL('Moisture loss', 'Загуба на влага'),
             lossPct == null ? '—' : lossPct.toFixed(1) + '%',
             AL('wet → dry', 'влажно → суво'))}
      ${tile(AL('Harvest lots', 'Лотови од берба'), dried.length,
             `${cycleCodes.size} ${AL('cycles', 'циклуси')} · ${openLots} ${AL('open', 'отворени')}`)}
    </div>`;

    // Yield per cycle — dry flower summed per batch, most recent ~10 cycles
    // oldest→newest (ordered by each batch's latest lot date).
    const byBatch = new Map();
    for (const l of dried) {
      const b = byBatch.get(l.batch_code) || { code: l.batch_code || '—', g: 0, last: '' };
      b.g += l.dry_flower_g || 0;
      const dt = l.dried_on || l.harvested_on || '';
      if (dt > b.last) b.last = dt;
      byBatch.set(l.batch_code, b);
    }
    const cycles = [...byBatch.values()]
      .sort((a, b) => (a.last < b.last ? -1 : a.last > b.last ? 1 : 0))
      .slice(-10)
      .map((b) => ({ code: b.code, kg: b.g / 1000 }));

    // Yield by strain — dry flower summed per cultivar.
    const byStrain = new Map();
    for (const l of dried) {
      const k = l.cultivar_code || '—';
      byStrain.set(k, (byStrain.get(k) || 0) + (l.dry_flower_g || 0));
    }
    const strains = [...byStrain.entries()].map(([code, g]) => ({ code, g })).sort((a, b) => b.g - a.g);
    const maxStrain = Math.max(1, ...strains.map((s) => s.g));
    const strainRows = strains.map((s) => yRow(s.code, s.g / maxStrain, kg(s.g) + ' kg')).join('');

    // Yield per plant by room (zone) — g/plant, the real efficiency figure the
    // register supports. NOT g/W: watt draw is not a field this data carries.
    const byRoom = new Map();
    for (const l of dried) {
      const k = l.room_name || AL('Unassigned', 'Недоделено');
      const r = byRoom.get(k) || { flower: 0, plants: 0 };
      r.flower += l.dry_flower_g || 0; r.plants += l.plants_harvested || 0;
      byRoom.set(k, r);
    }
    const zones = [...byRoom.entries()]
      .map(([name, r]) => ({ name, gpp: r.plants > 0 ? r.flower / r.plants : null }))
      .filter((z) => z.gpp != null).sort((a, b) => b.gpp - a.gpp);
    const maxZone = Math.max(1, ...zones.map((z) => z.gpp));
    const zoneRows = zones.length
      ? zones.map((z) => yRow(z.name, z.gpp / maxZone, z.gpp.toFixed(1) + ' g')).join('')
      : `<div class="ana-note">${AL('No per-plant figures yet.', 'Сè уште нема податоци по растение.')}</div>`;

    // Output composition — the real split of dry mass (flower / trim / waste).
    // Stands in for the mockup's graded A/B/C distribution, which needs a grade
    // field the register does not have.
    const comp = [
      { label: AL('Flower', 'Соцветие'), g: flowerG, c: 'var(--ch-a)' },
      { label: AL('Trim', 'Кастрен материјал'), g: trimG, c: 'var(--ch-b)' },
      { label: AL('Waste', 'Отпад'), g: wasteG, c: 'var(--ink-3)' },
    ];
    const compRows = comp.map((p) => {
      const pctv = dryTotalG > 0 ? p.g / dryTotalG : 0;
      return yRow(p.label, pctv, (pctv * 100).toFixed(pctv * 100 < 10 ? 1 : 0) + '%', p.c);
    }).join('');

    return head + kpis + `
      <div class="ana-grid2">
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Yield per cycle · kg', 'Принос по циклус · кг')}</div>
          ${chartCycle(cycles)}
        </div>
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Yield by strain', 'Принос по сорта')}</div>
          ${strainRows}
        </div>
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Yield per plant by room · g', 'Принос по растение по просторија · г')}</div>
          ${zoneRows}
        </div>
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Output composition', 'Состав на принос')}</div>
          ${compRows}
        </div>
      </div>`;
  };

  GF.views.analytics = () => {
    const st = GF.WWF._ana;
    if (!st.data && !st.loading && !st.error) GF.WWF.loadAnalytics();
    const yst = GF.WWF._anaY;
    if (!yst.data && !yst.loading && !yst.error) GF.WWF.loadAnaYield();
    const head = GF.viewHead
      ? GF.viewHead('analytics', 'analytics_sub')
      : `<h2>${AL('Analytics', 'Аналитика')}</h2>`;
    if (st.loading || (!st.data && !st.error)) {
      return head + `<div class="mw-skel" style="height:80px;margin-bottom:10px"></div>
        <div class="mw-skel" style="height:220px"></div>`;
    }
    if (st.error) {
      return head + `<div class="panel" style="padding:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <span style="color:var(--red-fg,var(--red))">${GF.esc(st.error)}</span>
        <button class="btn btn-sm" onclick="GF.WWF.loadAnalytics()">${AL('Retry', 'Обиди се повторно')}</button></div>`;
    }
    const d = st.data;
    const cur = d.weeks[d.weeks.length - 1] || {};
    const doneRange = d.weeks.reduce((s, w) => s + w.completed, 0);
    const onTimeRange = d.weeks.reduce((s, w) => s + w.on_time, 0);
    const pct = doneRange ? Math.round(100 * onTimeRange / doneRange) : null;
    const openNow = d.departments.reduce((s, x) => s + x.open, 0);
    const overdueNow = d.departments.reduce((s, x) => s + x.overdue, 0);

    const tile = GF.kpiTile;

    const kpis = `<div class="ana-tiles">
      ${tile(AL('Open tasks now', 'Отворени задачи сега'), openNow,
             overdueNow ? `${overdueNow} ${GF.t('overdue').toLowerCase()}` : '',
             undefined, overdueNow ? 'bad' : '')}
      ${tile(AL('Completed', 'Завршени') + ` · ${d.range.weeks}${AL('w', 'н')}`, doneRange, '')}
      ${tile(AL('On time', 'Навреме'), pct === null ? '—' : pct + '%',
             AL('of completed tasks', 'од завршените задачи'))}
      ${tile(AL('Active people this week', 'Активни лица оваа недела'), cur.active_people || 0,
             `${cur.sessions || 0} ${AL('sessions', 'сесии')}`)}
    </div>`;

    const ranges = [4, 8, 12].map((n) =>
      `<button class="ntf-tab${st.weeks === n ? ' on' : ''}" onclick="GF.WWF.anaRange(${n})">${n} ${AL('weeks', 'недели')}</button>`).join('');

    const maxOpen = Math.max(1, ...d.departments.map((x) => x.open));
    const deptRows = d.departments.map((x) => `
      <div class="ana-row">
        <div class="ana-rl" title="${GF.esc(deptName(x))}">${GF.esc(deptName(x))}</div>
        ${hbar(x.open / maxOpen)}
        <div class="ana-rv">${x.open}</div>
        <div class="ana-rx">
          ${x.stuck ? `<span><i class="fs-dot" style="background:var(--orange)"></i>${x.stuck} ${GF.t('stuck').toLowerCase()}</span>` : ''}
          ${x.overdue ? `<span><i class="fs-dot" style="background:var(--red)"></i>${x.overdue} ${GF.t('overdue').toLowerCase()}</span>` : ''}
        </div>
      </div>`).join('');

    const maxType = Math.max(1, ...d.task_types.map((t) => t.count));
    const typeRows = d.task_types.map((t) => {
      const lbl = (GF.TASK_TYPE_LABELS[t.task_type] || {})[GF.state.lang === 'mk' ? 'mk' : 'en'] || t.task_type;
      return `<div class="ana-row">
        <div class="ana-rl">${GF.esc(lbl)}</div>
        ${hbar(t.count / maxType)}
        <div class="ana-rv">${t.count}</div><div class="ana-rx"></div>
      </div>`;
    }).join('');

    return head + `
      <div class="ana-head">${ranges}</div>
      ${kpis}
      <div class="ana-grid2">
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Task flow per week', 'Проток на задачи по недела')}</div>
          ${chartFlow(d.weeks)}
        </div>
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('On-time completion', 'Навремено завршување')}</div>
          ${chartOnTime(d.weeks)}
          <div class="ana-note">${AL('Share of completed tasks finished on or before their due date.',
                                     'Удел на завршени задачи завршени на или пред рокот.')}</div>
        </div>
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Open tasks by department', 'Отворени задачи по оддел')}</div>
          ${deptRows || `<div class="ana-note">${GF.t('no_tasks')}</div>`}
        </div>
        <div class="panel ana-panel">
          <div class="ana-pt">${AL('Open tasks by type', 'Отворени задачи по тип')}</div>
          ${typeRows || `<div class="ana-note">${GF.t('no_tasks')}</div>`}
        </div>
      </div>
      ${yieldSection()}`;
  };

  GF.WWF._registerFullPageView({
    key: 'analytics', icon: 'trend',
    label: () => AL('Analytics', 'Аналитика'),
    insertBefore: 'report',   // Management group, beside the weekly report
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
