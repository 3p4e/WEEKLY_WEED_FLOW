/* waste-view.js — destruction / waste manifests and the reconciliation report.

   The record the campaign's 30.07-01.08 destruction window needs (migration
   0048 + app/api/waste.py). Cultivation can mark a batch destroyed; that says
   the batch is gone but not what left the building, how much it weighed, who
   watched it go, or who took it. This board is that record.

   Read: every role above base USER. Recording (draft, lines, seal, disposal):
   cultivation crew + executives + ADMIN. Witnessing: QA manager + executives +
   ADMIN — and never the person who weighed the load.

   THE LADDER, and why the buttons follow it rather than a status dropdown:
   draft -> sealed -> witnessed -> disposed, each rung a different person's
   assertion. Exactly one action is offered per manifest, the next rung, so
   there is no way to reach for a step out of order and no way to read the
   ladder backwards. The server refuses violations with 409 and this view
   surfaces `detail` verbatim — the rules live there.

   TWO PLACES THIS VIEW DELIBERATELY ADDS FRICTION OF ITS OWN:

   1. Sealing is irreversible and it is what the witness later signs against, so
      it is confirmed in a modal that states the line count and total, not a bare
      button. A seal that fixed the wrong contents cannot be unfixed.
   2. The witness modal names the two-person rule up front. The server enforces
      it, but discovering it as a 409 after tapping "witness" teaches the
      operator that the app is broken rather than that the control exists.

   The reconciliation tab is the reason the module is worth having: it joins
   cultivation's batch phase against the waste register and flags the batches
   closed as destroyed with nothing ever manifested. Neither module can see that
   on its own.

   Same monkey-patch/view pattern as the other *-view.js files; loads after
   worklog.js (uses AL(), GF.WWF._ensureModal, GF.selectField). */

(function () {
  GF.WWF._waste = {
    tab: 'manifests',            // 'manifests' | 'recon'
    manifests: null, recon: null, loading: false, error: null,
    statusFilter: '', open: null,   // id of the manifest whose detail modal is up
  };

  // Must stay in step with the CHECK constraints in migration 0048 and the
  // tuples in app/api/waste.py.
  const WASTE_TYPES = [
    { v: 'plant_material', en: 'Plant material',  mk: 'Растителен материјал' },
    { v: 'root_substrate', en: 'Roots + substrate', mk: 'Корени и субстрат' },
    { v: 'growing_medium', en: 'Growing medium',  mk: 'Медиум за раст' },
    { v: 'trim',           en: 'Trim',            mk: 'Трим' },
    { v: 'packaging',      en: 'Packaging',       mk: 'Пакување' },
    { v: 'other',          en: 'Other',           mk: 'Друго' },
  ];
  const REASONS = [
    { v: 'hlvd_eradication', en: 'HLVd eradication', mk: 'Искоренување HLVd' },
    { v: 'routine_cull',     en: 'Routine cull',     mk: 'Редовно отфрлање' },
    { v: 'failed_qc',        en: 'Failed QC',        mk: 'Негативна контрола' },
    { v: 'expired',          en: 'Expired',          mk: 'Истечено' },
    { v: 'spillage',         en: 'Spillage',         mk: 'Расипување' },
    { v: 'other',            en: 'Other',            mk: 'Друго' },
  ];
  const STATUS = {
    draft:     { en: 'Draft',     mk: 'Нацрт',       color: '#8296B4' },
    sealed:    { en: 'Sealed',    mk: 'Затворено',   color: '#E0A73E' },
    witnessed: { en: 'Witnessed', mk: 'Потврдено',   color: '#2FD9D9' },
    disposed:  { en: 'Disposed',  mk: 'Уништено',    color: '#2BE8A0' },
  };
  const lbl = (list, v) => {
    const o = list.find(x => x.v === v);
    return o ? AL(o.en, o.mk) : v;
  };
  const stLbl = (s) => AL(STATUS[s]?.en || s, STATUS[s]?.mk || s);
  const stCol = (s) => (STATUS[s] || {}).color || 'var(--ink-3)';

  const role = () => (GF.API.user || {}).role;
  const canRecord = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'CU_MGR'].includes(role());
  const canWitness = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'QA_MGR'].includes(role());
  // Mirrors ManifestIn.manifest_code server-side (slashes allowed: carrier
  // dockets are routinely written WM/2026/0731-04).
  const CODE_RE = /^[A-Za-z0-9_/-]{1,64}$/;
  const kg = (n) => (n == null ? '—' : (Math.round(n * 100) / 100).toLocaleString() + ' kg');

  GF.WWF.loadWaste = async () => {
    const st = GF.WWF._waste;
    st.loading = true; st.error = null;
    try {
      if (st.tab === 'recon') {
        st.recon = (await GF.API.wasteReconciliation()).batches || [];
      } else {
        const q = st.statusFilter ? { status: st.statusFilter } : {};
        st.manifests = (await GF.API.wasteManifests(q)).manifests || [];
      }
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'waste') GF.render.all();
  };

  // ── manifest card ─────────────────────────────────────────────────────────

  // Exactly ONE ladder action per manifest — the next rung. Offering several at
  // once would invite reaching past a step the server will refuse anyway, and
  // would make the ladder look like a set of independent checkboxes.
  const ladderAction = (m) => {
    if (m.status === 'draft' && canRecord()) {
      return `<button class="btn btn-orange btn-sm" onclick="GF.WWF.wasteSealForm('${m.id}')">
        ${GF.icon('shield', 'icon', '#fff')}${AL('Weigh &amp; seal', 'Измери и затвори')}</button>`;
    }
    if (m.status === 'sealed' && canWitness()) {
      return `<button class="btn btn-orange btn-sm" onclick="GF.WWF.wasteWitnessForm('${m.id}')">
        ${GF.icon('eye', 'icon', '#fff')}${AL('Witness', 'Потврди како сведок')}</button>`;
    }
    if (m.status === 'witnessed' && canRecord()) {
      return `<button class="btn btn-orange btn-sm" onclick="GF.WWF.wasteDisposeForm('${m.id}')">
        ${GF.icon('trash', 'icon', '#fff')}${AL('Record disposal', 'Запиши уништување')}</button>`;
    }
    // Sealed and waiting on QA, seen by someone who is not QA: say what it is
    // waiting for instead of showing a card with no action and no explanation.
    if (m.status === 'sealed') {
      return `<span style="color:var(--ink-3);font-size:11px">${AL(
        'waiting on a QA witness', 'чека QA сведок')}</span>`;
    }
    if (m.status === 'witnessed') {
      return `<span style="color:var(--ink-3);font-size:11px">${AL(
        'witnessed — waiting on the carrier reference', 'потврдено — чека број од превозникот')}</span>`;
    }
    return '';
  };

  const manifestCard = (m) => {
    const empty = !m.line_count;
    return `<div class="card" style="padding:12px;margin-bottom:10px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <strong style="flex:1">${GF.esc(m.manifest_code)}</strong>
        <span style="color:${stCol(m.status)};font-size:12px">${GF.esc(stLbl(m.status))}</span>
      </div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:6px">
        ${GF.esc(lbl(WASTE_TYPES, m.waste_type))} · ${GF.esc(lbl(REASONS, m.reason))}
        ${m.origin_room_name ? ' · ' + GF.esc(m.origin_room_name) : ''}
        ${m.campaign ? ' · ' + GF.esc(m.campaign) : ''}
      </div>
      <div style="font-size:12px;margin-bottom:8px">
        ${m.line_count} ${AL('line(s)', 'ставки')}
        ${m.plant_qty_total ? ' · ' + m.plant_qty_total + ' ' + AL('plants', 'растенија') : ''}
        ${m.weight_kg_total ? ' · ' + kg(m.weight_kg_total) + ' ' + AL('on lines', 'на ставки') : ''}
        ${m.gross_weight_kg != null ? ' · ' + AL('gross ', 'бруто ') + kg(m.gross_weight_kg) : ''}
      </div>
      ${empty && m.status === 'draft' ? `<div style="color:#E0A73E;font-size:11px;margin-bottom:8px">${AL(
        'Nothing on this manifest yet — it cannot be sealed until you add what is in the load.',
        'Манифестот е празен — не може да се затвори додека не додадете што има во товарот.')}</div>` : ''}
      ${m.carrier_ref ? `<div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">
        ${AL('Carrier', 'Превозник')}: ${GF.esc(m.carrier_name || '—')} · ${GF.esc(m.carrier_ref)}</div>` : ''}
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="btn btn-sm" onclick="GF.WWF.wasteDetail('${m.id}')">
          ${GF.icon('file', 'icon')}${AL('Contents', 'Содржина')}</button>
        ${ladderAction(m)}
      </div>
    </div>`;
  };

  // ── reconciliation ────────────────────────────────────────────────────────

  // `unaccounted` from the API is plain arithmetic (planned minus declared
  // destroyed), and for a LIVE batch that number is the whole batch — the plants
  // are in the room, not missing. Rendering "2000 unaccounted" on every healthy
  // batch would bury the handful of rows that are genuinely wrong, which is the
  // only reason this report exists. So the arithmetic is interpreted by phase
  // here, and exactly three states count as problems:
  //   over-declared                  — wrong whatever the phase;
  //   destroyed, nothing manifested  — the material left with no record at all;
  //   destroyed, partly manifested   — the manifests do not cover the batch.
  // A harvested or still-growing batch with no destruction against it is normal,
  // and says so.
  const reconState = (r) => {
    if (r.over_declared) {
      return { key: 'over', bad: true,
               label: AL('OVER-DECLARED', 'ПРЕКУМЕРНО'), color: '#E5484D' };
    }
    if (r.phase === 'destroyed') {
      if (!r.declared_destroyed) {
        return { key: 'unmanifested', bad: true,
                 label: AL('destroyed, not manifested', 'уништено, без манифест'),
                 color: '#E5484D' };
      }
      if (r.declared_destroyed < r.plant_count) {
        return { key: 'partial', bad: true,
                 label: AL(`only ${r.declared_destroyed} of ${r.plant_count} manifested`,
                           `само ${r.declared_destroyed} од ${r.plant_count} со манифест`),
                 color: '#E0A73E' };
      }
      return { key: 'balanced', bad: false,
               label: AL('balanced', 'усогласено'), color: '#2BE8A0' };
    }
    if (r.phase === 'harvested') {
      return { key: 'harvested', bad: false,
               label: AL('harvested', 'ожнеано'), color: 'var(--ink-3)' };
    }
    return { key: 'live', bad: false,
             label: AL('in production', 'во производство'), color: 'var(--ink-3)' };
  };

  const reconRow = (r) => {
    const st = reconState(r);
    // Culls to date are the useful number on an open batch; the planned total is
    // the useful denominator on a closed one.
    const qty = (st.key === 'live' || st.key === 'harvested')
      ? `${r.declared_destroyed} <span style="color:var(--ink-3);font-size:11px">${
          AL('culled', 'отфрлени')}</span>`
      : `${r.declared_destroyed}/${r.plant_count} <span style="color:var(--ink-3);font-size:11px">${
          AL('declared', 'пријавени')}</span>`;
    return `<div style="display:flex;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line)${st.bad ? ';background:rgba(229,72,77,.06)' : ''}">
      <strong style="min-width:110px">${GF.esc(r.code || '—')}</strong>
      <span style="flex:1;color:var(--ink-3);font-size:11px">
        ${GF.esc(r.cultivar_code || '—')} · ${GF.esc(r.room_name || '—')} · ${GF.esc(r.phase)}</span>
      <span style="font-size:12px;min-width:120px;text-align:right">${qty}</span>
      <span style="min-width:170px;text-align:right;color:${st.color};font-size:11px">${
        GF.esc(st.label)}</span>
    </div>`;
  };

  // ── view ──────────────────────────────────────────────────────────────────

  GF.views.waste = () => {
    const st = GF.WWF._waste;
    const need = st.tab === 'recon' ? st.recon : st.manifests;
    if (!need && !st.loading && !st.error) GF.WWF.loadWaste();
    const newBtn = canRecord()
      ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.wasteManifestForm()">${GF.icon('plus', 'icon', '#fff')}${AL('New manifest', 'Нов манифест')}</button>`
      : '';
    const head = GF.viewHead
      ? GF.viewHead('waste', 'waste_sub', newBtn)
      : `<div class="view-head"><h2>${AL('Destruction', 'Уништување')}</h2>${newBtn}</div>`;
    const tabs = `<div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn btn-sm${st.tab === 'manifests' ? ' btn-primary' : ''}"
        onclick="GF.WWF.wasteTab('manifests')">${AL('Manifests', 'Манифести')}</button>
      <button class="btn btn-sm${st.tab === 'recon' ? ' btn-primary' : ''}"
        onclick="GF.WWF.wasteTab('recon')">${AL('Reconciliation', 'Усогласување')}</button>
    </div>`;
    if (st.loading && !need) return head + tabs + `<div class="ntf-empty">${AL('Loading…', 'Вчитување…')}</div>`;
    if (st.error) return head + tabs + `<div class="ntf-empty">${GF.esc(st.error)}</div>`;

    if (st.tab === 'recon') {
      const rows = st.recon || [];
      if (!rows.length) {
        return head + tabs + `<div class="ntf-empty">${AL(
          'No batches to reconcile yet.', 'Нема батчови за усогласување.')}</div>`;
      }
      // Counted through reconState, not by re-testing the API flags: the row and
      // the banner must never disagree about how many problems there are, and two
      // independent predicates over the same data is how they come to.
      const bad = rows.filter(r => reconState(r).bad);
      const closed = rows.filter(r => r.phase === 'destroyed').length;
      const banner = bad.length
        ? `<div style="color:#E5484D;font-size:12px;margin-bottom:10px">${AL(
            `${bad.length} of ${closed} destroyed batch(es) do not reconcile — a batch closed as destroyed with nothing manifested means the material left with no record of where it went.`,
            `${bad.length} од ${closed} уништени батч(ови) не се усогласуваат — батч затворен како уништен без манифест значи материјал заминал без запис каде.`)}</div>`
        : closed
          ? `<div style="color:#2BE8A0;font-size:12px;margin-bottom:10px">${AL(
              `All ${closed} destroyed batch(es) are covered by manifests.`,
              `Сите ${closed} уништени батч(ови) имаат манифести.`)}</div>`
          // No destroyed batches at all is neither good nor bad news, and saying
          // "everything reconciles" would read as a clean bill of health for a
          // check that has not actually had anything to check.
          : `<div style="color:var(--ink-3);font-size:12px;margin-bottom:10px">${AL(
              'No batch has been closed as destroyed yet, so there is nothing to reconcile. Culls against open batches are shown below.',
              'Ниту еден батч не е затворен како уништен, па нема што да се усогласува. Отфрлените од отворени батчови се прикажани подолу.')}</div>`;
      return head + tabs + banner + rows.map(reconRow).join('');
    }

    const list = st.manifests || [];
    const filter = `<div style="margin-bottom:10px;display:flex;gap:6px;flex-wrap:wrap">
      ${['', 'draft', 'sealed', 'witnessed', 'disposed'].map(s =>
        `<button class="btn btn-sm${st.statusFilter === s ? ' btn-primary' : ''}"
          onclick="GF.WWF.wasteFilter('${s}')">${s ? GF.esc(stLbl(s)) : AL('All', 'Сите')}</button>`).join('')}
    </div>`;
    if (!list.length) {
      return head + tabs + filter + `<div class="ntf-empty">${AL(
        'No manifests. Open one per consignment that leaves the site — one manifest is one physical load, however many batches it empties.',
        'Нема манифести. Отворете по еден за секој товар што ја напушта локацијата — еден манифест е еден физички товар, колку и батчови да опразни.')}</div>`;
    }
    return head + tabs + filter + list.map(manifestCard).join('');
  };

  GF.WWF.wasteTab = (tab) => {
    const st = GF.WWF._waste;
    if (st.tab === tab) return;
    st.tab = tab;
    GF.WWF.loadWaste();
  };

  GF.WWF.wasteFilter = (status) => {
    const st = GF.WWF._waste;
    st.statusFilter = status;
    st.manifests = null;
    GF.WWF.loadWaste();
  };

  // ── contents / lines ──────────────────────────────────────────────────────

  GF.WWF.wasteDetail = async (manifestId) => {
    let m;
    try { m = await GF.API.wasteManifest(manifestId); }
    catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._waste.open = m;
    GF.WWF._ensureModal('wa-detail-modal', '560px');
    GF.$('wa-detail-modal-title').textContent =
      AL('Manifest', 'Манифест') + ' ' + m.manifest_code;
    GF.WWF._wasteRenderDetail();
    GF.openModal('wa-detail-modal');
  };

  GF.WWF._wasteRenderDetail = () => {
    const m = GF.WWF._waste.open; if (!m) return;
    const body = GF.$('wa-detail-modal-body'); if (!body) return;
    const editable = m.status === 'draft' && canRecord();
    const lines = (m.lines || []).map(l => `
      <div style="display:flex;gap:8px;align-items:center;padding:5px 0;border-bottom:1px solid var(--line)">
        <span style="flex:1">${GF.esc(l.batch_code || AL('unattributed', 'без батч'))}
          <span style="color:var(--ink-3);font-size:11px"> ${GF.esc(l.room_name || '')}</span></span>
        <span style="font-size:12px;min-width:70px;text-align:right">${
          l.plant_qty != null ? l.plant_qty + ' ' + AL('pl', 'рас') : ''}</span>
        <span style="font-size:12px;min-width:80px;text-align:right">${
          l.weight_kg != null ? kg(l.weight_kg) : ''}</span>
        ${editable ? `<button class="btn btn-sm" style="color:var(--red)"
          onclick="GF.WWF.wasteLineRemove('${m.id}','${l.id}')">${GF.t('delete')}</button>` : ''}
      </div>`).join('');
    // The signature block: who did what, when. Present on every rung the
    // manifest has actually reached, absent on the ones it has not.
    const sig = [];
    if (m.sealed_at) sig.push(`${AL('Weighed &amp; sealed', 'Измерено и затворено')}: ${GF.esc(String(m.sealed_at).slice(0, 16).replace('T', ' '))} · ${kg(m.gross_weight_kg)}`);
    if (m.witnessed_at) sig.push(`${AL('Witnessed', 'Потврдено')}: ${GF.esc(String(m.witnessed_at).slice(0, 16).replace('T', ' '))}`);
    if (m.disposed_at) sig.push(`${AL('Disposed', 'Уништено')}: ${GF.esc(String(m.disposed_at).slice(0, 16).replace('T', ' '))} · ${GF.esc(m.carrier_ref || '')}`);
    body.innerHTML = `
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:10px">
        ${GF.esc(lbl(WASTE_TYPES, m.waste_type))} · ${GF.esc(lbl(REASONS, m.reason))} ·
        <span style="color:${stCol(m.status)}">${GF.esc(stLbl(m.status))}</span>
        ${m.destination ? '<br>' + AL('Destination', 'Дестинација') + ': ' + GF.esc(m.destination) : ''}
      </div>
      ${lines || `<div class="ntf-empty">${AL('Nothing on this manifest yet', 'Манифестот е празен')}</div>`}
      ${m.lines && m.lines.length ? `<div style="display:flex;gap:8px;padding:6px 0;font-size:12px">
        <strong style="flex:1">${AL('Total', 'Вкупно')}</strong>
        <span style="min-width:70px;text-align:right">${m.plant_qty_total || 0}</span>
        <span style="min-width:80px;text-align:right">${kg(m.weight_kg_total)}</span>
        ${editable ? '<span style="min-width:52px"></span>' : ''}
      </div>` : ''}
      ${sig.length ? `<div style="color:var(--ink-3);font-size:11px;margin-top:10px;line-height:1.7">
        ${sig.join('<br>')}</div>` : ''}
      ${m.note ? `<div style="font-size:11px;color:var(--ink-3);margin-top:8px">${GF.esc(m.note)}</div>` : ''}
      ${editable ? `<div class="row" style="gap:8px;margin-top:12px"><div class="spacer"></div>
        <button class="btn btn-primary" onclick="GF.WWF.wasteLineForm('${m.id}')">
          ${AL('Add to load', 'Додади во товар')}</button></div>`
        : `<div style="color:var(--ink-3);font-size:11px;margin-top:12px">${AL(
            'The contents were fixed when this manifest was sealed.',
            'Содржината е фиксирана при затворањето на манифестот.')}</div>`}`;
  };

  GF.WWF.wasteLineRemove = async (manifestId, lineId) => {
    if (!canRecord()) return;
    try {
      await GF.API.wasteLineDelete(manifestId, lineId);
      GF.toast(AL('Removed from the load', 'Отстрането од товарот'), 'success');
      await GF.WWF.wasteDetail(manifestId);
      await GF.WWF.loadWaste();
    } catch (e) { GF.toast(e.message, 'error'); }
  };

  GF.WWF.wasteLineForm = async (manifestId) => {
    if (!canRecord()) return;
    let batches = [];
    try { batches = (await GF.API.cultivationBatches(false)).batches || []; }
    catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._ensureModal('wa-line-modal', '440px');
    GF.$('wa-line-modal-title').textContent = AL('Add to load', 'Додади во товар');
    // Unattributed is a real, legitimate case (corridor sweepings, spent
    // medium), so it is the FIRST option rather than something to work around by
    // picking an arbitrary batch — a wrong batch attribution corrupts the
    // reconciliation, a blank one merely leaves it unattributed.
    const opts = [{ v: '', label: AL('— not from a specific batch —', '— не од определен батч —') }]
      .concat(batches.map(b => ({
        v: b.id,
        label: `${b.code} · ${b.cultivar_code || b.strain || '—'} · ${b.plant_count} ${AL('pl', 'рас')}`,
        sub: b.room_name || '',
      })));
    GF.$('wa-line-modal-body').innerHTML = `
      <div class="field"><label>${AL('From batch', 'Од батч')}</label>
        ${GF.selectField('wa-l-batch', { value: '', title: AL('From batch', 'Од батч'),
          options: opts, searchable: true })}</div>
      <div class="field"><label>${AL('Plants', 'Растенија')}</label>
        <input id="wa-l-qty" type="number" min="0" step="1"></div>
      <div class="field"><label>${AL('Weight (kg)', 'Тежина (kg)')}</label>
        <input id="wa-l-kg" type="number" min="0" step="0.1"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="wa-l-note" maxlength="500"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'State at least one of the two: plants are counted, substrate is weighed. Declaring more plants than a batch holds is refused — the register has to balance.',
        'Внесете барем едно од двете: растенијата се бројат, субстратот се тежи. Пријавување повеќе растенија отколку што батчот има се одбива — регистарот мора да се усогласи.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="wa-l-save"
          onclick="GF.WWF.wasteLineSave('${manifestId}')">${GF.t('save')}</button>
      </div>`;
    GF.openModal('wa-line-modal');
  };

  GF.WWF.wasteLineSave = (manifestId) => GF.once('wa-l-save', async () => {
    const qtyRaw = ((GF.$('wa-l-qty') || {}).value || '').trim();
    const kgRaw = ((GF.$('wa-l-kg') || {}).value || '').trim();
    const qty = qtyRaw === '' ? null : parseInt(qtyRaw, 10);
    const weight = kgRaw === '' ? null : parseFloat(kgRaw);
    // Checked here as well as server-side: the server's 422 is correct but this
    // is a form filled in many times an hour, and a blank-blank submit is a slip
    // rather than an error worth a round trip.
    if (qty == null && weight == null) {
      GF.toast(AL('Enter a plant count or a weight', 'Внесете број на растенија или тежина'), 'error');
      return;
    }
    try {
      await GF.API.wasteLineAdd(manifestId, {
        batch_id: ((GF.$('wa-l-batch') || {}).value || '') || null,
        plant_qty: qty, weight_kg: weight,
        note: ((GF.$('wa-l-note') || {}).value || '').trim() || null });
      GF.closeModal('wa-line-modal');
      GF.toast(AL('Added to the load', 'Додадено во товарот'), 'success');
      await GF.WWF.wasteDetail(manifestId);
      await GF.WWF.loadWaste();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── new manifest ──────────────────────────────────────────────────────────

  GF.WWF.wasteManifestForm = async () => {
    if (!canRecord()) return;
    let rooms = [];
    try { rooms = (await GF.API.facility()).rooms || []; }
    catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._ensureModal('wa-new-modal', '460px');
    GF.$('wa-new-modal-title').textContent = AL('New manifest', 'Нов манифест');
    const roomOpts = [{ v: '', label: AL('— no single origin room —', '— без определена соба —') }]
      .concat(rooms.map(r => ({ v: r.id, label: r.name })));
    GF.$('wa-new-modal-body').innerHTML = `
      <div class="field"><label>${AL('Manifest code', 'Код на манифест')}</label>
        <input id="wa-n-code" maxlength="64" placeholder="WM-2026-0731-01"></div>
      <div class="field"><label>${AL('Material', 'Материјал')}</label>
        ${GF.selectField('wa-n-type', { value: 'plant_material', title: AL('Material', 'Материјал'),
          options: WASTE_TYPES.map(t => ({ v: t.v, label: AL(t.en, t.mk) })) })}</div>
      <div class="field"><label>${AL('Reason', 'Причина')}</label>
        ${GF.selectField('wa-n-reason', { value: 'hlvd_eradication', title: AL('Reason', 'Причина'),
          options: REASONS.map(t => ({ v: t.v, label: AL(t.en, t.mk) })) })}</div>
      <div class="field"><label>${AL('Origin room', 'Соба на потекло')}</label>
        ${GF.selectField('wa-n-room', { value: '', title: AL('Origin room', 'Соба на потекло'), options: roomOpts })}</div>
      <div class="field"><label>${AL('Campaign', 'Кампања')}</label>
        <input id="wa-n-campaign" maxlength="120" value="hlvd-2026-07"></div>
      <div class="field"><label>${AL('Destination', 'Дестинација')}</label>
        <input id="wa-n-dest" maxlength="300"
          placeholder="${AL('e.g. licensed incinerator', 'пр. овластена инсинерација')}"></div>
      <div class="field"><label>${AL('Carrier', 'Превозник')}</label>
        <input id="wa-n-carrier" maxlength="200"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="wa-n-note" maxlength="1000"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'One manifest is one physical load, however many batches it empties. It opens as a draft: add the contents, then weigh and seal it.',
        'Еден манифест е еден физички товар, колку и батчови да опразни. Се отвора како нацрт: додадете содржина, потоа измерете и затворете.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="wa-n-save" onclick="GF.WWF.wasteManifestSave()">${GF.t('save')}</button>
      </div>`;
    GF.openModal('wa-new-modal');
    setTimeout(() => { const f = GF.$('wa-n-code'); if (f) f.focus(); }, 60);
  };

  GF.WWF.wasteManifestSave = () => GF.once('wa-n-save', async () => {
    const code = ((GF.$('wa-n-code') || {}).value || '').trim();
    if (!CODE_RE.test(code)) {
      GF.toast(AL('Manifest code must be 1–64 characters: letters, digits, _ / or -',
                  'Кодот мора да е 1–64 знаци: букви, цифри, _ / или -'), 'error');
      return;
    }
    try {
      const r = await GF.API.wasteManifestCreate({
        manifest_code: code,
        waste_type: (GF.$('wa-n-type') || {}).value,
        reason: (GF.$('wa-n-reason') || {}).value,
        origin_room_id: ((GF.$('wa-n-room') || {}).value || '') || null,
        campaign: ((GF.$('wa-n-campaign') || {}).value || '').trim() || null,
        destination: ((GF.$('wa-n-dest') || {}).value || '').trim() || null,
        carrier_name: ((GF.$('wa-n-carrier') || {}).value || '').trim() || null,
        note: ((GF.$('wa-n-note') || {}).value || '').trim() || null });
      GF.closeModal('wa-new-modal');
      GF.toast(AL('Manifest opened — add what is in the load',
                  'Манифестот е отворен — додадете што има во товарот'), 'success');
      await GF.WWF.loadWaste();
      // Straight into the contents: an empty manifest is the one state that
      // cannot progress, so leaving the operator on the list would strand them.
      if (r && r.id) await GF.WWF.wasteDetail(r.id);
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── the ladder ────────────────────────────────────────────────────────────

  GF.WWF.wasteSealForm = async (manifestId) => {
    if (!canRecord()) return;
    let m;
    try { m = await GF.API.wasteManifest(manifestId); }
    catch (e) { GF.toast(e.message, 'error'); return; }
    if (!m.line_count) {
      GF.toast(AL('Add what is in the load before sealing it',
                  'Додадете што има во товарот пред затворање'), 'error');
      await GF.WWF.wasteDetail(manifestId);
      return;
    }
    GF.WWF._ensureModal('wa-seal-modal', '440px');
    GF.$('wa-seal-modal-title').textContent = AL('Weigh and seal', 'Измери и затвори')
      + ' — ' + m.manifest_code;
    // The contents are restated here on purpose. Sealing cannot be undone and it
    // is what the witness signs against, so the numbers being fixed have to be
    // on screen at the moment of fixing them.
    GF.$('wa-seal-modal-body').innerHTML = `
      <div style="margin-bottom:10px">${AL(
        'Sealing fixes the contents of this manifest. Nothing can be added or removed afterwards, and this is the record the witness will sign against.',
        'Затворањето ја фиксира содржината. Потоа не може да се додава или отстранува, и ова е записот што сведокот го потпишува.')}</div>
      <div style="font-size:12px;margin-bottom:10px;padding:8px;border:1px solid var(--line);border-radius:6px">
        ${m.line_count} ${AL('line(s)', 'ставки')} ·
        ${m.plant_qty_total || 0} ${AL('plants', 'растенија')} ·
        ${kg(m.weight_kg_total)} ${AL('on the lines', 'на ставките')}
      </div>
      <div class="field"><label>${AL('Gross weight (kg)', 'Бруто тежина (kg)')}</label>
        <input id="wa-s-kg" type="number" min="0" step="0.1"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="wa-s-note" maxlength="1000"></div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-orange" id="wa-s-save"
          onclick="GF.WWF.wasteSealSave('${manifestId}')">${AL('Weigh &amp; seal', 'Измери и затвори')}</button>
      </div>`;
    GF.openModal('wa-seal-modal');
    setTimeout(() => { const f = GF.$('wa-s-kg'); if (f) f.focus(); }, 60);
  };

  GF.WWF.wasteSealSave = (manifestId) => GF.once('wa-s-save', async () => {
    const raw = ((GF.$('wa-s-kg') || {}).value || '').trim();
    const gross = raw === '' ? NaN : parseFloat(raw);
    if (!Number.isFinite(gross) || gross < 0) {
      GF.toast(AL('Enter the gross weight', 'Внесете бруто тежина'), 'error'); return;
    }
    try {
      await GF.API.wasteSeal(manifestId, {
        gross_weight_kg: gross,
        note: ((GF.$('wa-s-note') || {}).value || '').trim() || null });
      GF.closeModal('wa-seal-modal');
      GF.closeModal('wa-detail-modal');
      GF.toast(AL('Sealed — a QA witness is next', 'Затворено — следно е QA сведок'), 'success');
      await GF.WWF.loadWaste();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  GF.WWF.wasteWitnessForm = (manifestId) => {
    if (!canWitness()) return;
    GF.WWF._ensureModal('wa-wit-modal', '460px');
    GF.$('wa-wit-modal-title').textContent = AL('Witness the destruction', 'Потврди како сведок');
    // The two-person rule is stated here rather than discovered as a 409. The
    // server still enforces it; this is so the operator understands the refusal
    // as a control rather than as a bug.
    GF.$('wa-wit-modal-body').innerHTML = `
      <div style="margin-bottom:10px">${AL(
        'You are recording that you personally saw this sealed load. The signature goes against your name and cannot be undone.',
        'Потврдувате дека лично сте го видели затворениот товар. Потписот е на ваше име и не може да се врати.')}</div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:10px">${AL(
        'Whoever weighed and sealed the load cannot also witness it — that is the whole point of a witness, and the server refuses it.',
        'Оној што го измерил и затворил товарот не може да биде и сведок — тоа е смислата на сведокот, и серверот го одбива.')}</div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="wa-w-note" maxlength="1000"
          placeholder="${AL('e.g. 12 bags sealed, tag WM-04, loaded 14:20', 'пр. 12 вреќи затворени, ознака WM-04, натоварено 14:20')}"></div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-orange" id="wa-w-save"
          onclick="GF.WWF.wasteWitnessSave('${manifestId}')">${AL('I witnessed this', 'Бев сведок')}</button>
      </div>`;
    GF.openModal('wa-wit-modal');
  };

  GF.WWF.wasteWitnessSave = (manifestId) => GF.once('wa-w-save', async () => {
    try {
      await GF.API.wasteWitness(manifestId, {
        note: ((GF.$('wa-w-note') || {}).value || '').trim() || null });
      GF.closeModal('wa-wit-modal');
      GF.toast(AL('Witnessed', 'Потврдено'), 'success');
      await GF.WWF.loadWaste();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  GF.WWF.wasteDisposeForm = (manifestId) => {
    if (!canRecord()) return;
    GF.WWF._ensureModal('wa-disp-modal', '440px');
    GF.$('wa-disp-modal-title').textContent = AL('Record disposal', 'Запиши уништување');
    GF.$('wa-disp-modal-body').innerHTML = `
      <div style="margin-bottom:10px">${AL(
        'The carrier’s own reference closes the chain: this is what ties our record to theirs.',
        'Бројот од превозникот го затвора синџирот: тоа го врзува нашиот запис со нивниот.')}</div>
      <div class="field"><label>${AL('Carrier reference', 'Број од превозникот')}</label>
        <input id="wa-d-ref" maxlength="200" placeholder="CARRIER-2026-0731-004"></div>
      <div class="field"><label>${AL('Carrier (if not already recorded)', 'Превозник (ако не е запишан)')}</label>
        <input id="wa-d-carrier" maxlength="200"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="wa-d-note" maxlength="1000"></div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="wa-d-save"
          onclick="GF.WWF.wasteDisposeSave('${manifestId}')">${GF.t('save')}</button>
      </div>`;
    GF.openModal('wa-disp-modal');
    setTimeout(() => { const f = GF.$('wa-d-ref'); if (f) f.focus(); }, 60);
  };

  GF.WWF.wasteDisposeSave = (manifestId) => GF.once('wa-d-save', async () => {
    const ref = ((GF.$('wa-d-ref') || {}).value || '').trim();
    // A disposal with no external reference is a claim with nothing behind it —
    // the whole value of this rung is that it points at someone else's document.
    if (!ref) {
      GF.toast(AL('The carrier reference is required', 'Бројот од превозникот е задолжителен'), 'error');
      return;
    }
    try {
      await GF.API.wasteDispose(manifestId, {
        carrier_ref: ref,
        carrier_name: ((GF.$('wa-d-carrier') || {}).value || '').trim() || null,
        note: ((GF.$('wa-d-note') || {}).value || '').trim() || null });
      GF.closeModal('wa-disp-modal');
      GF.toast(AL('Disposal recorded — the chain is closed', 'Запишано — синџирот е затворен'), 'success');
      await GF.WWF.loadWaste();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // Same registration + read gate as the Cultivation and Decontamination
  // boards: every role above base USER may READ the register; recording and
  // witnessing are gated per action above.
  GF.WWF._registerFullPageView({
    key: 'waste', icon: 'trash',
    label: () => AL('Destruction', 'Уништување'),
    // Anchored on a key render.sidebar() itself emits, not on a sibling view:
    // _registerFullPageView wraps render.sidebar, so an anchor on another
    // registered view would depend on <script> order.
    insertBefore: 'mywork',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
