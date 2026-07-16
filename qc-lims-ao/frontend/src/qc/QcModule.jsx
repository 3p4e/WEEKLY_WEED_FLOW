// QC Lab module — sidebar nav + workspace views. Ported from qc/render.js,
// preserving the prototype's inline styles (load-bearing for pixel parity) via
// the css() string→object helper.
import { useMemo } from 'react';
import { Icon } from '../lib/icons.jsx';
import { Avatar } from '../lib/ui.jsx';
import { css } from '../lib/style.js';
import {
  NAV, SampleType, SamplingPoint, PotencyGrade, OOSPhaseLabel, TEST_SPECS, PEOPLE, makeQcLabels,
} from './data.js';
import { Specs } from './screens/specs.jsx';
import { RQS } from './screens/rqs.jsx';
import { Review } from './screens/review.jsx';
import { Transport } from './screens/transport.jsx';
import { Water } from './screens/water.jsx';
import { Stability } from './screens/stability.jsx';
import { Genealogy } from './screens/genealogy.jsx';
import { CAPA } from './screens/capa.jsx';
import { Knowledge } from './screens/knowledge.jsx';
import { AIAudit } from './screens/aiaudit.jsx';

// ── Badges ──
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
const GradeBadge = ({ g, tr }) => {
  if (!g) return null;
  const c = g === 'A' ? 'var(--green)' : g === 'B' ? 'var(--blue)' : 'var(--orange)';
  return <span className="pill" style={css(`color:${c};background:${c}18;font-size:11px;padding:3px 8px`)}>{tr(PotencyGrade[g])}</span>;
};

// ── Sample table (shared by dashboard + samples list) ──
function SampleTable({ arr, lang, labels, qc }) {
  const cols = '120px 1fr 90px 70px 80px';
  return (
    <>
      <div style={css(`display:grid;grid-template-columns:${cols};padding:7px 18px;background:var(--surface-2);border-bottom:1px solid var(--line-2);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase`)}>
        <div>{lang === 'mk' ? 'Примерок' : 'Sample'}</div>
        <div>{lang === 'mk' ? 'Материјал' : 'Material'}</div>
        <div>{lang === 'mk' ? 'Тип' : 'Type'}</div>
        <div>Status</div>
        <div>{lang === 'mk' ? 'Датум' : 'Date'}</div>
      </div>
      {arr.map((s) => (
        <div key={s.id} style={css(`display:grid;grid-template-columns:${cols};padding:10px 18px;border-bottom:1px solid var(--line-2);font-size:12.5px;font-weight:600;cursor:pointer`)} onClick={() => qc.viewSample(s.id)}>
          <div className="mono" style={css('font-weight:700;color:var(--blue)')}>{s.sample_id}</div>
          <div>
            <div style={{ fontWeight: 700 }}>{labels.materialName(s)}</div>
            <div className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{s.batch_id}</div>
          </div>
          <div style={css('font-size:11px;color:var(--ink-2)')}>{labels.typeLabel(s.sample_type).slice(0, 12)}</div>
          <div><StatusBadge st={s.status} labels={labels} /></div>
          <div className="mono" style={css('font-size:11px;color:var(--ink-3)')}>{s.date}</div>
        </div>
      ))}
    </>
  );
}

const KPI = ({ l, v, ic, c, s, sub }) => (
  <div style={css('flex:1;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:14px 16px')}>
    <div className="row" style={css('gap:8px;margin-bottom:8px')}>
      <span style={css(`width:30px;height:30px;border-radius:9px;background:${s};display:flex;align-items:center;justify-content:center`)}>
        <Icon name={ic} className="icon" stroke={c} />
      </span>
      <span style={css('font-size:12px;font-weight:700;color:var(--ink-2)')}>{l}</span>
    </div>
    <div className="row" style={css('gap:6px;align-items:baseline')}>
      <span style={css('font-size:26px;font-weight:800;letter-spacing:-1px')}>{v}</span>
      {sub ? <span style={css(`font-size:11px;font-weight:700;color:${c}`)}>{sub}</span> : null}
    </div>
  </div>
);

// ══════ DASHBOARD ══════
function Dashboard({ qc, lang, labels }) {
  const all = qc.samples;
  const n = all.length;
  const app = all.filter((s) => s.status === 'APPROVED').length;
  const rej = all.filter((s) => s.status === 'REJECTED').length;
  const inTest = all.filter((s) => s.status === 'IN_TEST').length;
  const rate = n ? Math.round((app / n) * 100) : 0;
  const oosOpen = qc.oos.filter((o) => o.phase !== 'CLOSED').length;
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:18px')}>
        <div>
          <h1 style={css('font-size:22px;font-weight:800;letter-spacing:-.5px;margin:0')}>{lang === 'mk' ? 'Контролна табла' : 'QC Dashboard'}</h1>
          <div style={css('font-size:13px;color:var(--ink-2);font-weight:600;margin-top:2px')}>Purely Plant GmbH · EU GMP Annex 11 + MK GMP</div>
        </div>
        <div className="spacer" />
        <span className="pill" style={css('color:var(--blue-700);background:var(--blue-soft)')}>EU GMP</span>
        <span className="pill" style={css('color:#0B7A4B;background:var(--green-soft)')}>MK GMP</span>
      </div>
      <div className="row" style={css('gap:14px;margin-bottom:16px')}>
        <KPI l={lang === 'mk' ? 'Вкупно примероци' : 'Total Samples'} v={n} ic="flask" c="var(--blue)" s="var(--blue-soft)" />
        <KPI l={lang === 'mk' ? 'Во тестирање' : 'In Test'} v={inTest} ic="clock" c="var(--orange)" s="var(--orange-soft)" sub={inTest ? 'active' : ''} />
        <KPI l={lang === 'mk' ? 'Одобрени' : 'Approved'} v={app} ic="check" c="var(--green)" s="var(--green-soft)" />
        <KPI l={lang === 'mk' ? 'Одбиени / OOS' : 'Rejected / OOS'} v={rej + '/' + oosOpen} ic="flag" c="var(--red)" s="var(--red-soft)" sub={oosOpen ? 'CAPA' : ''} />
      </div>
      <div style={css('display:grid;grid-template-columns:1fr 320px;gap:16px')}>
        <div style={css('display:flex;flex-direction:column;gap:14px')}>
          <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden')}>
            <div className="row" style={css('padding:14px 18px;border-bottom:1px solid var(--line)')}>
              <h3 style={css('font-size:15px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Последни примероци' : 'Recent Samples'}</h3>
              <div className="spacer" />
              <button className="btn btn-sm" onClick={() => qc.navigate('samples')}>{lang === 'mk' ? 'Сите' : 'View all'} →</button>
            </div>
            <SampleTable arr={all.slice(0, 5)} lang={lang} labels={labels} qc={qc} />
          </div>
          {oosOpen ? (
            <div className="row" style={css('gap:12px;padding:13px 15px;border-radius:13px;background:var(--red-soft);border:1px solid #F3C5C7')}>
              <Icon name="alert" className="icon" stroke="var(--red)" />
              <div style={{ flex: 1 }}>
                <div style={css('font-weight:800;font-size:13px;color:#C0353A')}>{lang === 'mk' ? 'Отворени OOS истраги' : 'Open OOS Investigations'}: {oosOpen}</div>
                <div style={css('font-size:12px;font-weight:600;color:#9E3035;margin-top:1px')}>{qc.oos.filter((o) => o.phase !== 'CLOSED').map((o) => o.id).join(', ')}</div>
              </div>
              <button className="btn btn-sm" style={css('border-color:#F3C5C7;color:#C0353A')} onClick={() => qc.navigate('oos')}>{lang === 'mk' ? 'Преглед' : 'Review'}</button>
            </div>
          ) : null}
        </div>
        <div style={css('display:flex;flex-direction:column;gap:14px')}>
          <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px;text-align:center')}>
            <div style={css('font-size:10px;font-weight:700;letter-spacing:.5px;color:var(--ink-3);text-transform:uppercase;margin-bottom:12px')}>{lang === 'mk' ? 'Стапка на усогласеност' : 'Compliance Rate'}</div>
            <div style={css('width:110px;height:110px;margin:0 auto 10px;position:relative')}>
              <svg viewBox="0 0 100 100" width="110" height="110" style={{ transform: 'rotate(-90deg)' }}>
                <circle cx="50" cy="50" r="42" fill="none" stroke="var(--line-2)" strokeWidth="8" />
                <circle cx="50" cy="50" r="42" fill="none" stroke="var(--green)" strokeWidth="8" strokeDasharray={`${rate * 2.64} 264`} strokeLinecap="round" />
              </svg>
              <div style={css('position:absolute;inset:0;display:flex;align-items:center;justify-content:center')}>
                <span style={css('font-size:26px;font-weight:800;letter-spacing:-1px')}>{rate}<span style={css('font-size:13px;color:var(--ink-2)')}>%</span></span>
              </div>
            </div>
          </div>
          <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px')}>
            <h3 style={css('font-size:14px;font-weight:800;margin:0 0 10px')}>{lang === 'mk' ? 'По тип' : 'By Type'}</h3>
            {Object.keys(SampleType).map((tp) => {
              const c = all.filter((s) => s.sample_type === tp).length;
              return c ? (
                <div className="row" key={tp} style={css('gap:8px;margin-bottom:7px;font-size:12px;font-weight:600;color:var(--ink-2)')}>
                  <span className="dot" style={{ background: 'var(--blue)' }} />{labels.typeLabel(tp)}
                  <div className="spacer" /><span className="mono" style={{ fontWeight: 700 }}>{c}</span>
                </div>
              ) : null;
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// ══════ SAMPLES LIST ══════
function Samples({ qc, lang, labels }) {
  const f = qc.filterStatus;
  let list = qc.samples;
  if (f !== 'all') list = list.filter((s) => s.status === f);
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Примероци' : 'Samples'}</h1>
        <span className="pill" style={css('background:var(--surface-3);color:var(--ink-2);margin-left:8px')}>{qc.samples.length}</span>
        <div className="spacer" />
        <button className="btn btn-sm" onClick={() => qc.navigate('sp06')}><Icon name="barcode" className="icon" />SP-06 {lang === 'mk' ? 'Прием' : 'Reception'}</button>
        <button className="btn btn-primary btn-sm" onClick={() => qc.navigate('sp06')}><Icon name="plus" className="icon" stroke="#fff" />{lang === 'mk' ? 'Регистрирај' : 'Register'}</button>
      </div>
      <div className="row" style={css('gap:6px;margin-bottom:10px;flex-wrap:wrap')}>
        {['all', 'COLLECTED', 'IN_TEST', 'TESTED', 'APPROVED', 'REJECTED'].map((s) => (
          <span key={s} className="pill" style={css(`padding:6px 12px;font-size:12px;cursor:pointer;background:${f === s ? 'var(--ink)' : 'var(--surface)'};color:${f === s ? '#fff' : 'var(--ink-2)'};border:${f === s ? 'none' : '1px solid var(--line)'}`)} onClick={() => qc.setFilterStatus(s)}>
            {s === 'all' ? (lang === 'mk' ? 'Сите' : 'All') : labels.statusLabel(s)}
          </span>
        ))}
      </div>
      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh-1)')}>
        <SampleTable arr={list} lang={lang} labels={labels} qc={qc} />
      </div>
    </div>
  );
}

// ══════ RESULTS TABLE (within detail) ══════
function ResultsTable({ s, lang, qc }) {
  return (
    <>
      <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:8px')}>{lang === 'mk' ? 'Резултати од тестирање' : 'Test Results'}</div>
      <div style={css('border-radius:12px;overflow:hidden;border:1px solid var(--line);box-shadow:var(--sh-1);background:var(--surface);margin-bottom:14px')}>
        <div style={css('display:grid;grid-template-columns:1fr 150px 120px 90px 60px;padding:7px 14px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase')}>
          <div>{lang === 'mk' ? 'Параметар' : 'Parameter'}</div><div>{lang === 'mk' ? 'Метода' : 'Method'}</div><div>Spec</div><div>{lang === 'mk' ? 'Резултат' : 'Result'}</div><div>Status</div>
        </div>
        {TEST_SPECS.map((spec, i) => {
          const val = (s.results || {})[spec.id] || '—';
          const pass = val === '—' ? null : qc.passCheck(spec.id, val);
          return (
            <div key={spec.id} style={css(`display:grid;grid-template-columns:1fr 150px 120px 90px 60px;padding:8px 14px;border-bottom:${i < TEST_SPECS.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12px;font-weight:600;align-items:center`)}>
              <div style={{ fontWeight: 700 }}>{lang === 'mk' ? spec.mk || spec.p : spec.p}</div>
              <div className="mono" style={css('font-size:10px;color:var(--ink-2)')}>{spec.method.slice(0, 22)}</div>
              <div className="mono" style={css('font-size:11px;color:var(--ink-2)')}>{spec.specLabel || spec.specMin + '–' + spec.specMax}</div>
              <div className="mono" style={{ fontWeight: 700 }}>{val}</div>
              <div>{pass === null ? '' : pass ? <span className="pill" style={css('background:var(--green-soft);color:#0B7A4B;font-size:10px;padding:2px 7px')}>✓</span> : <span className="pill" style={css('background:var(--red-soft);color:#C0353A;font-size:10px;padding:2px 7px')}>✗</span>}</div>
            </div>
          );
        })}
      </div>
    </>
  );
}

// ══════ SAMPLE DETAIL / CoA ══════
function Detail({ qc, lang, labels }) {
  const s = qc.sample(qc.selSample);
  if (!s) return <div style={css('padding:40px;text-align:center;color:var(--ink-3)')}>Select a sample</div>;
  const hasR = Object.keys(s.results || {}).length > 0;
  const events = qc.audit.filter((e) => e.target === s.coa || e.target === s.id);
  return (
    <div style={css('display:flex;height:100%')}>
      <div style={css('flex:1;overflow:auto;padding:22px 26px;background:var(--bg)')}>
        <div className="row mono" style={css('gap:6px;font-size:11px;color:var(--ink-3);margin-bottom:10px')}>
          <span style={{ cursor: 'pointer' }} onClick={() => qc.navigate('samples')}>{lang === 'mk' ? 'Примероци' : 'Samples'}</span>
          <Icon name="chevR" className="icon" stroke="var(--ink-3)" /><span style={{ color: 'var(--ink)' }}>{s.coa || s.sample_id}</span>
        </div>
        <div className="row" style={css('gap:8px;margin-bottom:6px')}>
          <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{s.coa || s.sample_id}</h1>
          <StatusBadge st={s.status} labels={labels} />{s.esig && <EsigBadge />}<GradeBadge g={s.potency_grade} tr={labels.tr} />
        </div>
        <div className="mono" style={css('font-size:12px;color:var(--ink-2);font-weight:600;margin-bottom:4px')}>{s.batch_id} · {labels.materialName(s)}</div>
        <div style={css('font-size:12px;color:var(--ink-3);margin-bottom:18px')}>{labels.spLabel(s.sampling_point)} · {s.lab}</div>
        {s.esig && (
          <div className="row" style={css('gap:10px;padding:12px 14px;border-radius:12px;background:var(--green-soft);border:1px solid #B8E6C8;margin-bottom:16px')}>
            <span style={css('width:32px;height:32px;border-radius:999px;background:var(--green);display:flex;align-items:center;justify-content:center')}><Icon name="shield" className="icon" stroke="#fff" /></span>
            <div style={{ flex: 1 }}><div style={css('font-weight:800;font-size:13px;color:#0B7A4B')}>{lang === 'mk' ? 'Е-потпис верификуван' : 'E-Signature Verified'}</div></div>
          </div>
        )}
        {s.oos && (
          <div className="row" style={css('gap:10px;padding:12px 14px;border-radius:12px;background:var(--red-soft);border:1px solid #F3C5C7;margin-bottom:16px')}>
            <Icon name="alert" className="icon" stroke="var(--red)" />
            <div style={{ flex: 1 }}><div style={css('font-weight:800;color:#C0353A')}>OOS — {s.oos}</div></div>
            <button className="btn btn-sm" style={css('border-color:#F3C5C7;color:#C0353A')} onClick={() => qc.viewOOS(s.oos)}>{lang === 'mk' ? 'Преглед на истрага' : 'View investigation'}</button>
          </div>
        )}
        {hasR ? <ResultsTable s={s} lang={lang} qc={qc} /> : (
          <div style={css('padding:30px;text-align:center;color:var(--ink-3)')}>
            {lang === 'mk' ? 'Нема резултати' : 'No results yet'}<br />
            <button className="btn btn-primary" style={{ marginTop: 10 }} onClick={() => qc.editResults(s.id)}>{lang === 'mk' ? 'Внеси резултати' : 'Enter results'}</button>
          </div>
        )}
        <div className="row" style={css('gap:8px;margin-top:14px')}>
          {hasR && <button className="btn btn-sm" onClick={() => qc.editResults(s.id)}><Icon name="grid" className="icon" />{lang === 'mk' ? 'Уреди' : 'Edit'}</button>}
          {!s.esig && <button className="btn btn-primary btn-sm" onClick={() => qc.applyEsig(s.id)}><Icon name="shield" className="icon" stroke="#fff" />{lang === 'mk' ? 'Примени Е-потпис' : 'Apply E-Signature'}</button>}
        </div>
      </div>
      <div style={css('width:320px;flex-shrink:0;border-left:1px solid var(--line);background:var(--surface);display:flex;flex-direction:column')}>
        <div className="row" style={css('padding:16px 18px;border-bottom:1px solid var(--line)')}>
          <h3 style={css('font-size:14px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Хронологија' : 'Timeline'}</h3>
        </div>
        <div style={css('flex:1;overflow:auto;padding:16px 18px')}>
          {events.map((e, i) => (
            <div key={i} style={css('display:flex;gap:12px;margin-bottom:18px')}>
              <div style={css('display:flex;flex-direction:column;align-items:center;flex-shrink:0')}>
                <span style={css(`width:9px;height:9px;border-radius:999px;background:${e.type === 'esig' ? 'var(--green)' : e.type === 'oos' ? 'var(--red)' : 'var(--blue)'}`)} />
                {i < events.length - 1 && <div style={css('width:2px;flex:1;background:var(--line-2);margin-top:5px')} />}
              </div>
              <div style={{ flex: 1 }}>
                <div className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{e.ts}</div>
                <div style={css('font-weight:700;font-size:12.5px;margin:2px 0')}>{e.action}</div>
                <div style={css('font-size:11.5px;color:var(--ink-2)')}>{e.detail}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ══════ RESULTS ENTRY ══════
function Results({ qc, lang, labels, onToast }) {
  const s = qc.selSample ? qc.sample(qc.selSample) : qc.samples.find((x) => x.status === 'IN_TEST') || qc.samples[0];
  if (!s) return null;
  const cols = '30px 1fr 140px 110px 130px 60px';
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('gap:10px;margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Внес на резултати' : 'Results Entry'}</h1>
        <StatusBadge st={s.status} labels={labels} /><div className="spacer" />
        <button className="btn btn-primary btn-sm" onClick={() => { qc.applyEsig(s.id); onToast(lang === 'mk' ? 'Поднесено за преглед ✓' : 'Submitted for review ✓', 'success'); }}>
          <Icon name="check" className="icon" stroke="#fff" />{lang === 'mk' ? 'Поднеси за преглед' : 'Submit for review'}
        </button>
      </div>
      <div className="row" style={css('gap:12px;margin-bottom:16px')}>
        {[['Sample', s.sample_id], ['Batch', s.batch_id], [lang === 'mk' ? 'Материјал' : 'Material', labels.materialName(s)], [lang === 'mk' ? 'Аналитичар' : 'Analyst', labels.personName(s.analyst)]].map(([l, v]) => (
          <div key={l} style={css('background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:9px 12px;flex:1')}>
            <div style={css('font-size:10px;font-weight:700;color:var(--ink-3);text-transform:uppercase;letter-spacing:.4px')}>{l}</div>
            <div style={css('font-weight:700;font-size:13px;margin-top:2px')}>{v}</div>
          </div>
        ))}
      </div>
      <div style={css('border-radius:12px;overflow:hidden;border:1px solid var(--line);box-shadow:var(--sh-1);background:var(--surface)')}>
        <div style={css(`display:grid;grid-template-columns:${cols};padding:7px 14px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase`)}>
          <div>#</div><div>{lang === 'mk' ? 'Параметар' : 'Parameter'}</div><div>{lang === 'mk' ? 'Метода' : 'Method'}</div><div>Spec</div><div>{lang === 'mk' ? 'Резултат' : 'Result'}</div><div>✓/✗</div>
        </div>
        {TEST_SPECS.map((spec, i) => {
          const val = (s.results || {})[spec.id] || '';
          const pass = val ? qc.passCheck(spec.id, val) : null;
          return (
            <div key={spec.id} style={css(`display:grid;grid-template-columns:${cols};padding:8px 14px;border-bottom:${i < TEST_SPECS.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12px;font-weight:600;align-items:center;background:${pass === false ? 'var(--red-soft)' : 'var(--surface)'}`)}>
              <div className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{i + 1}</div>
              <div style={{ fontWeight: 700 }}>{lang === 'mk' ? spec.mk || spec.p : spec.p}</div>
              <div className="mono" style={css('font-size:10px;color:var(--ink-2)')}>{spec.method.slice(0, 20)}</div>
              <div className="mono" style={css('font-size:11px;color:var(--ink-2)')}>{spec.specLabel || spec.specMin + '–' + spec.specMax}</div>
              <div>
                <input defaultValue={val} placeholder={lang === 'mk' ? 'Внеси…' : 'Enter…'}
                  style={css('width:110px;border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:12px;font-weight:700;font-family:var(--mono);background:var(--surface-2);outline:none')}
                  onBlur={(e) => qc.updateResult(s.id, spec.id, e.target.value)} />
              </div>
              <div>{pass === null ? '' : pass ? <span style={css('color:var(--green);font-weight:800')}>✓</span> : <span style={css('color:var(--red);font-weight:800')}>✗</span>}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ══════ SP-06 RECEPTION ══════
function SP06({ qc, lang, onToast }) {
  const fields = [['batch_id', { en: 'Batch ID', mk: 'Серија' }, 'PP-FP-2026-004'], ['material_name_mk', { en: 'Material (МК)', mk: 'Материјал (МК)' }, 'Горила Глу #4'], ['material_name_en', { en: 'Material (EN)', mk: 'Материјал (EN)' }, 'Gorilla Glue #4 (Flower)'], ['material_code', { en: 'Material Code', mk: 'Шифра' }, 'PP-MC-001'], ['batch_size', { en: 'Batch Size (N)', mk: 'Големина (N)' }, '120']];
  const tr = (o) => o[lang] || o.en;
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <h1 style={css('font-size:22px;font-weight:800;margin:0 0 4px')}>{lang === 'mk' ? 'СП-06 Прием на серија' : 'SP-06 Batch Reception'}</h1>
      <div style={css('font-size:13px;color:var(--ink-2);font-weight:600;margin-bottom:20px')}>{lang === 'mk' ? 'Регистрирај влезна серија — автоматски креира СП-07, СП-08, СП-09' : 'Register incoming cannabis flower batch — auto-creates SP-07, SP-08, SP-09 child samples'}</div>
      <div style={css('display:grid;grid-template-columns:1fr 340px;gap:20px')}>
        <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:22px')}>
          {fields.map(([id, lb, ph]) => (
            <div key={id} style={css('margin-bottom:14px')}>
              <label style={css('display:block;font-size:11px;font-weight:700;color:var(--ink-2);margin-bottom:5px')}>{tr(lb)}</label>
              <input placeholder={ph} style={css('width:100%;border:1px solid var(--line);border-radius:9px;padding:9px 12px;font-size:13px;outline:none;background:var(--surface-2);font-family:var(--font)')} />
            </div>
          ))}
          <div className="row" style={css('gap:8px;margin-top:8px')}>
            <button className="btn" style={css('flex:1;justify-content:center')} onClick={() => qc.navigate('samples')}>{lang === 'mk' ? 'Откажи' : 'Cancel'}</button>
            <button className="btn btn-primary" style={css('flex:2;justify-content:center')} onClick={() => onToast(lang === 'mk' ? 'Серијата е примена ✓' : 'Batch received ✓', 'success')}>
              <Icon name="barcode" className="icon" stroke="#fff" />{lang === 'mk' ? 'Прими и креирај примероци' : 'Receive & Create Samples'}
            </button>
          </div>
        </div>
        <div style={css('display:flex;flex-direction:column;gap:14px')}>
          <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px')}>
            <div style={css('font-size:10px;font-weight:700;letter-spacing:.5px;color:var(--ink-3);text-transform:uppercase;margin-bottom:12px')}>{lang === 'mk' ? 'Автоматски креирани' : 'Auto-created children'}</div>
            {[['SP-07', { en: 'IPC — Drying', mk: 'МПК — Сушење' }, 'var(--orange)'], ['SP-08', { en: 'IPC — Curing', mk: 'МПК — Зреење' }, 'var(--violet,#7A5BE0)'], ['SP-09', { en: 'Finished Product', mk: 'Готов производ' }, 'var(--green)']].map(([sp, lb, c]) => (
              <div className="row" key={sp} style={css('gap:8px;margin-bottom:8px;font-size:12px;font-weight:600;color:var(--ink-2)')}>
                <span style={css(`width:20px;height:20px;border-radius:6px;background:${c}18;display:flex;align-items:center;justify-content:center`)}><span className="dot" style={{ background: c }} /></span>
                <span style={css('font-weight:700;color:var(--ink)')}>{sp}</span>{tr(lb)}
              </div>
            ))}
          </div>
          <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px')}>
            <div style={css('font-size:10px;font-weight:700;letter-spacing:.5px;color:var(--ink-3);text-transform:uppercase;margin-bottom:12px')}>{lang === 'mk' ? 'Усогласеност' : 'Compliance'}</div>
            {[{ en: 'Barcode assigned (PP-SMP-YYYY-NNNN)', mk: 'Баркод доделен' }, { en: 'Chain of custody initiated', mk: 'Ланец на надзор активиран' }, { en: 'Audit trail entry created', mk: 'Ревизорски запис креиран' }, { en: 'QCSOP 011 sampling plan applied', mk: 'QCSOP 011 план за земање примероци' }].map((c, i) => (
              <div className="row" key={i} style={css('gap:7px;margin-bottom:7px;font-size:11.5px;font-weight:600;color:var(--ink-2)')}>
                <span style={css('width:16px;height:16px;border-radius:999px;background:var(--green);display:flex;align-items:center;justify-content:center;flex-shrink:0')}><Icon name="check" className="icon" stroke="#fff" /></span>{tr(c)}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ══════ OOS LIST ══════
function OOSList({ qc, lang }) {
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:16px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{lang === 'mk' ? 'ООС Истраги' : 'OOS Investigations'}</h1>
        <span className="pill" style={css('background:var(--red-soft);color:#C0353A;margin-left:8px')}>{qc.oos.filter((o) => o.phase !== 'CLOSED').length} {lang === 'mk' ? 'отворени' : 'open'}</span>
      </div>
      <div style={css('display:flex;flex-direction:column;gap:10px')}>
        {qc.oos.map((o) => (
          <div key={o.id} style={css(`background:var(--surface);border:1px solid var(--line);border-left:4px solid ${o.phase === 'CLOSED' ? 'var(--green)' : 'var(--red)'};border-radius:12px;padding:14px 16px;cursor:pointer`)} onClick={() => qc.viewOOS(o.id)}>
            <div className="row" style={css('gap:8px;margin-bottom:6px')}>
              <span className="mono" style={css(`font-weight:700;color:${o.phase === 'CLOSED' ? 'var(--green)' : 'var(--red)'}`)}>{o.id}</span>
              <span className="pill" style={css(`background:${o.phase === 'CLOSED' ? 'var(--green-soft)' : 'var(--red-soft)'};color:${o.phase === 'CLOSED' ? '#0B7A4B' : '#C0353A'};font-size:10px`)}>{(OOSPhaseLabel[o.phase] || {})[lang] || ''}</span>
              <div className="spacer" /><span className="mono" style={css('font-size:11px;color:var(--ink-3)')}>{o.opened}</span>
            </div>
            <div style={css('font-weight:700;font-size:13px')}>{o.param}: {o.result} vs {o.spec}</div>
            <div className="mono" style={css('font-size:11px;color:var(--ink-3);margin-top:2px')}>{o.sample_id} · {o.batch_id}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ══════ OOS DETAIL ══════
function OOSDetail({ qc, lang, labels }) {
  const o = qc.oos.find((x) => x.id === qc.selOOS);
  if (!o) return null;
  const tr = (obj) => (obj ? obj[lang] || obj.en : '');
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row mono" style={css('gap:6px;font-size:11px;color:var(--ink-3);margin-bottom:10px')}>
        <span style={{ cursor: 'pointer' }} onClick={() => qc.navigate('oos')}>OOS</span><Icon name="chevR" className="icon" stroke="var(--ink-3)" /><span style={{ color: 'var(--ink)' }}>{o.id}</span>
      </div>
      <div className="row" style={css('gap:8px;margin-bottom:16px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{o.id}</h1>
        <span className="pill" style={css('background:var(--red-soft);color:#C0353A')}>{tr(OOSPhaseLabel[o.phase])}</span>
      </div>
      <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px')}>
        {[['Parameter', o.param], ['Result', o.result], ['Specification', o.spec], ['Sample', o.sample_id], ['Batch', o.batch_id], ['Opened by', labels.personName(o.opened_by)]].map(([l, v]) => (
          <div key={l} style={css('background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:10px 14px')}>
            <div style={css('font-size:10px;font-weight:700;color:var(--ink-3);text-transform:uppercase;letter-spacing:.4px')}>{l}</div>
            <div style={css('font-weight:700;font-size:14px;margin-top:2px')}>{v}</div>
          </div>
        ))}
      </div>
      {o.phase1 && (
        <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:14px')}>
          <div className="row" style={css('margin-bottom:10px')}>
            <h3 style={css('font-size:15px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Фаза I — Лаб. грешка' : 'Phase I — Lab Error Check'}</h3>
            <span className="pill" style={css('background:var(--green-soft);color:#0B7A4B;margin-left:8px;font-size:10px')}>{lang === 'mk' ? 'Завршено' : 'Complete'}</span>
          </div>
          <div style={css('font-size:13px;line-height:1.5;color:var(--ink)')}>{o.phase1.conclusion}</div>
          <div className="mono" style={css('font-size:11px;color:var(--ink-3);margin-top:6px')}>{lang === 'mk' ? 'Завршено' : 'Completed'}: {o.phase1.completed} · {labels.personName(o.phase1.by)}</div>
        </div>
      )}
      {o.phase2 && (
        <div style={css('background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--red);border-radius:14px;padding:18px;margin-bottom:14px')}>
          <div className="row" style={css('margin-bottom:10px')}>
            <h3 style={css('font-size:15px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Фаза II — Целосна истрага' : 'Phase II — Full Investigation'}</h3>
            <span className="pill" style={css(`background:${o.phase2.status === 'open' ? 'var(--orange-soft)' : 'var(--green-soft)'};color:${o.phase2.status === 'open' ? '#B45309' : '#0B7A4B'};margin-left:8px;font-size:10px`)}>{o.phase2.status}</span>
          </div>
          <div style={css('margin-bottom:8px')}>
            <div style={css('font-size:10px;font-weight:700;color:var(--ink-3);text-transform:uppercase;margin-bottom:4px')}>{lang === 'mk' ? 'Основна причина' : 'Root Cause'}</div>
            <div style={css('font-size:13px;line-height:1.5')}>{o.phase2.root_cause}</div>
          </div>
          <div>
            <div style={css('font-size:10px;font-weight:700;color:var(--ink-3);text-transform:uppercase;margin-bottom:4px')}>CAPA</div>
            <div style={css('font-size:13px;line-height:1.5;color:var(--orange)')}>{o.phase2.capa}</div>
          </div>
        </div>
      )}
    </div>
  );
}

// ══════ AI SEARCH ══════
function AISearch({ lang, onToast }) {
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <h1 style={css('font-size:22px;font-weight:800;margin:0 0 4px')}>{lang === 'mk' ? 'АИ Пребарување' : 'AI Search'}</h1>
      <div style={css('font-size:13px;color:var(--ink-2);font-weight:600;margin-bottom:18px')}>{lang === 'mk' ? 'Семантичко пребарување · Letta + DeepSeek' : 'Semantic query across lab records · Powered by Letta + DeepSeek'}</div>
      <div className="row" style={css('gap:8px;margin-bottom:22px')}>
        <div className="row" style={css('flex:1;gap:8px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 16px;box-shadow:var(--sh-2)')}>
          <Icon name="sparkle" className="icon" stroke="var(--orange)" />
          <input defaultValue={lang === 'mk' ? 'Покажи ги последните OOS и поврзаните CAPA' : 'Show recent OOS results and associated CAPAs'} style={css('flex:1;border:none;background:none;font-size:14px;font-weight:600;outline:none;font-family:var(--font)')} />
        </div>
        <button className="btn btn-primary" style={css('padding:12px 18px;border-radius:12px')} onClick={() => onToast(lang === 'mk' ? 'Поврзете го АИ серверот во Поставки' : 'Connect the AI backend in Settings', 'info')}><Icon name="arrowR" className="icon" stroke="#fff" /></button>
      </div>
      <div style={css('text-align:center;padding:30px;color:var(--ink-3);font-weight:600')}>{lang === 'mk' ? 'Внесете барање. АИ синтезира од лабораториските податоци.' : 'Enter a query. AI synthesises from your lab data.'}</div>
    </div>
  );
}

// ══════ AUDIT TRAIL ══════
function Audit({ qc, lang, onToast }) {
  const tc = { esig: 'var(--green)', review: 'var(--blue)', data: 'var(--ink-3)', custody: 'var(--orange)', upload: 'var(--violet,#7A5BE0)', oos: 'var(--red)' };
  const cols = '140px 70px 130px 110px 1fr 70px';
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:16px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Ревизорска трага' : 'Audit Trail'}</h1>
        <span className="pill" style={css('color:var(--blue-700);background:var(--blue-soft);margin-left:8px')}>EU GMP Annex 11</span>
        <span className="pill" style={css('color:#0B7A4B;background:var(--green-soft)')}>ALCOA++</span>
        <div className="spacer" />
        <button className="btn btn-sm" onClick={() => onToast(lang === 'mk' ? 'Филтер' : 'Filter', 'info')}><Icon name="filter" className="icon" />{lang === 'mk' ? 'Филтер' : 'Filter'}</button>
        <button className="btn btn-sm" onClick={() => onToast(lang === 'mk' ? 'Извези' : 'Export', 'info')}><Icon name="forward" className="icon" />{lang === 'mk' ? 'Извези' : 'Export'}</button>
      </div>
      <div style={css('border-radius:12px;overflow:hidden;border:1px solid var(--line);box-shadow:var(--sh-1);background:var(--surface)')}>
        <div style={css(`display:grid;grid-template-columns:${cols};padding:7px 14px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase`)}>
          <div>{lang === 'mk' ? 'Време' : 'Time'}</div><div>{lang === 'mk' ? 'Корисник' : 'User'}</div><div>{lang === 'mk' ? 'Акција' : 'Action'}</div><div>{lang === 'mk' ? 'Цел' : 'Target'}</div><div>{lang === 'mk' ? 'Детали' : 'Details'}</div><div>Type</div>
        </div>
        {qc.audit.map((e, i) => (
          <div key={i} style={css(`display:grid;grid-template-columns:${cols};padding:10px 14px;border-bottom:${i < qc.audit.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12px;font-weight:600;align-items:center`)}>
            <div className="mono" style={css('font-size:11px;color:var(--ink-2)')}>{e.ts}</div>
            <div><Avatar person={PEOPLE[e.user] || { init: '?', bg: '#8A99B0' }} size={24} /></div>
            <div style={{ fontWeight: 700 }}>{e.action}</div>
            <div className="mono" style={css('font-size:11px;font-weight:700;color:var(--blue)')}>{e.target}</div>
            <div style={css('font-size:11.5px;color:var(--ink-2)')}>{e.detail}</div>
            <div><span className="pill" style={css(`background:${tc[e.type] || 'var(--ink-3)'}1A;color:${tc[e.type] || 'var(--ink-3)'};font-size:9px;padding:2px 6px`)}>{e.type}</span></div>
          </div>
        ))}
      </div>
      <div className="row" style={css('gap:8px;margin-top:12px;padding:10px 14px;border-radius:11px;background:var(--surface);border:1px solid var(--line)')}>
        <Icon name="shield" className="icon" stroke="var(--green)" /><span style={css('font-size:12px;font-weight:700;color:#0B7A4B')}>{lang === 'mk' ? 'Интегритет верифициран' : 'Integrity verified'}</span>
        <span className="mono" style={css('font-size:10px;color:var(--ink-3)')}>· SHA-256 · {qc.audit.length} events</span>
      </div>
    </div>
  );
}

// ── Public components ──
export function QcSidebar({ qc, lang }) {
  const openOOS = qc.oos.filter((o) => o.phase !== 'CLOSED').length;
  const tr = (o) => o[lang] || o.en;
  return (
    <nav id="qc-nav-inner">
      {NAV.map((n) => {
        const active = n.id === qc.view || (n.id === 'oos' && qc.view === 'oosDetail') || (n.id === 'samples' && qc.view === 'detail');
        return (
          <div key={n.id} className={`nav-item ${active ? 'active' : ''}`} onClick={() => qc.navigate(n.id)}>
            <Icon name={n.icon} /><span>{tr(n.label)}</span>
            {n.id === 'oos' && openOOS ? <span className="nav-badge">{openOOS}</span> : null}
          </div>
        );
      })}
    </nav>
  );
}

export function QcWorkspace({ qc, lang, onToast }) {
  const labels = useMemo(() => makeQcLabels(lang), [lang]);
  const common = { qc, lang, labels, onToast };
  switch (qc.view) {
    case 'samples': return <Samples {...common} />;
    case 'specs': return <Specs {...common} />;
    case 'rqs': return <RQS {...common} />;
    case 'review': return <Review {...common} />;
    case 'transport': return <Transport {...common} />;
    case 'water': return <Water {...common} />;
    case 'stability': return <Stability {...common} />;
    case 'genealogy': return <Genealogy {...common} />;
    case 'capa': return <CAPA {...common} />;
    case 'knowledge': return <Knowledge {...common} />;
    case 'aiaudit': return <AIAudit {...common} />;
    case 'detail': return <Detail {...common} />;
    case 'results': return <Results {...common} />;
    case 'sp06': return <SP06 {...common} />;
    case 'oos': return <OOSList {...common} />;
    case 'oosDetail': return <OOSDetail {...common} />;
    case 'search': return <AISearch {...common} />;
    case 'audit': return <Audit {...common} />;
    default: return <Dashboard {...common} />;
  }
}
