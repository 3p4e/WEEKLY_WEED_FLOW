/* data.js — GrowFlow seed data + bilingual (EN / МК) dictionary. Global: GF */
window.GF = window.GF || {};

GF.DEPTS = [
  { id: 'clone',  name: 'Cloning & Nursery', mk: 'Клонирање и расадник', icon: 'leaf',   color: '#15A86B' },
  { id: 'veg',    name: 'Vegetation',        mk: 'Вегетација',           icon: 'leaf',   color: '#3FA34D' },
  { id: 'flower', name: 'Flowering',         mk: 'Цветање',              icon: 'sun',    color: '#FF7A1A' },
  { id: 'irr',    name: 'Irrigation',        mk: 'Наводнување',          icon: 'drop',   color: '#0EA5A5' },
  { id: 'prod',   name: 'Production',        mk: 'Производство',         icon: 'box',    color: '#2F6BFF' },
  { id: 'qc',     name: 'Quality Control',   mk: 'Контрола на квалитет', icon: 'flask',  color: '#7A5BE0' },
  { id: 'qa',     name: 'QA / QP',           mk: 'ОК / КвЛ',             icon: 'shield', color: '#C2410C' },
  { id: 'whin',   name: 'Warehouse In',      mk: 'Магацин (влез)',       icon: 'box',    color: '#0891B2' },
  { id: 'whout',  name: 'Warehouse Out',     mk: 'Магацин (излез)',      icon: 'box',    color: '#D6336C' },
  { id: 'sec',    name: 'Security',          mk: 'Обезбедување',         icon: 'shield', color: '#566884' },
  { id: 'maint',  name: 'Maintenance',       mk: 'Одржување',            icon: 'wrench', color: '#5A6B82' },
];

// Populated from the real org roster by integrate.js's loadTeam() before
// first render; starts empty so lookups like GF.PEOPLE[id] are always safe.
GF.PEOPLE = {};

// status cycle order
GF.STATUS_ORDER = ['pending', 'working', 'review', 'stuck', 'postponed', 'done'];
GF.STATUS = {
  pending:   { en: 'Not started',  mk: 'Не започнато' },
  working:   { en: 'Working on it', mk: 'Во тек' },
  review:    { en: 'In review',     mk: 'На преглед' },
  stuck:     { en: 'Stuck',         mk: 'Блокирано' },
  postponed: { en: 'Postponed',     mk: 'Одложено' },
  done:      { en: 'Done',          mk: 'Завршено' },
};
GF.PRIORITY = {
  critical: { en: 'Critical', mk: 'Критичен' },
  high:     { en: 'High',     mk: 'Висок' },
  medium:   { en: 'Medium',   mk: 'Среден' },
  low:      { en: 'Low',      mk: 'Низок' },
};
GF.DAYS    = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
GF.DAYS_MK = ['Пон', 'Вто', 'Сре', 'Чет', 'Пет', 'Саб', 'Нед'];

// ── i18n ──
GF.I18N = {
  en: {
    my_week:'My Week', board:'Board', timeline:'Timeline', coordination:'Coordination', dashboard:'Dashboard',
    departments:'Departments', search:'Search tasks, batches, rooms…', voice_task:'Voice task', today:'Today',
    this_week:'This Week', next_week:'Next Week', all:'All', add_task:'Add a task — or speak it', new_task:'New task',
    done_count:'Done', total:'Total', working:'Working', stuck:'Stuck', postponed:'Postponed', completion:'Completion',
    busiest:'Busiest day', notes:'Progress notes', add_note:'Add a progress note…', subtasks:'Sub-tasks',
    add_sub:'Add a sub-task…', deps:'Dependencies', handoff:'Cross-department handoff', request_handoff:'Request handoff',
    paraphrase:'AI rewrite', dictate:'Dictate', export:'Export', report:'Report', plan:'Plan', rollover:'Roll over',
    settings:'Settings', ai_summary:'AI weekly summary', ai_brief:'AI brief', owner:'Owner', priority:'Priority',
    due:'Due', delete:'Delete', cancel:'Cancel', save:'Save', create_task:'Create task', edit:'Edit', listening:'Listening…',
    speak_task:'Speak your task', voice_hint:'GrowFlow fills in the details for you', auto_detected:'Auto-detected',
    assignee:'Assignee', dept_label:'Department', this_week_badge:'This week', no_tasks:'No tasks here yet.',
    blocker:'Blocked', generate:'Generate', close:'Close', ai_backend:'AI backend (Letta gateway)', language:'Language',
    team:'Team', new_task_btn:'New task', accountable:'Accountable', responsible:'Responsible',
    accountable_hint:'One person who owns the outcome', responsible_hint:'People who do the work',
    assistant:'Assistant', ai_assistant:'GrowFlow Assistant', ask_anything:'Ask anything, or pick an action…',
    add_user:'Add person', edit_user:'Edit person', role:'Role', full_name:'Full name', avatar_color:'Avatar colour',
    permissions:'Permissions', members:'members', remove:'Remove', active:'Active', you:'You', set_active:'Set active',
    draft_task:'Draft a task', flag_risks:'Flag risks & blockers', suggest_handoffs:'Suggest handoffs',
    week_report:'This week report', send:'Send', coming_soon:'View ready',
    coord_sub:'Cross-department handoffs for the week', board_sub:'Tasks by status', timeline_sub:'Tasks across the week',
    dash_sub:'Production overview', team_sub:'People & roles',
    view_only:'View only', your_role:'Your role', drag_hint:'Drag cards between columns to change status',
  },
  mk: {
    my_week:'Моја недела', board:'Табла', timeline:'Времеплов', coordination:'Координација', dashboard:'Контролна табла',
    departments:'Оддели', search:'Барај задачи, серии, простории…', voice_task:'Гласовна задача', today:'Денес',
    this_week:'Оваа недела', next_week:'Следна недела', all:'Сите', add_task:'Додај задача — или кажи ја', new_task:'Нова задача',
    done_count:'Завршени', total:'Вкупно', working:'Во тек', stuck:'Блокирани', postponed:'Одложени', completion:'Завршеност',
    busiest:'Најнатоварен ден', notes:'Белешки за напредок', add_note:'Додај белешка…', subtasks:'Под-задачи',
    add_sub:'Додај под-задача…', deps:'Зависности', handoff:'Меѓуоддел. предавање', request_handoff:'Побарај предавање',
    paraphrase:'АИ препиши', dictate:'Диктирај', export:'Извези', report:'Извештај', plan:'План', rollover:'Пренеси',
    settings:'Поставки', ai_summary:'АИ неделен преглед', ai_brief:'АИ резиме', owner:'Носител', priority:'Приоритет',
    due:'Рок', delete:'Избриши', cancel:'Откажи', save:'Зачувај', create_task:'Креирај задача', edit:'Уреди', listening:'Слушам…',
    speak_task:'Кажете ја задачата', voice_hint:'GrowFlow ги пополнува деталите', auto_detected:'Автоматски препознаено',
    assignee:'Доделено на', dept_label:'Оддел', this_week_badge:'Оваа недела', no_tasks:'Сè уште нема задачи.',
    blocker:'Блокирано', generate:'Генерирај', close:'Затвори', ai_backend:'АИ сервер (Letta)', language:'Јазик',
    team:'Тим', new_task_btn:'Нова задача', accountable:'Одговорен', responsible:'Извршители',
    accountable_hint:'Едно лице одговорно за резултатот', responsible_hint:'Луѓе што ја вршат работата',
    assistant:'Асистент', ai_assistant:'GrowFlow Асистент', ask_anything:'Прашајте било што, или изберете дејство…',
    add_user:'Додади лице', edit_user:'Уреди лице', role:'Улога', full_name:'Име и презиме', avatar_color:'Боја на аватар',
    permissions:'Дозволи', members:'членови', remove:'Отстрани', active:'Активен', you:'Вие', set_active:'Постави активен',
    draft_task:'Состави задача', flag_risks:'Означи ризици', suggest_handoffs:'Предложи предавања',
    week_report:'Извештај за неделата', send:'Испрати', coming_soon:'Приказ',
    coord_sub:'Меѓуодделски предавања за неделата', board_sub:'Задачи по статус', timeline_sub:'Задачи низ неделата',
    dash_sub:'Преглед на производство', team_sub:'Луѓе и улоги',
    view_only:'Само преглед', your_role:'Ваша улога', drag_hint:'Повлечете картички меѓу колони за промена на статус',
  },
};
