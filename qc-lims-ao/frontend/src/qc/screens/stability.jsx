// Stability Programme — ported from qc/stability-oox.js (study model + dashboard
// + detail) and qc/sprint4.js (A08 Withdrawal · A09 Execution · A10 Annual plan),
// folding the OOx/trend terminology in where it belongs. Inline styles preserved
// verbatim via css() for pixel parity.
import { useState } from 'react';
import { css } from '../../lib/style.js';
import { Icon } from '../../lib/icons.jsx';

// ── Doc refs (QCSOP 018 stability + QCSOP 019 OOx) ──
const DOCS = {
  SOP_OOX: 'QCSOP 019',
  SOP_STABILITY: 'QCSOP 018 v02',
  STAB_PROTO_LT: 'QCSOP 018-A01',
  STAB_PROTO_ACC: 'QCSOP 018-A02',
  STAB_PROTO_INT: 'QCSOP 018-A03',
  STAB_REPORT_LT: 'QCSOP 018-A04',
  STAB_REPORT_ACC: 'QCSOP 018-A05',
  STAB_REPORT_INT: 'QCSOP 018-A06',
  STAB_SCHEDULE: 'QCSOP 018-A07',
  STAB_WITHDRAWAL: 'QCSOP 018-A08',
  STAB_EXECUTION: 'QCSOP 018-A09',
  STAB_ANNUAL: 'QCSOP 018-A10',
  STAB_QRC: 'QCSOP 018-O2',
  STAB_DELTA: 'QCSOP 018-O3',
  STAB_RESERVE: 'QCSOP 018-O4',
  STAB_CLOSURE: 'QCSOP 018-O5',
};

// ── Stability model (per QCSOP 018) ──
const STAB_TYPE = {
  LT: { code: 'LT', en: 'Long-Term', mk: 'Долгорочна', temp: '25°C', rh: '60% RH', duration: '24 months', time_points: [0, 3, 6, 9, 12, 18, 24], proto: DOCS.STAB_PROTO_LT, report: DOCS.STAB_REPORT_LT },
  ACC: { code: 'ACC', en: 'Accelerated', mk: 'Забрзана', temp: '40°C', rh: '75% RH', duration: '6 months', time_points: [0, 1, 2, 3, 6], proto: DOCS.STAB_PROTO_ACC, report: DOCS.STAB_REPORT_ACC },
  INT: { code: 'INT', en: 'Intermediate', mk: 'Средна', temp: '30°C', rh: '65% RH', duration: '12 months', time_points: [0, 3, 6, 9, 12], proto: DOCS.STAB_PROTO_INT, report: DOCS.STAB_REPORT_INT, trigger: 'Activated only if significant change @ ACC per QCSOP 018 §6.10' },
};
const STAB_CLASS = {
  FULL: { en: 'FULL', tests: 'CNP + MIC + CON + TOX', when: 'T0 + final TP' },
  MEDIUM: { en: 'MEDIUM', tests: 'CNP + MIC + CON', when: 'Mid-TPs (6/12/18 LT; 3 ACC)' },
  REDUCED: { en: 'REDUCED', tests: 'CNP + MIC', when: 'Early TPs (1/2 ACC; 3/9 LT)' },
};
const stabSampleId = (type, batch, tp, param, n, N) => `SS-${type}-${batch}-T${tp}-${param}-P${n}/${N}`;
const stabSRS = (nB) => Math.floor(Math.sqrt(nB) * 1.5);
const stabClassify = (typeCode, tp) => {
  if (tp === 0) return 'FULL';
  const t = STAB_TYPE[typeCode];
  const final = t.time_points[t.time_points.length - 1];
  if (tp === final) return 'FULL';
  if (typeCode === 'LT') return [6, 12, 18].includes(tp) ? 'MEDIUM' : 'REDUCED';
  if (typeCode === 'ACC') return tp === 3 ? 'MEDIUM' : 'REDUCED';
  if (typeCode === 'INT') return 'MEDIUM';
  return 'REDUCED';
};

// ── Seed stability studies ──
const SEED_STAB = [
  { id: 'LT-2026-001', type: 'LT', material: 'TD1-DF400', material_name_en: 'Gorilla Glue — Dried Cannabis Flower', material_name_mk: 'Горила Глу — Сушен канабис цвет', batches: ['GG1024', 'GG1024_02', 'GG0824'], started: '2026-01-15', status: 'IN_PROGRESS', protocol: DOCS.STAB_PROTO_LT, schedule: DOCS.STAB_SCHEDULE },
  { id: 'ACC-2026-001', type: 'ACC', material: 'TD1-DF400', material_name_en: 'Gorilla Glue — Dried Cannabis Flower', material_name_mk: 'Горила Глу — Сушен канабис цвет', batches: ['GG1024', 'GG1024_02', 'GG0824'], started: '2026-01-15', status: 'IN_PROGRESS', protocol: DOCS.STAB_PROTO_ACC, schedule: DOCS.STAB_SCHEDULE },
  { id: 'LT-2025-003', type: 'LT', material: 'TD1-DF400', material_name_en: 'Blue Gelato — Dried Cannabis Flower', material_name_mk: 'Блу Желато — Сушен канабис цвет', batches: ['BG1024', 'BG0824', 'BG0624'], started: '2025-06-01', status: 'IN_PROGRESS', protocol: DOCS.STAB_PROTO_LT, schedule: DOCS.STAB_SCHEDULE },
  { id: 'LT-2024-002', type: 'LT', material: 'TD1-DF400', material_name_en: 'Grape Pie — Dried Cannabis Flower', material_name_mk: 'Грејп Пај — Сушен канабис цвет', batches: ['GP0824', 'GP0624', 'GP0424'], started: '2024-09-01', status: 'CLOSED', protocol: DOCS.STAB_PROTO_LT, report: DOCS.STAB_REPORT_LT, shelf_life: '18 months (assigned)' },
];

const typeColor = (type) => (type === 'LT' ? 'var(--blue)' : type === 'ACC' ? 'var(--orange)' : 'var(--violet,#7A5BE0)');

// ── Badges ──
const StabBadge = ({ st }) => {
  const c = st === 'IN_PROGRESS' ? 'var(--orange)' : st === 'CLOSED' ? 'var(--green)' : 'var(--ink-3)';
  return <span className="pill" style={css(`color:${c};background:${c}18;font-size:11px;padding:3px 9px`)}>{st.replace('_', ' ')}</span>;
};

export function Stability({ qc, lang, labels, onToast }) {
  const tr = (o) => (o && typeof o === 'object' ? o[lang] || o.en : o);
  // local sub-view state: { name:'list'|'detail'|'a08'|'a09'|'a10', id, tp, batch }
  const [view, setView] = useState({ name: 'list' });
  const studies = qc.stability ?? SEED_STAB;
  const stab = (id) => studies.find((s) => s.id === id);

  const goList = () => setView({ name: 'list' });
  const goDetail = (id) => setView({ name: 'detail', id });
  const goA08 = (id, tp) => setView({ name: 'a08', id, tp });
  const goA09 = (id, batch) => setView({ name: 'a09', id, batch });
  const goA10 = () => setView({ name: 'a10' });

  if (view.name === 'detail') return <StabDetail s={stab(view.id)} lang={lang} tr={tr} goList={goList} goA08={goA08} goA09={goA09} goA10={goA10} />;
  if (view.name === 'a08') return <StabA08 s={stab(view.id)} tp={view.tp ?? 0} lang={lang} tr={tr} goList={goList} goDetail={goDetail} onToast={onToast} />;
  if (view.name === 'a09') return <StabA09 s={stab(view.id)} batch={view.batch} lang={lang} tr={tr} goList={goList} goDetail={goDetail} goA08={goA08} goA09={goA09} />;
  if (view.name === 'a10') return <StabA10 studies={studies} lang={lang} tr={tr} goList={goList} goDetail={goDetail} />;

  // ── Programme overview ──
  const active = studies.filter((s) => s.status === 'IN_PROGRESS');
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{tr({ en: 'Stability Programme', mk: 'Програма за стабилност' })}</h1>
        <span className="pill" style={css('background:var(--blue-soft);color:var(--blue-700);margin-left:8px')}>{active.length} {tr({ en: 'active', mk: 'активни' })}</span>
        <div className="spacer" />
        <button className="btn btn-sm" onClick={goA10}><Icon name="calendar" className="icon" />{tr({ en: 'Annual plan', mk: 'Годишен план' })}</button>
        <button className="btn btn-primary btn-sm" onClick={() => onToast(tr({ en: 'New study — protocol-driven', mk: 'Нова студија' }), 'info')}><Icon name="plus" className="icon" stroke="#fff" />{tr({ en: 'New study', mk: 'Нова студија' })}</button>
      </div>

      {/* Study-type conditions strip (Quick Reference Card §1) */}
      <div className="row" style={css('gap:12px;margin-bottom:18px')}>
        {Object.values(STAB_TYPE).map((t) => (
          <div key={t.code} style={css(`flex:1;background:var(--surface);border:1px solid var(--line);border-top:4px solid ${typeColor(t.code)};border-radius:14px;padding:14px 16px`)}>
            <div className="row" style={css('gap:8px;margin-bottom:6px')}>
              <span style={css('font-weight:800;font-size:14px')}>{tr({ en: t.en, mk: t.mk })}</span>
              <span className="pill mono" style={css('background:var(--surface-3);color:var(--ink-2);font-size:10px')}>{t.code}</span>
            </div>
            <div className="mono" style={css('font-size:11.5px;color:var(--ink-2);line-height:1.7')}>{t.temp} · {t.rh} · {t.duration}</div>
            <div className="mono" style={css('font-size:10.5px;color:var(--ink-3);margin-top:4px')}>TPs: {t.time_points.join(', ')} mo</div>
            {t.trigger ? <div style={css('font-size:10.5px;color:var(--orange);font-weight:600;margin-top:6px;line-height:1.4')}>⚠ {t.trigger}</div> : null}
          </div>
        ))}
      </div>

      {/* Studies list */}
      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh-1)')}>
        <div style={css('display:grid;grid-template-columns:140px 1fr 60px 100px 100px 110px;padding:8px 16px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase')}>
          <div>Study ID</div><div>{tr({ en: 'Material', mk: 'Материјал' })}</div><div>Type</div><div>{tr({ en: 'Batches', mk: 'Серии' })}</div><div>{tr({ en: 'Started', mk: 'Започната' })}</div><div>Status</div>
        </div>
        {studies.map((st, i) => (
          <div key={st.id} style={css(`display:grid;grid-template-columns:140px 1fr 60px 100px 100px 110px;padding:11px 16px;border-bottom:${i < studies.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12.5px;font-weight:600;align-items:center;cursor:pointer`)} onClick={() => goDetail(st.id)}>
            <div className="mono" style={css('font-weight:700;color:var(--blue)')}>{st.id}</div>
            <div>
              <div style={{ fontWeight: 700 }}>{lang === 'mk' ? st.material_name_mk : st.material_name_en}</div>
              <div className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{st.material}</div>
            </div>
            <div><span className="pill" style={css(`background:${typeColor(st.type)}18;color:${typeColor(st.type)};font-size:10px;padding:2px 7px;font-weight:700`)}>{st.type}</span></div>
            <div className="mono" style={css('font-size:11px;color:var(--ink-2)')}>{st.batches.length}</div>
            <div className="mono" style={css('font-size:11px;color:var(--ink-3)')}>{st.started}</div>
            <div><StabBadge st={st.status} /></div>
          </div>
        ))}
      </div>

      <div className="row" style={css('gap:14px;margin-top:14px;flex-wrap:wrap')}>
        <span className="mono" style={css('font-size:10px;color:var(--ink-3);font-weight:600')}>{DOCS.SOP_STABILITY}</span>
        <span style={css('font-size:10px;color:var(--ink-3)')}>·</span>
        <span className="mono" style={css('font-size:10px;color:var(--ink-3);font-weight:600')}>{tr({ en: 'SRS formula', mk: 'SRS формула' })}: nG = ⌊√nB × 1.5⌋</span>
        <span style={css('font-size:10px;color:var(--ink-3)')}>·</span>
        <span className="mono" style={css('font-size:10px;color:var(--ink-3);font-weight:600')}>{tr({ en: 'TP classification', mk: 'Класификација TP' })}: FULL / MEDIUM / REDUCED</span>
      </div>
    </div>
  );
}

// ── Study detail with schedule grid (per QCSOP 018-A07) ──
function StabDetail({ s, lang, tr, goList, goA08, goA09, goA10 }) {
  if (!s) return null;
  const t = STAB_TYPE[s.type];
  const monthsElapsed = Math.floor((new Date('2026-06-01') - new Date(s.started)) / (1000 * 60 * 60 * 24 * 30));
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row mono" style={css('gap:6px;font-size:11px;color:var(--ink-3);margin-bottom:10px')}>
        <span style={{ cursor: 'pointer' }} onClick={goList}>{tr({ en: 'Stability', mk: 'Стабилност' })}</span><Icon name="chevR" className="icon" stroke="var(--ink-3)" /><span style={{ color: 'var(--ink)' }}>{s.id}</span>
      </div>
      <div className="row" style={css('gap:8px;margin-bottom:6px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{s.id}</h1>
        <span className="pill" style={css(`background:${typeColor(s.type)}18;color:${typeColor(s.type)};font-weight:700`)}>{tr({ en: t.en, mk: t.mk })}</span>
        <StabBadge st={s.status} />
      </div>
      <div style={css('font-size:13px;color:var(--ink-2);font-weight:600;margin-bottom:16px')}>{lang === 'mk' ? s.material_name_mk : s.material_name_en} · {s.material}</div>

      {/* Conditions */}
      <div className="row" style={css('gap:12px;margin-bottom:18px')}>
        {[[tr({ en: 'Temperature', mk: 'Температура' }), t.temp], [tr({ en: 'Humidity', mk: 'Влажност' }), t.rh], [tr({ en: 'Duration', mk: 'Времетраење' }), t.duration], [tr({ en: 'Started', mk: 'Започната' }), s.started], [tr({ en: 'Batches', mk: 'Серии' }), s.batches.join(', ')]].map(([l, v]) => (
          <div key={l} style={css('flex:1;background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:10px 14px')}>
            <div style={css('font-size:10px;font-weight:700;color:var(--ink-3);text-transform:uppercase;letter-spacing:.4px')}>{l}</div>
            <div className="mono" style={css('font-weight:700;font-size:13px;margin-top:2px')}>{v}</div>
          </div>
        ))}
      </div>

      {/* Time-point schedule (per QCSOP 018-A07 / O2) */}
      <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:8px')}>{tr({ en: 'Withdrawal schedule', mk: 'Распоред на повлекувања' })} <span className="mono" style={css('color:var(--ink-3);font-weight:500;text-transform:none')}>· {DOCS.STAB_SCHEDULE}</span></div>
      <div style={css('border-radius:12px;overflow:hidden;border:1px solid var(--line);box-shadow:var(--sh-1);background:var(--surface);margin-bottom:18px')}>
        <div style={css('display:grid;grid-template-columns:80px 110px 1fr 90px 110px;padding:7px 14px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase')}>
          <div>{tr({ en: 'Time pt', mk: 'Време' })}</div><div>{tr({ en: 'Class', mk: 'Класа' })}</div><div>{tr({ en: 'Tests', mk: 'Тестови' })}</div><div>{tr({ en: 'Bags', mk: 'Кеси' })}</div><div>Status</div>
        </div>
        {t.time_points.map((tp, i) => {
          const cls = stabClassify(s.type, tp);
          const c = STAB_CLASS[cls];
          const done = tp <= monthsElapsed && s.status !== 'CLOSED' ? true : (s.status === 'CLOSED');
          const cur = tp <= monthsElapsed + 1 && tp > monthsElapsed;
          const bags = cls === 'FULL' ? 8 : cls === 'MEDIUM' ? 7 : 6;
          return (
            <div key={tp} style={css(`display:grid;grid-template-columns:80px 110px 1fr 90px 110px;padding:9px 14px;border-bottom:${i < t.time_points.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12.5px;font-weight:600;align-items:center;background:${cur ? 'var(--blue-soft-2)' : 'var(--surface)'}`)}>
              <div className="mono" style={css('font-weight:700')}>T{tp}{tp === 0 ? ' (start)' : tp === t.time_points[t.time_points.length - 1] ? ' (final)' : ''}</div>
              <div><span className="pill" style={css(`background:${cls === 'FULL' ? 'var(--green-soft)' : cls === 'MEDIUM' ? 'var(--blue-soft)' : 'var(--surface-3)'};color:${cls === 'FULL' ? '#0B7A4B' : cls === 'MEDIUM' ? 'var(--blue-700)' : 'var(--ink-2)'};font-size:10px;padding:2px 7px;font-weight:700`)}>{cls}</span></div>
              <div className="mono" style={css('font-size:11px;color:var(--ink-2)')}>{c.tests}</div>
              <div className="mono" style={css('font-size:11px;font-weight:700')}>{bags}/{bags * s.batches.length}</div>
              <div>{done ? <span className="pill" style={css('background:var(--green-soft);color:#0B7A4B;font-size:10px;padding:2px 7px')}>✓ {tr({ en: 'Done', mk: 'Завршено' })}</span> : cur ? <span className="pill" style={css('background:var(--orange-soft);color:#B45309;font-size:10px;padding:2px 7px')}>Due</span> : <span className="pill" style={css('background:var(--surface-3);color:var(--ink-3);font-size:10px;padding:2px 7px')}>Pending</span>}</div>
            </div>
          );
        })}
      </div>

      {/* Sample ID convention reminder */}
      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:14px')}>
        <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:6px')}>{tr({ en: 'Sample ID convention', mk: 'Конвенција за ID' })} <span className="mono" style={css('font-weight:500;text-transform:none')}>· {DOCS.STAB_QRC}</span></div>
        <div className="mono" style={css('font-size:13px;font-weight:700')}>SS-[Type]-[Batch]-T[X]-[Param]-P[n/N]</div>
        <div className="mono" style={css('font-size:11px;color:var(--ink-3);margin-top:4px')}>{tr({ en: 'Example', mk: 'Пример' })}: <b style={{ color: 'var(--blue)' }}>{stabSampleId(s.type, s.batches[0], 0, 'CNP', 1, 6)}</b></div>
        <div className="mono" style={css('font-size:11px;color:var(--ink-3);margin-top:3px')}>{tr({ en: 'SRS', mk: 'SRS' })}: nG = ⌊√nB × 1.5⌋ — {tr({ en: 'e.g.', mk: 'пр.' })} nB=16 → nG={stabSRS(16)}</div>
      </div>

      <div className="row" style={css('gap:8px')}>
        <button className="btn btn-sm" onClick={() => goA08(s.id, 0)}><Icon name="forward" className="icon" />{tr({ en: 'Withdrawal form', mk: 'Повлекување' })} (A08)</button>
        <button className="btn btn-sm" onClick={() => goA09(s.id, s.batches[0])}><Icon name="grid" className="icon" />{tr({ en: 'Execution record', mk: 'Извршување' })} (A09)</button>
        <button className="btn btn-sm" onClick={goA10}><Icon name="calendar" className="icon" />{tr({ en: 'Annual plan', mk: 'Годишен план' })} (A10)</button>
        {s.status === 'CLOSED' ? <button className="btn btn-sm"><Icon name="shield" className="icon" />{tr({ en: 'Final report', mk: 'Финален извештај' })}</button> : null}
      </div>
      <div style={css('margin-top:14px;font-size:10px;color:var(--ink-3);font-weight:600;display:flex;gap:14px;flex-wrap:wrap')}>
        <span className="mono">{DOCS.SOP_STABILITY}</span>
        <span className="mono">{s.protocol}</span>
        {s.report ? <span className="mono">{s.report}</span> : null}
        <span className="mono">OOS/OOT: {DOCS.SOP_OOX}</span>
      </div>
    </div>
  );
}

// ── A08 Withdrawal Detail Form ──
function StabA08({ s, tp, lang, tr, goList, goDetail, onToast }) {
  if (!s) return null;
  const t = STAB_TYPE[s.type];
  const cls = stabClassify(s.type, tp);
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row mono" style={css('gap:6px;font-size:11px;color:var(--ink-3);margin-bottom:10px')}>
        <span style={{ cursor: 'pointer' }} onClick={goList}>{tr({ en: 'Stability', mk: 'Стабилност' })}</span><Icon name="chevR" className="icon" stroke="var(--ink-3)" />
        <span style={{ cursor: 'pointer' }} onClick={() => goDetail(s.id)}>{s.id}</span><Icon name="chevR" className="icon" stroke="var(--ink-3)" />
        <span style={{ color: 'var(--ink)' }}>A08 — T{tp}</span>
      </div>
      <div className="row" style={css('gap:8px;margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{tr({ en: 'Withdrawal Detail Form', mk: 'Образец за детали на повлекување' })}</h1>
        <span className="pill mono" style={css('background:var(--blue-soft);color:var(--blue-700)')}>{DOCS.STAB_WITHDRAWAL}</span>
      </div>

      <div style={css('display:grid;grid-template-columns:1fr 320px;gap:18px')}>
        <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px')}>
          <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px')}>
            {[['Study', s.id], ['Type', `${s.type} (${t.temp}/${t.rh})`], ['Time point', `T${tp} ${tp === 0 ? '(start)' : 'months'}`], ['Class', cls], ['Material', lang === 'mk' ? s.material_name_mk : s.material_name_en], ['Withdrawal date', new Date().toISOString().slice(0, 10)]].map(([l, v]) => (
              <div key={l}>
                <label style={css('font-size:11px;font-weight:700;color:var(--ink-2);display:block;margin-bottom:4px')}>{l}</label>
                <div style={css('background:var(--surface-2);border:1px solid var(--line);border-radius:9px;padding:9px 12px;font-size:13px;font-weight:600')}>{v}</div>
              </div>
            ))}
          </div>

          <div style={css('font-size:11px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:8px')}>{tr({ en: 'Bags pulled per batch (SRS-driven)', mk: 'Кеси по серија' })}</div>
          <div style={css('border:1px solid var(--line);border-radius:11px;overflow:hidden;margin-bottom:16px')}>
            <div style={css('display:grid;grid-template-columns:1fr 70px 70px 90px;padding:7px 14px;background:var(--surface-2);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;border-bottom:1px solid var(--line)')}>
              <div>Batch</div><div>Pool (nB)</div><div>SRS (nG)</div><div>Bag IDs</div>
            </div>
            {s.batches.map((b) => {
              const nB = 16; const nG = stabSRS(nB);
              return (
                <div key={b} style={css('display:grid;grid-template-columns:1fr 70px 70px 90px;padding:9px 14px;border-bottom:1px solid var(--line-2);font-size:12.5px;align-items:center')}>
                  <div className="mono" style={css('font-weight:700')}>{b}</div>
                  <div className="mono">{nB}</div>
                  <div className="mono" style={css('font-weight:700;color:var(--blue)')}>{nG}</div>
                  <div className="mono" style={css('font-size:10px;color:var(--ink-3)')}>B-{Math.floor(Math.random() * 900 + 100)}…</div>
                </div>
              );
            })}
          </div>

          <div style={css('font-size:11px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:8px')}>{tr({ en: 'Δ Gross weight check', mk: 'Δ Бруто тежина' })} <span className="mono" style={css('font-weight:500;text-transform:none')}>· {DOCS.STAB_DELTA}</span></div>
          <div style={css('display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:18px')}>
            {[['T0 weight', '12.450 g'], ['Current', '12.418 g'], ['Δ', '-0.26%']].map(([l, v]) => (
              <div key={l} style={css('background:var(--surface-2);border:1px solid var(--line);border-radius:9px;padding:10px 12px')}>
                <div style={css('font-size:10px;font-weight:700;color:var(--ink-3);text-transform:uppercase')}>{l}</div>
                <div className="mono" style={css('font-weight:800;font-size:14px;margin-top:2px')}>{v}</div>
              </div>
            ))}
          </div>

          <div className="row" style={css('gap:8px')}>
            <button className="btn" onClick={goList}>{tr({ en: 'Cancel', mk: 'Откажи' })}</button>
            <button className="btn btn-primary" onClick={() => { onToast(tr({ en: 'Withdrawal recorded ✓', mk: 'Повлекување запишано ✓' }), 'success'); goDetail(s.id); }}><Icon name="shield" className="icon" stroke="#fff" />{tr({ en: 'Save & e-Sign', mk: 'Зачувај и потпиши' })}</button>
          </div>
        </div>

        <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px')}>
          <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:12px')}>{tr({ en: 'SS Sample IDs', mk: 'SS ID примероци' })}</div>
          {['CNP', 'MIC', 'CON', 'TOX'].slice(0, cls === 'REDUCED' ? 2 : cls === 'MEDIUM' ? 3 : 4).map((param) => {
            const n = param === 'CNP' ? 2 : param === 'MIC' ? 4 : 1;
            return (
              <div key={param} style={css('margin-bottom:12px')}>
                <div style={css('font-size:11px;font-weight:700;color:var(--ink-2);margin-bottom:4px')}>{param}</div>
                {Array.from({ length: n }).map((_, i) => (
                  <div key={i} className="mono" style={css('font-size:10.5px;color:var(--blue);padding:2px 0')}>{stabSampleId(s.type, s.batches[0], tp, param, i + 1, n)}</div>
                ))}
              </div>
            );
          })}
          <div style={css('margin-top:14px;padding-top:14px;border-top:1px solid var(--line);font-size:10px;color:var(--ink-3);font-weight:600')}>
            <div>SRS: nG = ⌊√nB × 1.5⌋</div>
            <div className="mono" style={css('margin-top:4px')}>{DOCS.SOP_STABILITY}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── A09 Batch Execution Record ──
function StabA09({ s, batch, lang, tr, goList, goDetail, goA08, goA09 }) {
  if (!s) return null;
  const t = STAB_TYPE[s.type];
  const cur = batch || s.batches[0];
  const monthsElapsed = Math.floor((new Date('2026-06-01') - new Date(s.started)) / (1000 * 60 * 60 * 24 * 30));
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row mono" style={css('gap:6px;font-size:11px;color:var(--ink-3);margin-bottom:10px')}>
        <span style={{ cursor: 'pointer' }} onClick={goList}>{tr({ en: 'Stability', mk: 'Стабилност' })}</span><Icon name="chevR" className="icon" stroke="var(--ink-3)" />
        <span style={{ cursor: 'pointer' }} onClick={() => goDetail(s.id)}>{s.id}</span><Icon name="chevR" className="icon" stroke="var(--ink-3)" />
        <span style={{ color: 'var(--ink)' }}>A09 — {cur}</span>
      </div>
      <div className="row" style={css('gap:8px;margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{tr({ en: 'Batch Stability Execution Record', mk: 'Запис за извршување — серија' })}</h1>
        <span className="pill mono" style={css('background:var(--blue-soft);color:var(--blue-700)')}>{DOCS.STAB_EXECUTION}</span>
        <span className="pill mono" style={css('background:var(--orange-soft);color:#B45309')}>{cur}</span>
      </div>

      {/* Batch switcher */}
      <div className="row" style={css('gap:6px;margin-bottom:18px')}>
        {s.batches.map((b) => (
          <button key={b} className="btn btn-sm" style={b === cur ? css('background:var(--ink);color:#fff;border:none') : undefined} onClick={() => goA09(s.id, b)}>{b}</button>
        ))}
      </div>

      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh-1);margin-bottom:18px')}>
        <div style={css('display:grid;grid-template-columns:80px 100px 1fr 100px 110px 90px;padding:7px 14px;background:var(--surface-2);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;border-bottom:1px solid var(--line)')}>
          <div>TP</div><div>Class</div><div>Tests</div><div>Pulled</div><div>Tested</div><div>Status</div>
        </div>
        {t.time_points.map((tp, i) => {
          const cls = stabClassify(s.type, tp);
          const c = STAB_CLASS[cls];
          const done = tp <= monthsElapsed && s.status !== 'CLOSED' ? true : (s.status === 'CLOSED');
          const cur2 = tp <= monthsElapsed + 1 && tp > monthsElapsed;
          const cnt = cls === 'FULL' ? 8 : cls === 'MEDIUM' ? 7 : 6;
          return (
            <div key={tp} style={css(`display:grid;grid-template-columns:80px 100px 1fr 100px 110px 90px;padding:10px 14px;border-bottom:${i < t.time_points.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12px;font-weight:600;align-items:center;background:${cur2 ? 'var(--blue-soft-2)' : done ? 'var(--green-soft)' : 'var(--surface)'}`)}>
              <div className="mono" style={css('font-weight:700')}>T{tp}</div>
              <div><span className="pill" style={css(`background:${cls === 'FULL' ? 'var(--green-soft)' : cls === 'MEDIUM' ? 'var(--blue-soft)' : 'var(--surface-3)'};color:${cls === 'FULL' ? '#0B7A4B' : cls === 'MEDIUM' ? 'var(--blue-700)' : 'var(--ink-2)'};font-size:10px;padding:2px 7px;font-weight:700`)}>{cls}</span></div>
              <div className="mono" style={css('font-size:10.5px;color:var(--ink-2)')}>{c.tests}</div>
              <div className="mono" style={css('font-size:11px')}>{done ? `${cnt}/${cnt}` : '—'}</div>
              <div className="mono" style={css('font-size:11px')}>{done ? 'Complete' : cur2 ? 'In progress' : 'Pending'}</div>
              <div>{done ? <button className="btn btn-sm" style={css('padding:3px 8px;font-size:11px')} onClick={() => goA08(s.id, tp)}>View A08</button> : cur2 ? <button className="btn btn-primary btn-sm" style={css('padding:3px 8px;font-size:11px')} onClick={() => goA08(s.id, tp)}>Withdraw</button> : null}</div>
            </div>
          );
        })}
      </div>

      <div style={css('font-size:10.5px;color:var(--ink-3);font-weight:600;display:flex;gap:14px;flex-wrap:wrap')}>
        <span className="mono">{DOCS.SOP_STABILITY}</span>
        <span className="mono">{DOCS.STAB_EXECUTION}</span>
        <span>{tr({ en: 'OOS/OOT during stability', mk: 'OOS/OOT за време на студија' })}: {DOCS.SOP_OOX}</span>
      </div>
    </div>
  );
}

// ── A10 Annual Programme Plan ──
function StabA10({ studies, lang, tr, goList, goDetail }) {
  const months = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row mono" style={css('gap:6px;font-size:11px;color:var(--ink-3);margin-bottom:10px')}>
        <span style={{ cursor: 'pointer' }} onClick={goList}>{tr({ en: 'Stability', mk: 'Стабилност' })}</span><Icon name="chevR" className="icon" stroke="var(--ink-3)" />
        <span style={{ color: 'var(--ink)' }}>A10 — 2026</span>
      </div>
      <div className="row" style={css('gap:8px;margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{tr({ en: 'Annual Stability Programme — 2026', mk: 'Годишна програма — 2026' })}</h1>
        <span className="pill mono" style={css('background:var(--blue-soft);color:var(--blue-700)')}>{DOCS.STAB_ANNUAL}</span>
      </div>

      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh-1)')}>
        <div style={css('display:grid;grid-template-columns:130px 60px 1fr repeat(12,28px);padding:8px 14px;background:var(--surface-2);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;border-bottom:1px solid var(--line)')}>
          <div>Study</div><div>Type</div><div>{tr({ en: 'Material', mk: 'Материјал' })}</div>{months.map((m, mi) => <div key={mi} style={css('text-align:center')}>{m}</div>)}
        </div>
        {studies.map((st, i) => {
          const t = STAB_TYPE[st.type];
          const startMonth = parseInt(st.started.slice(5, 7), 10);
          return (
            <div key={st.id} style={css(`display:grid;grid-template-columns:130px 60px 1fr repeat(12,28px);padding:10px 14px;border-bottom:${i < studies.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12px;align-items:center;cursor:pointer`)} onClick={() => goDetail(st.id)}>
              <div className="mono" style={css('font-weight:700;color:var(--blue)')}>{st.id}</div>
              <div><span className="pill" style={css(`background:${typeColor(st.type)}18;color:${typeColor(st.type)};font-size:10px;padding:2px 7px;font-weight:700`)}>{st.type}</span></div>
              <div style={css('font-size:11.5px;font-weight:700')}>{lang === 'mk' ? st.material_name_mk : st.material_name_en}</div>
              {Array.from({ length: 12 }).map((_, mi) => {
                const monthsSinceStart = (2026 - parseInt(st.started.slice(0, 4), 10)) * 12 + (mi + 1) - startMonth;
                const tpAtMonth = t.time_points.find((tp) => tp === monthsSinceStart);
                if (tpAtMonth !== undefined) {
                  const cls = stabClassify(st.type, tpAtMonth);
                  const col = cls === 'FULL' ? 'var(--green)' : cls === 'MEDIUM' ? 'var(--blue)' : 'var(--orange)';
                  return <div key={mi} style={css('text-align:center')}><span title={`T${tpAtMonth} — ${cls}`} style={css(`display:inline-block;width:18px;height:18px;border-radius:4px;background:${col};color:#fff;font-size:9px;font-weight:800;display:inline-flex;align-items:center;justify-content:center`)}>{tpAtMonth}</span></div>;
                }
                return <div key={mi} />;
              })}
            </div>
          );
        })}
      </div>

      <div style={css('margin-top:14px;display:flex;gap:14px;flex-wrap:wrap;align-items:center')}>
        <span style={css('font-size:11px;font-weight:700;color:var(--ink-2)')}>{tr({ en: 'Legend', mk: 'Легенда' })}:</span>
        {[['FULL', 'var(--green)'], ['MEDIUM', 'var(--blue)'], ['REDUCED', 'var(--orange)']].map(([l, c]) => (
          <span key={l} className="row" style={css('gap:5px;font-size:11px;color:var(--ink-2);font-weight:600')}><span style={css(`width:14px;height:14px;border-radius:3px;background:${c}`)} />{l}</span>
        ))}
        <div className="spacer" />
        <span className="mono" style={css('font-size:10px;color:var(--ink-3);font-weight:600')}>{DOCS.SOP_STABILITY} · {DOCS.STAB_RESERVE} · {DOCS.STAB_CLOSURE}</span>
      </div>
    </div>
  );
}
