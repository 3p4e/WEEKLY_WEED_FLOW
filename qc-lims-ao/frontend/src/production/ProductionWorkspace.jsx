// Production workspace — weekStrip, dayPills, telemetry, panels.
// Ported from gf/render.js (weekStrip/dayPills/telemetry/panels).
import { useState, useMemo } from 'react';
import { Icon } from '../lib/icons.jsx';
import { AvatarStack } from '../lib/ui.jsx';
import { TaskCard } from './TaskCard.jsx';
import { PEOPLE, DEPTS, DAYS, dep, uid } from './data.js';
import { makeLabels } from './labels.js';

function Telemetry({ store, labels }) {
  const { t, statusLabel, dayLabel } = labels;
  const all = store.weekTasks(store.selWeek);
  const n = all.length;
  const by = (s) => all.filter((x) => x.status === s).length;
  const done = by('done');
  const rate = n ? Math.round((done / n) * 100) : 0;
  const dayCount = {};
  DAYS.forEach((d) => (dayCount[d] = all.filter((x) => (x.days || []).includes(d)).length));
  const busiest = Object.entries(dayCount).sort((a, b) => b[1] - a[1])[0];
  const Stat = ({ v, l, c }) => (
    <div className="tele-stat">
      <span className="v" style={{ color: c }}>
        {v}
      </span>
      <span className="l">{l}</span>
    </div>
  );
  return (
    <div className={'telemetry' + (store.teleOpen ? ' open' : '')}>
      <div className="tele-bar" onClick={() => store.setTeleOpen(!store.teleOpen)}>
        <Stat v={rate + '%'} l={t('completion')} c="var(--green)" />
        <Stat v={n} l={t('total')} c="var(--ink)" />
        <Stat v={by('working')} l={t('working')} c="var(--orange)" />
        <Stat v={by('stuck')} l={t('stuck')} c="var(--red)" />
        <Stat v={by('postponed')} l={t('postponed')} c="var(--amber)" />
        <Icon name="chevD" className="icon tele-chev" />
      </div>
      <div className="tele-detail">
        <div className="track" style={{ height: 9 }}>
          <span style={{ width: `${rate}%`, background: 'var(--green)' }} />
        </div>
        <div className="tele-grid">
          <div className="tele-card"><div className="v" style={{ color: 'var(--green)' }}>{done}</div><div className="l">{statusLabel('done')}</div></div>
          <div className="tele-card"><div className="v" style={{ color: 'var(--orange)' }}>{by('working')}</div><div className="l">{statusLabel('working')}</div></div>
          <div className="tele-card"><div className="v" style={{ color: 'var(--blue)' }}>{by('review')}</div><div className="l">{statusLabel('review')}</div></div>
          <div className="tele-card"><div className="v" style={{ color: 'var(--red)' }}>{by('stuck')}</div><div className="l">{statusLabel('stuck')}</div></div>
          <div className="tele-card"><div className="v" style={{ color: 'var(--violet)' }}>{busiest ? dayLabel(busiest[0]) : '—'}</div><div className="l">{t('busiest')}</div></div>
        </div>
      </div>
    </div>
  );
}

export function AddTaskModal({ weekId, onCreate, onClose, lang }) {
  const { t, depName, prLabel, dayLabel } = makeLabels(lang);
  const [form, setForm] = useState({ title: '', dept: DEPTS[0].id, owner: 'marko', pr: 'medium', room: '', batch: '', days: [] });
  const toggleDay = (d) => setForm((f) => ({ ...f, days: f.days.includes(d) ? f.days.filter((x) => x !== d) : [...f.days, d] }));
  const submit = () => {
    if (!form.title.trim()) return;
    onCreate({
      id: uid(), title: form.title.trim(), dept: form.dept, owner: form.owner, helpers: [],
      status: 'pending', pr: form.pr, days: form.days.length ? form.days : ['Mon'], weekId,
      room: form.room, batch: form.batch, tags: [], desc: '', notes: [], subs: [], deps: [], blocker: '',
    });
  };
  return (
    <div className="overlay open" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-head">
          <h3>{t('new_task')}</h3>
          <button className="btn-ghost" onClick={onClose}><Icon name="x" /></button>
        </div>
        <div className="modal-body">
          <div className="field"><label>{t('new_task')}</label>
            <input value={form.title} placeholder={t('new_task') + '…'} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </div>
          <div className="field"><label>{t('dept_label')}</label>
            <select value={form.dept} onChange={(e) => setForm({ ...form, dept: e.target.value })}>
              {DEPTS.map((d) => <option key={d.id} value={d.id}>{depName(d.id)}</option>)}
            </select>
          </div>
          <div className="field"><label>{t('owner')}</label>
            <select value={form.owner} onChange={(e) => setForm({ ...form, owner: e.target.value })}>
              {Object.entries(PEOPLE).map(([k, v]) => <option key={k} value={k}>{v.name}</option>)}
            </select>
          </div>
          <div className="field"><label>{t('priority')}</label>
            <select value={form.pr} onChange={(e) => setForm({ ...form, pr: e.target.value })}>
              {['critical', 'high', 'medium', 'low'].map((p) => <option key={p} value={p}>{prLabel(p)}</option>)}
            </select>
          </div>
          <div className="field"><label>{t('due')}</label>
            <div className="chips">
              {DAYS.slice(0, 5).map((d) => (
                <span key={d} className={`chip-opt ${form.days.includes(d) ? 'on' : ''}`} onClick={() => toggleDay(d)}>{dayLabel(d)}</span>
              ))}
            </div>
          </div>
          <div className="field"><label>Room</label><input value={form.room} placeholder="e.g. Flower 3" onChange={(e) => setForm({ ...form, room: e.target.value })} /></div>
          <div className="field"><label>Batch</label><input value={form.batch} placeholder="e.g. GG4" onChange={(e) => setForm({ ...form, batch: e.target.value })} /></div>
        </div>
        <div className="modal-foot">
          <button className="btn" onClick={onClose}>{t('cancel')}</button>
          <button className="btn btn-primary" onClick={submit}>{t('create_task')}</button>
        </div>
      </div>
    </div>
  );
}

export function ProductionWorkspace({ store, lang, onToast }) {
  const labels = useMemo(() => makeLabels(lang), [lang]);
  const { t, dayLabel } = labels;
  const [adding, setAdding] = useState(null); // weekId being added to
  const [nextCollapsed, setNextCollapsed] = useState(true);
  const tasksById = useMemo(() => Object.fromEntries(store.tasks.map((x) => [x.id, x])), [store.tasks]);

  const w = store.calendar.weeks[store.selWeek];
  const isNow = store.selWeek === store.calendar.todayId;
  const cur = store.visibleTasks(store.selWeek);
  const nextId = store.selWeek + 1;
  const nxt = store.weekTasks(nextId);

  const wt = store.weekTasks(store.selWeek);
  const dayCounts = { All: wt.length };
  DAYS.forEach((d) => (dayCounts[d] = wt.filter((x) => (x.days || []).includes(d)).length));

  const renderCard = (task) => (
    <TaskCard
      key={task.id}
      task={task}
      lang={lang}
      labels={labels}
      expanded={store.expanded.has(task.id)}
      store={store}
      tasksById={tasksById}
      onToast={onToast}
    />
  );

  return (
    <div className="workspace" id="prod-workspace" style={{ overflow: 'auto' }}>
      {/* Week strip */}
      <div className="week-strip">
        <div className="weeknav">
          <button className="icon-btn btn-sm" style={{ width: 34, height: 34 }} onClick={() => store.selectWeek(store.selWeek - 1)}><Icon name="chevL" /></button>
          <button className="icon-btn btn-sm" style={{ width: 34, height: 34 }} onClick={() => store.selectWeek(store.selWeek + 1)}><Icon name="chevR" /></button>
        </div>
        <div><div className="week-title">{isNow ? t('this_week') : 'Week ' + w.weekNum}</div></div>
        <div className="week-dates">{w.label}, {w.year}</div>
        {isNow && <span className="badge-now">{t('this_week_badge')}</span>}
        <div className="spacer" />
        <AvatarStack people={['marko', 'elena', 'dimitar', 'viktor', 'nina'].map((id) => PEOPLE[id])} size={30} />
      </div>

      {/* Day pills */}
      <div className="day-pills">
        {['All', ...DAYS.slice(0, 5)].map((d) => (
          <button key={d} className={`day-pill ${store.selDay === d ? 'active' : ''}`} onClick={() => store.setSelDay(d)}>
            {d === 'All' ? t('all') : dayLabel(d)}
            <span className="count">{dayCounts[d] || 0}</span>
          </button>
        ))}
      </div>

      <Telemetry store={store} labels={labels} />

      {/* Panels */}
      <div className="panels">
        <div className="panel">
          <div className="panel-head">
            <span className="ttl">{isNow ? t('this_week') : 'Week ' + w.weekNum}</span>
            <span className="cnt">{cur.length}</span>
            <div className="spacer" />
            <button className="btn btn-sm" onClick={() => onToast(t('report'), 'info')}><Icon name="forward" className="icon" />{t('report')}</button>
            <button className="btn btn-sm" onClick={() => onToast(t('ai_summary') + ' ✓', 'info')}><Icon name="sparkle" className="icon" stroke="var(--orange)" />{t('ai_summary')}</button>
            <button className="btn btn-sm" onClick={() => { store.rollover(); onToast(t('rollover') + ' ✓', 'success'); }}><Icon name="forward" className="icon" />{t('rollover')}</button>
          </div>
          <div className="panel-body">
            {cur.length ? cur.map(renderCard) : <div className="add-row" style={{ justifyContent: 'center', cursor: 'default' }}>{t('no_tasks')}</div>}
          </div>
          <div className="add-row" onClick={() => setAdding(store.selWeek)}>
            <Icon name="plus" /><span>{t('add_task')}</span>
            <div className="spacer" /><Icon name="mic" className="icon" stroke="var(--orange)" />
          </div>
        </div>

        <div className={'panel' + (nextCollapsed ? ' collapsed' : '')}>
          <div className="panel-head" style={{ cursor: 'pointer' }} onClick={() => setNextCollapsed((c) => !c)}>
            <Icon name="chevD" className="icon collapse-chev" />
            <span className="ttl">{t('next_week')}</span>
            <span className="cnt">{nxt.length}</span>
            <div className="spacer" />
            <button className="btn btn-sm" onClick={(e) => { e.stopPropagation(); onToast(t('ai_brief') + ' ✓', 'info'); }}>
              <Icon name="sparkle" className="icon" stroke="var(--orange)" />{t('ai_brief')}
            </button>
          </div>
          <div className="panel-body">
            {nxt.length ? nxt.map(renderCard) : <div className="add-row" style={{ justifyContent: 'center', cursor: 'default' }}>{t('no_tasks')}</div>}
          </div>
          <div className="add-row" onClick={() => setAdding(nextId)}><Icon name="plus" /><span>{t('add_task')}</span></div>
        </div>
      </div>

      {adding != null && (
        <AddTaskModal
          weekId={adding}
          lang={lang}
          onClose={() => setAdding(null)}
          onCreate={(task) => { store.addTask(task); setAdding(null); onToast(t('create_task') + ' ✓', 'success'); }}
        />
      )}
    </div>
  );
}

export function ProductionSidebar({ store, lang, onToast }) {
  const labels = useMemo(() => makeLabels(lang), [lang]);
  const { t, depName } = labels;
  const nav = [
    ['mywork', 'my_week', 'check', null], ['board', 'board', 'grid', null], ['timeline', 'timeline', 'timeline', null],
    ['coord', 'coordination', 'at', 3], ['dash', 'dashboard', 'trend', null],
  ];
  const counts = {};
  store.weekTasks(store.selWeek).forEach((x) => (counts[x.dept] = (counts[x.dept] || 0) + 1));
  return (
    <>
      <nav id="nav">
        {nav.map(([id, key, ic, badge]) => (
          <div
            key={id}
            className={`nav-item ${id === 'mywork' ? 'active' : ''}`}
            onClick={() => id !== 'mywork' && onToast(`${t(key)} — prototype view`, 'info')}
          >
            <Icon name={ic} /><span>{t(key)}</span>
            {badge && <span className="nav-badge">{badge}</span>}
          </div>
        ))}
      </nav>
      <div className="mode-divider" />
      <div className="side-label" id="side-label">{t('departments')}</div>
      <div className="dept-list">
        {DEPTS.map((d) => (
          <div key={d.id} className={`dept-row ${store.deptFilter === d.id ? 'active' : ''}`} onClick={() => store.filterDept(d.id)}>
            <span className="dept-dot" style={{ background: d.color }} />
            {depName(d.id)}
            {counts[d.id] ? <span className="dept-count">{counts[d.id]}</span> : null}
          </div>
        ))}
      </div>
    </>
  );
}
