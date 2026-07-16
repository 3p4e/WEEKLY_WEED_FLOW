// CAPA Register — ported from qc/sprint5.js (QC.render.capa + capaDetail). List
// of corrective/preventive actions with progress, owner, OOx link; detail view
// with action-plan checklist and lifecycle stepper. Local useState replaces the
// prototype's QC.state.capa + re-render. Inline styles preserved via css().
import { useState, useEffect } from 'react';
import { css } from '../../lib/style.js';
import { Icon } from '../../lib/icons.jsx';
import { Avatar } from '../../lib/ui.jsx';
import { PEOPLE as BASE_PEOPLE } from '../data.js';

const DOCS = { SOP_OOX: 'QCSOP 019' };

// People extend data.js with the cultivation/QA owners referenced by CAPA seed.
const PEOPLE = {
  ...BASE_PEOPLE,
  goran: { name: 'Goran Petrov', init: 'GP', role: 'Cultivation', mk: 'Горан Петров', bg: '#15A86B' },
  marko: { name: 'Marko Ilievski', init: 'MI', role: 'Production', mk: 'Марко Илиевски', bg: '#C2410C' },
};

const CAPA_STATUS = {
  OPEN: { en: 'Open', mk: 'Отворен', color: 'var(--red)' },
  IN_PROGRESS: { en: 'In Progress', mk: 'Во тек', color: 'var(--orange)' },
  EFFECTIVE: { en: 'Effectiveness', mk: 'Ефективност', color: 'var(--blue)' },
  CLOSED: { en: 'Closed', mk: 'Затворен', color: 'var(--green)' },
};

const SEED_CAPA = [
  { id: 'CAPA-2025-019', oos: 'PP-OOS-2025-007', status: 'IN_PROGRESS', opened: '2025-09-30', owner: 'elena', due: '2025-12-30', title: 'Pesticide residue control — Flower Room 1 ventilation', actions: [
    { id: 1, what: 'Install dedicated extraction fans (Flower Room 1)', who: 'goran', due: '2025-11-15', done: true },
    { id: 2, what: 'Extend pre-harvest withholding to 14 days', who: 'marko', due: '2025-10-15', done: true },
    { id: 3, what: 'Re-validate IPM SOP and retrain operators', who: 'sofija', due: '2025-12-01', done: false },
    { id: 4, what: 'Effectiveness check — 3 consecutive batches PASS', who: 'elena', due: '2025-12-30', done: false },
  ] },
  { id: 'CAPA-2025-018', oos: 'PP-OOS-2025-006', status: 'CLOSED', opened: '2025-09-29', closed: '2025-10-20', owner: 'stefan', due: '2025-10-30', title: 'Inherent THC variance — Motor Breath cultivar', actions: [
    { id: 1, what: 'Adjust harvest window per phenotype assay', who: 'marko', due: '2025-10-15', done: true },
    { id: 2, what: 'Update QCSP-IMB-001 v02 — Motor Breath addendum', who: 'elena', due: '2025-10-20', done: true },
  ] },
  { id: 'CAPA-2025-017', oos: '', status: 'OPEN', opened: '2025-11-12', owner: 'elena', due: '2026-02-12', title: 'RO conductivity trend exceedance — preventive', actions: [
    { id: 1, what: 'Schedule RO membrane integrity test', who: 'goran', due: '2025-12-01', done: false },
    { id: 2, what: 'Increase TR sampling to monthly', who: 'stefan', due: '2025-11-30', done: false },
  ] },
];

const LIFECYCLE = ['OPEN', 'IN_PROGRESS', 'EFFECTIVE', 'CLOSED'];

const CapaBadge = ({ st, tr }) => {
  const c = (CAPA_STATUS[st] || {}).color || 'var(--ink-3)';
  return (
    <span className="pill" style={css(`background:${c}18;color:${c};font-size:11px;padding:3px 9px;font-weight:700`)}>
      <span className="dot" style={{ background: c }} />{tr(CAPA_STATUS[st] || { en: st, mk: st })}
    </span>
  );
};

export function CAPA({ qc, lang, onToast }) {
  const tr = (o) => (o && typeof o === 'object' ? o[lang] || o.en : o);
  const [capa, setCapa] = useState(() =>
    JSON.parse(JSON.stringify(qc.capa ?? SEED_CAPA))
  );
  const [selId, setSelId] = useState(null);
  // Re-sync when live data arrives from the backend after mount.
  useEffect(() => {
    if (qc.capa) setCapa(JSON.parse(JSON.stringify(qc.capa)));
  }, [qc.capa]);

  const sel = capa.find((c) => c.id === selId);

  const toggleAction = (cid, aid) => {
    setCapa((list) => list.map((c) => (c.id !== cid ? c : { ...c, actions: c.actions.map((a) => (a.id === aid ? { ...a, done: !a.done } : a)) })));
  };
  const advance = (cid, to) => {
    setCapa((list) => list.map((c) => (c.id !== cid ? c : { ...c, status: to, ...(to === 'CLOSED' ? { closed: new Date().toISOString().slice(0, 10) } : null) })));
    onToast(`CAPA ${to}`, 'success');
  };

  if (sel) {
    return (
      <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
        <div className="row mono" style={css('gap:6px;font-size:11px;color:var(--ink-3);margin-bottom:10px')}>
          <span style={{ cursor: 'pointer' }} onClick={() => setSelId(null)}>CAPA</span><Icon name="chevR" className="icon" stroke="var(--ink-3)" /><span style={{ color: 'var(--ink)' }}>{sel.id}</span>
        </div>
        <div className="row" style={css('gap:8px;margin-bottom:6px')}>
          <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{sel.id}</h1><CapaBadge st={sel.status} tr={tr} />
          {sel.oos ? <span className="pill" style={css('background:var(--red-soft);color:#C0353A;font-size:11px;font-weight:700;cursor:pointer')} onClick={() => qc.viewOOS(sel.oos)}>↳ {sel.oos}</span> : null}
        </div>
        <div style={css('font-size:14px;font-weight:700;color:var(--ink);margin-bottom:18px')}>{sel.title}</div>

        <div style={css('display:grid;grid-template-columns:1fr 320px;gap:18px')}>
          <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px')}>
            <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:12px')}>{tr({ en: 'Action plan', mk: 'План на дејства' })}</div>
            {sel.actions.map((a) => (
              <div key={a.id} className="row" style={css(`gap:12px;padding:12px 14px;border:1px solid var(--line-2);border-radius:10px;margin-bottom:8px;background:${a.done ? 'var(--green-soft)' : 'var(--surface)'};border-left:3px solid ${a.done ? 'var(--green)' : 'var(--orange)'}`)}>
                <label style={{ cursor: 'pointer' }}><input type="checkbox" checked={a.done} onChange={() => toggleAction(sel.id, a.id)} style={css('width:18px;height:18px;cursor:pointer')} /></label>
                <div style={{ flex: 1 }}>
                  <div style={css(`font-weight:700;font-size:13px;${a.done ? 'text-decoration:line-through;color:var(--ink-3)' : ''}`)}>{a.what}</div>
                  <div className="row" style={css('gap:8px;margin-top:4px;font-size:11px;color:var(--ink-3)')}>
                    <Avatar person={PEOPLE[a.who] || { init: '?', bg: '#8A99B0' }} size={20} /><span>{PEOPLE[a.who]?.name || a.who}</span>
                    <span>·</span><span className="mono">{tr({ en: 'due', mk: 'рок' })} {a.due}</span>
                  </div>
                </div>
              </div>
            ))}

            <div className="row" style={css('gap:8px;margin-top:14px')}>
              {sel.status === 'IN_PROGRESS' && sel.actions.every((a) => a.done) ? <button className="btn btn-primary" onClick={() => advance(sel.id, 'EFFECTIVE')}><Icon name="arrowR" className="icon" stroke="#fff" />{tr({ en: 'Move to Effectiveness check', mk: 'Преглед на ефективност' })}</button> : null}
              {sel.status === 'EFFECTIVE' ? <button className="btn btn-primary" onClick={() => advance(sel.id, 'CLOSED')}><Icon name="check" className="icon" stroke="#fff" />{tr({ en: 'Close CAPA (e-Sign)', mk: 'Затвори (е-потпис)' })}</button> : null}
              {sel.status === 'OPEN' ? <button className="btn btn-primary" onClick={() => advance(sel.id, 'IN_PROGRESS')}>{tr({ en: 'Start work', mk: 'Започни' })}</button> : null}
            </div>
          </div>
          <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px')}>
            <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:10px')}>{tr({ en: 'Lifecycle', mk: 'Животен циклус' })}</div>
            {LIFECYCLE.map((st, i) => {
              const idx = LIFECYCLE.indexOf(sel.status);
              const done = i < idx; const cur = i === idx;
              return (
                <div key={st} className="row" style={css('gap:10px;margin-bottom:12px')}>
                  <span style={css(`width:20px;height:20px;border-radius:999px;background:${done ? 'var(--green)' : cur ? CAPA_STATUS[st].color : 'var(--surface-3)'};display:flex;align-items:center;justify-content:center;flex-shrink:0`)}>{done ? <Icon name="check" className="icon" stroke="#fff" /> : <span className="mono" style={css(`font-size:10px;font-weight:700;color:${cur ? '#fff' : 'var(--ink-3)'}`)}>{i + 1}</span>}</span>
                  <span style={css(`font-size:12.5px;font-weight:${cur ? 700 : 600};color:${cur || done ? 'var(--ink)' : 'var(--ink-3)'}`)}>{tr(CAPA_STATUS[st])}</span>
                </div>
              );
            })}
            <div style={css('margin-top:14px;padding-top:14px;border-top:1px solid var(--line);font-size:11px;color:var(--ink-3);font-weight:600')}>
              <div>{tr({ en: 'Opened', mk: 'Отворен' })}: {sel.opened}</div>
              <div>{tr({ en: 'Owner', mk: 'Носител' })}: {PEOPLE[sel.owner]?.name}</div>
              {sel.closed ? <div>{tr({ en: 'Closed', mk: 'Затворен' })}: {sel.closed}</div> : null}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Register list ──
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{tr({ en: 'CAPA Register', mk: 'CAPA Регистар' })}</h1>
        <span className="pill" style={css('background:var(--red-soft);color:#C0353A;margin-left:8px')}>{capa.filter((c) => c.status !== 'CLOSED').length} {tr({ en: 'open', mk: 'отворени' })}</span>
        <div className="spacer" />
        <button className="btn btn-primary btn-sm" onClick={() => onToast(tr({ en: 'New CAPA', mk: 'Нов CAPA' }), 'info')}>+ {tr({ en: 'New CAPA', mk: 'Нов CAPA' })}</button>
      </div>

      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh-1)')}>
        <div style={css('display:grid;grid-template-columns:140px 1fr 130px 80px 100px 110px;padding:8px 16px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase')}>
          <div>CAPA ID</div><div>{tr({ en: 'Title', mk: 'Наслов' })}</div><div>OOx link</div><div>{tr({ en: 'Owner', mk: 'Носител' })}</div><div>{tr({ en: 'Due', mk: 'Рок' })}</div><div>Status</div>
        </div>
        {capa.map((c, i) => {
          const totalA = c.actions.length; const doneA = c.actions.filter((a) => a.done).length;
          const overdue = c.status !== 'CLOSED' && new Date(c.due) < new Date('2026-06-01');
          return (
            <div key={c.id} style={css(`display:grid;grid-template-columns:140px 1fr 130px 80px 100px 110px;padding:11px 16px;border-bottom:${i < capa.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12.5px;font-weight:600;align-items:center;cursor:pointer`)} onClick={() => setSelId(c.id)}>
              <div className="mono" style={css('font-weight:700;color:var(--blue)')}>{c.id}</div>
              <div>
                <div style={{ fontWeight: 700 }}>{c.title}</div>
                <div className="row" style={css('gap:6px;margin-top:4px')}><div style={css('height:5px;width:80px;background:var(--surface-3);border-radius:3px;overflow:hidden')}><div style={css(`height:100%;width:${totalA ? Math.round((doneA / totalA) * 100) : 0}%;background:var(--green)`)} /></div><span className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{doneA}/{totalA}</span></div>
              </div>
              <div className="mono" style={css(`font-size:11px;color:${c.oos ? 'var(--red)' : 'var(--ink-3)'}`)}>{c.oos || '—'}</div>
              <div><Avatar person={PEOPLE[c.owner] || { init: '?', bg: '#8A99B0' }} size={26} /></div>
              <div className="mono" style={css(`font-size:11px;color:${overdue ? 'var(--red)' : 'var(--ink-3)'}`)}>{overdue ? '⚠ ' : ''}{c.due.slice(5)}</div>
              <div><CapaBadge st={c.status} tr={tr} /></div>
            </div>
          );
        })}
      </div>
      <div style={css('margin-top:14px;font-size:10.5px;color:var(--ink-3);font-weight:600')}><span className="mono">{DOCS.SOP_OOX}</span> · {tr({ en: 'CAPA flow: Open → In Progress → Effectiveness check → Closed', mk: 'CAPA тек: Отворен → Во тек → Ефективност → Затворен' })}</div>
    </div>
  );
}
