// Production state: tasks, calendar, week/day/dept filters, CRUD — ported from
// the prototype's GF.state + gf/core.js + gf/main.js, as a React hook backed by
// localStorage (the same offline-first model the prototype used).

import { useState, useCallback, useMemo, useRef } from 'react';
import { SEED, STATUS_ORDER, buildCalendar, todayDay, uid } from './data.js';

const TASKS_KEY = 'gf_tasks_v1';

function loadTasks(todayId) {
  try {
    const saved = JSON.parse(localStorage.getItem(TASKS_KEY));
    if (saved && Array.isArray(saved)) return saved;
  } catch {
    /* ignore */
  }
  return SEED.map((s) => ({
    ...s,
    weekId: todayId + (s.wOff || 0),
    subs: (s.subs || []).map((x) => ({ id: uid(), t: x.t, done: x.done })),
  }));
}

export function useProduction() {
  const calendar = useMemo(() => buildCalendar(), []);
  const [tasks, setTasks] = useState(() => loadTasks(calendar.todayId));
  const [selWeek, setSelWeek] = useState(calendar.todayId);
  const [selDay, setSelDay] = useState('All');
  const [deptFilter, setDeptFilter] = useState(null);
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState(() => new Set());
  const [teleOpen, setTeleOpen] = useState(false);

  const persist = useRef((t) => {
    try {
      localStorage.setItem(TASKS_KEY, JSON.stringify(t));
    } catch {
      /* ignore */
    }
  }).current;

  const mutate = useCallback(
    (fn) =>
      setTasks((prev) => {
        const next = fn(prev);
        persist(next);
        return next;
      }),
    [persist]
  );

  const weekTasks = useCallback((weekId) => tasks.filter((t) => t.weekId === weekId && !t.parentId), [tasks]);

  const visibleTasks = useCallback(
    (weekId) => {
      const q = search.trim().toLowerCase();
      return weekTasks(weekId).filter((t) => {
        if (selDay !== 'All' && !(t.days || []).includes(selDay)) return false;
        if (deptFilter && t.dept !== deptFilter) return false;
        if (q && !`${t.title} ${t.room} ${t.batch} ${t.id}`.toLowerCase().includes(q)) return false;
        return true;
      });
    },
    [weekTasks, selDay, deptFilter, search]
  );

  // ── Mutations ──
  const cycleStatus = useCallback(
    (id) =>
      mutate((ts) =>
        ts.map((t) => {
          if (t.id !== id) return t;
          const i = STATUS_ORDER.indexOf(t.status);
          const status = STATUS_ORDER[(i + 1) % STATUS_ORDER.length];
          const subs = status === 'done' ? (t.subs || []).map((s) => ({ ...s, done: true })) : t.subs;
          return { ...t, status, subs };
        })
      ),
    [mutate]
  );
  const toggleDone = useCallback(
    (id) =>
      mutate((ts) =>
        ts.map((t) => (t.id === id ? { ...t, status: t.status === 'done' ? 'working' : 'done' } : t))
      ),
    [mutate]
  );
  const toggleSub = useCallback(
    (taskId, subId) =>
      mutate((ts) =>
        ts.map((t) =>
          t.id === taskId
            ? { ...t, subs: (t.subs || []).map((s) => (s.id === subId ? { ...s, done: !s.done } : s)) }
            : t
        )
      ),
    [mutate]
  );
  const addNote = useCallback(
    (taskId, text) => {
      if (!text.trim()) return;
      mutate((ts) =>
        ts.map((t) =>
          t.id === taskId ? { ...t, notes: [...(t.notes || []), { d: todayDay.slice(0, 3), n: text.trim() }] } : t
        )
      );
    },
    [mutate]
  );
  const addSub = useCallback(
    (taskId, text) => {
      if (!text.trim()) return;
      mutate((ts) =>
        ts.map((t) =>
          t.id === taskId ? { ...t, subs: [...(t.subs || []), { id: uid(), t: text.trim(), done: false }] } : t
        )
      );
    },
    [mutate]
  );
  const deleteTask = useCallback(
    (id) => {
      mutate((ts) => ts.filter((t) => t.id !== id));
      setExpanded((s) => {
        const n = new Set(s);
        n.delete(id);
        return n;
      });
    },
    [mutate]
  );
  const addTask = useCallback(
    (task) => mutate((ts) => [...ts, task]),
    [mutate]
  );
  const rollover = useCallback(() => {
    mutate((ts) =>
      ts.map((t) =>
        t.weekId === selWeek && t.status !== 'done' ? { ...t, weekId: t.weekId + 1 } : t
      )
    );
  }, [mutate, selWeek]);

  const toggleExpand = useCallback((id) => {
    setExpanded((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  }, []);

  const selectWeek = useCallback(
    (id) => setSelWeek(Math.max(0, Math.min(calendar.weeks.length - 1, id))),
    [calendar.weeks.length]
  );
  const goToday = useCallback(() => {
    setSelWeek(calendar.todayId);
    setSelDay('All');
  }, [calendar.todayId]);
  const filterDept = useCallback((id) => setDeptFilter((d) => (d === id ? null : id)), []);

  return {
    calendar, tasks, selWeek, selDay, deptFilter, search, expanded, teleOpen,
    setSearch, setSelDay, setTeleOpen,
    weekTasks, visibleTasks,
    cycleStatus, toggleDone, toggleSub, addNote, addSub, deleteTask, addTask, rollover,
    toggleExpand, selectWeek, goToday, filterDept,
  };
}
