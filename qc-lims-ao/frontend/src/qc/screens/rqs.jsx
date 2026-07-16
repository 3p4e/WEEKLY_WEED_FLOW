// Sampling Requests (RQS) — list + detail with workflow stepper.
// Ported from the prototype qc/p1.js (QC.render.rqs / QC.render.rqsDetail),
// preserving inline styles (load-bearing for pixel parity) via the css() helper.
// Selection is kept in local state within RQS (the shared qc hook has no RQS
// selection); clicking a row swaps the list for an inline detail view.
import { useState } from 'react';
import { css } from '../../lib/style.js';
import { Icon } from '../../lib/icons.jsx';
import { SamplingPoint } from '../data.js';

// ── RQS enums (match backend) ──
const RQSStatusLabel = {
  OPEN: { en: 'Open', mk: 'Отворен' }, REGISTERED: { en: 'Registered', mk: 'Регистриран' },
  IN_PROGRESS: { en: 'In Progress', mk: 'Во тек' }, COMPLETED: { en: 'Completed', mk: 'Завршен' },
  CANCELLED: { en: 'Cancelled', mk: 'Откажан' },
};
const RQSStatusColor = { OPEN: 'var(--blue)', REGISTERED: 'var(--violet,#7A5BE0)', IN_PROGRESS: 'var(--orange)', COMPLETED: 'var(--green)', CANCELLED: 'var(--red)' };

// ── Seed sampling requests (from QC.SEED_RQS) ──
export const SEED_RQS = [
  { id: 'PP-RQS-2026-0021', rqs_id: 'PP-RQS-2026-0021', material_code: 'PP-MC-001', material_name_en: 'Cannabis Flower (Flower Room 3)', material_name_mk: 'Канабис цвет (Соба 3)', batch_id: 'PP-FP-2026-004', dept: 'Production', requested_by: 'marko', requested_at: '2026-06-01 08:30', assigned_sp: 'SP_06', status: 'IN_PROGRESS', registered_by: 'elena', due: '2026-06-02 08:30' },
  { id: 'PP-RQS-2026-0020', rqs_id: 'PP-RQS-2026-0020', material_code: 'PP-MC-WTR', material_name_en: 'Purified Water — Loop A', material_name_mk: 'Прочистена вода — Јамка А', batch_id: '', dept: 'Engineering', requested_by: 'goran', requested_at: '2026-05-31 14:00', assigned_sp: 'SP_03', status: 'COMPLETED', registered_by: 'stefan', due: '2026-06-01 14:00' },
  { id: 'PP-RQS-2026-0019', rqs_id: 'PP-RQS-2026-0019', material_code: 'PP-MC-001', material_name_en: 'Cannabis Flower (IPC drying)', material_name_mk: 'Канабис цвет (МПК сушење)', batch_id: 'PP-IPC-2026-013', dept: 'Production', requested_by: 'dimitar', requested_at: '2026-06-01 10:15', assigned_sp: 'SP_07', status: 'OPEN', registered_by: '', due: '2026-06-02 10:15' },
  { id: 'PP-RQS-2026-0018', rqs_id: 'PP-RQS-2026-0018', material_code: 'PP-MC-PKG', material_name_en: 'Packaging film — lot 88', material_name_mk: 'Фолија за пакување — лот 88', batch_id: '', dept: 'Packaging', requested_by: 'nina', requested_at: '2026-05-30 09:00', assigned_sp: 'SP_02', status: 'REGISTERED', registered_by: 'elena', due: '2026-05-31 09:00' },
];

// ── RQS status badge ──
function RQSBadge({ st, lang }) {
  const c = RQSStatusColor[st] || 'var(--ink-3)';
  const lbl = RQSStatusLabel[st] || { en: st, mk: st };
  return (
    <span className="pill" style={css(`color:${c};background:${c}18;font-size:11px;padding:3px 9px`)}>
      <span className="dot" style={{ background: c }} />{lang === 'mk' ? lbl.mk : lbl.en}
    </span>
  );
}

// ══════ SAMPLING REQUESTS LIST ══════
export function RQS({ qc, lang, labels, onToast }) {
  const [sel, setSel] = useState(null);
  if (sel) return <RQSDetail rqs={sel} onBack={() => setSel(null)} onChange={setSel} lang={lang} labels={labels} onToast={onToast} />;

  const list = qc.rqs ?? SEED_RQS;
  const cols = '160px 1fr 120px 80px 120px 90px';
  const openCount = list.filter((r) => r.status === 'OPEN').length;
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Барања за примерок (RQS)' : 'Sampling Requests (RQS)'}</h1>
        <span className="pill" style={css('background:var(--blue-soft);color:var(--blue-700);margin-left:8px')}>{openCount} {lang === 'mk' ? 'отворени' : 'open'}</span>
        <div className="spacer" />
        <button className="btn btn-primary btn-sm" onClick={() => onToast(`PP-QC-SOP-017 ${lang === 'mk' ? 'тек' : 'request flow'}`, 'info')}>
          <Icon name="plus" className="icon" stroke="#fff" />{lang === 'mk' ? 'Ново RQS' : 'New RQS'}
        </button>
      </div>
      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh-1)')}>
        <div style={css(`display:grid;grid-template-columns:${cols};padding:8px 16px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase`)}>
          <div>RQS ID</div><div>{lang === 'mk' ? 'Материјал' : 'Material'}</div><div>{lang === 'mk' ? 'Оддел' : 'Origin'}</div><div>SP</div><div>Status</div><div>{lang === 'mk' ? 'Рок' : 'Due'}</div>
        </div>
        {list.map((r, i) => {
          const overdue = r.status !== 'COMPLETED' && r.status !== 'CANCELLED' && new Date(r.due) < new Date('2026-06-01 12:00');
          return (
            <div key={r.id} style={css(`display:grid;grid-template-columns:${cols};padding:11px 16px;border-bottom:${i < list.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12.5px;font-weight:600;align-items:center;cursor:pointer`)} onClick={() => setSel(r)}>
              <div className="mono" style={css('font-weight:700;color:var(--blue)')}>{r.rqs_id}</div>
              <div>
                <div style={{ fontWeight: 700 }}>{lang === 'mk' ? r.material_name_mk : r.material_name_en}</div>
                {r.batch_id && <div className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{r.batch_id}</div>}
              </div>
              <div style={css('font-size:12px;color:var(--ink-2)')}>{r.dept}</div>
              <div className="mono" style={css('font-size:11px;font-weight:700;color:var(--ink-2)')}>{(SamplingPoint[r.assigned_sp] || {}).code || r.assigned_sp}</div>
              <div><RQSBadge st={r.status} lang={lang} /></div>
              <div className="mono" style={css(`font-size:10px;color:${overdue ? 'var(--red)' : 'var(--ink-3)'}`)}>{overdue ? '⚠ ' : ''}{r.due.slice(5, 10)}</div>
            </div>
          );
        })}
      </div>
      <div style={css('font-size:11px;color:var(--ink-3);margin-top:12px;font-weight:600')}>
        {lang === 'mk'
          ? 'Спрема PP-QC-SOP-017 — 24-часовен прозорец. Без одбројување.'
          : 'Per PP-QC-SOP-017 — 24-hour sampling window. Status tracked, no countdown timer (professional pace).'}
      </div>
    </div>
  );
}

// ══════ RQS DETAIL ══════
function RQSDetail({ rqs, onBack, onChange, lang, labels, onToast }) {
  const r = rqs;
  if (!r) return null;
  const sp = SamplingPoint[r.assigned_sp] || {};
  const fields = [
    [lang === 'mk' ? 'Материјал' : 'Material', lang === 'mk' ? r.material_name_mk : r.material_name_en],
    ['Material code', r.material_code],
    ['Batch', r.batch_id || '—'],
    [lang === 'mk' ? 'Оддел' : 'Origin dept', r.dept],
    [lang === 'mk' ? 'Побарано од' : 'Requested by', labels.personName(r.requested_by)],
    [lang === 'mk' ? 'Точка' : 'Sampling point', lang === 'mk' ? sp.mk || '' : sp.en || ''],
  ];
  const steps = [
    ['OPEN', 'Submitted', r.requested_by, r.requested_at],
    ['REGISTERED', 'Registered by QC', r.registered_by, r.registered_by ? r.requested_at : ''],
    ['IN_PROGRESS', 'Sampling in progress', '', ''],
    ['COMPLETED', 'Completed', '', ''],
  ];
  const curIdx = ['OPEN', 'REGISTERED', 'IN_PROGRESS', 'COMPLETED'].indexOf(r.status);

  const register = () => { onChange({ ...r, status: 'REGISTERED', registered_by: 'elena' }); onToast(lang === 'mk' ? 'RQS регистриран ✓' : 'RQS registered ✓', 'success'); };
  const complete = () => { onChange({ ...r, status: 'COMPLETED' }); onToast(lang === 'mk' ? 'Примерок креиран ✓' : 'Sample created from RQS ✓', 'success'); };

  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row mono" style={css('gap:6px;font-size:11px;color:var(--ink-3);margin-bottom:10px')}>
        <span style={{ cursor: 'pointer' }} onClick={onBack}>RQS</span>
        <Icon name="chevR" className="icon" stroke="var(--ink-3)" /><span style={{ color: 'var(--ink)' }}>{r.rqs_id}</span>
      </div>
      <div className="row" style={css('gap:8px;margin-bottom:16px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{r.rqs_id}</h1><RQSBadge st={r.status} lang={lang} />
      </div>
      <div style={css('display:grid;grid-template-columns:1fr 320px;gap:18px')}>
        <div>
          <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px')}>
            {fields.map(([l, v]) => (
              <div key={l} style={css('background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:10px 14px')}>
                <div style={css('font-size:10px;font-weight:700;color:var(--ink-3);text-transform:uppercase;letter-spacing:.4px')}>{l}</div>
                <div style={css('font-weight:700;font-size:13px;margin-top:2px')}>{v}</div>
              </div>
            ))}
          </div>
          {r.status === 'OPEN' ? (
            <button className="btn btn-primary" onClick={register}>
              <Icon name="check" className="icon" stroke="#fff" />{lang === 'mk' ? 'Регистрирај и додели' : 'Register & assign SP'}
            </button>
          ) : r.status === 'REGISTERED' || r.status === 'IN_PROGRESS' ? (
            <button className="btn btn-primary" onClick={complete}>
              <Icon name="box" className="icon" stroke="#fff" />{lang === 'mk' ? 'Креирај примерок' : 'Create sample & complete'}
            </button>
          ) : null}
        </div>
        <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px')}>
          <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:14px')}>{lang === 'mk' ? 'Тек на работа' : 'Workflow'}</div>
          {steps.map((st, i) => (
            <div key={i} className="row" style={css('gap:10px;margin-bottom:14px')}>
              <div style={css('display:flex;flex-direction:column;align-items:center;flex-shrink:0')}>
                <span style={css(`width:22px;height:22px;border-radius:999px;background:${i <= curIdx ? 'var(--green)' : 'var(--surface-3)'};display:flex;align-items:center;justify-content:center`)}>
                  {i <= curIdx ? <Icon name="check" className="icon" stroke="#fff" /> : <span style={css('font-size:11px;font-weight:700;color:var(--ink-3)')}>{i + 1}</span>}
                </span>
                {i < steps.length - 1 && <div style={css(`width:2px;height:18px;background:${i < curIdx ? 'var(--green)' : 'var(--line-2)'};margin-top:3px`)} />}
              </div>
              <div style={{ flex: 1 }}>
                <div style={css(`font-weight:700;font-size:12.5px;color:${i <= curIdx ? 'var(--ink)' : 'var(--ink-3)'}`)}>{st[1]}</div>
                {st[2] && <div style={css('font-size:11px;color:var(--ink-3)')}>{labels.personName(st[2])}{st[3] ? ' · ' + st[3] : ''}</div>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
