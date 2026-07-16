// Production (GrowFlow) static data + bilingual dictionary + calendar, ported
// verbatim from the prototype gf/data.js and gf/core.js.

export const DEPTS = [
  { id: 'clone', name: 'Cloning & Nursery', mk: 'Клонирање и расадник', icon: 'leaf', color: '#15A86B' },
  { id: 'veg', name: 'Vegetation', mk: 'Вегетација', icon: 'leaf', color: '#3FA34D' },
  { id: 'flower', name: 'Flowering', mk: 'Цветање', icon: 'sun', color: '#FF7A1A' },
  { id: 'irr', name: 'Irrigation', mk: 'Наводнување', icon: 'drop', color: '#0EA5A5' },
  { id: 'prod', name: 'Production', mk: 'Производство', icon: 'box', color: '#2F6BFF' },
  { id: 'qc', name: 'Quality Control', mk: 'Контрола на квалитет', icon: 'flask', color: '#7A5BE0' },
  { id: 'qa', name: 'QA / QP', mk: 'ОК / КвЛ', icon: 'shield', color: '#C2410C' },
  { id: 'whin', name: 'Warehouse In', mk: 'Магацин (влез)', icon: 'box', color: '#0891B2' },
  { id: 'whout', name: 'Warehouse Out', mk: 'Магацин (излез)', icon: 'box', color: '#D6336C' },
  { id: 'sec', name: 'Security', mk: 'Обезбедување', icon: 'shield', color: '#566884' },
  { id: 'maint', name: 'Maintenance', mk: 'Одржување', icon: 'wrench', color: '#5A6B82' },
];

export const PEOPLE = {
  marko: { name: 'Marko Petrov', init: 'MP', role: 'hod', roleLabel: 'HOD · Cultivation', dept: 'veg', bg: '#2F6BFF' },
  elena: { name: 'Elena Stojanova', init: 'ES', role: 'hod', roleLabel: 'HOD · QC', dept: 'qc', bg: '#15A86B' },
  dimitar: { name: 'Dimitar Ilievski', init: 'DI', role: 'hod', roleLabel: 'HOD · Production', dept: 'prod', bg: '#FF7A1A' },
  sofija: { name: 'Sofija Trajkova', init: 'ST', role: 'qa', roleLabel: 'QA Officer', dept: 'qa', bg: '#7A5BE0' },
  jana: { name: 'Jana Kostova', init: 'JK', role: 'qp', roleLabel: 'QP · Release', dept: 'qa', bg: '#C2410C' },
  viktor: { name: 'Viktor Angelov', init: 'VA', role: 'operator', roleLabel: 'Irrigation Op.', dept: 'irr', bg: '#0EA5A5' },
  ana: { name: 'Ana Nikolova', init: 'AN', role: 'operator', roleLabel: 'Cultivation Op.', dept: 'veg', bg: '#E5484D' },
  nina: { name: 'Nina Ristova', init: 'NR', role: 'operator', roleLabel: 'Warehouse Op.', dept: 'whout', bg: '#D6336C' },
  goran: { name: 'Goran Markovski', init: 'GM', role: 'operator', roleLabel: 'Maintenance', dept: 'maint', bg: '#5A6B82' },
};

export const STATUS_ORDER = ['pending', 'working', 'review', 'stuck', 'postponed', 'done'];
export const STATUS = {
  pending: { en: 'Not started', mk: 'Не започнато' },
  working: { en: 'Working on it', mk: 'Во тек' },
  review: { en: 'In review', mk: 'На преглед' },
  stuck: { en: 'Stuck', mk: 'Блокирано' },
  postponed: { en: 'Postponed', mk: 'Одложено' },
  done: { en: 'Done', mk: 'Завршено' },
};
export const PRIORITY = {
  critical: { en: 'Critical', mk: 'Критичен' },
  high: { en: 'High', mk: 'Висок' },
  medium: { en: 'Medium', mk: 'Среден' },
  low: { en: 'Low', mk: 'Низок' },
};
export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export const DAYS_MK = ['Пон', 'Вто', 'Сре', 'Чет', 'Пет', 'Саб', 'Нед'];
export const HANDOFF = { clone: 'veg', veg: 'flower', flower: 'prod', prod: 'qc', qc: 'qa', qa: 'whout', irr: 'prod', whin: 'prod', maint: 'irr' };

export const SEED = [
  { id: 'T-101', dept: 'clone', title: 'Take 240 cuttings — Gorilla Glue #4', owner: 'ana', helpers: ['marko'], status: 'done', pr: 'medium', days: ['Mon'], wOff: 0, room: 'Nursery A', batch: 'GG4', tags: ['EU-GMP'], desc: 'Cut 240 clones from mother GG4-M3. Dip in rooting hormone, set in propagation tray under dome.', notes: [{ d: 'Mon', n: '240 cut, 100% turgid. Logged in batch record.' }], subs: [{ t: 'Sanitise scalpels', done: true }, { t: 'Label trays', done: true }], deps: [] },
  { id: 'T-102', dept: 'clone', title: 'Rooting hormone dip + tray label', owner: 'ana', helpers: [], status: 'working', pr: 'medium', days: ['Tue'], wOff: 0, room: 'Nursery A', batch: 'BD', tags: [], desc: '', notes: [], subs: [], deps: [] },
  { id: 'T-201', dept: 'veg', title: 'Transplant to 11L pots — Veg Room 2', owner: 'marko', helpers: ['ana'], status: 'working', pr: 'high', days: ['Tue', 'Wed'], wOff: 0, room: 'Veg 2', batch: 'GG4', tags: ['EU-GMP'], desc: 'Up-pot rooted GG4 clones to 11L coco. Space at 16/m². Record substrate lot.', notes: [{ d: 'Tue', n: '48 of 120 done before shift end.' }], subs: [{ t: 'Stage substrate', done: true }, { t: 'Up-pot 120 plants', done: false }, { t: 'Update plant map', done: false }], deps: ['T-101'] },
  { id: 'T-301', dept: 'irr', title: 'Calibrate EC/pH dosing — Line 3', owner: 'viktor', helpers: [], status: 'stuck', pr: 'critical', days: ['Mon'], wOff: 0, room: 'Fertigation', batch: '', tags: ['MK-GMP'], desc: 'Calibrate EC to 2.2 mS and pH to 5.8 on fertigation line 3.', blocker: 'Dosing pump #3 fault — Maintenance ticket open', notes: [{ d: 'Mon', n: 'Pump #3 not priming. Raised maintenance ticket M-901.' }], subs: [], deps: [] },
  { id: 'T-401', dept: 'flower', title: 'Flip Flower Room 3 to 12/12', owner: 'marko', helpers: [], status: 'review', pr: 'high', days: ['Wed'], wOff: 0, room: 'Flower 3', batch: 'GG4', tags: [], desc: 'Switch photoperiod to 12/12, confirm blackout integrity.', notes: [], subs: [{ t: 'Blackout check', done: true }, { t: 'Set timer 12/12', done: true }], deps: ['T-201'] },
  { id: 'T-501', dept: 'prod', title: 'Trim & wet-weigh — Batch GG4-2401', owner: 'dimitar', helpers: ['nina'], status: 'working', pr: 'high', days: ['Thu', 'Fri'], wOff: 0, room: 'Trim Hall', batch: 'GG4', tags: ['EU-GMP'], desc: 'Machine + hand trim harvested GG4. Wet-weigh each plant, reconcile against harvest log.', notes: [{ d: 'Thu', n: 'Line A running. 12 kg wet logged so far.' }], subs: [{ t: 'Sanitise trim hall', done: true }, { t: 'Wet-weigh', done: false }], deps: [] },
  { id: 'T-601', dept: 'qc', title: 'Moisture & water-activity test — Lot 2398', owner: 'elena', helpers: [], status: 'review', pr: 'medium', days: ['Wed'], wOff: 0, room: 'Lab', batch: 'BD', tags: ['EU-GMP', 'sampling'], desc: 'Aw must be < 0.65 before packaging release.', notes: [{ d: 'Wed', n: 'Aw 0.58, moisture 11.2% — within spec.' }], subs: [], deps: [] },
  { id: 'T-602', dept: 'qc', title: 'Microbial + potency sampling — GG4', owner: 'elena', helpers: ['sofija'], status: 'stuck', pr: 'critical', days: ['Thu'], wOff: 0, room: 'Lab', batch: 'GG4', tags: ['EU-GMP', 'sampling'], desc: 'Pull samples from 4 zones of GG4-2401 for TYMC/TAMC and HPLC potency.', blocker: 'Awaiting HPLC reagent — Procurement notified', notes: [{ d: 'Thu', n: 'Samples pulled. HPLC down to reagent — flagged procurement.' }], subs: [{ t: 'Pull 4-zone samples', done: true }, { t: 'Microbial plates', done: false }, { t: 'HPLC potency', done: false }], deps: [] },
  { id: 'T-701', dept: 'qa', title: 'Batch record review — GG4-2401', owner: 'sofija', helpers: ['jana'], status: 'pending', pr: 'high', days: ['Fri'], wOff: 0, room: 'QA Office', batch: 'GG4', tags: ['EU-GMP'], desc: '', notes: [], subs: [], deps: ['T-602'] },
  { id: 'T-801', dept: 'whin', title: 'Receive nutrient delivery + GRN', owner: 'nina', helpers: [], status: 'done', pr: 'low', days: ['Mon'], wOff: 0, room: 'WH In', batch: '', tags: [], desc: '', notes: [], subs: [], deps: [] },
  { id: 'T-802', dept: 'whout', title: 'Pick & pack order #SO-4471', owner: 'nina', helpers: [], status: 'working', pr: 'medium', days: ['Thu'], wOff: 0, room: 'WH Out', batch: 'BD', tags: [], desc: '', notes: [], subs: [], deps: [] },
  { id: 'T-901', dept: 'maint', title: 'Repair dosing pump #3 (Irrigation)', owner: 'goran', helpers: ['viktor'], status: 'working', pr: 'critical', days: ['Mon'], wOff: 0, room: 'Fertigation', batch: '', tags: [], desc: 'Strip and reseal dosing pump #3, test prime.', notes: [{ d: 'Mon', n: 'Seal kit fitted, bench-tested OK. Reinstalling.' }], subs: [], deps: [] },
  { id: 'T-110', dept: 'flower', title: 'Trichome check + harvest window — GG4', owner: 'elena', helpers: ['marko'], status: 'pending', pr: 'high', days: ['Tue'], wOff: 1, room: 'Flower 3', batch: 'GG4', tags: ['sampling'], desc: '', notes: [], subs: [], deps: [] },
  { id: 'T-111', dept: 'qa', title: 'QP release sign-off — Lot 2398', owner: 'jana', helpers: [], status: 'pending', pr: 'critical', days: ['Wed'], wOff: 1, room: 'QA Office', batch: 'BD', tags: ['EU-GMP'], desc: '', notes: [], subs: [], deps: [] },
  { id: 'T-112', dept: 'prod', title: 'Dry-room RH log — set 58% / 18°C', owner: 'dimitar', helpers: [], status: 'pending', pr: 'medium', days: ['Mon', 'Tue', 'Wed'], wOff: 1, room: 'Dry 2', batch: 'GG4', tags: [], desc: '', notes: [], subs: [], deps: [] },
];

export const I18N = {
  en: {
    my_week: 'My Week', board: 'Board', timeline: 'Timeline', coordination: 'Coordination', dashboard: 'Dashboard',
    departments: 'Departments', search: 'Search tasks, batches, rooms…', voice_task: 'Voice task', today: 'Today',
    this_week: 'This Week', next_week: 'Next Week', all: 'All', add_task: 'Add a task — or speak it', new_task: 'New task',
    done_count: 'Done', total: 'Total', working: 'Working', stuck: 'Stuck', postponed: 'Postponed', completion: 'Completion',
    busiest: 'Busiest day', notes: 'Progress notes', add_note: 'Add a progress note…', subtasks: 'Sub-tasks',
    add_sub: 'Add a sub-task…', deps: 'Dependencies', handoff: 'Cross-department handoff', request_handoff: 'Request handoff',
    paraphrase: 'AI rewrite', dictate: 'Dictate', export: 'Export', report: 'Report', plan: 'Plan', rollover: 'Roll over',
    settings: 'Settings', ai_summary: 'AI weekly summary', ai_brief: 'AI brief', owner: 'Owner', priority: 'Priority',
    due: 'Due', delete: 'Delete', cancel: 'Cancel', save: 'Save', create_task: 'Create task', edit: 'Edit', listening: 'Listening…',
    speak_task: 'Speak your task', voice_hint: 'GrowFlow fills in the details for you', auto_detected: 'Auto-detected',
    assignee: 'Assignee', dept_label: 'Department', this_week_badge: 'This week', no_tasks: 'No tasks here yet.',
    blocker: 'Blocked', generate: 'Generate', close: 'Close', ai_backend: 'AI backend (Letta gateway)', language: 'Language',
  },
  mk: {
    my_week: 'Моја недела', board: 'Табла', timeline: 'Времеплов', coordination: 'Координација', dashboard: 'Контролна табла',
    departments: 'Оддели', search: 'Барај задачи, серии, простории…', voice_task: 'Гласовна задача', today: 'Денес',
    this_week: 'Оваа недела', next_week: 'Следна недела', all: 'Сите', add_task: 'Додај задача — или кажи ја', new_task: 'Нова задача',
    done_count: 'Завршени', total: 'Вкупно', working: 'Во тек', stuck: 'Блокирани', postponed: 'Одложени', completion: 'Завршеност',
    busiest: 'Најнатоварен ден', notes: 'Белешки за напредок', add_note: 'Додај белешка…', subtasks: 'Под-задачи',
    add_sub: 'Додај под-задача…', deps: 'Зависности', handoff: 'Меѓуоддел. предавање', request_handoff: 'Побарај предавање',
    paraphrase: 'АИ препиши', dictate: 'Диктирај', export: 'Извези', report: 'Извештај', plan: 'План', rollover: 'Пренеси',
    settings: 'Поставки', ai_summary: 'АИ неделен преглед', ai_brief: 'АИ резиме', owner: 'Носител', priority: 'Приоритет',
    due: 'Рок', delete: 'Избриши', cancel: 'Откажи', save: 'Зачувај', create_task: 'Креирај задача', edit: 'Уреди', listening: 'Слушам…',
    speak_task: 'Кажете ја задачата', voice_hint: 'GrowFlow ги пополнува деталите', auto_detected: 'Автоматски препознаено',
    assignee: 'Доделено на', dept_label: 'Оддел', this_week_badge: 'Оваа недела', no_tasks: 'Сè уште нема задачи.',
    blocker: 'Блокирано', generate: 'Генерирај', close: 'Затвори', ai_backend: 'АИ сервер (Letta)', language: 'Јазик',
  },
};

// ── Calendar (14 weeks, 4 back from current Monday) ──
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export function buildCalendar() {
  const now = new Date();
  const dow = (now.getDay() + 6) % 7;
  const monday = new Date(now);
  monday.setDate(now.getDate() - dow);
  monday.setHours(0, 0, 0, 0);
  const start = new Date(monday);
  start.setDate(monday.getDate() - 4 * 7);
  const weeks = [];
  let todayId = 0;
  for (let i = 0; i < 14; i++) {
    const s = new Date(start);
    s.setDate(start.getDate() + i * 7);
    const e = new Date(s);
    e.setDate(s.getDate() + 6);
    const num = Math.ceil(((s - new Date(s.getFullYear(), 0, 1)) / 86400000 + 1) / 7);
    weeks.push({
      id: i, start: s, end: e, weekNum: num, monthIndex: s.getMonth(), year: s.getFullYear(),
      label: `${MONTHS[s.getMonth()]} ${s.getDate()} – ${MONTHS[e.getMonth()]} ${e.getDate()}`,
      short: `W${num}`,
    });
    if (now >= s && now <= e) todayId = i;
  }
  return { weeks, todayId };
}
export const todayDay = DAYS[(new Date().getDay() + 6) % 7];

export const uid = () => 'T-' + Math.random().toString(36).slice(2, 7).toUpperCase();
export const dep = (id) => DEPTS.find((d) => d.id === id) || DEPTS[0];
export const progressOf = (t) => {
  if (t.subs && t.subs.length) return Math.round((t.subs.filter((s) => s.done).length / t.subs.length) * 100);
  return { done: 100, working: 50, review: 75, stuck: 25, postponed: 10, pending: 0 }[t.status] ?? 0;
};
