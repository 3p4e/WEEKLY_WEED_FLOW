// Task card — collapsed + expanded, ported from gf/render.js `card(t)`.
import { useState } from 'react';
import { Icon } from '../lib/icons.jsx';
import { AvatarStack } from '../lib/ui.jsx';
import { PEOPLE, DEPTS, HANDOFF, dep, progressOf } from './data.js';

const peopleOf = (ids) => (ids || []).map((id) => PEOPLE[id]).filter(Boolean);

export function TaskCard({ task: t, lang, labels, expanded, store, tasksById, onToast }) {
  const { t: tr, depName, statusLabel, prLabel, dayLabel } = labels;
  const d = dep(t.dept);
  const prog = progressOf(t);
  const meta = [t.id, t.room, t.batch].filter(Boolean);
  const [note, setNote] = useState('');
  const [sub, setSub] = useState('');

  const head = (
    <div className="card-head" onClick={() => store.toggleExpand(t.id)}>
      <button
        className={`check ${t.status === 'done' ? 'done' : ''}`}
        onClick={(e) => {
          e.stopPropagation();
          store.toggleDone(t.id);
        }}
      >
        {t.status === 'done' && <Icon name="check" stroke="#fff" />}
      </button>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="card-title">{t.title}</div>
        <div className="card-meta">
          <span className="dn" style={{ color: d.color }}>
            {depName(t.dept)}
          </span>
          {meta.map((m, i) => (
            <span key={i}>
              <span>·</span> <span>{m}</span>
            </span>
          ))}
        </div>
      </div>
      <div className="daytags">
        {(t.days || []).map((x) => (
          <span className="daytag" key={x}>
            {dayLabel(x)}
          </span>
        ))}
      </div>
      <AvatarStack people={peopleOf([t.owner, ...(t.helpers || [])])} size={26} />
      <span
        className={`pill s-${t.status}`}
        onClick={(e) => {
          e.stopPropagation();
          store.cycleStatus(t.id);
        }}
      >
        <span className="dot" style={{ background: 'currentColor', opacity: 0.7 }} />
        {statusLabel(t.status)}
      </span>
      <span className={`prtag ${t.pr}`}>{prLabel(t.pr)}</span>
      <Icon name="chevD" className="icon chev-card" />
    </div>
  );

  if (!expanded) return <div className={`card s-${t.status}`}>{head}</div>;

  const toDept = HANDOFF[t.dept];

  return (
    <div className={`card s-${t.status} expanded`}>
      {head}
      <div className="card-body">
        {t.status === 'stuck' && t.blocker && (
          <div className="blocker">
            <Icon name="flag" />
            <div>
              <div className="bt">
                {tr('blocker')}: {t.blocker}
              </div>
            </div>
          </div>
        )}
        {t.desc && <div className="card-desc">{t.desc}</div>}

        <div className="sec-label">
          <Icon name="chat" className="icon" />
          {tr('notes')}
        </div>
        <div className="notes">
          {(t.notes || []).map((n, i) => (
            <div className="note" key={i}>
              <span className="nd">{dayLabel(n.d)}</span>
              <span>{n.n}</span>
            </div>
          ))}
        </div>
        <div className="note-input">
          <input
            value={note}
            placeholder={tr('add_note')}
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                store.addNote(t.id, note);
                setNote('');
              }
            }}
          />
          <button className="mini-btn ai" title={tr('paraphrase')} onClick={() => onToast(tr('paraphrase') + ' ✓', 'info')}>
            <Icon name="sparkle" />
          </button>
          <button
            className="mini-btn"
            style={{ color: 'var(--blue)' }}
            onClick={() => {
              store.addNote(t.id, note);
              setNote('');
            }}
          >
            <Icon name="plus" />
          </button>
        </div>

        <div className="sec-label">
          <Icon name="grid" className="icon" />
          {tr('subtasks')} {t.subs && t.subs.length ? `· ${t.subs.filter((s) => s.done).length}/${t.subs.length}` : ''}
        </div>
        <div className="subtasks">
          {(t.subs || []).map((s) => (
            <div className={`subtask ${s.done ? 'done' : ''}`} key={s.id}>
              <button
                className={`check ${s.done ? 'done' : ''}`}
                style={{ width: 18, height: 18 }}
                onClick={() => store.toggleSub(t.id, s.id)}
              >
                {s.done && <Icon name="check" stroke="#fff" />}
              </button>
              <span className="stt">{s.t}</span>
            </div>
          ))}
          <div className="sub-add">
            <input
              value={sub}
              placeholder={tr('add_sub')}
              onChange={(e) => setSub(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  store.addSub(t.id, sub);
                  setSub('');
                }
              }}
            />
            <button
              className="mini-btn"
              style={{ color: 'var(--blue)' }}
              onClick={() => {
                store.addSub(t.id, sub);
                setSub('');
              }}
            >
              <Icon name="plus" />
            </button>
          </div>
        </div>

        {(t.deps || []).length > 0 && (
          <>
            <div className="sec-label">
              <Icon name="link" className="icon" />
              {tr('deps')}
            </div>
            <div className="deps">
              {(t.deps || []).map((id) => {
                const dt = tasksById[id];
                if (!dt) return null;
                const met = dt.status === 'done';
                return (
                  <span className={`dep-chip ${met ? 'met' : 'unmet'}`} key={id}>
                    <Icon name="link" className="icon" />
                    {dt.title.slice(0, 28)}
                  </span>
                );
              })}
            </div>
          </>
        )}

        {toDept && (
          <>
            <div className="sec-label">
              <Icon name="arrowR" className="icon" />
              {tr('handoff')}
            </div>
            <div className="handoff">
              <span className="hbadge">
                <span className="chip-dept">
                  <Icon name={d.icon} className="icon" stroke={d.color} />
                </span>
                {depName(t.dept)}
              </span>
              <Icon name="arrowR" className="icon" stroke="var(--ink-3)" />
              <span className="hbadge">
                <span className="chip-dept">
                  <Icon name={dep(toDept).icon} className="icon" stroke={dep(toDept).color} />
                </span>
                {depName(toDept)}
              </span>
              <div className="spacer" />
              <button
                className="btn btn-orange btn-sm"
                onClick={() => onToast(`${tr('request_handoff')} → ${depName(toDept)}`, 'success')}
              >
                <Icon name="arrowR" className="icon" stroke="#fff" />
                {tr('request_handoff')}
              </button>
            </div>
          </>
        )}

        <div className="card-actions">
          <button className="btn btn-sm" onClick={() => onToast(tr('paraphrase') + ' ✓', 'info')}>
            <Icon name="sparkle" className="icon" stroke="var(--orange)" />
            {tr('paraphrase')}
          </button>
          <div className="track" style={{ maxWidth: 160, margin: '0 6px' }}>
            <span style={{ width: `${prog}%`, background: d.color }} />
          </div>
          <span className="mono" style={{ fontSize: 12, color: 'var(--ink-2)', fontWeight: 600 }}>
            {prog}%
          </span>
          <div className="spacer" />
          <button className="btn btn-sm btn-danger" onClick={() => store.deleteTask(t.id)}>
            <Icon name="trash" className="icon" />
            {tr('delete')}
          </button>
        </div>
      </div>
    </div>
  );
}

export { DEPTS };
