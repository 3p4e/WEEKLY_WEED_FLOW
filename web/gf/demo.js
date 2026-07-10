/* demo.js — DEMO MODE: a complete, self-contained sample company.
   Entered from the login screen ("Try the demo"); NEVER touches the real
   backend: when sessionStorage.wwf_demo === '1', GF.API._req routes every
   call into the in-memory router below instead of fetch(), so no request can
   reach the production API or database. Mutations (new tasks, status changes,
   notes, sessions, roster edits) work fully but live in this tab's memory —
   a reload resets the dataset to the seed.

   TWO sample casts run the same GMP-flavoured pipeline as the real facility
   (Cultivation → Production → QC → QA → Warehouse, plus Security &
   Maintenance), and every demo start alternates between them:
     · the cartoon crew — batch GC-042 "Golden Carrot";
     · Arrakis spice ops (Dune) — batch SP-042 "Melange Prime".
   Both follow one batch through every department so cross-team handoffs and
   dependencies are visible, statuses cover every state, sessions include
   weekend/night/overtime, and the OWNER's notes render with the gold
   executive highlight. Every demo start also applies a RANDOM skin from
   GF.THEMES (the visitor's own theme is remembered and restored on exit). */
window.GF = window.GF || {};

GF.DEMO = (function () {
  const KEY = 'wwf_demo';
  const CAST_KEY = 'wwf_demo_cast';         // localStorage — flips on every enter()
  const PREV_THEME_KEY = 'wwf_demo_prev_theme';
  const active = () => { try { return sessionStorage.getItem(KEY) === '1'; } catch (e) { return false; } };

  /* ── date helpers: 3 weeks (last / this / next) anchored on the real today ── */
  function monday(d) { const x = new Date(d); const dow = (x.getDay() + 6) % 7; x.setDate(x.getDate() - dow); x.setHours(0,0,0,0); return x; }
  function iso(d) { return d.toISOString().slice(0, 10); }
  function isoWeek(d) {
    const x = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    const day = x.getUTCDay() || 7; x.setUTCDate(x.getUTCDate() + 4 - day);
    const y0 = new Date(Date.UTC(x.getUTCFullYear(), 0, 1));
    return Math.ceil((((x - y0) / 86400000) + 1) / 7);
  }
  const MON = monday(new Date());
  const wk = (off) => { const s = new Date(MON); s.setDate(s.getDate() + off * 7); const e = new Date(s); e.setDate(e.getDate() + 6); return { s, e }; };
  const W = { prev: wk(-1), cur: wk(0), next: wk(1) };

  /* ── the facility (same departments for both casts) ────────────────── */
  const DEPTS = [
    { id: 'dd-cu', code: 'cultivation',       name: 'Cultivation',       name_mk: 'Одгледување' },
    { id: 'dd-pr', code: 'production',        name: 'Production',        name_mk: 'Производство' },
    { id: 'dd-qc', code: 'qc',                name: 'Quality Control',   name_mk: 'Контрола на квалитет' },
    { id: 'dd-qa', code: 'quality_assurance', name: 'Quality Assurance', name_mk: 'Обезбедување квалитет' },
    { id: 'dd-wh', code: 'logistics',         name: 'Warehouse',         name_mk: 'Магацин' },
    { id: 'dd-se', code: 'security',          name: 'Security',          name_mk: 'Обезбедување' },
    { id: 'dd-mu', code: 'tooling',           name: 'Maintenance',       name_mk: 'Одржување' },
  ];

  /* ── shared builders ───────────────────────────────────────────────── */
  const mkPeople = (rows) => rows.map(([id, full_name, role, department_id, function_role]) => ({
    id, username: full_name.toLowerCase().replace(/[^a-z]+/g, '.'),
    full_name, role, department_id, function_role,
    is_active: true, must_change_password: false,
  }));
  const note = (by, day, text) => ({ day_label: day, note: text, created_at: new Date().toISOString(), user_id: by });
  let seq = 0;
  function T(o) {
    seq++;
    const week = o.w || 'cur';
    return Object.assign({
      id: 'dt-' + String(seq).padStart(2, '0'),
      description: '', assignee_ids: o.helpers || [], status: 'pending', priority: 'normal',
      days: [], tags: [], task_type: 'other', reference_code: '',
      week_id: 'dw-' + week, week_start: iso(W[week].s),
      due_date: null, blocker_reason: null, progress_notes: [],
      session_hours: 0, subtask_count: 0, subtask_done_count: 0,
      estimated_hours: null, actual_hours: null, recurrence: null,
      is_archived: false, parent_id: null, outcome: '',
    }, o);
  }

  /* ═══ CAST 1 — the cartoon crew (batch GC-042 "Golden Carrot") ═══════ */
  function buildCartoon() {
    seq = 0;
    const PEOPLE = mkPeople([
      ['u-mickey',  'Mickey Mouse',    'ADMIN',  null,    'System Administrator'],
      ['u-scrooge', 'Scrooge McDuck',  'OWNER',  null,    'Owner'],
      ['u-minnie',  'Minnie Mouse',    'CEO',    null,    'Chief Executive Officer'],
      ['u-daisy',   'Daisy Duck',      'COO',    null,    'Chief Operating Officer'],
      ['u-dexter',  'Dexter',          'QP',     null,    'Qualified Person'],
      ['u-lisa',    'Lisa Simpson',    'QA_MGR', 'dd-qa', 'QA Manager'],
      ['u-donald',  'Donald Duck',     'QC_MGR', 'dd-qc', 'QC Manager'],
      ['u-goofy',   'Goofy',           'PR_MGR', 'dd-pr', 'Production Manager'],
      ['u-bugs',    'Bugs Bunny',      'CU_MGR', 'dd-cu', 'Cultivation Manager'],
      ['u-popeye',  'Popeye',          'WH_MGR', 'dd-wh', 'Warehouse Manager'],
      ['u-scooby',  'Scooby-Doo',      'SE_MGR', 'dd-se', 'Security Manager'],
      ['u-manny',   'Handy Manny',     'MU_MGR', 'dd-mu', 'Maintenance Manager'],
      ['u-sponge',  'SpongeBob',       'USER',   'dd-pr', 'Production Operator'],
      ['u-patrick', 'Patrick Star',    'USER',   'dd-wh', 'Warehouse Operator'],
      ['u-jerry',   'Jerry',           'USER',   'dd-cu', 'Grow Room Operator'],
      ['u-tweety',  'Tweety',          'USER',   'dd-qc', 'Lab Technician'],
    ]);
    const TASKS = [
      /* — last week (mostly done → feeds the weekly report) — */
      T({ w:'prev', title:'Harvest Flower Room 3 — batch GC-042 "Golden Carrot" | Берба во соба 3 — серија GC-042',
          department_id:'dd-cu', user_id:'u-bugs', helpers:['u-jerry'], status:'completed', priority:'high',
          days:['Mon','Tue'], tags:['GC-042','harvest'], reference_code:'SOP-CU-014', session_hours:14,
          progress_notes:[ note('u-bugs','Tue','Harvest complete: 42.5 kg wet weight, all trolleys transferred to drying.'),
                           note('u-scrooge','Tue','Excellent yield. I want the drying loss figure on my desk the moment it exists.') ] }),
      T({ w:'prev', title:'Load drying room 2 and set environmental program | Полнење на сушара 2',
          department_id:'dd-pr', user_id:'u-goofy', helpers:['u-sponge'], status:'completed',
          days:['Tue','Wed'], tags:['GC-042','drying'], reference_code:'SOP-PR-007', session_hours:6 }),
      T({ w:'prev', title:'Night-shift environmental checks (weekend) | Ноќни проверки на параметри',
          department_id:'dd-se', user_id:'u-scooby', status:'completed', days:['Sat','Sun'],
          tags:['monitoring'], session_hours:9,
          progress_notes:[ note('u-scooby','Sun','Ruh-roh — RH spiked to 62% at 03:00, dehumidifier #2 restarted, stable after.') ] }),
      T({ w:'prev', title:'Replace HEPA pre-filters, corridor B | Замена на HEPA предфилтри',
          department_id:'dd-mu', user_id:'u-manny', status:'completed', days:['Fri'],
          task_type:'validation', tags:['HVAC'], reference_code:'PM-2026-31', session_hours:4 }),

      /* — this week: the GC-042 chain, one department to the next — */
      T({ title:'Trim & weigh dried batch GC-042 | Тримирање и мерење на GC-042',
          description:'Dry trim, record net weight per container, transfer to QC sampling. Depends on drying completion (last week, Production).',
          department_id:'dd-pr', user_id:'u-goofy', helpers:['u-sponge'], status:'ongoing', priority:'critical',
          days:['Mon','Tue','Wed'], tags:['GC-042','trim'], reference_code:'SOP-PR-009',
          session_hours:11, estimated_hours:24, subtask_count:3, subtask_done_count:1,
          progress_notes:[ note('u-sponge','Mon','Aye aye! First 12 containers trimmed — I\'m ready!'),
                           note('u-goofy','Tue','Gawrsh, scale #2 drifted 0.3 g — Maintenance notified, using scale #1 meanwhile.'),
                           note('u-minnie','Tue','Please keep daily net-weight totals in the notes — board wants the drying-loss trend.') ] }),
      T({ title:'QC sampling of batch GC-042 per sampling plan | QC узорцирање на GC-042',
          description:'Sample per SOP-QC-003 after trim hand-off from Production; deliver to lab same day.',
          department_id:'dd-qc', user_id:'u-donald', helpers:['u-tweety'], status:'ongoing', priority:'critical',
          days:['Wed','Thu'], tags:['GC-042','sampling'], reference_code:'SOP-QC-003', task_type:'lab',
          estimated_hours:8, session_hours:3,
          progress_notes:[ note('u-donald','Wed','Sampling booth prepped. If Production is late AGAIN I will not be responsible for my temper.') ] }),
      T({ title:'Microbiology + potency testing GC-042 | Микробиологија и потентност GC-042',
          department_id:'dd-qc', user_id:'u-tweety', status:'pending', priority:'high',
          days:['Thu','Fri'], tags:['GC-042','lab'], task_type:'lab', reference_code:'TM-114' }),
      T({ title:'Batch record review & release dossier GC-042 | Преглед на серија и досие за GC-042',
          description:'QA review of executed batch record; assemble release dossier for QP decision.',
          department_id:'dd-qa', user_id:'u-lisa', status:'pending', priority:'high',
          days:['Fri'], tags:['GC-042','release'], task_type:'document', reference_code:'BR-GC-042',
          progress_notes:[ note('u-lisa','Mon','Pre-review checklist ready. I refuse to let a single uninitialled entry through.') ] }),
      T({ title:'QP certification decision — batch GC-042 | Одлука за сертификација на GC-042',
          department_id:'dd-qa', user_id:'u-dexter', status:'pending', priority:'critical',
          days:['Fri'], tags:['GC-042','release'], due_date: iso(W.cur.e), reference_code:'QP-CERT-042' }),
      T({ title:'Reserve quarantine bay & shipping paperwork GC-042 | Карантин и шпедиција за GC-042',
          department_id:'dd-wh', user_id:'u-popeye', helpers:['u-patrick'], status:'pending',
          days:['Fri'], tags:['GC-042','shipping'],
          progress_notes:[ note('u-popeye','Mon','Bay 4 cleared and labeled. I yam ready when QA is.') ] }),

      /* — this week: the rest of the facility — */
      T({ title:'Transplant 240 clones to Veg Room 1 | Пресадување 240 резници во вегетативна соба 1',
          department_id:'dd-cu', user_id:'u-bugs', helpers:['u-jerry'], status:'ongoing', priority:'high',
          days:['Mon','Tue'], tags:['new-genetics','propagation'], session_hours:7, estimated_hours:16,
          progress_notes:[ note('u-jerry','Mon','Trays 1–8 done, rooting hormone lot recorded.'),
                           note('u-scrooge','Mon','These clones cost me a fortune — I expect a 95% take rate, not a penny less!') ] }),
      T({ title:'Repair irrigation valve, Veg Room 2 | Поправка на вентил за наводнување',
          department_id:'dd-mu', user_id:'u-manny', status:'stuck', priority:'critical',
          days:['Tue'], tags:['irrigation'], blocker_reason:'Replacement valve stuck in customs — broker chasing daily; ETA Thursday.',
          progress_notes:[ note('u-manny','Tue','We can fix it! …as soon as the part actually arrives.') ] }),
      T({ title:'Weekly perimeter & camera audit | Неделна проверка на периметар и камери',
          department_id:'dd-se', user_id:'u-scooby', status:'ongoing', days:['Wed'],
          tags:['audit'], recurrence:'weekly', session_hours:2 }),
      T({ title:'Investigate temperature deviation DEV-2026-089 | Истрага за отстапување DEV-2026-089',
          department_id:'dd-qa', user_id:'u-lisa', helpers:['u-manny'], status:'review', priority:'high',
          days:['Wed','Thu'], task_type:'capa', tags:['deviation','HVAC'], reference_code:'DEV-2026-089',
          progress_notes:[ note('u-lisa','Thu','Root cause: compressor cycling. CAPA drafted, waiting Maintenance countersign.') ] }),
      T({ title:'Update SOP-PR-007 (hang-drying process) | Ажурирање на SOP-PR-007 (сушење со обесување)',
          department_id:'dd-pr', user_id:'u-goofy', status:'review', task_type:'sop',
          days:['Thu'], tags:['GMP','SOP'], reference_code:'SOP-PR-007' }),
      T({ title:'Cycle count — packaging materials | Попис на пакувачки материјали',
          department_id:'dd-wh', user_id:'u-patrick', status:'postponed', days:['Wed'],
          tags:['inventory'], progress_notes:[ note('u-patrick','Wed','Uhh… moved to next week, the forklift and I had a disagreement.') ] }),
      T({ title:'Weekly management meeting — production status | Неделен колегиум за производство',
          department_id:'dd-pr', user_id:'u-minnie', helpers:['u-daisy','u-goofy','u-bugs','u-donald'],
          status:'completed', task_type:'meeting', days:['Mon'], session_hours:1.5 }),

      /* — next week (the plan) — */
      T({ w:'next', title:'Package released batch GC-042 (400 g + 10 g) | Пакување на GC-042',
          department_id:'dd-pr', user_id:'u-goofy', helpers:['u-sponge'], status:'pending', priority:'high',
          days:['Mon','Tue'], tags:['GC-042','packaging'] }),
      T({ w:'next', title:'Ship GC-042 to distributor + CoA pack | Испорака на GC-042 со CoA',
          department_id:'dd-wh', user_id:'u-popeye', status:'pending', priority:'high',
          days:['Wed'], tags:['GC-042','shipping'] }),
      T({ w:'next', title:'Prepare mother-plant room for new genetics | Подготовка на соба за мајки — нова генетика',
          department_id:'dd-cu', user_id:'u-bugs', helpers:['u-jerry'], status:'pending', priority:'critical',
          days:['Mon','Tue','Wed'], tags:['new-genetics','quarantine'] }),
      T({ w:'next', title:'Environmental monitoring re-qualification | Реквалификација на мониторинг на средина',
          department_id:'dd-qc', user_id:'u-donald', status:'pending', task_type:'validation',
          days:['Thu','Fri'], tags:['GMP','EM'] }),
    ];
    const COMMENTS = {
      'dt-05': [ { id:'dc-1', user_id:'u-donald', content:'Hand-off window is Wed 09:00 — QC booth is booked. Don\'t be late.', created_at:new Date().toISOString() },
                 { id:'dc-2', user_id:'u-goofy',  content:'We\'ll be there! Probably. Almost certainly.', created_at:new Date().toISOString() } ],
    };
    const SESSIONS = {
      'dt-03': [ { id:'ds-1', user_id:'u-scooby', started_at:iso(W.prev.s)+'T22:00', hours:4.5, classification:'night',   note:'Sat night round' },
                 { id:'ds-2', user_id:'u-scooby', started_at:iso(W.prev.e)+'T10:00', hours:4.5, classification:'weekend', note:'Sun checks' } ],
      'dt-05': [ { id:'ds-3', user_id:'u-sponge', started_at:iso(W.cur.s)+'T08:00',  hours:8,   classification:'regular', note:'Trim day 1' },
                 { id:'ds-4', user_id:'u-goofy',  started_at:iso(W.cur.s)+'T17:00',  hours:3,   classification:'overtime', note:'Catch-up after scale drift' } ],
    };
    const AI = {
      summary: 'DEMO AI SUMMARY — Week highlights: batch GC-042 moved from drying into trim (Production) and is on '
        + 'track for QC sampling Wed and QP certification Friday. One critical blocker: the Veg Room 2 '
        + 'irrigation valve is stuck in customs (ETA Thu) — transplanting continues on manual watering. '
        + 'Deviation DEV-2026-089 (temperature) has a drafted CAPA awaiting Maintenance countersign. '
        + 'Weekend/night coverage logged 9 h (Security). Owner attention: drying-loss figure due after weigh-in.',
      qa: 'DEMO ASSISTANT — In the live app this answer is grounded in your tasks and documents. '
        + 'Try asking about batch GC-042: it is mid-trim in Production, QC samples Wednesday, QP decision Friday.',
    };
    return { label: 'Cartoon crew', label_mk: 'Цртана екипа', PEOPLE, TASKS, COMMENTS, SESSIONS, AI };
  }

  /* ═══ CAST 2 — Arrakis spice ops (batch SP-042 "Melange Prime") ══════ */
  function buildDune() {
    seq = 0;
    const PEOPLE = mkPeople([
      ['u-jessica', 'Lady Jessica',        'ADMIN',  null,    'System Administrator'],
      ['u-leto',    'Duke Leto Atreides',  'OWNER',  null,    'Owner'],
      ['u-paul',    'Paul Atreides',       'CEO',    null,    'Chief Executive Officer'],
      ['u-thufir',  'Thufir Hawat',        'COO',    null,    'Chief Operating Officer (Mentat)'],
      ['u-mohiam',  'Rev. Mother Mohiam',  'QP',     null,    'Qualified Person'],
      ['u-yueh',    'Dr. Wellington Yueh', 'QA_MGR', 'dd-qa', 'QA Manager'],
      ['u-kynes',   'Dr. Liet-Kynes',      'QC_MGR', 'dd-qc', 'QC Manager'],
      ['u-gurney',  'Gurney Halleck',      'PR_MGR', 'dd-pr', 'Production Manager'],
      ['u-stilgar', 'Stilgar',             'CU_MGR', 'dd-cu', 'Cultivation Manager'],
      ['u-tuek',    'Esmar Tuek',          'WH_MGR', 'dd-wh', 'Warehouse Manager'],
      ['u-duncan',  'Duncan Idaho',        'SE_MGR', 'dd-se', 'Security Manager'],
      ['u-mapes',   'Shadout Mapes',       'MU_MGR', 'dd-mu', 'Maintenance Manager'],
      ['u-jamis',   'Jamis',               'USER',   'dd-pr', 'Production Operator'],
      ['u-harah',   'Harah',               'USER',   'dd-wh', 'Warehouse Operator'],
      ['u-chani',   'Chani',               'USER',   'dd-cu', 'Grow Room Operator'],
      ['u-alia',    'Alia Atreides',       'USER',   'dd-qc', 'Lab Technician'],
    ]);
    const TASKS = [
      /* — last week (mostly done → feeds the weekly report) — */
      T({ w:'prev', title:'Harvest spice field, Sector 14 — batch SP-042 "Melange Prime" | Жетва на зачин, сектор 14 — серија SP-042',
          department_id:'dd-cu', user_id:'u-stilgar', helpers:['u-chani'], status:'completed', priority:'high',
          days:['Mon','Tue'], tags:['SP-042','harvest'], reference_code:'SOP-CU-014', session_hours:14,
          progress_notes:[ note('u-stilgar','Tue','Harvest complete: 42.5 kg raw melange, carryall lifted before wormsign. All crates in the maturation store.'),
                           note('u-leto','Tue','The Emperor watches our quotas. I want the maturation-loss figure the moment it exists.') ] }),
      T({ w:'prev', title:'Load maturation chamber 2 and set climate program | Полнење на комора за зреење 2',
          department_id:'dd-pr', user_id:'u-gurney', helpers:['u-jamis'], status:'completed',
          days:['Tue','Wed'], tags:['SP-042','maturation'], reference_code:'SOP-PR-007', session_hours:6 }),
      T({ w:'prev', title:'Night-shift wormsign & perimeter watch (weekend) | Ноќна стража на периметарот',
          department_id:'dd-se', user_id:'u-duncan', status:'completed', days:['Sat','Sun'],
          tags:['monitoring'], session_hours:9,
          progress_notes:[ note('u-duncan','Sun','Wormsign at 03:00, two klicks out — sentries recalled, thumper decoy deployed. All quiet after.') ] }),
      T({ w:'prev', title:'Replace air-filtration pre-filters, corridor B | Замена на предфилтри, коридор Б',
          department_id:'dd-mu', user_id:'u-mapes', status:'completed', days:['Fri'],
          task_type:'validation', tags:['HVAC'], reference_code:'PM-10191-31', session_hours:4 }),

      /* — this week: the SP-042 chain, one department to the next — */
      T({ title:'Sift & weigh matured batch SP-042 | Просејување и мерење на SP-042',
          description:'Sift, record net weight per container, transfer to QC sampling. Depends on maturation completion (last week, Production).',
          department_id:'dd-pr', user_id:'u-gurney', helpers:['u-jamis'], status:'ongoing', priority:'critical',
          days:['Mon','Tue','Wed'], tags:['SP-042','sift'], reference_code:'SOP-PR-009',
          session_hours:11, estimated_hours:24, subtask_count:3, subtask_done_count:1,
          progress_notes:[ note('u-jamis','Mon','First 12 containers sifted and sealed.'),
                           note('u-gurney','Tue','Scale #2 drifted 0.3 g — Maintenance notified; using scale #1. "Mood\'s a thing for cattle" — we work regardless.'),
                           note('u-paul','Tue','Keep daily net-weight totals in the notes — the Landsraad review wants the maturation-loss trend.') ] }),
      T({ title:'QC sampling of batch SP-042 per sampling plan | QC узорцирање на SP-042',
          description:'Sample per SOP-QC-003 after sift hand-off from Production; deliver to lab same day.',
          department_id:'dd-qc', user_id:'u-kynes', helpers:['u-alia'], status:'ongoing', priority:'critical',
          days:['Wed','Thu'], tags:['SP-042','sampling'], reference_code:'SOP-QC-003', task_type:'lab',
          estimated_hours:8, session_hours:3,
          progress_notes:[ note('u-kynes','Wed','Sampling booth calibrated. The spice must flow — but only through the sampling plan.') ] }),
      T({ title:'Purity & potency assay SP-042 | Чистота и потентност на SP-042',
          department_id:'dd-qc', user_id:'u-alia', status:'pending', priority:'high',
          days:['Thu','Fri'], tags:['SP-042','lab'], task_type:'lab', reference_code:'TM-114' }),
      T({ title:'Batch record review & release dossier SP-042 | Преглед на серија и досие за SP-042',
          description:'QA review of executed batch record; assemble release dossier for certification decision.',
          department_id:'dd-qa', user_id:'u-yueh', status:'pending', priority:'high',
          days:['Fri'], tags:['SP-042','release'], task_type:'document', reference_code:'BR-SP-042',
          progress_notes:[ note('u-yueh','Mon','Pre-review checklist ready. My conditioning does not permit an uninitialled entry.') ] }),
      T({ title:'QP certification decision — batch SP-042 | Одлука за сертификација на SP-042',
          department_id:'dd-qa', user_id:'u-mohiam', status:'pending', priority:'critical',
          days:['Fri'], tags:['SP-042','release'], due_date: iso(W.cur.e), reference_code:'GOM-CERT-042' }),
      T({ title:'Reserve quarantine bay & Guild shipping manifests SP-042 | Карантин и шпедиција за SP-042',
          department_id:'dd-wh', user_id:'u-tuek', helpers:['u-harah'], status:'pending',
          days:['Fri'], tags:['SP-042','shipping'],
          progress_notes:[ note('u-tuek','Mon','Bay 4 cleared and sealed. The Guild asks no questions when the papers are perfect.') ] }),

      /* — this week: the rest of the facility — */
      T({ title:'Establish 240 desert-hardened seedlings, Greenhouse 1 | Садење 240 садници во стаклена градина 1',
          department_id:'dd-cu', user_id:'u-stilgar', helpers:['u-chani'], status:'ongoing', priority:'high',
          days:['Mon','Tue'], tags:['new-genetics','propagation'], session_hours:7, estimated_hours:16,
          progress_notes:[ note('u-chani','Mon','Trays 1–8 planted; dew collectors mounted and logged.'),
                           note('u-leto','Mon','Those seedlings cost House Atreides a fortune — I expect a 95% take rate, not a seed less.') ] }),
      T({ title:'Repair windtrap condenser valve, Greenhouse 2 | Поправка на вентил на кондензатор, градина 2',
          department_id:'dd-mu', user_id:'u-mapes', status:'stuck', priority:'critical',
          days:['Tue'], tags:['irrigation'], blocker_reason:'Replacement valve held at Guild customs — broker chasing daily; ETA Thursday.',
          progress_notes:[ note('u-mapes','Tue','Water discipline holds — hand-watering rota posted while we wait for the part.') ] }),
      T({ title:'Weekly perimeter & sentry-eye audit | Неделна проверка на периметар и сензори',
          department_id:'dd-se', user_id:'u-duncan', status:'ongoing', days:['Wed'],
          tags:['audit'], recurrence:'weekly', session_hours:2 }),
      T({ title:'Investigate temperature deviation DEV-10191-089 | Истрага за отстапување DEV-10191-089',
          department_id:'dd-qa', user_id:'u-yueh', helpers:['u-mapes'], status:'review', priority:'high',
          days:['Wed','Thu'], task_type:'capa', tags:['deviation','HVAC'], reference_code:'DEV-10191-089',
          progress_notes:[ note('u-yueh','Thu','Root cause: compressor cycling. CAPA drafted, awaiting Maintenance countersign.') ] }),
      T({ title:'Update SOP-PR-007 (maturation process) | Ажурирање на SOP-PR-007 (процес на зреење)',
          department_id:'dd-pr', user_id:'u-gurney', status:'review', task_type:'sop',
          days:['Thu'], tags:['GMP','SOP'], reference_code:'SOP-PR-007' }),
      T({ title:'Cycle count — spice containers & packaging | Попис на амбалажа и контејнери',
          department_id:'dd-wh', user_id:'u-harah', status:'postponed', days:['Wed'],
          tags:['inventory'], progress_notes:[ note('u-harah','Wed','Moved to next week — the loader crew was called to the landing field.') ] }),
      T({ title:'Weekly management meeting — production status | Неделен колегиум за производство',
          department_id:'dd-pr', user_id:'u-paul', helpers:['u-thufir','u-gurney','u-stilgar','u-kynes'],
          status:'completed', task_type:'meeting', days:['Mon'], session_hours:1.5 }),

      /* — next week (the plan) — */
      T({ w:'next', title:'Package certified batch SP-042 (400 g + 10 g) | Пакување на SP-042',
          department_id:'dd-pr', user_id:'u-gurney', helpers:['u-jamis'], status:'pending', priority:'high',
          days:['Mon','Tue'], tags:['SP-042','packaging'] }),
      T({ w:'next', title:'Ship SP-042 to Guild freighter + certificate pack | Испорака на SP-042 со сертификати',
          department_id:'dd-wh', user_id:'u-tuek', status:'pending', priority:'high',
          days:['Wed'], tags:['SP-042','shipping'] }),
      T({ w:'next', title:'Prepare propagation room for new cultivar | Подготовка на соба за нова генетика',
          department_id:'dd-cu', user_id:'u-stilgar', helpers:['u-chani'], status:'pending', priority:'critical',
          days:['Mon','Tue','Wed'], tags:['new-genetics','quarantine'] }),
      T({ w:'next', title:'Environmental monitoring re-qualification | Реквалификација на мониторинг на средина',
          department_id:'dd-qc', user_id:'u-kynes', status:'pending', task_type:'validation',
          days:['Thu','Fri'], tags:['GMP','EM'] }),
    ];
    const COMMENTS = {
      'dt-05': [ { id:'dc-1', user_id:'u-kynes',  content:'Hand-off window is Wed 09:00 — the lab booth is booked. The desert does not forgive lateness.', created_at:new Date().toISOString() },
                 { id:'dc-2', user_id:'u-gurney', content:'We\'ll be there at 09:00 sharp — "quickly, they will strike", and so shall we.', created_at:new Date().toISOString() } ],
    };
    const SESSIONS = {
      'dt-03': [ { id:'ds-1', user_id:'u-duncan', started_at:iso(W.prev.s)+'T22:00', hours:4.5, classification:'night',   note:'Sat night watch' },
                 { id:'ds-2', user_id:'u-duncan', started_at:iso(W.prev.e)+'T10:00', hours:4.5, classification:'weekend', note:'Sun rounds' } ],
      'dt-05': [ { id:'ds-3', user_id:'u-jamis',  started_at:iso(W.cur.s)+'T08:00',  hours:8,   classification:'regular', note:'Sift day 1' },
                 { id:'ds-4', user_id:'u-gurney', started_at:iso(W.cur.s)+'T17:00',  hours:3,   classification:'overtime', note:'Catch-up after scale drift' } ],
    };
    const AI = {
      summary: 'DEMO AI SUMMARY — Week highlights: batch SP-042 moved from maturation into sifting (Production) and '
        + 'is on track for QC sampling Wednesday and certification Friday. One critical blocker: the Greenhouse 2 '
        + 'windtrap condenser valve is held at Guild customs (ETA Thu) — planting continues on hand-watering. '
        + 'Deviation DEV-10191-089 (temperature) has a drafted CAPA awaiting Maintenance countersign. '
        + 'Weekend/night watch logged 9 h (Security). Owner attention: maturation-loss figure due after weigh-in.',
      qa: 'DEMO ASSISTANT — In the live app this answer is grounded in your tasks and documents. '
        + 'Try asking about batch SP-042: it is mid-sift in Production, QC samples Wednesday, certification Friday. '
        + 'The spice must flow.',
    };
    return { label: 'Arrakis spice ops', label_mk: 'Аракис — зачин', PEOPLE, TASKS, COMMENTS, SESSIONS, AI };
  }

  /* ── pick the cast set by the last enter(); default: cartoon ───────── */
  const CAST = (function () { try { return localStorage.getItem(CAST_KEY) === 'dune' ? 'dune' : 'cartoon'; } catch (e) { return 'cartoon'; } })();
  const DATA = CAST === 'dune' ? buildDune() : buildCartoon();
  const PEOPLE = DATA.PEOPLE, TASKS = DATA.TASKS, COMMENTS = DATA.COMMENTS, SESSIONS = DATA.SESSIONS;
  const ME = PEOPLE[0];   // the demo login identity (the cast's ADMIN)

  let AUDIT = null;
  function audit() {
    if (AUDIT) return AUDIT;
    const byRole = (r) => (PEOPLE.find(p => p.role === r) || ME).id;
    const users = PEOPLE.filter(p => p.role === 'USER');
    const prOp = users.find(p => p.department_id === 'dd-pr') || ME;
    const labTech = users.find(p => p.department_id === 'dd-qc') || ME;
    let n = 0; const mk = (mins, user, action, table, rec, nv) => ({
      id: ++n, created_at: new Date(Date.now() - mins*60000).toISOString(), user_id: user,
      user_email: (PEOPLE.find(p=>p.id===user)||{}).username + '@demo.example', action, table_name: table,
      record_id: rec, old_values: null, new_values: nv || null, source: table === 'profiles' ? 'users' : 'tasks',
      prev_hash: 'demo', entry_hash: 'demo-' + n });
    AUDIT = [
      mk(12,  byRole('PR_MGR'), 'UPDATE', 'tasks', 'dt-05', { status: 'ongoing' }),
      mk(45,  prOp.id,          'INSERT', 'task_progress', 'dt-05', { note: 'daily progress note' }),
      mk(90,  byRole('QC_MGR'), 'INSERT', 'task_comments', 'dt-05', { content: 'hand-off window agreed' }),
      mk(300, ME.id,            'INSERT', 'profiles', labTech.id, { username: labTech.username }),
      mk(400, byRole('CU_MGR'), 'INSERT', 'tasks', 'dt-11', { title: ((byId('dt-11')||{}).title || '').split('|')[0].trim() }),
    ];
    return AUDIT;
  }

  /* ── tiny helpers ───────────────────────────────────────────────── */
  const clone = (x) => JSON.parse(JSON.stringify(x));
  const byId = (id) => TASKS.find(t => t.id === id);
  const S_LABEL = { completed:'completed', ongoing:'in_progress' };

  function weeklyReport(mode, refDate) {
    // Pick the week containing refDate (default: current), aggregate its tasks.
    const ref = refDate ? new Date(refDate) : new Date();
    const key = ['prev','cur','next'].find(k => ref >= W[k].s && ref <= W[k].e) || 'cur';
    const win = W[key];
    const rows = TASKS.filter(t => t.week_id === 'dw-' + key);
    const c = (s) => rows.filter(t => t.status === s).length;
    const people = {};
    rows.forEach(t => {
      const p = PEOPLE.find(x => x.id === t.user_id); if (!p) return;
      const b = people[p.id] = people[p.id] || { user_id:p.id, username:p.username, name:p.full_name, full_name:p.full_name,
        regular:0, overtime:0, night:0, weekend:0, total:0, completed:0 };
      (SESSIONS[t.id] || []).forEach(s => { b[s.classification] = (b[s.classification]||0) + s.hours; b.total += s.hours; });
      if (t.status === 'completed') b.completed++;
    });
    const dm = {};
    rows.forEach(t => { const d = DEPTS.find(x => x.id === t.department_id);
      const e = dm[d.id] = dm[d.id] || { name: d.name, department: d.name, total:0, completed:0, in_progress:0, stuck:0 };
      e.total++; if (t.status==='completed') e.completed++; if (t.status==='ongoing') e.in_progress++; if (t.status==='stuck') e.stuck++; });
    return {
      mode, period: { label: `${iso(win.s)} → ${iso(win.e)} (demo)`, start: iso(win.s), end: iso(win.e) },
      summary: { total: rows.length, completed: c('completed'), in_progress: c('ongoing'), stuck: c('stuck'),
                 pending: c('pending'), review: c('review'), postponed: c('postponed'),
                 estimated_hours: rows.reduce((a,t)=>a+(+t.estimated_hours||0),0),
                 actual_hours: rows.reduce((a,t)=>a+(+t.session_hours||0),0) },
      task_types: {}, hours_by_person: Object.values(people).sort((a,b)=>b.total-a.total),
      overdue: [], departments: Object.values(dm).sort((a,b)=>b.total-a.total),
      tasks: rows.map(t => ({ title: t.title, status: S_LABEL[t.status] || t.status,
        department: (DEPTS.find(d=>d.id===t.department_id)||{}).name })),
      time_band: [], pins: [],
    };
  }

  /* ── the router: every GF.API call lands here in demo mode ──────── */
  async function handle(method, path, body) {
    const p = path.split('?')[0];
    const q = Object.fromEntries(new URLSearchParams(path.split('?')[1] || ''));
    const seg = p.split('/').filter(Boolean);

    /* auth */
    if (p === '/auth/me') return clone(ME);
    if (p === '/auth/directory' || (p === '/auth/users' && method === 'GET')) return clone(PEOPLE);
    if (seg[0] === 'auth' && seg[1] === 'users') {
      if (method === 'POST' && seg.length === 2) {
        const u = { id:'u-new-'+Date.now(), username: body.username, full_name: body.full_name, role: body.role||'USER',
          department_id: body.department_id||null, function_role: body.function_role||null, is_active:true, must_change_password:true };
        PEOPLE.push(u); return { user: clone(u), otp: 'DEMO-DEMO-DEMO' };
      }
      if (seg[2] === 'deleted') return [];
      if (method === 'PATCH') { const u = PEOPLE.find(x=>x.id===seg[2]); if (u) Object.assign(u, body||{}); return clone(u||{}); }
      if (method === 'DELETE') { const i = PEOPLE.findIndex(x=>x.id===seg[2]); if (i>0) PEOPLE.splice(i,1); return { ok:true }; }
      if (seg[3] === 'reset-password') return { user: clone(PEOPLE.find(x=>x.id===seg[2])||{}), otp: 'DEMO-DEMO-DEMO' };
    }
    if (p === '/auth/change-password') return { ok:true, access_token:'demo' };

    /* core data */
    if (p === '/departments') return clone(DEPTS);
    if (p === '/weeks') return [
      { id:'dw-prev', iso_week: isoWeek(W.prev.s), starts_on: iso(W.prev.s), ends_on: iso(W.prev.e) },
      { id:'dw-cur',  iso_week: isoWeek(W.cur.s),  starts_on: iso(W.cur.s),  ends_on: iso(W.cur.e) },
      { id:'dw-next', iso_week: isoWeek(W.next.s), starts_on: iso(W.next.s), ends_on: iso(W.next.e) },
    ];

    /* tasks */
    if (p === '/tasks' && method === 'GET') return clone(TASKS.filter(t => !t.is_archived));
    if (p === '/tasks' && method === 'POST') {
      const t = T(Object.assign({}, body, {
        title: body.title, department_id: body.department_id || 'dd-pr', user_id: ME.id,
        status: body.status || 'pending', priority: body.priority || 'normal',
        days: body.days || [], tags: body.tags || [],
        week_id: body.week_id || 'dw-cur',
        week_start: body.week_start || iso(W.cur.s),
        w: undefined }));
      if (body.week_id) { const k = { 'dw-prev':'prev','dw-cur':'cur','dw-next':'next' }[body.week_id]; if (k) t.week_start = iso(W[k].s); }
      TASKS.push(t); return clone(t);
    }
    if (seg[0] === 'tasks' && seg.length >= 2) {
      const t = byId(seg[1]);
      if (!t) { const e = new Error('Task not found (demo)'); e.status = 404; throw e; }
      if (seg.length === 2 && method === 'GET')
        return { task: clone(t), subtasks: [], progress: clone(t.progress_notes), sessions: clone(SESSIONS[t.id] || []), links: [] };
      if (seg.length === 2 && method === 'PATCH') { Object.assign(t, body || {}); return clone(t); }
      if (seg[2] === 'progress' && method === 'POST') {
        t.progress_notes.unshift(note(ME.id, body.day_label || 'Mon', body.note)); return { ok: true };
      }
      if (seg[2] === 'comments') {
        const list = COMMENTS[t.id] = COMMENTS[t.id] || [];
        if (method === 'POST') { list.push({ id:'dc-'+Date.now(), user_id:ME.id, content: body.content, created_at: new Date().toISOString() }); return { ok:true }; }
        return clone(list);
      }
      if (seg[2] === 'assignees') {
        if (method === 'POST') { if (!t.assignee_ids.includes(body.user_id)) t.assignee_ids.push(body.user_id); return { ok:true }; }
        if (method === 'DELETE') { t.assignee_ids = t.assignee_ids.filter(x => x !== seg[3]); return { ok:true }; }
        return t.assignee_ids.map(uid => ({ user_id: uid, role: 'assignee', acknowledged_at: null }));
      }
      if (seg[2] === 'ack') return { ok: true };
      if (seg[2] === 'sessions') {
        const list = SESSIONS[t.id] = SESSIONS[t.id] || [];
        if (method === 'POST') {
          const s = Object.assign({ id:'ds-'+Date.now(), user_id:ME.id, classification:'regular' }, body);
          list.push(s); t.session_hours = (+t.session_hours || 0) + (+body.hours || 0); return clone(s);
        }
        return clone(list);
      }
      if (seg[2] === 'links') return method === 'POST' ? { ok:true } : [];
    }
    if (seg[0] === 'sessions' && method === 'DELETE') return { ok: true };

    /* reports + documents */
    if (p === '/reports/weekly') return weeklyReport(q.mode || 'report', q.ref_date);
    if (p === '/reports/documents' && method === 'GET') return { found: false };
    if (p.startsWith('/reports/documents')) {
      const e = new Error(GF.state && GF.state.lang === 'mk'
        ? 'Составувањето документи не е достапно во демо режим.'
        : 'Document compilation is not available in demo mode.');
      e.status = 400; throw e;
    }

    /* AI — canned, so every sparkle button demonstrably works */
    if (seg[0] === 'ai') {
      if (seg[1] === 'pins') return [];
      if (seg[1] === 'functions' || seg[1] === 'agents' || seg[1] === 'bindings') return [];
      if (method === 'PUT' || method === 'DELETE') return { ok: true };
      const input = (body && body.input) || '';
      if (seg[1] === 'weekly_summary') return { available: true, output: DATA.AI.summary };
      if (seg[1] === 'draft_description') return { available: true, output:
        'DEMO AI DRAFT — ' + input.slice(0, 140) + ' … (concise, GMP-appropriate wording would be generated here).' };
      if (seg[1] === 'voice_capture') return { available: true, title: 'Demo task from voice',
        description: input.slice(0, 160) || 'Captured demo task', output: 'ok' };
      if (seg[1] === 'corpus_qa') return { available: true, output: DATA.AI.qa };
      return { available: true, output: 'DEMO AI response.' };
    }
    if (p === '/intake/bilingual') return { en: (body && (body.en || body.text)) || '', mk: (body && (body.mk || body.text)) || '' };
    if (seg[0] === 'intake') return { tasks: [
      { title: 'Demo: order 400 g primary packaging bags', description: 'From pasted meeting notes', department: 'Warehouse', priority: 'high' },
      { title: 'Demo: schedule HVAC compressor service',   description: 'From pasted meeting notes', department: 'Maintenance', priority: 'critical' },
    ] };

    /* audit */
    if (p === '/audit') return clone(audit());
    if (p === '/audit/tables') return [ { table_name:'tasks', count:3 }, { table_name:'task_progress', count:1 }, { table_name:'profiles', count:1 } ];
    if (p === '/audit/verify') return { ok:true, users:{ ok:true, breaks:0, first_break_id:null }, tasks:{ ok:true, breaks:0, first_break_id:null } };

    if (p === '/health') return { status: 'healthy (demo)' };
    return { ok: true, demo: true };
  }

  /* ── mode plumbing ──────────────────────────────────────────────── */
  function enter() {
    try {
      // Alternate the sample cast on every start: cartoon crew ↔ Arrakis.
      const next = localStorage.getItem(CAST_KEY) === 'cartoon' ? 'dune' : 'cartoon';
      localStorage.setItem(CAST_KEY, next);
      // Random skin per start (always different from the one on screen);
      // the visitor's own theme is remembered once and restored on exit.
      if (GF.THEMES && GF.THEMES.length) {
        const cur = localStorage.getItem('gf_theme') || 'dark';
        if (localStorage.getItem(PREV_THEME_KEY) === null) localStorage.setItem(PREV_THEME_KEY, cur);
        const pool = GF.THEMES.filter(t => t.id !== cur);
        const pick = pool[Math.floor(Math.random() * pool.length)] || GF.THEMES[0];
        localStorage.setItem('gf_theme', pick.id);   // the <head> boot script applies it after reload
      }
      sessionStorage.setItem(KEY, '1');
      sessionStorage.setItem('wwf_token', 'demo');
      sessionStorage.removeItem('wwf_user');   // set by install() after reload, from the NEW cast
    } catch (e) {}
    location.reload();
  }
  function exit() {
    try {
      sessionStorage.removeItem(KEY); sessionStorage.removeItem('wwf_token'); sessionStorage.removeItem('wwf_user');
      restoreTheme();
    } catch (e) {}
    location.reload();
  }
  function restoreTheme() {
    const prev = localStorage.getItem(PREV_THEME_KEY);
    if (prev === null) return;
    localStorage.setItem('gf_theme', prev);
    localStorage.removeItem(PREV_THEME_KEY);
    const root = document.documentElement;
    root.dataset.theme = prev;
    if (GF.THEME_CORE && GF.THEME_CORE[prev]) root.removeAttribute('data-skin-carbon');
    else root.setAttribute('data-skin-carbon', '');
  }

  function banner() {
    if (document.getElementById('gf-demo-banner')) return;
    const b = document.createElement('div');
    b.id = 'gf-demo-banner';
    const mk = (GF.state && GF.state.lang) === 'mk';
    b.innerHTML = `<span class="gfdb-dot"></span><b>${mk ? 'ДЕМО' : 'DEMO'} · ${GF.esc ? GF.esc(mk ? DATA.label_mk : DATA.label) : (mk ? DATA.label_mk : DATA.label)}</b>
      <span>${mk ? 'примерни податоци · екипата и изгледот се менуваат при секој старт · промените не се зачувуваат · не е поврзано со продукциската база'
                 : 'sample data · cast & skin rotate every start · changes are not saved · not connected to the production database'}</span>
      <button onclick="GF.DEMO.exit()">${mk ? 'Излези од демо' : 'Exit demo'}</button>`;
    document.body.appendChild(b);
    document.body.classList.add('demo-on');
  }

  // Install the interception once api.js exists (demo.js loads after it).
  function install() {
    if (!GF.API || GF.API._demoWrapped) return;
    GF.API._demoWrapped = true;
    const real = GF.API._req.bind(GF.API);
    GF.API._req = function (method, path, body) {
      if (active()) return handle(method, path, body);   // NEVER touches fetch in demo
      return real(method, path, body);
    };
    if (active()) {
      GF.API.token = 'demo';
      GF.API.user = clone(ME);
      try { sessionStorage.setItem('wwf_user', JSON.stringify(ME)); } catch (e) {}
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', banner);
      else banner();
    } else {
      // A demo tab that was closed (not exited) leaves the random skin behind —
      // heal it on the next non-demo load.
      try { restoreTheme(); } catch (e) {}
    }
  }
  install();

  return { active, enter, exit, handle };
})();
