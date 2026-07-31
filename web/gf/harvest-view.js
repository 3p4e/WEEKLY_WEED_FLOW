/* harvest-view.js — the harvest / yield board and the IPM log behind its gate.

   The UI over migration 0051 + app/api/harvest.py. Cultivation's identity board
   says which plants exist and where; this board says what came off them, what it
   weighed wet and dry, and — because creating a harvest writes the
   `qc_batch_genealogy` edge `batch code -> lot code` — it is the point where
   cultivation finally joins the CoA chain.

   Read: every role above base USER. Recording the cut: cultivation crew +
   executives + ADMIN, plus QA (see below). Recording the yield, closing a lot and
   logging an IPM application: cultivation crew + executives + ADMIN.

   THE ONE THING THIS BOARD EXISTS TO MAKE VISIBLE — the pre-harvest interval.

   A grower should never meet the PHI as a 409 after filling in a cut form. So
   the harvest form asks the server for clearance FIRST and renders the answer
   above the fields: what was applied, how many days remain, the date it clears.
   The server still enforces it — this is the explanation, never the gate, and
   the two must not drift, so the view never computes an interval itself. It
   renders `blocking`, `days_remaining` and `clear` exactly as the server sends
   them.

   WHY THE OVERRIDE BOX ONLY APPEARS FOR QA. Releasing a blocked cut is a QA
   decision; a recorder sending a reason gets a 403. Showing the box to a
   recorder would teach them the control is a formality they can type past. When
   a recorder hits a block the form says who to go to instead.

   THE LADDER: wet -> dried -> closed, one action offered per lot, the next rung,
   for the same reason the destruction board does it — an ordered ladder rendered
   as independent buttons stops reading as ordered.

   Same monkey-patch/view pattern as the other *-view.js files; loads after
   worklog.js (uses AL(), GF.WWF._ensureModal, GF.selectField). */

(function () {
  GF.WWF._harv = {
    tab: 'lots',                 // 'lots' | 'yield' | 'ipm'
    lots: null, yield: null, ipm: null,
    loading: false, error: null,
    statusFilter: '',
    clearance: null,             // the clearance answer currently on the cut form
    // Bumped by harvestClearanceCheck on every call, initialized to 0 (not
    // left undefined) — `++undefined` is NaN, and NaN !== NaN is always true,
    // which would make the staleness guard reject even the first-ever call.
    _clearanceSeq: 0,
  };

  // Must stay in step with the CHECK constraints in migration 0051 and the
  // tuples in app/api/harvest.py.
  const CATEGORIES = [
    { v: 'biological', en: 'Biological',  mk: 'Биолошко' },
    { v: 'botanical',  en: 'Botanical',   mk: 'Растително' },
    { v: 'chemical',   en: 'Chemical',    mk: 'Хемиско' },
    { v: 'mechanical', en: 'Mechanical',  mk: 'Механичко' },
    { v: 'other',      en: 'Other',       mk: 'Друго' },
  ];
  const METHODS = [
    { v: 'spray',   en: 'Spray',   mk: 'Прскање' },
    { v: 'drench',  en: 'Drench',  mk: 'Залевање' },
    { v: 'fog',     en: 'Fog',     mk: 'Магла' },
    { v: 'dust',    en: 'Dust',    mk: 'Прашина' },
    { v: 'release', en: 'Release', mk: 'Испуштање' },
    { v: 'other',   en: 'Other',   mk: 'Друго' },
  ];
  const STATUS = {
    wet:    { en: 'Drying',  mk: 'Се суши',   color: '#2FD9D9' },
    dried:  { en: 'Dried',   mk: 'Исушено',   color: '#E0A73E' },
    closed: { en: 'Closed',  mk: 'Затворено', color: '#2BE8A0' },
  };

  const lbl = (list, v) => {
    const o = list.find(x => x.v === v);
    return o ? AL(o.en, o.mk) : v;
  };
  const stLbl = (s) => AL(STATUS[s]?.en || s, STATUS[s]?.mk || s);
  const stCol = (s) => (STATUS[s] || {}).color || 'var(--ink-3)';

  const role = () => (GF.API.user || {}).role;
  const canRecord = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'CU_MGR'].includes(role());
  // QA is in the cut set purely because the PHI release is written on the
  // harvest row — mirrors _CUTTERS in app/api/harvest.py.
  const canOverride = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'QA_MGR'].includes(role());
  const canCut = () => canRecord() || canOverride();
  // Mirrors HarvestIn.lot_code server-side (slashes allowed: lot dockets are
  // routinely written H/2026/0731-04).
  const LOT_RE = /^[A-Za-z0-9_/-]{1,64}$/;

  // Weights are grams on the wire (per-plant yield is unreadable in kg) and
  // shown in whichever unit the number is legible in. One formatter, so the
  // lot card and the yield table can never disagree about what 1250 means.
  const g = (n) => {
    if (n == null) return '—';
    return n >= 1000
      ? (Math.round(n / 10) / 100).toLocaleString() + ' kg'
      : (Math.round(n * 10) / 10).toLocaleString() + ' g';
  };
  const pct = (n) => (n == null ? '—' : n.toFixed(1) + '%');

  GF.WWF.loadHarvest = async () => {
    const st = GF.WWF._harv;
    st.loading = true; st.error = null;
    try {
      if (st.tab === 'yield') {
        st.yield = (await GF.API.harvestYield()).batches || [];
      } else if (st.tab === 'ipm') {
        st.ipm = (await GF.API.ipmApplications()).applications || [];
      } else {
        const q = st.statusFilter ? { status: st.statusFilter } : {};
        st.lots = (await GF.API.harvests(q)).harvests || [];
      }
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'harvest') GF.render.all();
  };

  // ── lot card ──────────────────────────────────────────────────────────────

  // Exactly ONE ladder action per lot, the next rung.
  const ladderAction = (h) => {
    if (!canRecord()) return '';
    if (h.status === 'wet') {
      return `<button class="btn btn-orange btn-sm" onclick="GF.WWF.harvestDryForm('${h.id}')">
        ${GF.icon('shield', 'icon', 'currentColor')}${AL('Record yield', 'Запиши принос')}</button>`;
    }
    if (h.status === 'dried') {
      return `<button class="btn btn-orange btn-sm" onclick="GF.WWF.harvestCloseForm('${h.id}')">
        ${GF.icon('check', 'icon', 'currentColor')}${AL('Close lot', 'Затвори лот')}</button>`;
    }
    return '';
  };

  const lotCard = (h) => {
    const overridden = !!h.phi_override_at;
    return `<div class="card" style="padding:12px;margin-bottom:10px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <strong style="flex:1">${GF.esc(h.lot_code)}</strong>
        <span style="color:${stCol(h.status)};font-size:12px">${GF.esc(stLbl(h.status))}</span>
      </div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:6px">
        ${GF.esc(h.batch_code || '—')}
        ${h.cultivar_code ? ' · ' + GF.esc(h.cultivar_code) : ''}
        ${h.room_name ? ' · ' + GF.esc(h.room_name) : ''}
        · ${GF.esc(String(h.harvested_on || ''))}
      </div>
      <div style="font-size:12px;margin-bottom:8px">
        ${h.plants_harvested} ${AL('plants', 'растенија')} ·
        ${AL('wet', 'свежо')} ${g(h.wet_weight_g)}
        ${h.dry_total_g != null ? ' · ' + AL('dry', 'суво') + ' ' + g(h.dry_total_g) : ''}
        ${h.moisture_loss_pct != null ? ' · ' + AL('loss ', 'загуба ') + pct(h.moisture_loss_pct) : ''}
        ${h.dry_flower_g_per_plant != null
          ? ' · ' + h.dry_flower_g_per_plant + ' ' + AL('g/plant', 'g/растение') : ''}
      </div>
      ${h.implausible_loss ? `<div style="color:#E0A73E;font-size:11px;margin-bottom:8px">${AL(
        'This lot’s moisture loss is outside the usual range. It is not refused — check the wet or dry figure was keyed correctly.',
        'Загубата на влага е надвор од вообичаениот опсег. Не е одбиено — проверете дали свежата или сувата бројка е внесена точно.')}</div>` : ''}
      ${overridden ? `<div style="color:#E5484D;font-size:11px;margin-bottom:8px">
        ${GF.icon('shield', 'icon', '#E5484D')}${AL(
          'Cut inside a pre-harvest interval, released by QA', 'Жнеано во период пред жетва, ослободено од QA')}:
        ${GF.esc(h.phi_override_reason || '')}</div>` : ''}
      ${h.note ? `<div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${GF.esc(h.note)}</div>` : ''}
      <div style="display:flex;gap:6px;flex-wrap:wrap">${ladderAction(h)}</div>
    </div>`;
  };

  // ── yield report ──────────────────────────────────────────────────────────

  // `unaccounted` from the API is plain arithmetic (planted minus harvested minus
  // destroyed), and on a LIVE batch that number is simply the plants still in the
  // room. Rendering it as a discrepancy on every healthy batch would bury the few
  // that are genuinely wrong, which is the only reason this report exists. So the
  // arithmetic is interpreted by phase HERE, in one predicate shared by the rows
  // and the banner — two independent predicates over the same data is how a row
  // and its summary come to disagree.
  const yieldState = (r) => {
    if (r.over_declared) {
      return { key: 'over', bad: true,
               label: AL('OVER-DECLARED', 'ПРЕКУМЕРНО'), color: '#E5484D' };
    }
    if (r.harvested_without_record) {
      return { key: 'norecord', bad: true,
               label: AL('harvested, no lot', 'ожнеано, без лот'), color: '#E5484D' };
    }
    if (r.phase === 'harvested') {
      if (r.unaccounted > 0) {
        return { key: 'short', bad: true,
                 label: AL(`${r.unaccounted} plant(s) unaccounted`,
                           `${r.unaccounted} растение(ја) неевидентирани`),
                 color: '#E0A73E' };
      }
      return { key: 'balanced', bad: false,
               label: AL('balanced', 'усогласено'), color: '#2BE8A0' };
    }
    if (r.phase === 'destroyed') {
      return { key: 'destroyed', bad: false,
               label: AL('destroyed', 'уништено'), color: 'var(--ink-3)' };
    }
    return { key: 'live', bad: false,
             label: AL('in production', 'во производство'), color: 'var(--ink-3)' };
  };

  const yieldRow = (r) => {
    const st = yieldState(r);
    return `<div style="display:flex;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line)${st.bad ? ';background:rgba(229,72,77,.06)' : ''}">
      <strong style="min-width:110px">${GF.esc(r.code || '—')}</strong>
      <span style="flex:1;color:var(--ink-3);font-size:11px">
        ${GF.esc(r.cultivar_code || '—')} · ${GF.esc(r.room_name || '—')} · ${GF.esc(r.phase)}</span>
      <span style="font-size:12px;min-width:90px;text-align:right">${
        r.plants_harvested}/${r.plant_count} <span style="color:var(--ink-3);font-size:11px">${
        AL('cut', 'жнеани')}</span></span>
      <span style="font-size:12px;min-width:90px;text-align:right">${g(r.dry_flower_g)}</span>
      <span style="font-size:12px;min-width:80px;text-align:right${
        r.implausible_loss ? ';color:#E0A73E' : ''}">${pct(r.moisture_loss_pct)}</span>
      <span style="min-width:160px;text-align:right;color:${st.color};font-size:11px">${
        GF.esc(st.label)}</span>
    </div>`;
  };

  // ── IPM log ───────────────────────────────────────────────────────────────

  const ipmRow = (a) => `<div style="display:flex;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid var(--line)">
      <strong style="min-width:140px">${GF.esc(a.product)}</strong>
      <span style="flex:1;color:var(--ink-3);font-size:11px">
        ${GF.esc(lbl(CATEGORIES, a.category))}${a.method ? ' · ' + GF.esc(lbl(METHODS, a.method)) : ''}
        · ${GF.esc(a.batch_code || a.room_name || '—')}
        ${a.active_ingredient ? ' · ' + GF.esc(a.active_ingredient) : ''}</span>
      <span style="font-size:11px;min-width:110px;text-align:right;color:var(--ink-3)">${
        GF.esc(String(a.applied_at || '').slice(0, 10))}</span>
      <span style="font-size:11px;min-width:150px;text-align:right;color:${
        a.rei_active ? '#E5484D' : 'var(--ink-3)'}">${
        a.rei_hours == null ? AL('no REI stated', 'без REI')
          : a.rei_active ? AL(`no entry until ${String(a.rei_until || '').slice(0, 16).replace('T', ' ')}`,
                              `без влез до ${String(a.rei_until || '').slice(0, 16).replace('T', ' ')}`)
            : AL(`REI ${a.rei_hours} h elapsed`, `REI ${a.rei_hours} ч. измина`)}</span>
      <span style="font-size:11px;min-width:130px;text-align:right">${
        a.phi_days == null ? `<span style="color:var(--ink-3)">${AL('no PHI stated', 'без PHI')}</span>`
          : AL(`PHI ${a.phi_days} d → ${a.phi_clear_on}`, `PHI ${a.phi_days} д. → ${a.phi_clear_on}`)}</span>
    </div>`;

  // ── view ──────────────────────────────────────────────────────────────────

  GF.views.harvest = () => {
    const st = GF.WWF._harv;
    const need = st.tab === 'yield' ? st.yield : st.tab === 'ipm' ? st.ipm : st.lots;
    if (!need && !st.loading && !st.error) GF.WWF.loadHarvest();

    const newBtn = st.tab === 'ipm'
      ? (canRecord()
        ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.ipmForm()">${GF.icon('plus', 'icon', 'currentColor')}${AL('Log application', 'Запиши третман')}</button>`
        : '')
      : (canCut()
        ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.harvestForm()">${GF.icon('plus', 'icon', 'currentColor')}${AL('Record a cut', 'Запиши жетва')}</button>`
        : '');
    const head = GF.viewHead
      ? GF.viewHead('harvest', 'harvest_sub', newBtn)
      : `<div class="view-head"><h2>${AL('Harvest', 'Жетва')}</h2>${newBtn}</div>`;
    const tabs = `<div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn btn-sm${st.tab === 'lots' ? ' btn-primary' : ''}"
        onclick="GF.WWF.harvestTab('lots')">${AL('Lots', 'Лотови')}</button>
      <button class="btn btn-sm${st.tab === 'yield' ? ' btn-primary' : ''}"
        onclick="GF.WWF.harvestTab('yield')">${AL('Yield', 'Принос')}</button>
      <button class="btn btn-sm${st.tab === 'ipm' ? ' btn-primary' : ''}"
        onclick="GF.WWF.harvestTab('ipm')">${AL('Plant protection', 'Заштита на растенија')}</button>
    </div>`;
    if (st.loading && !need) return head + tabs + `<div class="ntf-empty">${AL('Loading…', 'Вчитување…')}</div>`;
    if (st.error) return head + tabs + `<div class="ntf-empty">${GF.esc(st.error)}</div>`;

    if (st.tab === 'yield') {
      const rows = st.yield || [];
      if (!rows.length) {
        return head + tabs + `<div class="ntf-empty">${AL(
          'No batches yet.', 'Нема батчови.')}</div>`;
      }
      const bad = rows.filter(r => yieldState(r).bad);
      const closed = rows.filter(r => r.phase === 'harvested').length;
      const banner = bad.length
        ? `<div style="color:#E5484D;font-size:12px;margin-bottom:10px">${AL(
            `${bad.length} of ${closed} harvested batch(es) do not reconcile — a batch closed as harvested with no lot recorded leaves nothing for a certificate to be issued against.`,
            `${bad.length} од ${closed} ожнеани батч(ови) не се усогласуваат — батч затворен како ожнеан без евидентиран лот не остава ништо за издавање сертификат.`)}</div>`
        : closed
          ? `<div style="color:#2BE8A0;font-size:12px;margin-bottom:10px">${AL(
              `All ${closed} harvested batch(es) have their lots recorded.`,
              `Сите ${closed} ожнеани батч(ови) имаат евидентирани лотови.`)}</div>`
          : `<div style="color:var(--ink-3);font-size:12px;margin-bottom:10px">${AL(
              'No batch has been closed as harvested yet, so there is nothing to reconcile. Lots taken off open batches are shown below.',
              'Ниту еден батч не е затворен како ожнеан, па нема што да се усогласува. Лотовите од отворени батчови се прикажани подолу.')}</div>`;
      return head + tabs + banner + rows.map(yieldRow).join('');
    }

    if (st.tab === 'ipm') {
      const rows = st.ipm || [];
      if (!rows.length) {
        return head + tabs + `<div class="ntf-empty">${AL(
          'No applications logged. Every treatment recorded here carries its re-entry and pre-harvest intervals — the pre-harvest interval is what blocks a cut, so an unlogged treatment is a control that cannot act.',
          'Нема запишани третмани. Секој третман овде ги носи интервалите за повторен влез и пред жетва — интервалот пред жетва е тоа што ја блокира жетвата, па незапишан третман е контрола што не може да дејствува.')}</div>`;
      }
      return head + tabs + rows.map(ipmRow).join('');
    }

    const list = st.lots || [];
    const filter = `<div style="margin-bottom:10px;display:flex;gap:6px;flex-wrap:wrap">
      ${['', 'wet', 'dried', 'closed'].map(s =>
        `<button class="btn btn-sm${st.statusFilter === s ? ' btn-primary' : ''}"
          onclick="GF.WWF.harvestFilter('${s}')">${s ? GF.esc(stLbl(s)) : AL('All', 'Сите')}</button>`).join('')}
    </div>`;
    if (!list.length) {
      return head + tabs + filter + `<div class="ntf-empty">${AL(
        'No harvest lots. One lot is one pull off one batch — its code becomes the identifier a certificate is issued against, so it must be new and its own.',
        'Нема лотови. Еден лот е една жетва од еден батч — неговиот код станува идентификатор за издавање сертификат, па мора да е нов и свој.')}</div>`;
    }
    return head + tabs + filter + list.map(lotCard).join('');
  };

  GF.WWF.harvestTab = (tab) => {
    const st = GF.WWF._harv;
    if (st.tab === tab) return;
    st.tab = tab;
    GF.WWF.loadHarvest();
  };

  GF.WWF.harvestFilter = (status) => {
    const st = GF.WWF._harv;
    st.statusFilter = status;
    st.lots = null;
    GF.WWF.loadHarvest();
  };

  // ── the cut ───────────────────────────────────────────────────────────────

  GF.WWF.harvestForm = async () => {
    if (!canCut()) return;
    let batches = [];
    try { batches = (await GF.API.cultivationBatches(true)).batches || []; }
    catch (e) { GF.toast(e.message, 'error'); return; }
    // A terminal batch cannot be cut (the server refuses it), so it is not
    // offered — a picker that lists options the server will reject teaches
    // operators to expect errors.
    const open = batches.filter(b => !['harvested', 'destroyed'].includes(b.phase));
    if (!open.length) {
      GF.toast(AL('No open batch to harvest', 'Нема отворен батч за жетва'), 'error');
      return;
    }
    GF.WWF._harv.clearance = null;
    GF.WWF._ensureModal('hv-cut-modal', '480px');
    GF.$('hv-cut-modal-title').textContent = AL('Record a cut', 'Запиши жетва');
    const opts = open.map(b => ({
      v: b.id,
      label: `${b.code} · ${b.cultivar_code || b.strain || '—'} · ${b.plant_count} ${AL('pl', 'рас')}`,
      sub: b.room_name || '',
    }));
    GF.$('hv-cut-modal-body').innerHTML = `
      <div class="field"><label>${AL('Batch', 'Батч')}</label>
        ${GF.selectField('hv-c-batch', { value: opts[0].v, title: AL('Batch', 'Батч'),
          options: opts, searchable: true,
          // selectField renders a HIDDEN input and pickSel assigns .value
          // directly, firing no change event — onPick is the only hook that
          // runs, and it takes a FUNCTION (chooser.js calls cfg.onPick(v)).
          onPick: () => GF.WWF.harvestClearanceCheck() })}</div>
      <div id="hv-c-clearance" style="margin-bottom:10px"></div>
      <div class="field"><label>${AL('Lot code', 'Код на лот')}</label>
        <input id="hv-c-lot" maxlength="64" placeholder="H-GP072501-01"></div>
      <div class="field"><label>${AL('Plants cut', 'Ожнеани растенија')}</label>
        <input id="hv-c-plants" type="number" min="0" step="1" value="0"></div>
      <div class="field"><label>${AL('Wet weight (g)', 'Свежа тежина (g)')}</label>
        <input id="hv-c-wet" type="number" min="0" step="1"></div>
      <div class="field"><label>${AL('Date', 'Датум')}</label>
        <input id="hv-c-date" type="date"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="hv-c-note" maxlength="1000"></div>
      <div id="hv-c-override"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'The lot code becomes this crop’s identifier all the way to the certificate, so it must be new — reusing a batch or processing code is refused. Enter 0 plants for a partial pull that leaves the plants standing.',
        'Кодот на лотот станува идентификатор на овој род сè до сертификатот, па мора да е нов — повторна употреба на код од батч или преработка се одбива. Внесете 0 растенија за делумна берба што ги остава растенијата.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="hv-c-save" onclick="GF.WWF.harvestSave()">${GF.t('save')}</button>
      </div>`;
    GF.openModal('hv-cut-modal');
    // AWAITED, not fired and forgotten. The modal is already on screen, so this
    // costs nothing visible — and a harvestForm() promise that resolved before
    // the clearance box had rendered would be claiming the form was ready when
    // its most important field was still a spinner.
    await GF.WWF.harvestClearanceCheck();
  };

  // Renders the server's clearance answer above the form. Everything shown here
  // comes from the response verbatim — no interval is computed client-side, or
  // the board and the gate would drift apart.
  GF.WWF.harvestClearanceCheck = async () => {
    const box = GF.$('hv-c-clearance');
    const ovr = GF.$('hv-c-override');
    const batchId = ((GF.$('hv-c-batch') || {}).value || '');
    if (!box || !batchId) return;
    // A sequence token, not an abort controller: onPick fires on every batch
    // switch with no debounce, and two in-flight clearance lookups can resolve
    // out of order (the request for batch A can outlive a later request for
    // batch B). Without this, a stale response for a no-longer-selected batch
    // can overwrite the box a newer pick already populated. Bumped BEFORE the
    // await so this call's own token is fixed the instant it starts; checked
    // after every await so a call that is no longer the latest just stops
    // instead of rendering.
    const mySeq = ++GF.WWF._harv._clearanceSeq;
    box.innerHTML = `<div style="color:var(--ink-3);font-size:11px">${AL(
      'Checking pre-harvest intervals…', 'Проверка на интервали пред жетва…')}</div>`;
    let c;
    try { c = await GF.API.harvestClearance(batchId); }
    catch (e) {
      if (mySeq !== GF.WWF._harv._clearanceSeq) return; // a newer pick has since fired
      // A clearance lookup that fails must not silently look like "clear" —
      // that is the one wrong answer. Say it is unknown and let the server
      // refuse if it must.
      GF.WWF._harv.clearance = null;
      box.innerHTML = `<div style="color:#E0A73E;font-size:11px">${AL(
        'Could not check pre-harvest intervals', 'Не може да се проверат интервалите пред жетва')}: ${GF.esc(e.message)}</div>`;
      if (ovr) ovr.innerHTML = '';
      return;
    }
    if (mySeq !== GF.WWF._harv._clearanceSeq) return; // a newer pick has since fired
    GF.WWF._harv.clearance = c;
    const rei = (c.rei_active || []).length
      ? `<div style="color:#E0A73E;font-size:11px;margin-top:6px">${GF.icon('shield', 'icon', '#E0A73E')}${AL(
          'Re-entry restriction still active in this room — check before anyone goes in.',
          'Ограничување за влез сè уште е активно во оваа соба — проверете пред некој да влезе.')}
        ${(c.rei_active || []).map(r => GF.esc(`${r.product} · ${String(r.rei_until || '').slice(0, 16).replace('T', ' ')}`)).join('<br>')}</div>`
      : '';
    if (c.clear) {
      box.innerHTML = `<div style="color:#2BE8A0;font-size:11px">${GF.icon('check', 'icon', '#2BE8A0')}${AL(
        'Clear to harvest — no pre-harvest interval outstanding.',
        'Слободно за жетва — нема активен интервал пред жетва.')}</div>${rei}`;
      if (ovr) ovr.innerHTML = '';
      return;
    }
    const rows = (c.blocking || []).map(b => `<div style="font-size:11px;margin-top:4px">
        <strong>${GF.esc(b.product)}</strong>${b.active_ingredient ? ' (' + GF.esc(b.active_ingredient) + ')' : ''}
        · ${AL('PHI', 'PHI')} ${b.phi_days} ${AL('days', 'дена')}
        · ${AL('clears', 'слободно на')} ${GF.esc(String(b.phi_clear_on))}
        · <strong>${b.days_remaining} ${AL('day(s) to go', 'ден(а) преостануваат')}</strong>
      </div>`).join('');
    box.innerHTML = `<div style="border:1px solid #E5484D;border-radius:6px;padding:8px">
      <div style="color:#E5484D;font-size:12px">${GF.icon('shield', 'icon', '#E5484D')}${AL(
        'Inside a pre-harvest interval — this batch cannot be cut yet.',
        'Во интервал пред жетва — овој батч сè уште не смее да се жнее.')}</div>
      ${rows}</div>${rei}`;
    // The override box is QA-only. Showing it to a recorder would teach them the
    // control is a formality they can type past; the server answers 403 anyway.
    if (!ovr) return;
    ovr.innerHTML = canOverride()
      ? `<div class="field"><label>${AL('QA release reason', 'Причина за QA ослободување')}</label>
           <input id="hv-c-ovr" maxlength="500"
             placeholder="${AL('e.g. residue screen clear, ref QA-2026-114', 'пр. чист скрининг на резидуи, реф. QA-2026-114')}"></div>
         <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
           'Releasing a blocked cut is recorded against your name with this reason, permanently, on the lot.',
           'Ослободувањето на блокирана жетва се запишува на ваше име со оваа причина, трајно, на лотот.')}</div>`
      : `<div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
           'Only QA can release a cut inside a pre-harvest interval. Ask QA to record it if the crop has to come off.',
           'Само QA може да ослободи жетва во интервал пред жетва. Побарајте QA да ја запише ако родот мора да се собере.')}</div>`;
  };

  GF.WWF.harvestSave = () => GF.once('hv-c-save', async () => {
    const lot = ((GF.$('hv-c-lot') || {}).value || '').trim();
    if (!LOT_RE.test(lot)) {
      GF.toast(AL('Lot code must be 1–64 characters: letters, digits, _ / or -',
                  'Кодот мора да е 1–64 знаци: букви, цифри, _ / или -'), 'error');
      return;
    }
    const wetRaw = ((GF.$('hv-c-wet') || {}).value || '').trim();
    const wet = wetRaw === '' ? NaN : parseFloat(wetRaw);
    if (!Number.isFinite(wet) || wet < 0) {
      GF.toast(AL('Enter the wet weight', 'Внесете свежа тежина'), 'error');
      return;
    }
    const plantsRaw = ((GF.$('hv-c-plants') || {}).value || '').trim();
    const plants = plantsRaw === '' ? 0 : parseInt(plantsRaw, 10);
    if (!Number.isFinite(plants) || plants < 0) {
      GF.toast(AL('Enter the number of plants cut', 'Внесете број на ожнеани растенија'), 'error');
      return;
    }
    const reason = ((GF.$('hv-c-ovr') || {}).value || '').trim();
    try {
      await GF.API.harvestCreate({
        batch_id: (GF.$('hv-c-batch') || {}).value,
        lot_code: lot,
        plants_harvested: plants,
        wet_weight_g: wet,
        harvested_on: ((GF.$('hv-c-date') || {}).value || '') || null,
        note: ((GF.$('hv-c-note') || {}).value || '').trim() || null,
        phi_override_reason: reason || null });
      GF.closeModal('hv-cut-modal');
      GF.toast(reason
        ? AL('Cut recorded with a QA release', 'Жетвата е запишана со QA ослободување')
        : AL('Cut recorded — the lot is now in the genealogy',
             'Жетвата е запишана — лотот е во генеалогијата'),
        reason ? 'error' : 'success');
      await GF.WWF.loadHarvest();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── the yield ─────────────────────────────────────────────────────────────

  GF.WWF.harvestDryForm = async (harvestId) => {
    if (!canRecord()) return;
    let h;
    try { h = await GF.API.harvest(harvestId); }
    catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._ensureModal('hv-dry-modal', '440px');
    GF.$('hv-dry-modal-title').textContent = AL('Record yield', 'Запиши принос') + ' — ' + h.lot_code;
    // The wet weight is restated because it is the ceiling the three figures
    // below must fit under, and the server refuses the total if they do not.
    GF.$('hv-dry-modal-body').innerHTML = `
      <div style="font-size:12px;margin-bottom:10px;padding:8px;border:1px solid var(--line);border-radius:6px">
        ${AL('Came in wet at', 'Влезено свежо со')} <strong>${g(h.wet_weight_g)}</strong>
        · ${h.plants_harvested} ${AL('plants', 'растенија')}
      </div>
      <div class="field"><label>${AL('Dry flower (g)', 'Сув цвет (g)')}</label>
        <input id="hv-d-flower" type="number" min="0" step="1"
          value="${h.dry_flower_g != null ? h.dry_flower_g : ''}"></div>
      <div class="field"><label>${AL('Dry trim (g)', 'Сув трим (g)')}</label>
        <input id="hv-d-trim" type="number" min="0" step="1"
          value="${h.dry_trim_g != null ? h.dry_trim_g : ''}"></div>
      <div class="field"><label>${AL('Stems / waste (g)', 'Стебла / отпад (g)')}</label>
        <input id="hv-d-waste" type="number" min="0" step="1"
          value="${h.dry_waste_g != null ? h.dry_waste_g : ''}"></div>
      <div class="field"><label>${AL('Date out of the dry room', 'Датум на излез од сушара')}</label>
        <input id="hv-d-date" type="date"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="hv-d-note" maxlength="1000"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'The three figures together cannot exceed the wet weight — nothing gains mass in a dry room. You can correct these until the lot is closed.',
        'Трите бројки заедно не смеат да ја надминат свежата тежина — ништо не добива маса во сушара. Може да ги коригирате додека лотот не е затворен.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="hv-d-save"
          onclick="GF.WWF.harvestDrySave('${harvestId}')">${GF.t('save')}</button>
      </div>`;
    GF.openModal('hv-dry-modal');
    setTimeout(() => { const f = GF.$('hv-d-flower'); if (f) f.focus(); }, 60);
  };

  GF.WWF.harvestDrySave = (harvestId) => GF.once('hv-d-save', async () => {
    const num = (id) => {
      const raw = ((GF.$(id) || {}).value || '').trim();
      return raw === '' ? null : parseFloat(raw);
    };
    const flower = num('hv-d-flower');
    if (!Number.isFinite(flower) || flower < 0) {
      GF.toast(AL('Enter the dry flower weight', 'Внесете тежина на сув цвет'), 'error');
      return;
    }
    try {
      const r = await GF.API.harvestDry(harvestId, {
        dry_flower_g: flower,
        dry_trim_g: num('hv-d-trim'),
        dry_waste_g: num('hv-d-waste'),
        dried_on: ((GF.$('hv-d-date') || {}).value || '') || null,
        note: ((GF.$('hv-d-note') || {}).value || '').trim() || null });
      GF.closeModal('hv-dry-modal');
      GF.toast(r.implausible_loss
        ? AL(`Yield recorded — loss ${pct(r.moisture_loss_pct)} is outside the usual range, worth a check`,
             `Приносот е запишан — загубата ${pct(r.moisture_loss_pct)} е надвор од вообичаеното, вреди да се провери`)
        : AL(`Yield recorded — loss ${pct(r.moisture_loss_pct)}`,
             `Приносот е запишан — загуба ${pct(r.moisture_loss_pct)}`),
        r.implausible_loss ? 'error' : 'success');
      await GF.WWF.loadHarvest();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  GF.WWF.harvestCloseForm = (harvestId) => {
    if (!canRecord()) return;
    GF.WWF._ensureModal('hv-close-modal', '440px');
    GF.$('hv-close-modal-title').textContent = AL('Close lot', 'Затвори лот');
    GF.$('hv-close-modal-body').innerHTML = `
      <div style="margin-bottom:10px">${AL(
        'Closing fixes this lot’s yield. The weights cannot be corrected afterwards, and this is the figure the lot carries into processing and onto its certificate.',
        'Затворањето го фиксира приносот на овој лот. Тежините потоа не може да се коригираат, и ова е бројката што лотот ја носи во преработка и на сертификатот.')}</div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="hv-x-note" maxlength="1000"></div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-orange" id="hv-x-save"
          onclick="GF.WWF.harvestCloseSave('${harvestId}')">${AL('Close the lot', 'Затвори го лотот')}</button>
      </div>`;
    GF.openModal('hv-close-modal');
  };

  GF.WWF.harvestCloseSave = (harvestId) => GF.once('hv-x-save', async () => {
    try {
      await GF.API.harvestClose(harvestId, {
        note: ((GF.$('hv-x-note') || {}).value || '').trim() || null });
      GF.closeModal('hv-close-modal');
      GF.toast(AL('Lot closed', 'Лотот е затворен'), 'success');
      await GF.WWF.loadHarvest();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── IPM application ───────────────────────────────────────────────────────

  GF.WWF.ipmForm = async () => {
    if (!canRecord()) return;
    let rooms = [], batches = [];
    try {
      rooms = (await GF.API.facility()).rooms || [];
      batches = (await GF.API.cultivationBatches(true)).batches || [];
    } catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._ensureModal('hv-ipm-modal', '460px');
    GF.$('hv-ipm-modal-title').textContent = AL('Log application', 'Запиши третман');
    const roomOpts = [{ v: '', label: AL('— no room —', '— без соба —') }]
      .concat(rooms.map(r => ({ v: r.id, label: r.name })));
    const batchOpts = [{ v: '', label: AL('— whole room, not one batch —', '— цела соба, не еден батч —') }]
      .concat(batches.map(b => ({ v: b.id, label: `${b.code} · ${b.cultivar_code || '—'}`,
                                  sub: b.room_name || '' })));
    GF.$('hv-ipm-modal-body').innerHTML = `
      <div class="field"><label>${AL('Product', 'Производ')}</label>
        <input id="hv-i-product" maxlength="200"></div>
      <div class="field"><label>${AL('Active ingredient', 'Активна материја')}</label>
        <input id="hv-i-ai" maxlength="200"></div>
      <div class="field"><label>${AL('Category', 'Категорија')}</label>
        ${GF.selectField('hv-i-cat', { value: 'biological', title: AL('Category', 'Категорија'),
          options: CATEGORIES.map(t => ({ v: t.v, label: AL(t.en, t.mk) })) })}</div>
      <div class="field"><label>${AL('Method', 'Метод')}</label>
        ${GF.selectField('hv-i-method', { value: 'spray', title: AL('Method', 'Метод'),
          options: METHODS.map(t => ({ v: t.v, label: AL(t.en, t.mk) })) })}</div>
      <div class="field"><label>${AL('Room', 'Соба')}</label>
        ${GF.selectField('hv-i-room', { value: '', title: AL('Room', 'Соба'), options: roomOpts })}</div>
      <div class="field"><label>${AL('Batch (if only one)', 'Батч (ако е само еден)')}</label>
        ${GF.selectField('hv-i-batch', { value: '', title: AL('Batch', 'Батч'),
          options: batchOpts, searchable: true })}</div>
      <div class="field"><label>${AL('Dose', 'Доза')}</label>
        <input id="hv-i-dose" maxlength="120" placeholder="2 ml/L"></div>
      <div class="field"><label>${AL('Target pest', 'Целен штетник')}</label>
        <input id="hv-i-target" maxlength="200"></div>
      <div class="field"><label>${AL('Re-entry interval (hours)', 'Интервал за повторен влез (часови)')}</label>
        <input id="hv-i-rei" type="number" min="0" step="1"></div>
      <div class="field"><label>${AL('Pre-harvest interval (days)', 'Интервал пред жетва (денови)')}</label>
        <input id="hv-i-phi" type="number" min="0" step="1"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="hv-i-note" maxlength="1000"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'Name the room or the batch — an application scoped to neither cannot block a harvest or keep anyone out of a room, which is what this record is for. Leave an interval blank only if the product genuinely declares none.',
        'Наведете ја собата или батчот — третман без ниту едно од двете не може да блокира жетва ниту да задржи некој надвор од соба, а тоа е смислата на овој запис. Оставете интервал празен само ако производот навистина нема таков.')}
      </div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="hv-i-save" onclick="GF.WWF.ipmSave()">${GF.t('save')}</button>
      </div>`;
    GF.openModal('hv-ipm-modal');
    setTimeout(() => { const f = GF.$('hv-i-product'); if (f) f.focus(); }, 60);
  };

  GF.WWF.ipmSave = () => GF.once('hv-i-save', async () => {
    const product = ((GF.$('hv-i-product') || {}).value || '').trim();
    if (!product) {
      GF.toast(AL('Name the product', 'Внесете производ'), 'error'); return;
    }
    const room = ((GF.$('hv-i-room') || {}).value || '') || null;
    const batch = ((GF.$('hv-i-batch') || {}).value || '') || null;
    // Checked here as well as server-side: this form is filled in often, and a
    // scope-less submit is a slip rather than an error worth a round trip.
    if (!room && !batch) {
      GF.toast(AL('Pick the room or the batch this was applied to',
                  'Изберете соба или батч на кој е применето'), 'error');
      return;
    }
    const num = (id) => {
      const raw = ((GF.$(id) || {}).value || '').trim();
      return raw === '' ? null : parseInt(raw, 10);
    };
    try {
      await GF.API.ipmApply({
        product,
        active_ingredient: ((GF.$('hv-i-ai') || {}).value || '').trim() || null,
        category: (GF.$('hv-i-cat') || {}).value,
        method: (GF.$('hv-i-method') || {}).value,
        room_id: room, batch_id: batch,
        dose: ((GF.$('hv-i-dose') || {}).value || '').trim() || null,
        target: ((GF.$('hv-i-target') || {}).value || '').trim() || null,
        rei_hours: num('hv-i-rei'), phi_days: num('hv-i-phi'),
        note: ((GF.$('hv-i-note') || {}).value || '').trim() || null });
      GF.closeModal('hv-ipm-modal');
      GF.toast(AL('Application logged', 'Третманот е запишан'), 'success');
      await GF.WWF.loadHarvest();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // Same registration + read gate as the Cultivation, Decontamination and
  // Destruction boards: every role above base USER may READ; recording and
  // releasing are gated per action above.
  GF.WWF._registerFullPageView({
    key: 'harvest', icon: 'leaf',
    label: () => AL('Harvest', 'Жетва'),
    // Anchored on a key render.sidebar() itself emits, not on a sibling view:
    // _registerFullPageView wraps render.sidebar, so an anchor on another
    // registered view would depend on <script> order.
    insertBefore: 'mywork',
    guard: () => { const r = (GF.API.user || {}).role; return !!r && r !== 'USER'; },
  });
})();
