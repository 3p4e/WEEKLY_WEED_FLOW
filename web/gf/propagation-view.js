/* propagation-view.js — the mother-plant bank and clone runs: where a batch
   begins.

   Cultivation runs the plant from seed, import or clone up to the harvest cut
   (roles.py); this file is the clone end of that span, rendered as two tabs
   inside the cultivation board (cultivation-view.js): the MOTHER BANK the
   facility cuts from, and the CLONE RUNS that record a cutting event — which
   cultivar, from which mothers, how many cuttings, into which room, on which
   date — and which coded batch the cuttings became.

   Owner's description (2026-09-05): list the strains and phenotypes of mother
   plants, the number of mothers per strain, every mother with a unique ID and
   its own record — when it was last cut and how many generations of clones it
   has produced, which mother room it stands in and the pot or location within
   it, how old it is; cloning is initiated on a set date, by cultivation or QA,
   designating the cultivar and the propagation material's specification.

   Backend: app/api/propagation.py (migration 0065). Read: every role above
   base USER. The bank (register / edit a mother): cultivation manager +
   executives + ADMIN. Initiating or finishing a clone run: those PLUS the QA
   manager — the same set that registers a batch. Both mirror the server's
   _WRITERS / _INITIATORS; the server is authoritative.

   What the server derives, this view only shows: a mother's age, its last
   cut and its generations come from the runs it was cut in, never from a
   counter kept here. A mother with no recorded date has no age, not an age
   of zero; a mother never cut says "never", not "0 generations ago".

   Loads after cultivation-view.js (uses GF.WWF.cultSpecLine / cultSpecPanel,
   GF.WWF._ensureModal, GF.selectField, GF.dateField, GF.codeField). */

(function () {
  GF.WWF._prop = { mothers: null, byCultivar: null, runs: null, campaigns: null, products: null,
                   loading: false, error: null, showAll: false };

  const role = () => (GF.API.user || {}).role;
  // Mirrors _WRITERS / _INITIATORS in app/api/propagation.py.
  const canBank = () => ['ADMIN', 'OWNER', 'CEO', 'COO', 'CU_MGR', 'QA_MGR'].includes(role());
  const canInitiate = canBank;
  const today = () => GF.facilityToday();
  const fmtD = (iso) => (iso && GF.fmtDateHuman) ? GF.fmtDateHuman(iso) : (iso || '—');
  const CODE_RE = /^[A-Za-z0-9_-]{1,64}$/;

  // Must stay in step with the CHECK constraints in migration 0065.
  const MSTATUS = {
    active:    { en: 'Active',    mk: 'Активна',   color: '#2BE8A0' },
    retired:   { en: 'Retired',   mk: 'Повлечена', color: '#8296B4' },
    destroyed: { en: 'Destroyed', mk: 'Уништена',  color: '#E5484D' },
  };
  const RSTATUS = {
    started:      { en: 'Started',      mk: 'Започнато', color: '#2FD9D9' },
    transplanted: { en: 'Transplanted', mk: 'Пресадено', color: '#3FA34D' },
    failed:       { en: 'Failed',       mk: 'Неуспешно', color: '#E5484D' },
  };
  const sLbl = (map, k) => AL((map[k] || {}).en || k, (map[k] || {}).mk || k);
  const sCol = (map, k) => (map[k] || {}).color || 'var(--ink-3)';

  GF.WWF.loadPropagation = async () => {
    const st = GF.WWF._prop;
    st.loading = true; st.error = null;
    try {
      const [m, r, camps] = await Promise.all([
        GF.API.mothers(!st.showAll), GF.API.cloneRuns(!st.showAll),
        GF.API.campaigns ? GF.API.campaigns() : Promise.resolve({ campaigns: [] })]);
      st.mothers = m.mothers || [];
      st.byCultivar = m.by_cultivar || [];
      st.runs = r.runs || [];
      st.campaigns = camps.campaigns || [];
    } catch (e) { st.error = e.message; }
    st.loading = false;
    if (GF.state.view === 'cultivation') GF.render.all();
  };
  GF.WWF.propToggleAll = () => {
    const st = GF.WWF._prop;
    st.showAll = !st.showAll; st.mothers = null; st.runs = null;
    GF.WWF.loadPropagation();
  };

  // Age reads as days while it is days and as months once it is months; the
  // establishment date itself is always beside it.
  const ageLbl = (d) => d == null ? '—' : d < 60 ? `${d} ${AL('d', 'д.')}` : `${Math.round(d / 30.4)} ${AL('mo', 'мес.')}`;

  // ── the mother bank ───────────────────────────────────────────────────────

  const motherRow = (m) => `<tr>
      <td><strong>${GF.esc(m.code)}</strong>
        <div class="sub">${GF.esc(m.campaign_label)} · ${AL('gen.', 'ген.')} ${m.generation}${
          m.parent_code ? ` · ${AL('of', 'од')} ${GF.esc(m.parent_code)}` : ''}</div></td>
      <td>${GF.esc(m.phenotype || '—')}</td>
      <td>${GF.esc(m.room_name || AL('not placed', 'не е сместена'))}${m.position ? ` · ${GF.esc(m.position)}` : ''}</td>
      <td>${ageLbl(m.age_days)}${m.started_on ? `<div class="sub">${AL('since', 'од')} ${fmtD(m.started_on)}</div>` : ''}</td>
      <td>${m.last_cut_on ? fmtD(m.last_cut_on) : `<span class="sub">${AL('never', 'никогаш')}</span>`}</td>
      <td>${m.times_cut}${m.cuttings_total ? ` <span class="sub">(${m.cuttings_total} ${AL('cuttings', 'резници')})</span>` : ''}</td>
      <td>${m.tested && m.tested.n
        ? `<b>${Number(m.tested.avg).toFixed(2)} %</b> <span class="sub">${AL('of', 'од')} ${m.tested.n}</span>`
        : `<span class="sub">${AL('not tested yet', 'сè уште нетестирано')}</span>`}</td>
      <td><span style="color:${sCol(MSTATUS, m.status)}">${GF.esc(sLbl(MSTATUS, m.status))}</span></td>
      <td><button class="btn btn-sm" onclick="GF.WWF.motherPotency('${m.id}')">${AL('Potency', 'Потентност')}</button>${
        canBank() ? `<button class="btn btn-sm" onclick="GF.WWF.motherForm('${m.id}')">${AL('Edit', 'Уреди')}</button>` : ''}</td>
    </tr>`;

  const motherBank = () => {
    const st = GF.WWF._prop;
    const head = `<div class="row" style="gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
      <label style="display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--ink-3);cursor:pointer">
        <input type="checkbox" ${st.showAll ? 'checked' : ''} onchange="GF.WWF.propToggleAll()">
        ${AL('include retired and finished', 'вклучи повлечени и завршени')}</label>
      <div class="spacer"></div>
      ${canBank() ? `<button class="btn btn-sm" onclick="GF.WWF.campaignList()">${GF.icon('layers', 'icon')}${AL('Selection campaigns', 'Кампањи за селекција')}</button>` : ''}
      ${canBank() ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.motherForm()">${GF.icon('plus', 'icon', 'currentColor')}${AL('Register mother plant', 'Регистрирај мајка')}</button>` : ''}
    </div>`;
    if (st.error) return head + `<div class="ntf-empty">${GF.esc(st.error)}</div>`;
    if (!st.mothers) return head + `<div class="ntf-empty">${AL('Loading…', 'Вчитување…')}</div>`;
    if (!st.mothers.length) {
      return head + `<div class="ntf-empty">${AL(
        'No mother plants in the bank. A mother plant is registered per plant with its own ID, its cultivar and phenotype, the mother room and pot it stands in, and the date it was established.',
        'Нема мајки во банката. Мајката се регистрира поединечно со свој ID, сорта и фенотип, соба и саксија каде стои, и датум кога е воспоставена.')}</div>`;
    }
    const groups = (st.byCultivar || []).map(g => {
      const mine = st.mothers.filter(m => m.cultivar_id === g.cultivar_id);
      const phen = (g.phenotypes || []).map(p => `<span class="mw-attr">${GF.esc(p)}</span>`).join(' ');
      const prods = (g.products || []).map(p => `<span class="mw-attr">${GF.esc(p)}</span>`).join(' ');
      return `<div class="card" style="padding:12px;margin-bottom:10px">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
          <strong>${GF.esc(g.cultivar_code)} — ${GF.esc(g.cultivar_name)}</strong>
          <span style="color:#2BE8A0;font-size:12px">${g.active} ${AL('active', 'активни')}</span>
          ${g.total !== g.active ? `<span style="color:var(--ink-3);font-size:12px">${g.total} ${AL('total', 'вкупно')}</span>` : ''}
          ${prods} ${phen}
        </div>
        <div style="overflow-x:auto"><table class="pb-table"><thead><tr>
          <th>ID</th><th>${AL('Phenotype', 'Фенотип')}</th><th>${AL('Room · pot', 'Соба · саксија')}</th>
          <th>${AL('Age', 'Возраст')}</th><th>${AL('Last cut', 'Последно сечење')}</th>
          <th>${AL('Times cut', 'Пати сечена')}</th><th>${AL('Tested', 'Тестирано')}</th>
          <th>${AL('Status', 'Статус')}</th><th></th>
        </tr></thead><tbody>${mine.map(motherRow).join('')}</tbody></table></div>
      </div>`;
    }).join('');
    return head + groups;
  };

  // ── clone runs ────────────────────────────────────────────────────────────

  const runCard = (r) => {
    const mothers = (r.mothers || []).map(m =>
      `<span class="mw-attr">${GF.esc(m.code)}${m.cutting_no != null ? ` ·${String(m.cutting_no).padStart(2, '0')}` : ''}${
        m.cuttings != null ? ` <b>${m.cuttings}</b>` : ''}</span>`).join(' ');
    const spec = r.product_code
      ? `${GF.esc(r.product_code)}${r.product_status && r.product_status !== 'APPROVED' ? ` (${GF.esc(r.product_status)})` : ''}`
      : `<span style="color:var(--ink-3)">${AL('no product named', 'без наведен производ')}</span>`;
    const actions = [];
    if (canInitiate() && r.status === 'started') {
      actions.push(`<button class="btn btn-sm" onclick="GF.WWF.cloneRunFinish('${r.id}')">${GF.icon('forward', 'icon')}${AL('Transplanted / failed', 'Пресадено / неуспешно')}</button>`);
    }
    return `<div class="card" style="padding:12px;margin-bottom:10px">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap">
        <strong>${GF.esc(r.code || `${r.cultivar_code} · ${fmtD(r.started_on)}`)}</strong>
        <span style="color:var(--ink-3);font-size:12px">${GF.esc(r.cultivar_name || '')}</span>
        <span class="spacer"></span>
        <span style="color:${sCol(RSTATUS, r.status)};font-size:12px">${GF.esc(sLbl(RSTATUS, r.status))}${r.finished_on ? ` · ${fmtD(r.finished_on)}` : ''}</span>
      </div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:6px">
        ${AL('Initiated', 'Започнато')} ${fmtD(r.started_on)} · ${r.planned_count} ${AL('cuttings planned', 'планирани резници')}
        ${r.cuttings_total ? ` · ${r.cuttings_total} ${AL('taken', 'земени')}` : ''}
        · ${GF.esc(r.room_name || AL('no room', 'без соба'))}
        · ${r.batch_code ? `${AL('batch', 'батч')} <b>${GF.esc(r.batch_code)}</b>` : AL('no batch linked yet', 'сè уште без батч')}
      </div>
      <div style="font-size:12px;margin-bottom:6px">${AL('Mothers', 'Мајки')}: ${mothers || `<span style="color:var(--ink-3)">${AL('none named', 'не се наведени')}</span>`}</div>
      <div style="font-size:11px;margin-bottom:8px">${AL('Specification', 'Спецификација')}: ${spec}</div>
      ${r.note ? `<div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${GF.esc(r.note)}</div>` : ''}
      ${actions.length ? `<div style="display:flex;gap:6px;flex-wrap:wrap">${actions.join('')}</div>` : ''}
    </div>`;
  };

  const cloneRuns = () => {
    const st = GF.WWF._prop;
    const head = `<div class="row" style="gap:8px;align-items:center;margin-bottom:10px;flex-wrap:wrap">
      <label style="display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--ink-3);cursor:pointer">
        <input type="checkbox" ${st.showAll ? 'checked' : ''} onchange="GF.WWF.propToggleAll()">
        ${AL('include finished runs', 'вклучи завршени')}</label>
      <div class="spacer"></div>
      ${canInitiate() ? `<button class="btn btn-orange btn-sm" onclick="GF.WWF.cloneRunForm()">${GF.icon('layers', 'icon', 'currentColor')}${AL('Start clone run', 'Почни клонирање')}</button>` : ''}
    </div>`;
    if (st.error) return head + `<div class="ntf-empty">${GF.esc(st.error)}</div>`;
    if (!st.runs) return head + `<div class="ntf-empty">${AL('Loading…', 'Вчитување…')}</div>`;
    if (!st.runs.length) {
      return head + `<div class="ntf-empty">${AL(
        'No clone runs. A clone run is initiated on a set date for one cultivar: which mother plants were cut, how many cuttings, into which room — and, once they root, which registered batch they became.',
        'Нема клонирања. Клонирањето се започнува на одреден датум за една сорта: кои мајки се сечени, колку резници, во која соба — и, кога ќе се вкоренат, кој регистриран батч станале.')}</div>`;
    }
    return head + st.runs.map(runCard).join('');
  };

  GF.WWF.propagationSection = (tab) => {
    const st = GF.WWF._prop;
    if (!st.mothers && !st.loading && !st.error) GF.WWF.loadPropagation();
    return tab === 'mothers' ? motherBank() : cloneRuns();
  };

  // ── shared form pieces ────────────────────────────────────────────────────

  const cultivarsLoaded = async () => {
    const c = GF.WWF._cult || {};
    if (c.cultivars) return c.cultivars.filter(x => x.is_active);
    const r = await GF.API.cultivars();
    return (r.cultivars || []).filter(x => x.is_active);
  };
  // Rooms of the kind the form is about come first; every active room stays
  // choosable, because the register may not carry kinds for every room yet.
  const roomOpts = (rooms, kinds, none) => {
    const sorted = rooms.slice().sort((a, b) => (kinds.includes(b.kind) ? 1 : 0) - (kinds.includes(a.kind) ? 1 : 0));
    const opts = sorted.map(r => ({ v: r.id, label: r.name, sub: r.kind }));
    return none ? [{ v: '', label: none }].concat(opts) : opts;
  };

  // ── register / edit a mother plant ────────────────────────────────────────

  // ── selection campaigns ──────────────────────────────────────────────────
  // The S<n> in a mother's id. Numbered facility-wide by the server, so the
  // form asks only what the campaign WAS, never what to call it.

  const MATERIALS = [
    { v: 'seeds', en: 'From seeds', mk: 'Од семе' },
    { v: 'clones', en: 'From new clones', mk: 'Од нови клонови' },
    { v: 'phenotypes', en: 'Between phenotypes', mk: 'Помеѓу фенотипови' },
  ];

  GF.WWF.campaignList = async () => {
    const st = GF.WWF._prop;
    if (!st.campaigns) { try { st.campaigns = (await GF.API.campaigns()).campaigns || []; } catch (e) { GF.toast(e.message, 'error'); return; } }
    GF.WWF._ensureModal('sc-modal', '520px');
    GF.$('sc-modal-title').textContent = AL('Selection campaigns', 'Кампањи за селекција');
    const rows = st.campaigns.length ? st.campaigns.map(c => `<tr>
        <td><strong>${GF.esc(c.label)}</strong></td>
        <td>${fmtD(c.started_on)}</td>
        <td>${GF.esc(AL((MATERIALS.find(x => x.v === c.material) || {}).en || c.material,
                        (MATERIALS.find(x => x.v === c.material) || {}).mk || c.material))}</td>
        <td>${GF.esc(c.cultivar_code || '—')}</td>
        <td>${c.mothers_count} ${AL('mothers', 'мајки')}</td>
        <td>${GF.esc(c.description || '')}</td></tr>`).join('')
      : `<tr><td colspan="6" style="color:var(--ink-3)">${AL(
          'No campaigns yet. A campaign is one selection event — from seeds, from new clones, or between phenotypes — and every mother selected in it carries its number.',
          'Нема кампањи. Кампањата е еден настан на селекција — од семе, од нови клонови или помеѓу фенотипови — и секоја мајка од неа го носи нејзиниот број.')}</td></tr>`;
    GF.$('sc-modal-body').innerHTML = `
      <div style="overflow-x:auto"><table class="pb-table"><thead><tr>
        <th>#</th><th>${AL('Started', 'Започната')}</th><th>${AL('Material', 'Материјал')}</th>
        <th>${AL('Strain', 'Сорта')}</th><th>${AL('Mothers', 'Мајки')}</th><th></th>
      </tr></thead><tbody>${rows}</tbody></table></div>
      ${canBank() ? `<div class="row" style="gap:10px;margin-top:10px"><div class="spacer"></div>
        <button class="btn btn-orange btn-sm" onclick="GF.WWF.campaignForm()">${GF.icon('plus', 'icon', 'currentColor')}${AL('New campaign', 'Нова кампања')}</button></div>` : ''}`;
    GF.openModal('sc-modal');
  };

  GF.WWF.campaignForm = async () => {
    if (!canBank()) return;
    let cultivars = [];
    try { cultivars = await cultivarsLoaded(); } catch (e) { cultivars = []; }
    GF.WWF._ensureModal('scf-modal', '460px');
    GF.$('scf-modal-title').textContent = AL('New selection campaign', 'Нова кампања за селекција');
    GF.$('scf-modal-body').innerHTML = `
      <div class="field"><label>${AL('Started on', 'Започната на')}</label>
        ${GF.dateField('sc-date', { value: today(), clearable: false })}</div>
      <div class="field"><label>${AL('Material selected from', 'Материјал')}</label>
        ${GF.selectField('sc-material', { value: 'seeds', title: AL('Material', 'Материјал'),
          options: MATERIALS.map(x => ({ v: x.v, label: AL(x.en, x.mk) })) })}</div>
      <div class="field"><label>${AL('Strain (if the campaign is one strain)', 'Сорта (ако кампањата е за една сорта)')}</label>
        ${GF.selectField('sc-cultivar', { value: '', title: AL('Strain', 'Сорта'), searchable: true,
          options: [{ v: '', label: AL('— several strains —', '— повеќе сорти —') }]
            .concat(cultivars.map(c => ({ v: c.id, label: c.code + ' — ' + c.name }))) })}</div>
      <div class="field"><label>${AL('Description', 'Опис')}</label><input id="sc-desc" maxlength="300"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="sc-note" maxlength="500"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'The number is assigned by the facility’s running count — S1, S2, S3 — whatever the strain, and every mother selected in this campaign carries it in its id.',
        'Бројот се доделува по редослед во фабриката — S1, S2, S3 — без разлика на сортата, и секоја мајка од оваа кампања го носи во својот ID.')}</div>
      <div class="row" style="gap:10px"><div class="spacer"></div>
        <button class="btn btn-primary" id="sc-save" onclick="GF.WWF.campaignSave()">${GF.t('save')}</button></div>`;
    GF.openModal('scf-modal');
  };

  GF.WWF.campaignSave = () => GF.once('sc-save', async () => {
    const val = (id) => ((GF.$(id) || {}).value || '').trim();
    try {
      await GF.API.campaignCreate({
        started_on: val('sc-date') || null,
        material: val('sc-material') || 'seeds',
        cultivar_id: val('sc-cultivar') || null,
        description: val('sc-desc') || null,
        note: val('sc-note') || null });
      GF.closeModal('scf-modal');
      GF.toast(AL('Campaign opened', 'Кампањата е отворена'), 'success');
      GF.WWF._prop.campaigns = null;
      await GF.WWF.loadPropagation();
      if (GF.$('sc-modal')) await GF.WWF.campaignList();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── register / edit a mother plant ────────────────────────────────────────
  // The id is composed from segments, so the form offers the segments and the
  // server builds GP26_S1M03-2_020 from them. The preview shows what will be
  // written before it is written.

  const productOpts = (products) => products.map(p => ({
    v: p.id, label: `${p.product_code} — THC ${p.grade}`,
    sub: `${Number(p.window_min).toFixed(2)}–${Number(p.window_max).toFixed(2)} %` }));

  GF.WWF.motherCodePreview = (acr, grade, seq, motherNo, gen, stockNo) => {
    const g = String(grade).replace(/\.0+$/, '');
    return `${acr}${g}_S${seq}M${String(motherNo).padStart(2, '0')}-${gen}_${String(stockNo).padStart(3, '0')}`;
  };

  GF.WWF.motherForm = async (motherId) => {
    if (!canBank()) return;
    const st = GF.WWF._prop;
    const m = motherId ? (st.mothers || []).find(x => x.id === motherId) : null;
    if (motherId && !m) return;
    let products = [], rooms = [], campaigns = [];
    try {
      products = (await GF.API.qcProducts({ status: 'APPROVED' })) || [];
      rooms = (await GF.API.facility()).rooms || [];
      campaigns = (await GF.API.campaigns()).campaigns || [];
    } catch (e) { GF.toast(e.message, 'error'); return; }
    if (!m && !products.length) {
      GF.toast(AL('No approved product specification yet — import and approve the ImB catalogue first',
                  'Нема одобрена спецификација — прво внесете и одобрете го ImB каталогот'), 'error');
      return;
    }
    if (!m && !campaigns.length) {
      GF.toast(AL('Open a selection campaign first — a mother belongs to one',
                  'Прво отворете кампања за селекција — мајката припаѓа на една'), 'error');
      GF.WWF.campaignForm();
      return;
    }
    GF.WWF._motherCtx = { products, campaigns, mothers: st.mothers || [] };
    GF.WWF._ensureModal('mb-modal', '520px');
    GF.$('mb-modal-title').textContent = m
      ? AL('Mother plant', 'Мајка') + ' — ' + m.code
      : AL('Register mother plant', 'Регистрирај мајка');
    const identity = m
      ? `<div style="font-size:12px;color:var(--ink-3);margin-bottom:10px">${GF.esc(m.product_code)} · ${GF.esc(m.campaign_label)} ·
           ${AL('generation', 'генерација')} ${m.generation} · ID <b>${GF.esc(m.code)}</b></div>
         <div class="field"><label>${AL('Status', 'Статус')}</label>
           ${GF.selectField('mb-status', { value: m.status, title: AL('Status', 'Статус'),
             options: Object.keys(MSTATUS).map(k => ({ v: k, label: sLbl(MSTATUS, k), color: MSTATUS[k].color })) })}</div>`
      : `<div class="field"><label>${AL('Specification strain — the product it belongs to', 'Спецификациска сорта — производот')}</label>
           ${GF.selectField('mb-product', { value: products[0].id, title: AL('Product', 'Производ'), searchable: true,
             options: productOpts(products), onPick: () => GF.WWF._motherSync() })}</div>
         <div class="row" style="gap:10px">
           <div class="field" style="flex:2"><label>${AL('Selection campaign', 'Кампања')}</label>
             ${GF.selectField('mb-campaign', { value: campaigns[0].id, title: AL('Campaign', 'Кампања'),
               options: campaigns.map(c => ({ v: c.id, label: c.label, sub: fmtD(c.started_on) })),
               onPick: () => GF.WWF._motherSync() })}</div>
           <div class="field" style="flex:1"><label>${AL('Mother №', 'Мајка бр.')}</label>
             <input id="mb-mno" type="number" min="1" max="99" step="1" oninput="GF.WWF._motherSync()"></div>
           <div class="field" style="flex:1"><label>${AL('Generation', 'Генерација')}</label>
             <input id="mb-gen" type="number" min="1" max="9" step="1" value="1" oninput="GF.WWF._motherSync()"></div>
           <div class="field" style="flex:1"><label>${AL('In stock №', 'Во фонд бр.')}</label>
             <input id="mb-stock" type="number" min="1" max="999" step="1" oninput="GF.WWF._motherSync()"></div>
         </div>
         <div class="field" id="mb-parent-wrap" style="display:none"><label>${AL('Cut from mother (if known)', 'Сечена од мајка (ако е позната)')}</label>
           <div id="mb-parent-sel"></div></div>
         <div class="field"><label>${AL('Plant ID', 'ID на растение')}</label>
           <div id="mb-preview" class="mb-preview">—</div>
           <div style="color:var(--ink-3);font-size:11px;margin-top:3px">${AL(
             'Strain and grade · selection campaign · mother number · generation · number in stock. The facility’s numbers — the app only offers the next free one.',
             'Сорта и степен · кампања · број на мајка · генерација · број во фонд. Броевите се на фабриката — апликацијата само го предлага следниот слободен.')}</div></div>`;
    GF.$('mb-modal-body').innerHTML = `
      ${identity}
      <div class="field"><label>${AL('Phenotype (if known)', 'Фенотип (ако е познат)')}</label>
        <input id="mb-pheno" maxlength="120" value="${GF.esc((m || {}).phenotype || '')}"></div>
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1"><label>${AL('Mother room', 'Соба за мајки')}</label>
          ${GF.selectField('mb-room', { value: (m || {}).room_id || '', title: AL('Room', 'Соба'),
            options: roomOpts(rooms, ['mother'], AL('— not placed —', '— не е сместена —')) })}</div>
        <div class="field" style="flex:1"><label>${AL('Pot / location in room', 'Саксија / место во собата')}</label>
          <input id="mb-pos" maxlength="120" value="${GF.esc((m || {}).position || '')}" placeholder="${AL('e.g. pot 12, bench B', 'пр. саксија 12, маса B')}"></div>
      </div>
      <div class="field"><label>${AL('Established on (age counts from here)', 'Воспоставена на (возраста се смета од тука)')}</label>
        ${GF.dateField('mb-started', { value: m ? (m.started_on || '') : today(), clearable: true })}</div>
      <div class="field"><label>${AL('Source (seed lot, import, clone of…)', 'Потекло (семе, увоз, клон од…)')}</label>
        <input id="mb-source" maxlength="200" value="${GF.esc((m || {}).source || '')}"></div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="mb-note" maxlength="500" value="${GF.esc((m || {}).note || '')}"></div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="mb-save" onclick="GF.WWF.motherSave(${m ? `'${m.id}'` : ''})">${GF.t('save')}</button>
      </div>`;
    GF.openModal('mb-modal');
    if (!m) await GF.WWF._motherSync();
  };

  // Asks the server for the next free numbers whenever a segment changes, and
  // shows the id that will be written. A number the user typed is kept.
  GF.WWF._motherSync = async () => {
    const ctx = GF.WWF._motherCtx || {};
    const pid = (GF.$('mb-product') || {}).value;
    const cid = (GF.$('mb-campaign') || {}).value;
    const prod = (ctx.products || []).find(p => p.id === pid);
    const camp = (ctx.campaigns || []).find(c => c.id === cid);
    if (!prod || !camp) return;
    const gen = parseInt(((GF.$('mb-gen') || {}).value || '1'), 10) || 1;
    const typedM = ((GF.$('mb-mno') || {}).value || '').trim();
    const typedS = ((GF.$('mb-stock') || {}).value || '').trim();
    let next = null;
    try {
      next = await GF.API.motherNextCode({ product_id: pid, campaign_id: cid, generation: gen,
                                           ...(typedM ? { mother_no: typedM } : {}) });
    } catch (_) { next = null; }
    // The pick may have changed while the request was out.
    if (((GF.$('mb-product') || {}).value) !== pid || ((GF.$('mb-campaign') || {}).value) !== cid) return;
    const mno = typedM ? parseInt(typedM, 10) : (next ? next.mother_no : 1);
    const sno = typedS ? parseInt(typedS, 10) : (next ? next.next_stock_no : 1);
    const mEl = GF.$('mb-mno'), sEl = GF.$('mb-stock');
    if (mEl && !typedM) mEl.placeholder = String(mno);
    if (sEl && !typedS) sEl.placeholder = String(sno);
    const prev = GF.$('mb-preview');
    if (prev) {
      prev.textContent = GF.WWF.motherCodePreview(
        prod.product_code.split('_')[0], prod.grade, camp.seq, mno, gen, sno);
    }
    // A second-generation mother may name the plant it was cut from.
    const wrap = GF.$('mb-parent-wrap'), sel = GF.$('mb-parent-sel');
    if (wrap && sel) {
      if (gen > 1) {
        const eligible = (ctx.mothers || []).filter(x => x.product_id === pid && x.generation === gen - 1);
        wrap.style.display = '';
        sel.innerHTML = GF.selectField('mb-parent', { value: '', title: AL('Mother', 'Мајка'),
          options: [{ v: '', label: AL('— not in the bank —', '— не е во банката —') }]
            .concat(eligible.map(x => ({ v: x.id, label: x.code }))) });
      } else { wrap.style.display = 'none'; sel.innerHTML = ''; }
    }
  };

  GF.WWF.motherSave = (motherId) => GF.once('mb-save', async () => {
    const val = (id) => ((GF.$(id) || {}).value || '').trim();
    const num = (id) => { const v = val(id); return v === '' ? null : parseInt(v, 10); };
    const body = {
      phenotype: val('mb-pheno') || null,
      room_id: val('mb-room') || null,
      position: val('mb-pos') || null,
      started_on: val('mb-started') || null,
      source: val('mb-source') || null,
      note: val('mb-note') || null,
    };
    try {
      if (motherId) {
        body.status = val('mb-status') || undefined;
        await GF.API.motherPatch(motherId, body);
      } else {
        await GF.API.motherCreate({
          ...body,
          product_id: val('mb-product'),
          campaign_id: val('mb-campaign'),
          mother_no: num('mb-mno'),
          generation: num('mb-gen') || 1,
          stock_no: num('mb-stock'),
          parent_id: val('mb-parent') || null });
      }
      GF.closeModal('mb-modal');
      GF.toast(motherId ? AL('Mother plant updated', 'Мајката е ажурирана')
                        : AL('Mother plant registered', 'Мајката е регистрирана'), 'success');
      GF.WWF._cult.tab = 'mothers';
      await GF.WWF.loadPropagation();
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── what this mother's specification strain has tested ───────────────────

  GF.WWF.motherPotency = async (motherId) => {
    let body;
    try { body = await GF.API.motherPotency(motherId); }
    catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._ensureModal('mp-modal', '520px');
    GF.$('mp-modal-title').textContent = AL('Potency tested', 'Тестирана потентност') + ' — ' + body.code;
    const stat = (s, label, none) => `<div style="margin-bottom:10px">
      <div style="font-size:12px;margin-bottom:4px"><strong>${label}</strong></div>
      ${s.n ? `<div style="font-size:13px">${AL('average', 'просек')} <b>${Number(s.avg).toFixed(2)} %</b>
          <span style="color:var(--ink-3)">· ${s.n} ${AL('results', 'резултати')} · ${Number(s.min).toFixed(2)}–${Number(s.max).toFixed(2)} %</span></div>
        <div style="overflow-x:auto;margin-top:4px"><table class="pb-table"><tbody>${s.values.map(v =>
          `<tr><td>${GF.esc(v.coq_number || '—')}</td><td>${GF.esc(v.lot_code || '—')}</td>
           <td><b>${Number(v.total_thc).toFixed(2)} %</b></td><td>${fmtD(v.on)}</td></tr>`).join('')}</tbody></table></div>`
        : `<div style="color:var(--ink-3);font-size:12px">${none}</div>`}</div>`;
    GF.$('mp-modal-body').innerHTML = `
      <div style="font-size:12px;color:var(--ink-3);margin-bottom:10px">${GF.esc(body.product_code)} ·
        ${AL('window', 'прозорец')} ${Number(body.window[0]).toFixed(2)}–${Number(body.window[1]).toFixed(2)} %</div>
      ${stat(body.product, AL('This specification strain', 'Оваа спецификациска сорта'),
             AL('No approved Certificate of Quality carries a Total Δ9-THC for this product yet.',
                'Сè уште нема одобрен сертификат со вкупен Δ9-THC за овој производ.'))}
      ${stat(body.traced, AL('Traceable to this plant', 'Следливо до ова растение'),
             AL('Nothing yet links a tested lot back to this mother — it needs the clone run to name its batch and the harvest to record its lot.',
                'Сè уште ништо не поврзува тестирана серија со оваа мајка — потребно е клонирањето да го наведе батчот и жетвата да ја запише серијата.'))}`;
    GF.openModal('mp-modal');
  };

  // ── start a clone run ─────────────────────────────────────────────────────

  GF.WWF.cloneRunForm = async () => {
    if (!canInitiate()) return;
    let cultivars = [], rooms = [], mothers = [], batches = [];
    try {
      cultivars = await cultivarsLoaded();
      rooms = (await GF.API.facility()).rooms || [];
      mothers = ((await GF.API.mothers(true)).mothers || []);
      batches = ((await GF.API.cultivationBatches(true)).batches || []);
    } catch (e) { GF.toast(e.message, 'error'); return; }
    if (!cultivars.length) {
      GF.toast(AL('Register a cultivar first — a clone run is one cultivar', 'Прво регистрирајте сорта — клонирањето е една сорта'), 'error');
      return;
    }
    GF.WWF._cloneRunCtx = { cultivars, rooms, mothers, batches };
    GF.WWF._ensureModal('cr-modal', '560px');
    GF.$('cr-modal-title').textContent = AL('Start clone run', 'Почни клонирање');
    GF.$('cr-modal-body').innerHTML = `
      <div class="field"><label>${AL('Cultivar', 'Сорта')}</label>
        ${GF.selectField('cr-cultivar', { value: cultivars[0].id, title: AL('Cultivar', 'Сорта'), searchable: true,
          options: cultivars.map(c => ({ v: c.id, label: c.code + ' — ' + c.name, sub: GF.WWF.cultSpecLine(c) })),
          onPick: () => GF.WWF._cloneRunSync() })}</div>
      <div class="field"><label>${AL('Propagation material specification', 'Спецификација на материјалот')}</label>
        <div id="cr-product-wrap"></div>
        <div id="cr-spec"></div></div>
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1"><label>${AL('Date of cloning initiation', 'Датум на почеток на клонирање')}</label>
          ${GF.dateField('cr-date', { value: today(), clearable: false })}</div>
        <div class="field" style="flex:1"><label>${AL('Cuttings planned', 'Планирани резници')}</label>
          <input id="cr-count" type="number" min="0" max="100000" step="1" placeholder="2000"></div>
      </div>
      <div class="field"><label>${AL('Mother plants cut (with cuttings taken from each)', 'Сечени мајки (со резници од секоја)')}</label>
        <div id="cr-mothers" class="pb-mlist"></div></div>
      <div class="field"><label>${AL('Clone room', 'Соба за клонови')}</label>
        ${GF.selectField('cr-room', { value: '', title: AL('Room', 'Соба'),
          options: roomOpts(rooms, ['clone', 'nursery'], AL('— not yet placed —', '— сè уште не е сместено —')) })}</div>
      <div class="field"><label>${AL('Feeds registered batch (if already registered)', 'За регистриран батч (ако е веќе регистриран)')}</label>
        <div id="cr-batch-wrap"></div></div>
      <div class="row" style="gap:10px">
        <div class="field" style="flex:1"><label>${AL('Run code (optional)', 'Код на клонирање (опционално)')}</label>
          <input id="cr-code" maxlength="64"></div>
        <div class="field" style="flex:1"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
          <input id="cr-note" maxlength="500"></div>
      </div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'The run records the cutting event and snapshots the cultivar’s approved product specification. Leave a mother’s cuttings blank if not counted per mother — blank means "not counted", not zero.',
        'Клонирањето го запишува сечењето и ја зачувува одобрената спецификација на сортата. Оставете ги резниците на мајка празни ако не се броени по мајка — празно значи „не е броено“, не нула.')}</div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="cr-save" onclick="GF.WWF.cloneRunSave()">${AL('Start run', 'Започни')}</button>
      </div>`;
    GF.openModal('cr-modal');
    GF.WWF._cloneRunSync();
    setTimeout(() => { const f = GF.$('cr-count'); if (f) f.focus(); }, 60);
  };

  // On a cultivar pick: its specification, its active mothers, its open
  // batches. Same onPick-only rule as every chooser-driven form.
  GF.WWF._cloneRunSync = () => {
    const ctx = GF.WWF._cloneRunCtx || {};
    const id = (GF.$('cr-cultivar') || {}).value;
    const cv = (ctx.cultivars || []).find(c => c.id === id);
    const pw = GF.$('cr-product-wrap');
    if (pw && cv) {
      const ps = ((cv.products || []).filter(p => p.status === 'APPROVED'));
      pw.innerHTML = GF.selectField('cr-product', {
        value: '', title: AL('Product', 'Производ'),
        options: [{ v: '', label: AL('— no product named —', '— без наведен производ —') }]
          .concat(ps.map(p => ({ v: p.id, label: p.product_code,
                                 sub: `${Number(p.window_min).toFixed(2)}–${Number(p.window_max).toFixed(2)} %` }))) });
    }
    const spec = GF.$('cr-spec');
    if (spec) spec.innerHTML = GF.WWF.cultSpecPanel(cv);
    const ml = GF.$('cr-mothers');
    if (ml) {
      const mine = (ctx.mothers || []).filter(m => m.cultivar_id === id && m.status === 'active');
      ml.innerHTML = mine.length ? mine.map(m => `<label class="pb-mrow">
          <input type="checkbox" id="cr-m-${m.id}" data-mid="${m.id}">
          <span><b>${GF.esc(m.code)}</b>${m.phenotype ? ` · ${GF.esc(m.phenotype)}` : ''}
            <span style="color:var(--ink-3)"> · ${GF.esc(m.room_name || '—')}${m.position ? ` · ${GF.esc(m.position)}` : ''}
            · ${AL('last cut', 'последно')} ${m.last_cut_on ? fmtD(m.last_cut_on) : AL('never', 'никогаш')}
            · ${AL('next cutting', 'следно сечење')} ${String((m.times_cut || 0) + 1).padStart(2, '0')}</span></span>
          <input type="number" id="cr-c-${m.id}" min="0" max="100000" step="1" placeholder="${AL('cuttings', 'резници')}">
        </label>`).join('')
        : `<div style="color:var(--ink-3);font-size:12px">${AL(
            'No active mother plants of this cultivar in the bank. Register them under Mother bank, or start the run without naming mothers.',
            'Нема активни мајки од оваа сорта во банката. Регистрирајте ги во Банка на мајки, или започнете без наведени мајки.')}</div>`;
    }
    const bw = GF.$('cr-batch-wrap');
    if (bw) {
      const open = (ctx.batches || []).filter(b => b.cultivar_id === id && b.is_active !== false);
      bw.innerHTML = GF.selectField('cr-batch', { value: '', title: AL('Batch', 'Батч'),
        options: [{ v: '', label: AL('— not registered yet —', '— сè уште не е регистриран —') }]
          .concat(open.map(b => ({ v: b.id, label: b.code || '—', sub: `${b.phase} · ${b.room_name || ''}` }))) });
    }
  };

  GF.WWF.cloneRunSave = () => GF.once('cr-save', async () => {
    const val = (id) => ((GF.$(id) || {}).value || '').trim();
    const count = parseInt(val('cr-count'), 10);
    if (!Number.isFinite(count) || count < 0) {
      GF.toast(AL('Enter the cuttings planned', 'Внесете планирани резници'), 'error'); return;
    }
    const code = val('cr-code');
    if (code && !CODE_RE.test(code)) {
      GF.toast(AL('Run code must be 1–64 characters: letters, digits, _ or -',
                  'Кодот мора да е 1–64 знаци: букви, цифри, _ или -'), 'error');
      return;
    }
    const mothers = [];
    (typeof document !== 'undefined' ? document.querySelectorAll('#cr-mothers input[type=checkbox]:checked') : []).forEach(cb => {
      const mid = cb.getAttribute('data-mid');
      const raw = ((GF.$('cr-c-' + mid) || {}).value || '').trim();
      // Blank = not counted per mother (null), never 0.
      mothers.push({ mother_plant_id: mid, cuttings: raw === '' ? null : parseInt(raw, 10) });
    });
    try {
      await GF.API.cloneRunCreate({
        cultivar_id: val('cr-cultivar'),
        product_id: val('cr-product') || null,
        started_on: val('cr-date') || null,
        planned_count: count,
        room_id: val('cr-room') || null,
        batch_id: val('cr-batch') || null,
        code: code || null,
        note: val('cr-note') || null,
        mothers,
      });
      GF.closeModal('cr-modal');
      GF.toast(AL('Clone run started', 'Клонирањето е започнато'), 'success');
      GF.WWF._cult.tab = 'clones';
      await Promise.all([GF.WWF.loadPropagation(), GF.WWF.loadCultivation ? GF.WWF.loadCultivation() : null]);
    } catch (e) { GF.toast(e.message, 'error'); }
  });

  // ── finish a run: transplanted or failed, and the batch it became ─────────

  GF.WWF.cloneRunFinish = async (runId) => {
    if (!canInitiate()) return;
    const r = (GF.WWF._prop.runs || []).find(x => x.id === runId);
    if (!r) return;
    let batches = [];
    try { batches = ((await GF.API.cultivationBatches(true)).batches || []).filter(b => b.cultivar_id === r.cultivar_id); }
    catch (e) { GF.toast(e.message, 'error'); return; }
    GF.WWF._ensureModal('cf-modal', '460px');
    GF.$('cf-modal-title').textContent = AL('Finish clone run', 'Заврши клонирање') + ' — ' + (r.code || `${r.cultivar_code} · ${fmtD(r.started_on)}`);
    GF.$('cf-modal-body').innerHTML = `
      <div class="field"><label>${AL('Outcome', 'Исход')}</label>
        ${GF.selectField('cf-status', { value: 'transplanted', title: AL('Outcome', 'Исход'),
          options: ['transplanted', 'failed'].map(k => ({ v: k, label: sLbl(RSTATUS, k), color: RSTATUS[k].color })) })}</div>
      <div class="field"><label>${AL('Became batch', 'Стана батч')}</label>
        ${GF.selectField('cf-batch', { value: r.batch_id || '', title: AL('Batch', 'Батч'),
          options: [{ v: '', label: AL('— not registered as a batch —', '— не е регистрирано како батч —') }]
            .concat(batches.map(b => ({ v: b.id, label: b.code || '—', sub: `${b.phase} · ${b.room_name || ''}` }))) })}</div>
      <div class="field"><label>${AL('Note (optional)', 'Забелешка (опционално)')}</label>
        <input id="cf-note" maxlength="500" value="${GF.esc(r.note || '')}"></div>
      <div style="color:var(--ink-3);font-size:11px;margin-bottom:8px">${AL(
        'A finished run does not change again; the mothers it was cut from keep the cut in their record.',
        'Завршеното клонирање не се менува повеќе; мајките го задржуваат сечењето во својот запис.')}</div>
      <div class="row" style="gap:10px">
        <div class="spacer"></div>
        <button class="btn btn-primary" id="cf-save" onclick="GF.WWF.cloneRunFinishSave('${r.id}')">${AL('Record', 'Запиши')}</button>
      </div>`;
    GF.openModal('cf-modal');
  };

  GF.WWF.cloneRunFinishSave = (runId) => GF.once('cf-save', async () => {
    const val = (id) => ((GF.$(id) || {}).value || '').trim();
    try {
      await GF.API.cloneRunPatch(runId, {
        status: val('cf-status') || 'transplanted',
        batch_id: val('cf-batch') || null,
        note: val('cf-note') || null,
      });
      GF.closeModal('cf-modal');
      GF.toast(AL('Clone run finished', 'Клонирањето е завршено'), 'success');
      await Promise.all([GF.WWF.loadPropagation(), GF.WWF.loadCultivation ? GF.WWF.loadCultivation() : null]);
    } catch (e) { GF.toast(e.message, 'error'); }
  });
})();
