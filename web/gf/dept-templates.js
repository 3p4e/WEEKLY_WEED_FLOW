/* dept-templates.js — per-department task-field templates, one-tap presets,
   and department-home panel configs. Keyed by backend department CODE
   (integrate.js maps /departments rows into GF.DEPTS incl. `code`; the
   standalone data.js DEPTS carry no codes, so everything here degrades to a
   silent no-op). Values land in the task's `attributes` jsonb (tasks 0011) —
   the backend validates shape only, so adding a field here never needs a
   migration. Loads after core.js (uses GF.ICONS/GF.state), before render/main.

   Field spec: { key, en, mk, type: 'text'|'number'|'select', ph?, unit?,
                 chip?, opts?: [{v, en, mk}] } — `chip` fields render on cards.
   Preset spec: { en, mk, attrs?, type? } — one-tap suggestions in the add
   modal + dept home; titles are stored bilingual ("МК | EN") up front so the
   save path's AI translation short-circuits.
   Home spec:  [{ kind:'group', attr } | { kind:'queue', key } |
                { kind:'types', types:[] } | { kind:'inout', attr }] with
   bilingual panel labels; consumed by depthome-view.js. */
window.GF = window.GF || {};

// Icon for the department-home nav row (core.js's GF.ICONS is loaded by now).
GF.ICONS.home = 'M4 9.5L10 4l6 5.5M5.5 8.2V16h9V8.2M8.5 16v-4h3v4';

GF.DEPT_TEMPLATES = {
  cultivation: {
    fields: [
      { key: 'room', en: 'Room', mk: 'Просторија', type: 'text', ph: 'GR-2', chip: true },
      { key: 'strain', en: 'Strain', mk: 'Сорта', type: 'text', ph: 'Kalorist', chip: true },
      { key: 'plant_count', en: 'Plant count', mk: 'Број растенија', type: 'number', unit: 'pl', chip: true },
    ],
    presets: [
      { en: 'Watering', mk: 'Наводнување' },
      { en: 'Defoliation', mk: 'Дефолијација' },
      { en: 'IPM check', mk: 'ИПМ преглед' },
      { en: 'Transplanting', mk: 'Пресадување' },
    ],
    home: [
      { kind: 'group', attr: 'room', en: 'By room', mk: 'По просторија' },
      { kind: 'queue', key: 'handoff_ready', en: 'Ready for handoff', mk: 'Подготвени за предавање' },
    ],
  },
  production: {
    fields: [
      { key: 'batch_ref', en: 'Batch', mk: 'Серија', type: 'text', ph: 'B-2026-041', chip: true },
      { key: 'process_step', en: 'Process step', mk: 'Процесен чекор', type: 'select', chip: true,
        opts: [{ v: 'drying', en: 'Drying', mk: 'Сушење' }, { v: 'trimming', en: 'Trimming', mk: 'Тримување' },
               { v: 'extraction', en: 'Extraction', mk: 'Екстракција' }, { v: 'packaging', en: 'Packaging', mk: 'Пакување' }] },
    ],
    presets: [
      { en: 'Drying room check', mk: 'Проверка на сушара', attrs: { process_step: 'drying' } },
      { en: 'Trimming', mk: 'Тримување', attrs: { process_step: 'trimming' } },
      { en: 'Packaging run', mk: 'Пакување', attrs: { process_step: 'packaging' } },
    ],
    home: [{ kind: 'group', attr: 'batch_ref', en: 'By batch', mk: 'По серија' }],
  },
  qc: {
    fields: [
      { key: 'sample_ref', en: 'Sample', mk: 'Примерок', type: 'text', ph: 'S-0412', chip: true },
      { key: 'inspection_type', en: 'Inspection', mk: 'Инспекција', type: 'select', chip: true,
        opts: [{ v: 'lab', en: 'Lab', mk: 'Лабораторија' }, { v: 'incoming', en: 'Incoming', mk: 'Влезна' },
               { v: 'in_process', en: 'In-process', mk: 'Процесна' }, { v: 'final', en: 'Final', mk: 'Финална' },
               { v: 'environmental', en: 'Environmental', mk: 'Амбиентална' }] },
      { key: 'batch_ref', en: 'Batch', mk: 'Серија', type: 'text', ph: 'B-2026-041' },
    ],
    presets: [
      { en: 'Sampling', mk: 'Земање примероци' },
      { en: 'Lab analysis', mk: 'Лабораториска анализа', attrs: { inspection_type: 'lab' }, type: 'lab' },
      { en: 'Environmental monitoring', mk: 'Мониторинг на средина', attrs: { inspection_type: 'environmental' } },
    ],
    home: [
      { kind: 'queue', key: 'due_week', en: 'Due this week', mk: 'Рок оваа недела' },
      { kind: 'queue', key: 'in_review', en: 'In review', mk: 'На преглед' },
    ],
  },
  quality_assurance: {
    fields: [
      { key: 'doc_ref', en: 'Document', mk: 'Документ', type: 'text', ph: 'SOP-012', chip: true },
      { key: 'capa_ref', en: 'CAPA', mk: 'CAPA', type: 'text', ph: 'CAPA-07', chip: true },
    ],
    presets: [
      { en: 'SOP review', mk: 'Преглед на СОП', type: 'sop' },
      { en: 'CAPA follow-up', mk: 'Следење CAPA', type: 'capa' },
      { en: 'Document control', mk: 'Контрола на документи', type: 'document' },
    ],
    home: [
      { kind: 'types', types: ['capa', 'sop', 'document'], en: 'CAPA / SOP / Documents', mk: 'CAPA / СОП / Документи' },
      { kind: 'queue', key: 'in_review', en: 'Review queue', mk: 'Ред за преглед' },
    ],
  },
  logistics: {
    fields: [
      { key: 'flow', en: 'Flow', mk: 'Тек', type: 'select', chip: true,
        opts: [{ v: 'in', en: 'Inbound', mk: 'Влез' }, { v: 'out', en: 'Outbound', mk: 'Излез' }] },
      { key: 'batch_ref', en: 'Batch', mk: 'Серија', type: 'text', ph: 'B-2026-041', chip: true },
    ],
    presets: [
      { en: 'Goods receipt', mk: 'Прием на стока', attrs: { flow: 'in' } },
      { en: 'Dispatch', mk: 'Испорака', attrs: { flow: 'out' } },
      { en: 'Stock count', mk: 'Попис' },
    ],
    home: [{ kind: 'inout', attr: 'flow', en: 'Inbound / Outbound', mk: 'Влез / Излез' }],
  },
  security: {
    fields: [
      { key: 'area', en: 'Area', mk: 'Подрачје', type: 'text', ph: 'Perimeter', chip: true },
      { key: 'incident_type', en: 'Type', mk: 'Тип', type: 'select', chip: true,
        opts: [{ v: 'patrol', en: 'Patrol', mk: 'Патрола' }, { v: 'incident', en: 'Incident', mk: 'Инцидент' },
               { v: 'access', en: 'Access', mk: 'Пристап' }, { v: 'cctv', en: 'CCTV', mk: 'Видео надзор' }] },
    ],
    presets: [
      { en: 'Perimeter patrol', mk: 'Патрола на периметар', attrs: { incident_type: 'patrol' } },
      { en: 'CCTV review', mk: 'Преглед на видео надзор', attrs: { incident_type: 'cctv' } },
      { en: 'Access audit', mk: 'Ревизија на пристап', attrs: { incident_type: 'access' } },
    ],
    home: [
      { kind: 'group', attr: 'area', en: 'By area', mk: 'По подрачје' },
      { kind: 'queue', key: 'incidents', en: 'Incidents', mk: 'Инциденти' },
    ],
  },
  tooling: {
    fields: [
      { key: 'equipment_ref', en: 'Equipment', mk: 'Опрема', type: 'text', ph: 'HVAC-03', chip: true },
      { key: 'maintenance_type', en: 'Maintenance', mk: 'Одржување', type: 'select', chip: true,
        opts: [{ v: 'preventive', en: 'Preventive', mk: 'Превентивно' }, { v: 'corrective', en: 'Corrective', mk: 'Корективно' },
               { v: 'calibration', en: 'Calibration', mk: 'Калибрација' }, { v: 'inspection', en: 'Inspection', mk: 'Инспекција' }] },
    ],
    presets: [
      { en: 'Preventive maintenance', mk: 'Превентивно одржување', attrs: { maintenance_type: 'preventive' } },
      { en: 'Calibration', mk: 'Калибрација', attrs: { maintenance_type: 'calibration' } },
      { en: 'Repair', mk: 'Поправка', attrs: { maintenance_type: 'corrective' } },
    ],
    home: [
      { kind: 'group', attr: 'equipment_ref', en: 'By equipment', mk: 'По опрема' },
      { kind: 'queue', key: 'stuck', en: 'Stuck / blocked', mk: 'Блокирани' },
    ],
  },
};

GF.deptCode = (deptId) => (GF.DEPTS.find(d => d.id === deptId) || {}).code || null;
GF.deptTemplate = (deptId) => GF.DEPT_TEMPLATES[GF.deptCode(deptId)] || null;
GF.tplLabel = (o) => (GF.state.lang === 'mk' ? (o.mk || o.en) : o.en);

// The signed-in user's own department (null for cross-org roles: Owner/CEO/
// COO/QP and ADMIN). Drives the dept-home nav row + role landing default; a
// department WITHOUT a template still gets the generic home layout.
GF.myDeptId = () => (GF.API && GF.API.user && GF.API.user.department_id)
  || (GF.PEOPLE[GF.state.user] || {}).dept || null;
GF.hasDeptHome = () => !!GF.myDeptId();

// ── Add/Edit-modal department fields ────────────────────────────────────
// Rendered into #add-dept-fields; re-rendered whenever the dept select
// changes. `current` (edit mode) prefills; unknown current keys are kept by
// collectDeptAttrs so a template change never silently drops captured data.
GF.renderDeptFields = (deptId, current) => {
  const tpl = GF.deptTemplate(deptId);
  if (!tpl || !tpl.fields.length) return '';
  const cur = current || {};
  const input = (f) => {
    const v = cur[f.key] != null ? String(cur[f.key]) : '';
    if (f.type === 'select') {
      // Popup chooser (chooser.js), not a native dropdown — the hidden input
      // keeps the `GF.$('attr-f-…').value` contract for collectDeptAttrs.
      return GF.selectField(`attr-f-${f.key}`, {
        value: v, title: GF.tplLabel(f), placeholder: '—',
        options: [{ v: '', label: '—' }].concat(f.opts.map(o => ({ v: o.v, label: GF.tplLabel(o) }))),
        onPick: () => GF.renderAddPreview && GF.renderAddPreview(),
      });
    }
    const t = f.type === 'number' ? 'number' : 'text';
    return `<input id="attr-f-${f.key}" data-attr="${f.key}" data-type="${f.type}" type="${t}"`
      + ` value="${GF.esc(v)}" placeholder="${GF.esc(f.ph || '')}"${f.type === 'number' ? ' min="0" step="1"' : ''}`
      + ` oninput="GF.renderAddPreview&&GF.renderAddPreview()">`;
  };
  // Dept-tinted "fields well" (the mockup's af-modal .af-block): the accent
  // comes from --dept-acc, set on the modal by GF._addAccent.
  const dn = GF.depName(deptId);
  return `<div class="af-block">
    <div class="af-block-hd"><span class="dot"></span>${GF.esc(dn)} ${GF.state.lang === 'mk' ? 'полиња · опционални метаподатоци' : 'fields · optional metadata'}</div>
    <div class="dept-fields">${tpl.fields.map(f => `
    <div class="field af-field"><label>${GF.esc(GF.tplLabel(f))}${f.unit ? ` <span class="lbl-hint">(${GF.esc(f.unit)})</span>` : ''}</label>${input(f)}</div>`).join('')}</div></div>`;
};

// Tint the add modal with the chosen department's color (drives the af-block
// well + header dot via --dept-acc) and refresh the live preview.
GF._addAccent = (deptId) => {
  const modal = document.querySelector('#add-modal .modal');
  const color = (GF.dep(deptId) || {}).color || '';
  if (modal) { if (color) modal.style.setProperty('--dept-acc', color); else modal.style.removeProperty('--dept-acc'); }
  if (GF.renderAddPreview) GF.renderAddPreview();
};

// Live preview under the form (mockup af-modal): shows how the dept-field
// values become attribute chips and the comma tags become #tag chips, using
// the SAME chip renderers the board cards use — so what you see is what the
// card will look like.
GF.renderAddPreview = () => {
  const host = GF.$('add-preview'); if (!host) return;
  const deptId = GF.$('add-dept') ? GF.$('add-dept').value : null;
  const title = (GF.$('add-title') && GF.$('add-title').value || '').trim();
  const attrs = GF.collectDeptAttrs ? GF.collectDeptAttrs(deptId, {}) : {};
  const tags = (GF.$('add-tags') && GF.$('add-tags').value || '')
    .split(',').map(s => s.trim()).filter(Boolean);
  const chips = (GF.attrChips ? GF.attrChips({ attrs, dept: deptId }) : '')
    + tags.map(tg => `<span class="tag-chip">#${GF.esc(tg)}</span>`).join('');
  if (!title && !chips) { host.innerHTML = ''; return; }
  const d = GF.dep(deptId) || {};
  host.innerHTML = `
    <div class="af-prev-lbl">${GF.state.lang === 'mk' ? 'Преглед' : 'Preview'}</div>
    <div class="af-prev-card">
      <div class="af-prev-title">${GF.esc(title || '…')}</div>
      <div class="af-prev-meta"><span class="dn" style="color:${d.color || 'var(--primary)'}">${GF.esc(GF.depAbbr(deptId))}</span>${chips}</div>
    </div>`;
};

GF.refreshDeptFields = (deptId, current, showPresets) => {
  const host = GF.$('add-dept-fields');
  if (!host) return;
  host.innerHTML = GF.renderDeptFields(deptId, current);
  const pr = GF.$('add-preset-row');
  if (pr) {
    const tpl = GF.deptTemplate(deptId);
    const show = !!(showPresets && tpl && tpl.presets && tpl.presets.length);
    pr.style.display = show ? '' : 'none';
    pr.innerHTML = show ? `<label>${GF.state.lang === 'mk' ? 'Брзо додавање' : 'Quick add'}</label>
      <div class="chips">${tpl.presets.map((p, i) =>
        `<span class="chip-opt preset-chip" onclick="GF.applyPreset(${i})">${GF.esc(GF.tplLabel(p))}</span>`).join('')}</div>` : '';
  }
  if (GF.renderAddPreview) GF.renderAddPreview();
};

// One-tap preset: bilingual title ("МК | EN" — the save path's translator
// short-circuits on ' | '), template attrs, and task type when given.
GF.applyPreset = (i) => {
  const deptId = GF.$('add-dept') && GF.$('add-dept').value;
  const tpl = GF.deptTemplate(deptId);
  const p = tpl && tpl.presets && tpl.presets[i];
  if (!p) return;
  const title = GF.$('add-title');
  if (title) { title.value = `${p.mk} | ${p.en}`; title.focus(); }
  if (p.type && GF.$('add-type')) { GF.$('add-type').value = p.type; if (GF.syncSelect) GF.syncSelect('add-type'); }
  Object.entries(p.attrs || {}).forEach(([k, v]) => {
    const el = GF.$('attr-f-' + k); if (el) { el.value = String(v); if (GF.syncSelect) GF.syncSelect('attr-f-' + k); }
  });
  if (GF.renderAddPreview) GF.renderAddPreview();
};

// Read the rendered field inputs → attributes object. Starts from `base`
// (edit mode: the task's existing attributes) so keys OUTSIDE the current
// template — e.g. captured/imported metadata — survive the whole-object
// PATCH; a template field cleared to '' removes its key.
GF.collectDeptAttrs = (deptId, base) => {
  const out = Object.assign({}, base || {});
  const tpl = GF.deptTemplate(deptId);
  if (tpl) {
    tpl.fields.forEach(f => {
      const el = GF.$('attr-f-' + f.key);
      if (!el) return;
      const raw = (el.value || '').trim();
      if (!raw) { delete out[f.key]; return; }
      out[f.key] = f.type === 'number' && Number.isFinite(Number(raw)) ? Number(raw) : raw;
    });
  }
  return out;
};

// Card meta chips for a task's attributes — `chip:true` template fields (or,
// with no template, the first few raw keys). Attribute chips are filled soft
// chips with a mono value, visually distinct from #tag outline chips.
/* The label/value pairs behind a task's attribute chips, as DATA — one
   source of truth for every chip renderer. attrChips (below) draws the
   classic .attr-chip; depthome's .mw-tcard draws the design system's
   .mw-attr from the same pairs, so the two can never disagree about WHICH
   attributes a card shows. */
GF.attrChipData = (t) => {
  const attrs = t && t.attrs;
  if (!attrs || typeof attrs !== 'object') return [];
  const tpl = GF.deptTemplate(t.dept);
  let entries;
  if (tpl) {
    entries = tpl.fields.filter(f => f.chip && attrs[f.key] != null && attrs[f.key] !== '')
      .map(f => {
        let v = attrs[f.key];
        if (f.type === 'select' && f.opts) { const o = f.opts.find(o => o.v === v); if (o) v = GF.tplLabel(o); }
        return { label: GF.tplLabel(f), val: `${v}${f.unit ? ' ' + f.unit : ''}` };
      });
  } else {
    entries = Object.entries(attrs).slice(0, 3).map(([k, v]) => ({ label: k, val: String(v) }));
  }
  return entries.slice(0, 4).map(e => ({ label: e.label, val: String(e.val).slice(0, 24) }));
};

GF.attrChips = (t) => GF.attrChipData(t).map(e =>
  `<span class="attr-chip" title="${GF.esc(e.label)}">${GF.esc(e.val)}</span>`).join('');
