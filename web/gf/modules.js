/* modules.js — six broad module groupings, role mappings, and the module
   switcher UI. Loaded right after core.js/chooser.js so render.js, cmdk.js,
   search-view.js, and every _registerFullPageView caller can consult it.
   Roles are BACKEND uppercase tokens (GF.API.user.role) — the same idiom
   every existing guard uses. */
window.GF = window.GF || {};

GF.ALWAYS_FULL_ACCESS_ROLES = new Set(['ADMIN', 'OWNER', 'CEO', 'COO']);
GF.ELEVATED_MODULE_ROLES = ['ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR','SE_MGR','CU_MGR','IR_MGR','MU_MGR','QP'];

// i18n helper alias — AL is declared in data.js (already loaded).
const _AL = typeof AL === 'function' ? AL : (en) => en;

GF.MODULES = [
  {
    id: 'tasks', icon: 'check',
    label: () => _AL('Task Management', 'Управување со задачи'),
    desc:  () => _AL('Weekly work, boards, timelines, reports', 'Неделна работа, табли, временски рамки, извештаи'),
    roles: null,   // null = every signed-in role
    defaultView: () => (GF.hasDeptHome && GF.hasDeptHome()) ? 'depthome' : 'mywork',
    keys: ['depthome','mywork','board','timeline','calendar','myday','team',
           'coord','dash','report','inbox','search','import','intake'],
  },
  {
    id: 'qc', icon: 'flask',
    label: () => _AL('QC & QMS', 'КК и QMS'),
    desc:  () => _AL('Quality control, samples, QMS documents', 'Контрола на квалитет, примероци, QMS документи'),
    roles: ['QC_MGR', 'QA_MGR', 'QP'],
    defaultView: () => 'qccoa',
    keys: ['qccoa','qcregister','qcsample','qclab','qcspec','qcpotency','qcleaves',
           'qccustody','qcecoa','qcoos','qcgenealogy','qmsstudio','qmsregistry','qmsknow'],
  },
  {
    id: 'cultivation', icon: 'leaf',
    label: () => _AL('Cultivation & Facility', 'Одгледување и капацитет'),
    desc:  () => _AL('Growing, irrigation, rooms, harvest', 'Одгледување, наводнување, соби, жетва'),
    // QA_MGR is here because harvest.py lets QA record a cut to release a
    // pre-harvest-interval block — it is the ONLY role that can — and a
    // module list that hid the harvest view from them made that power
    // unreachable. IR_MGR runs the irrigation view.
    roles: ['CU_MGR', 'PR_MGR', 'IR_MGR', 'WH_MGR', 'MU_MGR', 'QA_MGR'],
    defaultView: () => 'cultivation',
    keys: ['cultivation', 'facility', 'harvest', 'irrigation'],
  },
  {
    id: 'biosecurity', icon: 'shield',
    label: () => _AL('Biosecurity & Waste', 'Биобезбедност и отпад'),
    desc:  () => _AL('Decontamination, destruction', 'Деконтаминација, уништување'),
    roles: ['CU_MGR', 'QA_MGR', 'SE_MGR'],
    defaultView: () => 'decon',
    keys: ['decon', 'waste'],
  },
  {
    id: 'audit', icon: 'clipboard-check',
    label: () => _AL('Audit & Compliance', 'Ревизија и усогласеност'),
    desc:  () => _AL('Audit trail, readiness, approvals', 'Ревизиска трага, подготвеност, одобрувања'),
    roles: ['QA_MGR', 'QC_MGR', 'QP'],
    defaultView: () => 'audit',
    keys: ['audit', 'auditprep', 'approvals'],
  },
  {
    id: 'analytics', icon: 'bar-chart',
    label: () => _AL('Analytics & Executive', 'Аналитика и извршни'),
    desc:  () => _AL('Reports, workload, executive overview', 'Извештаи, оптовареност, извршен преглед'),
    roles: GF.ELEVATED_MODULE_ROLES.slice(),
    defaultView: () => 'analytics',
    keys: ['analytics', 'execreport', 'workload', 'exec'],
  },
];

// key → owning module id lookup, built once at load.
GF.MODULE_OF_KEY = (() => {
  const m = {};
  GF.MODULES.forEach(mod => mod.keys.forEach(k => { m[k] = mod.id; }));
  return m;
})();

// i18n nav label key for each view key (used by cmdk.js / search-view.js).
GF.VIEW_LABEL_KEY = {
  depthome:'dept_home', mywork:'my_week', board:'board', timeline:'timeline',
  calendar:'calendar', myday:'my_day', team:'team', coord:'coordination',
  dash:'dashboard', report:'report', inbox:'inbox', search:'search',
  import:'import', intake:'intake',
  qccoa:'coa', qcregister:'register', qcsample:'qc_sample', qclab:'qc_lab',
  qcspec:'qc_spec', qcpotency:'potency', qcleaves:'qc_leaves',
  qccustody:'custody', qcecoa:'ecoa', qcoos:'oos', qcgenealogy:'genealogy',
  qmsstudio:'qms_studio', qmsregistry:'qms_registry', qmsknow:'knowledge',
  cultivation:'cultivation', facility:'facility', harvest:'harvest', irrigation:'irrigation',
  decon:'decon', waste:'waste',
  audit:'audit', auditprep:'audit_prep', approvals:'approvals',
  analytics:'analytics', execreport:'exec_report', workload:'workload', exec:'exec_overview',
};

GF.moduleForKey  = (key) => GF.MODULE_OF_KEY[key] || null;
GF.moduleById    = (id)  => GF.MODULES.find(m => m.id === id) || null;

GF.moduleAccessibleFor = (moduleId, role) => {
  const mod = GF.moduleById(moduleId);
  if (!mod) return false;
  if (mod.roles === null) return true;
  if (GF.ALWAYS_FULL_ACCESS_ROLES.has(role)) return true;
  return mod.roles.includes(role);
};

GF.accessibleModules = (role) => {
  role = role || ((GF.API && GF.API.user) ? GF.API.user.role : 'USER') || 'USER';
  return GF.MODULES.filter(m => GF.moduleAccessibleFor(m.id, role));
};

// Is the given nav key visible for the current role AND active module?
GF.keyVisibleNow = (key) => {
  const role = (GF.API && GF.API.user && GF.API.user.role) || 'USER';
  const modId = GF.moduleForKey(key);
  // An unclassified key fails CLOSED: a nav key missing from GF.MODULE_OF_KEY
  // is a gap in the module registry, not proof the key belongs everywhere —
  // it must stay invisible until someone deliberately classifies it, not
  // silently appear in every module by default.
  if (!modId) return false;
  if (!GF.moduleAccessibleFor(modId, role)) return false;
  const active = GF.state && GF.state.module || 'tasks';
  return active === modId;
};

// ── Persistence ──
// GF.state is set up by core.js before this file loads.
if (GF.state) GF.state.module = localStorage.getItem('gf_module') || null;

GF.setModule = (id, opts) => {
  const mod = GF.moduleById(id);
  if (!mod) return;
  if (GF.state) GF.state.module = id;
  try { localStorage.setItem('gf_module', id); } catch (e) {}
  if (!(opts && opts.keepView)) {
    const first = mod.defaultView ? mod.defaultView() : mod.keys[0];
    if (first && GF.setView) GF.setView(first);
    else if (GF.render && GF.render.all) GF.render.all();
  } else if (GF.render && GF.render.all) {
    GF.render.all();
  }
  GF.syncModuleBtn && GF.syncModuleBtn();
};

// Update the header module icon button to reflect the active module.
GF.syncModuleBtn = () => {
  const btn = GF.$('module-btn'); if (!btn) return;
  const mod = GF.moduleById((GF.state && GF.state.module) || 'tasks');
  if (!mod) return;
  btn.innerHTML = GF.icon(mod.icon, 'icon');
  btn.title = mod.label();
};

// ── Module picker modal ──
GF.openModulePicker = (opts) => {
  opts = opts || {};
  const role = (GF.API && GF.API.user && GF.API.user.role) || 'USER';
  const mods = GF.accessibleModules(role);
  const cur = (GF.state && GF.state.module) || null;
  let el = GF.$('gf-module-modal');
  if (!el) {
    el = document.createElement('div');
    el.id = 'gf-module-modal';
    el.className = 'overlay';
    document.body.appendChild(el);
  }
  if (opts.mandatory) el.setAttribute('data-mandatory', '1');
  else el.removeAttribute('data-mandatory');

  const tile = (m) => `
    <button class="module-chip${m.id === cur ? ' on' : ''}" onclick="GF.pickModule('${m.id}')">
      ${GF.icon(m.icon, 'icon module-chip-ic')}
      <span class="module-chip-nm">${GF.esc(m.label())}</span>
      <span class="module-chip-desc">${GF.esc(m.desc())}</span>
      ${m.id === cur ? GF.icon('check', 'icon module-chip-ck') : ''}
    </button>`;

  const closeBtn = opts.mandatory ? '' :
    `<button class="btn-ghost" onclick="GF.closeModal('gf-module-modal')">${GF.icon('x')}</button>`;

  el.innerHTML = `
    <div class="modal" style="max-width:640px">
      <div class="modal-head">
        <h3>${_AL('Choose a module', 'Изберете модул')}</h3>
        ${closeBtn}
      </div>
      <div class="modal-body">
        <div class="module-grid">${mods.map(tile).join('')}</div>
      </div>
    </div>`;
  GF.openModal('gf-module-modal');
};

GF.pickModule = (id) => {
  GF.setModule(id);
  GF.closeModal('gf-module-modal');
};
