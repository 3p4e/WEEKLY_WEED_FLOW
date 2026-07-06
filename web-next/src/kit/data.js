// Real org model (from WEEKLY_WEED_FLOW/web/gf/data.js) — 11 departments.
const GF_DEPARTMENTS = [
  { id: 'clone',  name: 'Cloning & Nursery', mk: 'Клонирање и расадник', icon: 'Sprout',       color: '#15A86B' },
  { id: 'veg',    name: 'Vegetation',        mk: 'Вегетација',           icon: 'Leaf',         color: '#3FA34D' },
  { id: 'flower', name: 'Flowering',         mk: 'Цветање',              icon: 'Sun',          color: '#FF7A1A' },
  { id: 'irr',    name: 'Irrigation',        mk: 'Наводнување',          icon: 'Droplet',      color: '#0EA5A5' },
  { id: 'prod',   name: 'Production',        mk: 'Производство',         icon: 'Package',      color: '#2F6BFF' },
  { id: 'qc',     name: 'Quality Control',   mk: 'Контрола на квалитет', icon: 'FlaskConical', color: '#7A5BE0' },
  { id: 'qa',     name: 'QA / QP',           mk: 'ОК / КвЛ',             icon: 'ShieldCheck',  color: '#C2410C' },
  { id: 'whin',   name: 'Warehouse In',      mk: 'Магацин (влез)',       icon: 'PackagePlus',  color: '#0891B2' },
  { id: 'whout',  name: 'Warehouse Out',     mk: 'Магацин (излез)',      icon: 'PackageMinus', color: '#D6336C' },
  { id: 'sec',    name: 'Security',          mk: 'Обезбедување',         icon: 'Shield',       color: '#566884' },
  { id: 'maint',  name: 'Maintenance',       mk: 'Одржување',            icon: 'Wrench',       color: '#5A6B82' },
];

// Cross-department handoff chain (render.js GF.HANDOFF)
const GF_HANDOFF = { clone:'veg', veg:'flower', flower:'prod', prod:'qc', qc:'qa', qa:'whout', irr:'prod', whin:'prod', maint:'irr' };

// 8 task types (backend enum) with EN/МК chip labels
const GF_TASK_TYPES = {
  capa:       { en: 'CAPA',       mk: 'CAPA' },
  sop:        { en: 'SOP',        mk: 'СОП' },
  validation: { en: 'Validation', mk: 'Валидација' },
  document:   { en: 'Document',   mk: 'Документ' },
  lab:        { en: 'Lab',        mk: 'Лабораторија' },
  meeting:    { en: 'Meeting',    mk: 'Состанок' },
  admin:      { en: 'Admin',      mk: 'Админ' },
  other:      { en: 'Other',      mk: 'Друго' },
};

// Roles (core.js GF.ROLES) — admin is a system role, never offered in the picker.
const GF_ROLES = {
  admin:    { en: 'Administrator',        mk: 'Администратор' },
  ceo:      { en: 'CEO',                  mk: 'Извршен директор' },
  coo:      { en: 'COO',                  mk: 'Оперативен директор' },
  qa_mgr:   { en: 'QA Manager',           mk: 'Менаџер за КО' },
  qc_mgr:   { en: 'QC Manager',           mk: 'Менаџер за КК' },
  pr_mgr:   { en: 'Production Manager',   mk: 'Менаџер за производство' },
  wh_mgr:   { en: 'Warehouse Manager',    mk: 'Менаџер за магацин' },
  sc_mgr:   { en: 'Supply Chain Manager', mk: 'Менаџер за снабдување' },
  cu_mgr:   { en: 'Cultivation Manager',  mk: 'Менаџер за одгледување' },
  qp:       { en: 'Qualified Person',     mk: 'Квалификувано лице' },
  operator: { en: 'Operator',             mk: 'Оператор' },
};
// Permissions: execs + managers + QP get the full row; operator is own-tasks-only.
const GF_PERMS = {
  _full: { create: true, editAny: true, deleteAny: true, status: 'any', team: true },
  operator: { create: true, editAny: false, deleteAny: false, status: 'own', team: false },
};
const GF_ROLE_PERMS = (role) =>
  role === 'operator' ? GF_PERMS.operator : GF_PERMS._full;

const GF_T = {
  en: { myweek:'My Week', board:'Board', timeline:'Timeline', coord:'Coordination', dash:'Dashboard',
    team:'Team', depts:'Departments', settings:'Settings', assistant:'Assistant', newtask:'New task',
    voice:'Voice task', today:'Today', addtask:'Add a task — or speak it', thisweek:'This week',
    search:'Search tasks, batches, rooms…', notasks:'No tasks here yet.', noresults:'No matches for', signin:'Sign in',
    completion:'Completion', total:'Total', working:'Working', stuck:'Stuck', busiest:'Busiest day' },
  mk: { myweek:'Моја недела', board:'Табла', timeline:'Времеплов', coord:'Координација', dash:'Контролна табла',
    team:'Тим', depts:'Оддели', settings:'Поставки', assistant:'Асистент', newtask:'Нова задача',
    voice:'Гласовна задача', today:'Денес', addtask:'Додај задача — или кажи ја', thisweek:'Оваа недела',
    search:'Барај задачи, серии, простории…', notasks:'Сè уште нема задачи.', noresults:'Нема резултати за', signin:'Најави се',
    completion:'Завршеност', total:'Вкупно', working:'Во тек', stuck:'Блокирани', busiest:'Најнатоварен ден' },
};

// People keyed by id (core.js GF.PEOPLE). role uses GF_ROLES tokens.
const GF_PEOPLE = [
  { id:'marko',  name: 'Marko Ilievski',   role: 'coo',      dept: 'prod',   active: 8, done: 41, color: '#2F6BFF' },
  { id:'blagoj', name: 'Blagoj Nikolov',   role: 'qc_mgr',   dept: 'qc',     active: 6, done: 37, color: '#7A5BE0' },
  { id:'ana',    name: 'Ana Petrova',      role: 'qa_mgr',   dept: 'qa',     active: 6, done: 33, color: '#C2410C' },
  { id:'elena',  name: 'Elena Stojanova',  role: 'qp',       dept: 'qa',     active: 3, done: 28, color: '#D6336C' },
  { id:'goran',  name: 'Goran Stojanov',   role: 'cu_mgr',   dept: 'veg',    active: 5, done: 29, color: '#3FA34D' },
  { id:'ivo',    name: 'Ivo Kirov',        role: 'operator', dept: 'flower', active: 4, done: 22, color: '#FF7A1A' },
  { id:'sara',   name: 'Sara Mitrova',     role: 'wh_mgr',   dept: 'whout',  active: 3, done: 18, color: '#0891B2' },
  { id:'kire',   name: 'Kire Todorov',     role: 'operator', dept: 'whin',   active: 2, done: 15, color: '#0EA5A5' },
];
const GF_PERSON = (id) => GF_PEOPLE.find((p) => p.id === id) || { name: '?', color: '#8A99B0' };

// Rich tasks — owner + helpers (RACI), multi-day, v2 badges (ref/type/due/subtasks/hours/tags).
const GF_TASKS = [
  { id:'T-4KZ9', title:'Validate HPLC method for potency', status:'working', pr:'critical', weekIdx:1,
    owner:'blagoj', helpers:['ana'], due:'2026-07-09', type:'validation', ref:'PP-QC-012', sessionHours:3.5,
    subDone:2, subCount:3, tags:['potency','batch-F27'], days:['Wed','Thu'], dept:'qc',
    desc:'Run system-suitability + linearity per protocol PP-QC-012. Record retention times and tailing factors before releasing batch F27.',
    notes:[{d:'Mon',n:'Column equilibrated; mobile phase prepared.'},{d:'Tue',n:'Linearity R²=0.9997 across 5 levels.'}],
    deps:['T-1H7C'] },
  { id:'T-2M1P', title:'Post-curing sampling — Batch F27', status:'stuck', pr:'high', weekIdx:1,
    owner:'ivo', helpers:['blagoj'], due:'2026-06-29', type:'lab', ref:'SP-06', days:['Mon'], dept:'flower',
    blocker:'Waiting on QC water verdict before sampling can proceed.',
    desc:'Post-curing sampling wizard SP-06: draw containers per formula, run pass/fail gates, record disposition.' },
  { id:'T-8Q4A', title:'Update transport SOP for finished goods', status:'review', pr:'medium', weekIdx:1,
    owner:'sara', helpers:['kire'], due:'2026-07-10', type:'sop', ref:'PP-LOG-004', subDone:3, subCount:4, days:['Fri'], dept:'whout',
    desc:'Revise cold-chain handling section; align with new GDP guidance.', tags:['gdp'] },
  { id:'T-1H7C', title:'CAPA — deviation on RH sensor calibration', status:'pending', pr:'high', weekIdx:1,
    owner:'ana', helpers:[], due:'2026-07-10', type:'capa', ref:'PP-QA-089', days:['Thu'], dept:'qa' },
  { id:'T-5D0X', title:'Weekly line-clearance checklist', status:'done', pr:'low', weekIdx:1,
    owner:'ana', helpers:[], type:'admin', sessionHours:1, days:['Mon'], dept:'prod' },
  { id:'T-9F3B', title:'Irrigation dosing — Veg room 2', status:'working', pr:'medium', weekIdx:1,
    owner:'goran', helpers:[], due:'2026-07-08', type:'other', sessionHours:2, days:['Wed'], dept:'irr', tags:['veg-2'] },
  { id:'T-6R2K', title:'Label reconciliation — Batch F26', status:'postponed', pr:'medium', weekIdx:1,
    owner:'sara', helpers:[], type:'document', ref:'PP-WH-021', days:['Fri'], dept:'whin' },
  { id:'T-3T7L', title:'Mother-plant health check — Clone room', status:'working', pr:'medium', weekIdx:1,
    owner:'goran', helpers:['ivo'], due:'2026-07-08', type:'other', days:['Tue','Wed'], dept:'clone', tags:['mothers'] },
  { id:'T-7B2N', title:'QP batch release — F25', status:'review', pr:'critical', weekIdx:1,
    owner:'elena', helpers:['ana'], due:'2026-07-11', type:'document', ref:'PP-QA-102', days:['Fri'], dept:'qa', tags:['release'] },

  // ── Last week (weekIdx 0) — mostly closed out ──
  { id:'T-0A1B', title:'Harvest logging — Batch F25', status:'done', pr:'high', weekIdx:0,
    owner:'ivo', helpers:['goran'], type:'lab', ref:'SP-04', sessionHours:5, days:['Tue','Wed'], dept:'flower', tags:['harvest'],
    desc:'Wet-weight logging and tag reconciliation for F25 at harvest.' },
  { id:'T-0C2D', title:'Nutrient stock audit — Veg', status:'done', pr:'medium', weekIdx:0,
    owner:'goran', helpers:[], type:'other', sessionHours:1.5, days:['Mon'], dept:'irr' },
  { id:'T-0E3F', title:'CoA compilation — Batch F24', status:'done', pr:'critical', weekIdx:0,
    owner:'elena', helpers:['ana'], type:'document', ref:'PP-QA-098', days:['Fri'], dept:'qa', tags:['release'] },
  { id:'T-0G4H', title:'Deviation review — RH excursion', status:'stuck', pr:'high', weekIdx:0,
    owner:'ana', helpers:[], type:'capa', ref:'PP-QA-085', days:['Thu'], dept:'qa',
    blocker:'Carried into this week — awaiting engineering root-cause.' },

  // ── Next week (weekIdx 2) — plan / upcoming ──
  { id:'T-2A5J', title:'Method transfer — HPLC to QC-2', status:'pending', pr:'high', weekIdx:2,
    owner:'blagoj', helpers:['elena'], due:'2026-07-15', type:'validation', ref:'PP-QC-020', days:['Mon','Tue'], dept:'qc',
    desc:'Transfer validated HPLC potency method to the second QC bench; run comparative suitability.' },
  { id:'T-2B6K', title:'Stability pull — 3-month timepoint', status:'pending', pr:'medium', weekIdx:2,
    owner:'ana', helpers:[], due:'2026-07-16', type:'lab', ref:'SP-11', days:['Wed'], dept:'qc', tags:['stability'] },
  { id:'T-2C7L', title:'Cold-chain SOP rollout training', status:'pending', pr:'medium', weekIdx:2,
    owner:'sara', helpers:['kire'], due:'2026-07-17', type:'sop', ref:'PP-LOG-004', days:['Thu','Fri'], dept:'whout' },
  { id:'T-2D8M', title:'Clone propagation — next cycle', status:'pending', pr:'low', weekIdx:2,
    owner:'goran', helpers:['ivo'], due:'2026-07-16', type:'other', days:['Tue'], dept:'clone', tags:['mothers'] },
];

// ── Back-compat augmentation: existing screens read legacy field names.
//    Give every task/person the aliases + derived fields the UI consumes.
const _todayISO = new Date().toISOString().slice(0, 10);
GF_TASKS.forEach((t) => {
  const d = GF_DEPARTMENTS.find((x) => x.id === t.dept) || GF_DEPARTMENTS[0];
  t.priority = t.pr;
  t.weekIdx = (t.weekIdx == null) ? 1 : t.weekIdx;
  t.color = d.color;
  t.day = (t.days || [])[0] || null;
  t.refCode = t.ref;
  t.hours = t.sessionHours;
  t.description = t.desc;
  t.overdue = !!(t.due && t.status !== 'done' && t.due < _todayISO);
  t.subtasks = t.subCount ? `${t.subDone || 0}/${t.subCount}` : null;
  t.people = [t.owner, ...(t.helpers || [])].map((id) => {
    const p = GF_PERSON(id); return { name: p.name, color: p.color };
  });
  // notes already {d,n}; add {date,text} alias for legacy renderers
  t.notes = (t.notes || []).map((n) => ({ ...n, date: n.d, text: n.n }));
  // deps id-list → {label,met} for legacy renderers
  t._depObjs = (t.deps || []).map((id) => {
    const dt = GF_TASKS.find((x) => x.id === id);
    return dt ? { label: dt.title, met: dt.status === 'done' } : null;
  }).filter(Boolean);
});
GF_PEOPLE.forEach((p) => {
  const r = GF_ROLES[p.role];
  p.roleToken = p.role;
  p.roleLabel = r ? r.en : p.role;
});

window.GF_DEPARTMENTS = GF_DEPARTMENTS; window.GF_T = GF_T;
window.GF_TASKS = GF_TASKS; window.GF_PEOPLE = GF_PEOPLE; window.GF_PERSON = GF_PERSON;
window.GF_HANDOFF = GF_HANDOFF; window.GF_TASK_TYPES = GF_TASK_TYPES;
window.GF_ROLES = GF_ROLES; window.GF_ROLE_PERMS = GF_ROLE_PERMS;

// ── PopSelect — popup single-choice picker that replaces every native dropdown ──
// options: [{ value, label, color?, sub? }].  onChange(value).  title = popup heading.
function PopSelect({ value, onChange, options, title, placeholder, disabled = false }) {
  const [open, setOpen] = React.useState(false);
  const opts = options || [];
  const sel = opts.find((o) => o.value === value);
  const label = sel ? sel.label : (placeholder || 'Select…');
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); } };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [open]);
  const trigger = (
    <button type="button" disabled={disabled} onClick={() => !disabled && setOpen(true)} style={{
      width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
      fontFamily: 'var(--font-app)', fontSize: 'var(--fs-14)', textAlign: 'left',
      color: sel ? 'var(--text-strong)' : 'var(--text-muted)', background: 'var(--surface-2)',
      border: '1px solid var(--border-default)', borderRadius: 'var(--r-md)', padding: '10px 12px',
      cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.55 : 1,
      transition: 'border-color var(--dur-ui), box-shadow var(--dur-ui)',
    }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 9, overflow: 'hidden' }}>
        {sel && sel.color && <span style={{ width: 10, height: 10, borderRadius: 3, background: sel.color, flexShrink: 0 }} />}
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
      </span>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="var(--text-muted)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}><path d="M4 6l4 4 4-4" /></svg>
    </button>
  );
  return (
    <React.Fragment>
      {trigger}
      {open && (
        <div onClick={() => setOpen(false)} style={{
          position: 'fixed', inset: 0, zIndex: 700, background: 'var(--overlay)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
          animation: 'gf-overlay-in var(--dur-ui) var(--ease-out)',
        }}>
          <div onClick={(e) => e.stopPropagation()} style={{
            width: '100%', maxWidth: 420, maxHeight: '72vh', display: 'flex', flexDirection: 'column',
            background: 'var(--surface-card)', color: 'var(--text-strong)', borderRadius: 'var(--r-2xl)',
            border: '1px solid var(--border-strong)', boxShadow: 'var(--sh-3)', overflow: 'hidden',
            animation: 'gf-modal-in var(--dur-panel) var(--ease-spring)',
          }}>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '15px 20px', borderBottom: '1px solid var(--border-default)' }}>
              <h3 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 'var(--fs-14)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.08em' }}>{title || 'Select'}</h3>
              <span style={{ position: 'absolute', left: 0, bottom: -1, height: 2, width: 56, background: 'var(--primary)', boxShadow: 'var(--sh-glow)' }} />
              <button type="button" onClick={() => setOpen(false)} style={{ appearance: 'none', border: 0, background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 17, lineHeight: 1, padding: 4 }}>✕</button>
            </div>
            <div style={{ overflowY: 'auto', padding: 6 }}>
              {opts.map((o) => {
                const active = o.value === value;
                return (
                  <button key={String(o.value)} type="button" onClick={() => { onChange(o.value); setOpen(false); }} style={{
                    width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
                    textAlign: 'left', fontFamily: 'var(--font-app)', fontSize: 'var(--fs-14)', fontWeight: active ? 700 : 500,
                    color: active ? 'var(--primary-fg)' : 'var(--text-strong)',
                    background: active ? 'var(--primary-soft)' : 'transparent',
                    border: '1px solid ' + (active ? 'var(--primary)' : 'transparent'), borderRadius: 'var(--r-md)',
                    padding: '11px 13px', margin: '2px 0', cursor: 'pointer',
                  }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 10, overflow: 'hidden' }}>
                      {o.color && <span style={{ width: 11, height: 11, borderRadius: 3, background: o.color, flexShrink: 0 }} />}
                      <span style={{ display: 'flex', flexDirection: 'column', gap: 1, overflow: 'hidden' }}>
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{o.label}</span>
                        {o.sub && <span style={{ fontSize: 'var(--fs-11)', fontWeight: 500, color: 'var(--text-muted)' }}>{o.sub}</span>}
                      </span>
                    </span>
                    {active && <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="var(--primary)" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}><path d="M3 8.5l3.5 3.5L13 4" /></svg>}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </React.Fragment>
  );
}
window.PopSelect = PopSelect;
