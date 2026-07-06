// Bridges the real backend (via GF_API) into the kit's mock-data shape.
// GF_DEPARTMENTS / GF_PEOPLE / GF_TASKS are mutated IN PLACE (splice+push,
// never reassigned) because app.js/screens.js destructure them from
// `window` once at script-load time — replacing the array reference
// wouldn't be visible through that stale binding, but mutating the same
// array object is.
(function () {
  // Same status/priority wire<->UI maps as the real vanilla app
  // (web/gf/integrate.js S_IN/P_IN) — the UI vocabulary predates this kit
  // and the kit's mock data already speaks it.
  const STATUS_IN = { ongoing: 'working', completed: 'done', pending: 'pending', stuck: 'stuck', review: 'review', postponed: 'postponed' };
  const PRIORITY_IN = { normal: 'medium', medium: 'medium', high: 'high', critical: 'critical', low: 'low' };
  const ROLE_IN = (role) => (role === 'USER' ? 'operator' : String(role || 'operator').toLowerCase());

  // GF_DEPARTMENTS ships icon/color per department CODE (the real org's 11
  // codes) — the API only returns id/code/name/name_mk, so keep the kit's
  // icon/color as a static lookup keyed by code and refresh name/name_mk
  // from the live department rows (a name change in Settings shows up here).
  const DEPT_VISUAL = {};
  (window.GF_DEPARTMENTS || []).forEach((d) => { DEPT_VISUAL[d.id] = { icon: d.icon, color: d.color }; });

  function weekIdxFor(dateStr, todayIdx) {
    // The kit models 3 relative weeks (0=prior,1=current,2=next) rather than
    // real arbitrary week history — bucket by calendar distance from today
    // until full week-strip parity lands.
    if (!dateStr) return todayIdx;
    const now = new Date(); const d = new Date(dateStr);
    const days = Math.round((d - now) / 86400000);
    if (days < -3) return Math.max(0, todayIdx - 1);
    if (days > 10) return Math.min(2, todayIdx + 1);
    return todayIdx;
  }

  function taskFromApi(t, deptCodeById, todayIdx) {
    const deptCode = (t.department_id && deptCodeById[t.department_id]) || t.department || 'prod';
    const days = Array.isArray(t.days) ? t.days.map((d) => d.slice(0, 3)) : [];
    const pr = PRIORITY_IN[t.priority] || 'medium';
    const desc = t.description || '';
    const ref = t.reference_code || '';
    return {
      id: t.id, title: t.title, status: STATUS_IN[t.status] || 'pending',
      // Dual-keyed, matching createTask()'s newTask shape below — different
      // components in this kit read priority/pr, description/desc, and
      // ref/refCode interchangeably, so both names must be populated or
      // whichever one a given card reads renders blank/defaulted (this is
      // exactly how a first pass here rendered every card's priority as the
      // PriorityTag default "MEDIUM" regardless of the real priority).
      pr, priority: pr, desc, description: desc, ref, refCode: ref,
      weekIdx: weekIdxFor(t.week_start || t.due_date, todayIdx),
      owner: t.user_id, helpers: (t.assignee_ids || []).filter((id) => id !== t.user_id),
      due: t.due_date || null, type: t.task_type || 'other',
      sessionHours: 0, subDone: 0, subCount: 0,
      tags: t.tags || [], days, day: days[0] || 'Mon',
      dept: deptCode, notes: [], deps: [],
      blocker: t.blocker_reason || '',
    };
  }

  function personFromApi(p, tasks, deptCodeById) {
    const mine = tasks.filter((t) => t.owner === p.id);
    return {
      id: p.id, name: p.full_name || p.username, role: ROLE_IN(p.role),
      // GF_DEPARTMENTS is keyed by CODE (see below), but profiles carry the
      // real department UUID — resolve through the id->code map or every
      // person card shows the raw uuid instead of a department name.
      dept: (p.department_id && deptCodeById[p.department_id]) || null,
      active: mine.filter((t) => t.status !== 'done').length,
      done: mine.filter((t) => t.status === 'done').length,
      color: '#' + ('000000' + (((p.id || '').split('').reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7) & 0xffffff))).slice(-6),
    };
  }

  async function loadRealData() {
    const api = window.GF_API;
    const [depts, people, tasksRaw] = await Promise.all([api.departments(), api.directory(), api.tasks()]);

    const deptCodeById = {};
    depts.forEach((d) => { deptCodeById[d.id] = d.code; });
    // Refresh GF_DEPARTMENTS in place: keep the static icon/color per code,
    // pull live name/name_mk, keyed by the real department id (a real uuid)
    // so task.dept (mapped to the department's CODE below) still resolves
    // through GF_DEPARTMENTS.find(d => d.id === code).
    const newDepts = depts.map((d) => ({
      id: d.code, name: d.name, mk: d.name_mk || d.name,
      icon: (DEPT_VISUAL[d.code] || {}).icon || 'Package',
      color: (DEPT_VISUAL[d.code] || {}).color || '#8A99B0',
    }));
    window.GF_DEPARTMENTS.splice(0, window.GF_DEPARTMENTS.length, ...newDepts);

    const todayIdx = 1; // the kit's fixed 3-slot model: 0=prior,1=current,2=next
    const tasks = tasksRaw.map((t) => taskFromApi(t, deptCodeById, todayIdx));

    const newPeople = people.map((p) => personFromApi(p, tasks, deptCodeById));
    window.GF_PEOPLE.splice(0, window.GF_PEOPLE.length, ...newPeople);
    const personById = {}; newPeople.forEach((p) => { personById[p.id] = p; });

    // Second pass: color (dept) + people (avatar-stack shape) need the
    // department/people tables built above — same derivation createTask()
    // uses for a task created live in the app.
    const deptColorByCode = {}; window.GF_DEPARTMENTS.forEach((d) => { deptColorByCode[d.id] = d.color; });
    tasks.forEach((t) => {
      t.color = deptColorByCode[t.dept];
      t.people = [t.owner, ...t.helpers].filter(Boolean).map((pid) => {
        const p = personById[pid]; return { name: (p && p.name) || '?', color: (p && p.color) || '#8A99B0' };
      });
    });
    window.GF_TASKS.splice(0, window.GF_TASKS.length, ...tasks);

    return { meId: (api.user && api.user.id) || (newPeople[0] && newPeople[0].id) };
  }

  window.GF_REAL = { loadRealData, ROLE_IN };
})();
