// Water Quality Control screen (PP-QC-SOP-014) — ported from the prototype
// qc/sprint4.js (QC.render.water), preserving the inline styles via the css()
// string→object helper. Annual plan grid (locations × 12 months) + results log.
import { css } from '../../lib/style.js';
import { Icon } from '../../lib/icons.jsx';

// ── Screen-specific seed data (ported from sprint4.js + lifecycle.js) ──
const DOCS = {
  SOP_WATER: 'PP-QC-SOP-014',
  WATER_PLAN: 'PP-QC-SOP-014-A01',
  WATER_RESULTS_LOG: 'PP-QC-SOP-014-A02',
  WATER_SAMPLING_QRG: 'PP-QC-SOP-014-A08',
};

const WATER_GRADE = {
  TW: { en: 'Municipality Tap Water (drinking)', mk: 'Градска водоводна мрежа (питка)', spec: 'PP-QC-SOP-014-A03' },
  BW: { en: 'Bore-well Water', mk: 'Бунарска вода', spec: '—' },
  TR: { en: 'Treated Water (post-treatment, pre-RO)', mk: 'Третирана вода (по третман, пред РО)', spec: 'PP-QC-SOP-014-A05' },
  RO: { en: 'Reverse Osmosis / Demineralised Water', mk: 'Реверзна осмоза (деминерализирана)', spec: 'PP-QC-SOP-014-A06' },
};

const WATER_LOCATIONS = [
  { id: 'TW_T161_001', grade: 'TW', room: 'T161', desc_en: 'Feed water collection reservoir (drinking)', desc_mk: 'Резервоар за почетна вода (питка)', inUse: true, freq: 'bimonthly' },
  { id: 'BW_T162_002', grade: 'BW', room: 'T162', desc_en: 'Bore-well 1 & 2 supply discharge valve', desc_mk: 'Доводна линија — Бунар 1 и 2', inUse: false, freq: 'bimonthly' },
  { id: 'TR_T161_001', grade: 'TR', room: 'T161', desc_en: 'After treatment, before RO unit', desc_mk: 'По третман, пред РО', inUse: true, freq: 'bimonthly' },
  { id: 'RO_F97_001', grade: 'RO', room: 'F97', desc_en: 'RO outlet — manufacturing supply', desc_mk: 'РО излез — снабдување', inUse: true, freq: 'bimonthly' },
  { id: 'RO_F98_002', grade: 'RO', room: 'F98', desc_en: 'RO loop — return', desc_mk: 'РО јамка — поврат', inUse: true, freq: 'bimonthly' },
];

const WATER_RESULTS_SEED = [
  { date: '2026-01-15', loc: 'TW_T161_001', pH: '7.4', Conductivity: '320', TAMC: '<10', 'E.coli': 'Absent', pass: true },
  { date: '2026-01-15', loc: 'TR_T161_001', pH: '6.2', Conductivity: '42', TAMC: '<10', pass: true },
  { date: '2026-01-15', loc: 'RO_F97_001', Conductivity: '1.8', TOC: '120', TAMC: '<10', Endotoxin: '<0.1', pass: true },
  { date: '2026-03-15', loc: 'TW_T161_001', pH: '7.5', Conductivity: '340', TAMC: '<10', 'E.coli': 'Absent', pass: true },
  { date: '2026-03-15', loc: 'RO_F97_001', Conductivity: '2.2', TOC: '140', TAMC: '15', Endotoxin: '<0.1', pass: true },
  { date: '2026-05-15', loc: 'RO_F97_001', Conductivity: '6.4', TOC: '180', TAMC: '<10', Endotoxin: '<0.1', pass: false, ooe: 'Conductivity 6.4 > spec 5.1' },
];

const gradeColor = (g) => ({ TW: 'var(--blue)', BW: 'var(--ink-3)', TR: 'var(--orange)', RO: 'var(--violet,#7A5BE0)' }[g] || 'var(--ink-3)');

export function Water({ qc, lang, labels, onToast }) {
  const t = (o) => (lang === 'mk' ? o.mk : o.en);
  const waterLog = qc.water ?? WATER_RESULTS_SEED;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const monthsMk = ['Јан', 'Фев', 'Мар', 'Апр', 'Мај', 'Јун', 'Јул', 'Авг', 'Сеп', 'Окт', 'Ное', 'Дек'];
  const M = lang === 'mk' ? monthsMk : months;

  // For each location × month, find a result and color the cell
  const grid = (loc) => M.map((m, i) => {
    const month = i + 1;
    const res = waterLog.find((r) => r.loc === loc && parseInt(r.date.slice(5, 7), 10) === month);
    const scheduled = i % 2 === 0; // bimonthly = odd-indexed months scheduled
    if (!scheduled && !res) return <span key={i} style={css('display:inline-block;width:22px;height:22px;border-radius:5px;background:transparent')} title="—" />;
    if (res) return <span key={i} style={css(`display:inline-block;width:22px;height:22px;border-radius:5px;background:${res.pass ? 'var(--green)' : 'var(--red)'};color:#fff;font-size:9px;font-weight:800;display:inline-flex;align-items:center;justify-content:center;cursor:pointer`)} title={`${res.date}${res.ooe ? ' — ' + res.ooe : ''}`}>{res.pass ? '✓' : '!'}</span>;
    return <span key={i} style={css('display:inline-block;width:22px;height:22px;border-radius:5px;border:1.5px dashed var(--line);background:transparent')} title={lang === 'mk' ? 'Планирано' : 'Planned'} />;
  });
  const perYear = M.filter((_, i) => i % 2 === 0).length;

  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Контрола на квалитет на вода' : 'Water Quality Control'}</h1>
        <span className="pill" style={css('background:var(--blue-soft);color:var(--blue-700);margin-left:8px')}>{waterLog.length} {lang === 'mk' ? 'резултати' : 'results'}</span>
        <div className="spacer" />
        <button className="btn btn-sm"><Icon name="calendar" className="icon" />2026</button>
        <button className="btn btn-primary btn-sm">+ {lang === 'mk' ? 'Внеси резултат' : 'Log result'}</button>
      </div>

      {/* Grades legend */}
      <div className="row" style={css('gap:10px;margin-bottom:18px;flex-wrap:wrap')}>
        {Object.entries(WATER_GRADE).map(([g, info]) => (
          <div key={g} style={css(`background:var(--surface);border:1px solid var(--line);border-left:3px solid ${gradeColor(g)};border-radius:10px;padding:9px 14px;flex:1;min-width:180px`)}>
            <div className="row" style={css('gap:6px;margin-bottom:3px')}>
              <span className="mono" style={css(`font-weight:800;font-size:13px;color:${gradeColor(g)}`)}>{g}</span>
              <span style={css('font-size:11.5px;font-weight:700;color:var(--ink)')}>{t(info)}</span>
            </div>
            <div className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{info.spec}</div>
          </div>
        ))}
      </div>

      {/* Annual plan grid */}
      <div style={css('font-size:11px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:8px')}>
        {lang === 'mk' ? '2026 Годишен план' : '2026 Annual Plan'} <span className="mono" style={css('font-weight:500;text-transform:none')}>· {DOCS.WATER_PLAN}</span>
      </div>
      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh-1);margin-bottom:18px')}>
        <div style={css('display:grid;grid-template-columns:170px 70px 1fr 70px 320px;padding:8px 16px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase')}>
          <div>SL Code</div><div>Grade</div><div>{lang === 'mk' ? 'Локација' : 'Location'}</div><div>Room</div><div>{lang === 'mk' ? 'План + резултати' : 'Schedule + results'}</div>
        </div>
        {WATER_LOCATIONS.map((l, i) => (
          <div key={l.id} style={css(`display:grid;grid-template-columns:170px 70px 1fr 70px 320px;padding:11px 16px;border-bottom:${i < WATER_LOCATIONS.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12.5px;font-weight:600;align-items:center;opacity:${l.inUse ? 1 : 0.5}`)}>
            <div className="mono" style={css('font-weight:700;color:var(--blue)')}>{l.id}</div>
            <div><span className="pill" style={css(`background:${gradeColor(l.grade)}18;color:${gradeColor(l.grade)};font-size:10px;padding:2px 7px;font-weight:700`)}>{l.grade}</span></div>
            <div style={css('font-size:12px;color:var(--ink-2)')}>{lang === 'mk' ? l.desc_mk : l.desc_en}{l.inUse ? '' : <span style={css('color:var(--ink-3);font-size:10px')}> · not in use</span>}</div>
            <div className="mono" style={css('font-size:11px;color:var(--ink-3)')}>{l.room}</div>
            <div style={css('display:flex;gap:3px;align-items:center')}>{grid(l.id)}<span className="mono" style={css('font-size:10px;color:var(--ink-3);margin-left:6px')}>{perYear}/yr</span></div>
          </div>
        ))}
      </div>

      {/* Recent results log */}
      <div style={css('font-size:11px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:8px')}>
        {lang === 'mk' ? 'Последни резултати' : 'Recent results'} <span className="mono" style={css('font-weight:500;text-transform:none')}>· {DOCS.WATER_RESULTS_LOG}</span>
      </div>
      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh-1)')}>
        <div style={css('display:grid;grid-template-columns:90px 150px 70px 1fr 80px;padding:7px 14px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase')}>
          <div>{lang === 'mk' ? 'Датум' : 'Date'}</div><div>SL Code</div><div>Grade</div><div>{lang === 'mk' ? 'Параметри' : 'Parameters'}</div><div>{lang === 'mk' ? 'Резултат' : 'Result'}</div>
        </div>
        {waterLog.slice().reverse().map((r, i) => {
          const grade = r.loc.split('_')[0];
          const params = Object.entries(r).filter(([k]) => !['date', 'loc', 'pass', 'ooe'].includes(k));
          return (
            <div key={i} style={css(`display:grid;grid-template-columns:90px 150px 70px 1fr 80px;padding:10px 14px;border-bottom:${i < waterLog.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12px;align-items:center;background:${r.pass ? 'var(--surface)' : 'var(--red-soft)'}`)}>
              <div className="mono" style={css('font-weight:700')}>{r.date}</div>
              <div className="mono" style={css('font-size:11px;color:var(--blue);font-weight:700')}>{r.loc}</div>
              <div><span className="pill" style={css(`background:${gradeColor(grade)}18;color:${gradeColor(grade)};font-size:10px;padding:2px 7px;font-weight:700`)}>{grade}</span></div>
              <div style={css('font-size:11.5px;color:var(--ink-2)')}>
                {params.map(([k, v]) => (<span key={k} className="mono" style={css('margin-right:10px')}><b>{k}</b>: {v}</span>))}
                {r.ooe ? <span style={css('color:var(--red);font-weight:700')}>⚠ {r.ooe}</span> : null}
              </div>
              <div>{r.pass
                ? <span className="pill" style={css('background:var(--green-soft);color:#0B7A4B;font-size:10px;padding:2px 7px;font-weight:700')}>✓ Pass</span>
                : <span className="pill" style={css('background:var(--red-soft);color:#C0353A;font-size:10px;padding:2px 7px;font-weight:700')}>✗ OOE</span>}</div>
            </div>
          );
        })}
      </div>

      <div style={css('margin-top:14px;font-size:10.5px;color:var(--ink-3);font-weight:600;display:flex;gap:14px;flex-wrap:wrap')}>
        <span className="mono">{DOCS.SOP_WATER}</span>
        <span className="mono">{DOCS.WATER_PLAN}</span>
        <span className="mono">{DOCS.WATER_SAMPLING_QRG}</span>
        <span className="mono">SL = Sampling Location · {lang === 'mk' ? 'Формат' : 'Format'}: &lt;GRADE&gt;_&lt;ROOM&gt;_&lt;NNN&gt;</span>
      </div>
    </div>
  );
}
