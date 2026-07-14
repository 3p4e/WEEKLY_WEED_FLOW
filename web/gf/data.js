/* data.js — GrowFlow seed data + bilingual (EN / МК) dictionary. Global: GF */
window.GF = window.GF || {};

GF.DEPTS = [
  { id: 'clone',  name: 'Cloning & Nursery', mk: 'Клонирање и расадник', icon: 'leaf',   color: '#2BE8A0' },
  { id: 'veg',    name: 'Vegetation',        mk: 'Вегетација',           icon: 'leaf',   color: '#3FA34D' },
  { id: 'flower', name: 'Flowering',         mk: 'Цветање',              icon: 'sun',    color: '#E0A73E' },
  { id: 'irr',    name: 'Irrigation',        mk: 'Наводнување',          icon: 'drop',   color: '#0EA5A5' },
  { id: 'prod',   name: 'Production',        mk: 'Производство',         icon: 'box',    color: '#2FD9D9' },
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
    my_week:'My Week', calendar:'Calendar', workload:'Workload', board:'Board', timeline:'Timeline', coordination:'Coordination', dashboard:'Dashboard',
    departments:'Departments', search:'Search tasks…', voice_task:'Voice task', today:'Today',
    this_week:'This Week', next_week:'Next Week', all:'All', add_task:'Add a task — or speak it', new_task:'New task', edit_task:'Edit task',
    done_count:'Done', total:'Total', working:'Working', stuck:'Stuck', postponed:'Postponed', completion:'Completion',
    busiest:'Busiest day', notes:'Progress notes', add_note:'Add a progress note…', subtasks:'Sub-tasks',
    add_sub:'Add a sub-task…', deps:'Dependencies', handoff:'Cross-department handoff', request_handoff:'Request handoff',
    paraphrase:'AI rewrite', dictate:'Dictate', export:'Export', report:'Report', plan:'Plan', rollover:'Roll over',
    ai_summary:'AI weekly summary', ai_brief:'AI brief', owner:'Owner', priority:'Priority',
    due:'Due', delete:'Delete', cancel:'Cancel', save:'Save', create_task:'Create task', edit:'Edit', listening:'Listening…',
    speak_task:'Speak your task', voice_hint:'GrowFlow fills in the details for you', auto_detected:'Auto-detected',
    assignee:'Assignee', dept_label:'Department', this_week_badge:'This week', no_tasks:'No tasks here yet.',
    blocker:'Blocked', generate:'Generate', close:'Close',
    team:'Team', new_task_btn:'New task', accountable:'Accountable', responsible:'Responsible',
    accountable_hint:'One person who owns the outcome', responsible_hint:'People who do the work',
    assistant:'Assistant', ai_assistant:'GrowFlow Assistant', ask_anything:'Ask anything, or pick an action…',
    add_user:'Add person', edit_user:'Edit person', role:'Role', full_name:'Full name', avatar_color:'Avatar colour',
    members:'members', remove:'Remove', active:'Active', you:'You', set_active:'Set active',
    draft_task:'Draft a task', flag_risks:'Flag risks & blockers', suggest_handoffs:'Suggest handoffs',
    week_report:'This week report', send:'Send',
    coord_sub:'Cross-department handoffs for the week', board_sub:'Tasks by day of the week', timeline_sub:'Tasks across the week',
    dash_sub:'Production overview', team_sub:'People & roles',
    view_only:'View only', your_role:'Your role', drag_hint:'Drag cards between columns to change status',
    est_hours:'Estimated hours', hours_spent:'Hours spent', ai_weekly_report:'AI Weekly Report',
    ai_next_week_plan:'AI Next-Week Plan', no_ai_report:'No AI report generated yet.',
    due_date:'Due date', task_type:'Type', reference_code:'Reference code', recurrence:'Repeats',
    rec_none:'Does not repeat', rec_daily:'Daily', rec_weekly:'Weekly', rec_monthly:'Monthly',
    log_work:'Log work', add_subtask:'Add subtask', archive:'Archive', outcome:'Outcome',
    mark_done:'Mark done', change_status:'Change status',
    all_tags:'All tags', overdue:'Overdue',
    exec_overview:'Executive', exec_sub:'Cross-department overview, one screen',
    dept_home:'My Department',
  },
  mk: {
    my_week:'Моја недела', calendar:'Календар', workload:'Оптовареност', board:'Табла', timeline:'Времеплов', coordination:'Координација', dashboard:'Контролна табла',
    departments:'Оддели', search:'Барај задачи…', voice_task:'Гласовна задача', today:'Денес',
    this_week:'Оваа недела', next_week:'Следна недела', all:'Сите', add_task:'Додај задача — или кажи ја', new_task:'Нова задача', edit_task:'Уреди задача',
    done_count:'Завршени', total:'Вкупно', working:'Во тек', stuck:'Блокирани', postponed:'Одложени', completion:'Завршеност',
    busiest:'Најнатоварен ден', notes:'Белешки за напредок', add_note:'Додај белешка…', subtasks:'Под-задачи',
    add_sub:'Додај под-задача…', deps:'Зависности', handoff:'Меѓуоддел. предавање', request_handoff:'Побарај предавање',
    paraphrase:'АИ препиши', dictate:'Диктирај', export:'Извези', report:'Извештај', plan:'План', rollover:'Пренеси',
    ai_summary:'АИ неделен преглед', ai_brief:'АИ резиме', owner:'Носител', priority:'Приоритет',
    due:'Рок', delete:'Избриши', cancel:'Откажи', save:'Зачувај', create_task:'Креирај задача', edit:'Уреди', listening:'Слушам…',
    speak_task:'Кажете ја задачата', voice_hint:'GrowFlow ги пополнува деталите', auto_detected:'Автоматски препознаено',
    assignee:'Доделено на', dept_label:'Оддел', this_week_badge:'Оваа недела', no_tasks:'Сè уште нема задачи.',
    blocker:'Блокирано', generate:'Генерирај', close:'Затвори',
    team:'Тим', new_task_btn:'Нова задача', accountable:'Одговорен', responsible:'Извршители',
    accountable_hint:'Едно лице одговорно за резултатот', responsible_hint:'Луѓе што ја вршат работата',
    assistant:'Асистент', ai_assistant:'GrowFlow Асистент', ask_anything:'Прашајте било што, или изберете дејство…',
    add_user:'Додади лице', edit_user:'Уреди лице', role:'Улога', full_name:'Име и презиме', avatar_color:'Боја на аватар',
    members:'членови', remove:'Отстрани', active:'Активен', you:'Вие', set_active:'Постави активен',
    draft_task:'Состави задача', flag_risks:'Означи ризици', suggest_handoffs:'Предложи предавања',
    week_report:'Извештај за неделата', send:'Испрати',
    coord_sub:'Меѓуодделски предавања за неделата', board_sub:'Задачи по ден во неделата', timeline_sub:'Задачи низ неделата',
    dash_sub:'Преглед на производство', team_sub:'Луѓе и улоги',
    view_only:'Само преглед', your_role:'Ваша улога', drag_hint:'Повлечете картички меѓу колони за промена на статус',
    est_hours:'Проценети часови', hours_spent:'Потрошени часови', ai_weekly_report:'АИ неделен извештај',
    ai_next_week_plan:'АИ план за следна недела', no_ai_report:'Сè уште нема генериран АИ извештај.',
    due_date:'Рок (датум)', task_type:'Тип', reference_code:'Референтен код', recurrence:'Се повторува',
    rec_none:'Не се повторува', rec_daily:'Дневно', rec_weekly:'Неделно', rec_monthly:'Месечно',
    log_work:'Внеси работа', add_subtask:'Додај под-задача', archive:'Архивирај', outcome:'Резултат',
    mark_done:'Означи завршено', change_status:'Промени статус',
    all_tags:'Сите ознаки', overdue:'Задоцнето',
    exec_overview:'Раководство', exec_sub:'Меѓуодделски преглед на еден екран',
    dept_home:'Мојот оддел',
  },
};

// v2 task-type labels (backend enum values — kept short for card chips)
GF.TASK_TYPE_LABELS = {
  capa:       { en: 'CAPA',       mk: 'CAPA' },
  sop:        { en: 'SOP',        mk: 'СОП' },
  validation: { en: 'Validation', mk: 'Валидација' },
  document:   { en: 'Document',   mk: 'Документ' },
  lab:        { en: 'Lab',        mk: 'Лабораторија' },
  meeting:    { en: 'Meeting',    mk: 'Состанок' },
  admin:      { en: 'Admin',      mk: 'Админ' },
  other:      { en: 'Other',      mk: 'Друго' },
};
