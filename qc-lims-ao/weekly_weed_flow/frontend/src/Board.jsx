import React, { useEffect, useState } from 'react';
import { api } from './api.js';

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const STATUS_COLOR = {
  completed: 'var(--green)', done: 'var(--green)', ongoing: 'var(--amber)', working: 'var(--amber)',
  review: 'var(--blue)', stuck: 'var(--red)', pending: 'var(--ink3)', postponed: 'var(--violet)',
};
const PRIO_COLOR = { critical: 'var(--red)', high: 'var(--amber)', normal: 'var(--ink3)', medium: 'var(--ink3)', low: 'var(--ink3)' };
const wkLabel = (w) => `${w.iso_year}-W${String(w.iso_week).padStart(2, '0')}`;

export default function Board({ t, dept }) {
  const [weeks, setWeeks] = useState([]); const [week, setWeek] = useState(null);
  const [tasks, setTasks] = useState([]); const [day, setDay] = useState(null);
  const [open, setOpen] = useState(null);

  useEffect(() => { api.weeks().then((w) => { setWeeks(w); if (w.length) setWeek(w[0].id); }).catch(() => {}); }, []);
  useEffect(() => {
    if (!week) return;
    let qs = `?week_id=${week}&parents_only=true`;
    if (dept) qs += `&department_id=${dept}`;
    api.tasks(qs).then(setTasks).catch(() => setTasks([]));
  }, [week, dept]);

  const shown = day ? tasks.filter((x) => (x.days || []).includes(day)) : tasks;
  const by = (s) => tasks.filter((x) => x.status === s).length;
  const doneN = by('completed') + by('done');
  const rate = tasks.length ? Math.round((doneN / tasks.length) * 100) : 0;

  // group by department label
  const groups = {};
  shown.forEach((x) => { const k = x.department || '—'; (groups[k] = groups[k] || []).push(x); });

  return (
    <div>
      <div className="weekstrip">
        {weeks.map((w) => (
          <div key={w.id} className={'weekchip' + (w.id === week ? ' on' : '')} onClick={() => setWeek(w.id)}>
            {wkLabel(w)}<br /><span style={{ opacity: .7 }}>{w.starts_on}</span>
          </div>
        ))}
      </div>
      <div className="daypills">
        <div className={'daypill' + (day === null ? ' on' : '')} onClick={() => setDay(null)}>All</div>
        {DAYS.map((d) => <div key={d} className={'daypill' + (day === d ? ' on' : '')} onClick={() => setDay(d)}>{d.slice(0, 3)}</div>)}
      </div>
      <div className="telemetry">
        <div className="stat"><span className="v" style={{ color: 'var(--green)' }}>{rate}%</span><span className="l">{t.completion}</span></div>
        <div className="stat"><span className="v">{tasks.length}</span><span className="l">{t.total}</span></div>
        <div className="stat"><span className="v" style={{ color: 'var(--amber)' }}>{by('ongoing') + by('working')}</span><span className="l">{t.status.ongoing}</span></div>
        <div className="stat"><span className="v" style={{ color: 'var(--red)' }}>{by('stuck')}</span><span className="l">{t.status.stuck}</span></div>
        <div className="stat"><span className="v" style={{ color: 'var(--green)' }}>{doneN}</span><span className="l">{t.status.completed}</span></div>
      </div>

      {Object.entries(groups).map(([g, items]) => (
        <div className="panel" key={g}>
          <h3>{g} · {items.length}</h3>
          {items.map((x) => (
            <div className="card" key={x.id} onClick={() => api.task(x.id).then(setOpen)}>
              <div className="t">{x.title}</div>
              <div className="meta">
                <span className="pill" style={{ background: STATUS_COLOR[x.status] || 'var(--ink3)', color: '#fff' }}>
                  {(t.status[x.status]) || x.status}</span>
                <span style={{ color: PRIO_COLOR[x.priority] }}>{x.priority}</span>
                {(x.tags || []).slice(0, 4).map((tg, i) => <span className="tag" key={i}>{tg}</span>)}
              </div>
            </div>
          ))}
        </div>
      ))}
      {shown.length === 0 && <div className="muted">No tasks for this selection.</div>}

      {open && <TaskModal t={t} data={open} onClose={() => setOpen(null)} />}
    </div>
  );
}

function TaskModal({ t, data, onClose }) {
  const x = data.task;
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2>{x.title}</h2><button className="btn" onClick={onClose}>{t.close}</button>
        </div>
        <div className="meta" style={{ display: 'flex', gap: 8, fontSize: 12, color: 'var(--ink3)', margin: '4px 0 12px' }}>
          <span>{x.department}</span>·<span>{x.status}</span>·<span>{x.priority}</span>·<span>{x.week_start}</span>
        </div>
        <h3 style={{ fontSize: 13 }}>{t.description}</h3>
        <div style={{ fontSize: 14, marginBottom: 14 }}>{x.description || t.no_desc}</div>
        {!!data.subtasks.length && <>
          <h3 style={{ fontSize: 13 }}>{t.subtasks} · {data.subtasks.length}</h3>
          {data.subtasks.map((s) => <div className="sub" key={s.id}>{s.title} <span className="muted">· {s.status}</span></div>)}
        </>}
        {!!data.progress.length && <>
          <h3 style={{ fontSize: 13, marginTop: 12 }}>{t.progress}</h3>
          {data.progress.map((p, i) => <div className="sub" key={i}><b>{p.day_label}:</b> {p.note}</div>)}
        </>}
        {!!(x.tags || []).length && <div style={{ marginTop: 12 }}>{x.tags.map((tg, i) => <span className="tag" key={i} style={{ marginRight: 6 }}>{tg}</span>)}</div>}
      </div>
    </div>
  );
}
