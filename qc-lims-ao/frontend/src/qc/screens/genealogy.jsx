// Batch Genealogy — ported from qc/sprint5.js (QC.render.genealogy). Builds a
// vertical SP timeline (cultivation → … → stability) for a chosen batch, with
// samples + CoAs at each step and any OOx investigations on the batch. Inline
// styles preserved verbatim via css().
import { useState } from 'react';
import { css } from '../../lib/style.js';
import { Icon } from '../../lib/icons.jsx';
import { makeQcLabels } from '../data.js';

const DOCS = { SOP_LIFECYCLE: 'PP-QC-SOP-001', SOP_SAMPLING: 'PP-QC-SOP-011' };

// Lifecycle flow — cultivation → harvest → trim → drying → curing → packaging →
// finished → retention → stability. (icons: leaf/wrench/sun/flask/box/shield/calendar)
const GENEALOGY_FLOW = [
  { sp: 'SP_01', en: 'Cultivation', mk: 'Култивација', icon: 'leaf', color: '#15A86B' },
  { sp: 'SP_02', en: 'Post-Harvest', mk: 'По берба', icon: 'leaf', color: '#3FA34D' },
  { sp: 'SP_03', en: 'Post-Hand Trim', mk: 'По рачно', icon: 'wrench', color: '#5A6B82' },
  { sp: 'SP_04', en: 'Post-Machine Trim', mk: 'По машинско', icon: 'wrench', color: '#5A6B82' },
  { sp: 'SP_05', en: 'Post-Drying', mk: 'По сушење', icon: 'sun', color: '#FF7A1A' },
  { sp: 'SP_06', en: '★ Pre-Packaging IPC', mk: '★ Пред пакување', icon: 'flask', color: '#7A5BE0' },
  { sp: 'SP_07', en: 'Finished Product', mk: 'Готов производ', icon: 'box', color: '#2F6BFF' },
  { sp: 'SP_08', en: 'Retention', mk: 'Ретенција', icon: 'shield', color: '#566884' },
  { sp: 'SP_09', en: 'Stability', mk: 'Стабилност', icon: 'calendar', color: '#0EA5A5' },
];

// ── Badges (mirroring QcModule.jsx conventions) ──
const StatusBadge = ({ st, labels }) => {
  const colorMap = { COLLECTED: 'var(--blue)', IN_TEST: 'var(--orange)', TESTED: 'var(--violet,#7A5BE0)', APPROVED: 'var(--green)', REJECTED: 'var(--red)' };
  const bgMap = { COLLECTED: 'var(--blue-soft)', IN_TEST: 'var(--orange-soft)', TESTED: 'var(--violet-soft,#ECE6FB)', APPROVED: 'var(--green-soft)', REJECTED: 'var(--red-soft)' };
  return (
    <span className="pill" style={css(`color:${colorMap[st] || 'var(--ink-3)'};background:${bgMap[st] || 'var(--surface-3)'};font-size:12px;padding:4px 10px`)}>
      <span className="dot" style={{ background: colorMap[st] || 'var(--ink-3)' }} />
      {labels.statusLabel(st)}
    </span>
  );
};
const EsigBadge = () => (
  <span className="pill" style={css('color:#0B7A4B;background:var(--green-soft);font-size:11px;padding:3px 8px;gap:4px')}>
    <Icon name="shield" className="icon" stroke="var(--green)" />E-sig
  </span>
);

export function Genealogy({ qc, lang }) {
  const labels = makeQcLabels(lang);
  const tr = (o) => (o && typeof o === 'object' ? o[lang] || o.en : o);
  const batches = [...new Set(qc.samples.map((s) => s.batch_id).filter(Boolean))];
  const [sel, setSel] = useState(batches[0]);
  const cur = sel || batches[0];
  const samples = qc.samples.filter((s) => s.batch_id === cur);
  const oosForBatch = qc.oos.filter((o) => o.batch_id === cur);

  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{tr({ en: 'Batch Genealogy', mk: 'Генеалогија на серија' })}</h1>
        <div className="spacer" />
        <select value={cur} onChange={(e) => setSel(e.target.value)} style={css('border:1px solid var(--line);border-radius:9px;padding:8px 12px;font-size:13px;font-weight:600;background:var(--surface);font-family:var(--font)')}>
          {batches.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
      </div>

      {/* Hero strip: batch + key stats */}
      <div style={css('background:linear-gradient(135deg,var(--blue),var(--blue-700));color:#fff;border-radius:16px;padding:20px 24px;margin-bottom:20px')}>
        <div className="row" style={css('gap:14px;align-items:flex-end')}>
          <div>
            <div style={css('font-size:11px;font-weight:700;letter-spacing:.4px;text-transform:uppercase;opacity:.7;margin-bottom:4px')}>{tr({ en: 'Batch', mk: 'Серија' })}</div>
            <div className="mono" style={css('font-size:30px;font-weight:800;letter-spacing:-1px')}>{cur}</div>
          </div>
          <div className="spacer" />
          {[[samples.length, tr({ en: 'samples', mk: 'примероци' })], [samples.filter((s) => s.coa).length, 'CoAs'], [oosForBatch.length, 'OOx']].map(([v, l], i) => (
            <div key={i} style={css('text-align:right')}>
              <div style={css('font-size:28px;font-weight:800;letter-spacing:-1px')}>{v}</div>
              <div style={css('font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;opacity:.7')}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Flow: vertical timeline of SPs */}
      <div style={css('position:relative')}>
        {GENEALOGY_FLOW.map((step, i) => {
          const samplesHere = samples.filter((s) => s.sampling_point === step.sp);
          const has = samplesHere.length > 0;
          return (
            <div key={step.sp} style={css('display:flex;gap:18px;margin-bottom:14px')}>
              <div style={css('display:flex;flex-direction:column;align-items:center;flex-shrink:0')}>
                <div style={css(`width:44px;height:44px;border-radius:11px;background:${has ? step.color : 'var(--surface-3)'};display:flex;align-items:center;justify-content:center;box-shadow:${has ? '0 4px 10px ' + step.color + '40' : 'none'}`)}>
                  <Icon name={step.icon} className="icon" stroke={has ? '#fff' : 'var(--ink-3)'} />
                </div>
                {i < GENEALOGY_FLOW.length - 1 ? <div style={css(`width:2px;flex:1;background:${has ? step.color : 'var(--line-2)'};margin-top:6px;min-height:32px`)} /> : null}
              </div>
              <div style={css(`flex:1;background:var(--surface);border:1px solid var(--line);border-left:4px solid ${has ? step.color : 'var(--line-2)'};border-radius:12px;padding:14px 18px;${has ? '' : 'opacity:.5'}`)}>
                <div className="row" style={css(`gap:10px;margin-bottom:${has ? 8 : 0}px`)}>
                  <span className="mono" style={css(`font-weight:800;font-size:12px;color:${has ? step.color : 'var(--ink-3)'}`)}>{step.sp.replace('_', '-')}</span>
                  <span style={css('font-weight:700;font-size:14px')}>{tr(step)}</span>
                  {has ? <span className="pill" style={css(`background:${step.color}18;color:${step.color};font-size:11px;padding:3px 9px;margin-left:auto`)}>{samplesHere.length} {samplesHere.length === 1 ? 'sample' : 'samples'}</span> : null}
                </div>
                {has ? (
                  <div style={css('display:flex;flex-direction:column;gap:6px;margin-top:8px')}>
                    {samplesHere.map((s) => (
                      <div key={s.id} className="row" style={css('gap:10px;padding:8px 11px;border:1px solid var(--line-2);border-radius:9px;cursor:pointer;background:var(--surface-2)')} onClick={() => qc.viewSample(s.id)}>
                        <span className="mono" style={css('font-weight:700;color:var(--blue);font-size:11.5px')}>{s.sample_id}</span>
                        <StatusBadge st={s.status} labels={labels} />
                        <span style={css('font-size:11.5px;color:var(--ink-2)')}>{labels.materialName(s)}</span>
                        <div className="spacer" />
                        {s.esig ? <EsigBadge /> : null}
                        {s.coa ? <span className="mono" style={css('font-size:10.5px;color:var(--ink-3)')}>{s.coa}</span> : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={css('font-size:11.5px;color:var(--ink-3);font-weight:600')}>{tr({ en: 'No samples at this point', mk: 'Нема примероци' })}</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {oosForBatch.length ? (
        <div style={css('margin-top:18px;padding:14px 18px;border-radius:12px;background:var(--red-soft);border:1px solid #F3C5C7')}>
          <div className="row" style={css('gap:10px;margin-bottom:8px')}><Icon name="alert" className="icon" stroke="var(--red)" /><span style={css('font-weight:800;color:#C0353A')}>{tr({ en: 'OOx investigations on this batch', mk: 'OOx истраги за оваа серија' })}</span></div>
          {oosForBatch.map((o) => (
            <div key={o.id} className="row" style={css('gap:10px;padding:7px 0;font-size:12.5px;font-weight:600;cursor:pointer')} onClick={() => qc.viewOOS(o.id)}>
              <span className="mono" style={css('font-weight:700;color:#C0353A')}>{o.id}</span>
              <span>{o.param}: {o.result} vs {o.spec}</span>
            </div>
          ))}
        </div>
      ) : null}

      <div style={css('margin-top:14px;font-size:10.5px;color:var(--ink-3);font-weight:600')}>
        <span className="mono">{DOCS.SOP_LIFECYCLE}</span> · <span className="mono">{DOCS.SOP_SAMPLING}</span>
      </div>
    </div>
  );
}
