// AI Audit Mode — ported from qc/sprint5.js (QC.render.aiaudit). A Letta-style
// proactive scan over live QC data (open OOx, recurring OOx trends, pending
// e-Signatures) plus self-contained register seeds (CAPA / stability / specs)
// that have no live source here. Findings link to the originating view; the
// live AI re-scan/export routes to onToast (no backend wired). Inline styles
// preserved verbatim via css(). Icon substitution: prototype's `warning` →
// allowed `alert`.
import { css } from '../../lib/style.js';
import { Icon } from '../../lib/icons.jsx';

// Static register seeds — the React qc object only exposes samples/oos/audit,
// so CAPA / stability / spec counts (and overdue CAPA) are sourced here to keep
// the prototype's finding categories intact.
const SEED_OPEN_CAPA = ['CAPA-2026-011', 'CAPA-2026-009', 'CAPA-2025-017'];
const SEED_OVERDUE_CAPA = ['CAPA-2025-017'];
const SEED_ACTIVE_STABILITY = 2;
const SEED_DRAFT_SPECS = 1;

const SEV_COLOR = { high: 'var(--red)', med: 'var(--orange)', low: 'var(--blue)' };
const SEV_BG = { high: 'var(--red-soft)', med: 'var(--orange-soft)', low: 'var(--blue-soft)' };
const SEV_LBL = { high: { en: 'High', mk: 'Висок' }, med: { en: 'Medium', mk: 'Среден' }, low: { en: 'Low', mk: 'Низок' } };

export function AIAudit({ qc, lang, labels, onToast }) {
  const tr = (o) => (o && typeof o === 'object' ? o[lang] || o.en : o);

  // ── Proactive scans (live where data exists, seed otherwise) ──
  const overdueOOS = qc.oos.filter((o) => o.phase !== 'CLOSED');
  const overdueCAPA = SEED_OVERDUE_CAPA;
  const oosBatchTrend = {};
  qc.oos.forEach((o) => { oosBatchTrend[o.batch_id] = (oosBatchTrend[o.batch_id] || 0) + 1; });
  const trendBatches = Object.entries(oosBatchTrend).filter(([, n]) => n >= 2);
  const stabsActive = SEED_ACTIVE_STABILITY;
  const samplesNoEsig = qc.samples.filter((s) => s.status === 'TESTED' && !s.esig);

  const findings = [
    overdueCAPA.length && { sev: 'high', type: 'CAPA overdue', msg: `${overdueCAPA.length} CAPA past due`, action: 'capa', icon: 'flag' },
    samplesNoEsig.length && { sev: 'high', type: 'Pending e-Signature', msg: `${samplesNoEsig.length} tested sample(s) awaiting QP e-Sig`, action: 'samples', icon: 'shield' },
    overdueOOS.length && { sev: 'med', type: 'Open OOx', msg: `${overdueOOS.length} OOx investigation(s) open`, action: 'oos', icon: 'alert' },
    trendBatches.length && { sev: 'med', type: 'OOx trend', msg: `Recurring OOx on: ${trendBatches.map(([b]) => b).join(', ')} — RCA recommended`, action: 'oos', icon: 'trend' },
    { sev: 'low', type: 'Stability TPs upcoming', msg: `${stabsActive} active studies — check withdrawal schedule (A07)`, action: 'stability', icon: 'calendar' },
    { sev: 'low', type: 'Spec change pending', msg: `${SEED_DRAFT_SPECS} draft specification awaiting QC Manager + QA approval`, action: 'specs', icon: 'shield' },
  ].filter(Boolean);

  const counts = { high: 0, med: 0, low: 0 };
  findings.forEach((f) => { counts[f.sev]++; });

  const reScan = () => onToast('Connect the AI backend in Settings', 'info');

  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{tr({ en: 'AI Audit Mode', mk: 'АИ ревизорски режим' })}</h1>
        <span className="pill" style={css('background:var(--orange);color:#fff;margin-left:8px')}><Icon name="sparkle" className="icon" stroke="#fff" /> Letta</span>
        <div className="spacer" />
        <button className="btn btn-sm" onClick={reScan}><Icon name="forward" className="icon" />{tr({ en: 'Export report', mk: 'Извести' })}</button>
        <button className="btn btn-primary btn-sm" onClick={reScan}><Icon name="sparkle" className="icon" stroke="#fff" />{tr({ en: 'Re-scan', mk: 'Скенирај пак' })}</button>
      </div>

      {/* Sev summary */}
      <div className="row" style={css('gap:14px;margin-bottom:18px')}>
        {[['high', 'flag'], ['med', 'alert'], ['low', 'info']].map(([k, ic]) => (
          <div key={k} style={css(`flex:1;background:var(--surface);border:1px solid var(--line);border-left:4px solid ${SEV_COLOR[k]};border-radius:14px;padding:16px 18px`)}>
            <div className="row" style={css('gap:10px;margin-bottom:8px')}><Icon name={ic} className="icon" stroke={SEV_COLOR[k]} /><span style={css('font-size:12px;font-weight:700;color:var(--ink-2)')}>{tr(SEV_LBL[k])}</span></div>
            <div style={css('font-size:30px;font-weight:800;letter-spacing:-1px')}>{counts[k]}</div>
          </div>
        ))}
      </div>

      {/* Findings */}
      <div style={css('font-size:11px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:8px')}>{tr({ en: 'Findings', mk: 'Наоди' })}</div>
      <div style={css('display:flex;flex-direction:column;gap:10px;margin-bottom:18px')}>
        {findings.map((f, i) => (
          <div key={i} className="row" style={css(`gap:14px;padding:14px 16px;background:var(--surface);border:1px solid var(--line);border-left:4px solid ${SEV_COLOR[f.sev]};border-radius:12px`)}>
            <span style={css(`width:36px;height:36px;border-radius:10px;background:${SEV_BG[f.sev]};display:flex;align-items:center;justify-content:center;flex-shrink:0`)}><Icon name={f.icon} className="icon" stroke={SEV_COLOR[f.sev]} /></span>
            <div style={{ flex: 1 }}>
              <div className="row" style={css('gap:8px;margin-bottom:3px')}>
                <span style={css('font-weight:800;font-size:13px')}>{f.type}</span>
                <span className="pill" style={css(`background:${SEV_COLOR[f.sev]}18;color:${SEV_COLOR[f.sev]};font-size:10px;font-weight:700`)}>{tr(SEV_LBL[f.sev]).toUpperCase()}</span>
              </div>
              <div style={css('font-size:12.5px;color:var(--ink-2)')}>{f.msg}</div>
            </div>
            <button className="btn btn-sm" onClick={() => qc.navigate(f.action)}>{tr({ en: 'Open', mk: 'Отвори' })} →</button>
          </div>
        ))}
      </div>

      <div style={css('background:var(--surface-2);border:1px solid var(--line);border-radius:12px;padding:14px 18px;font-size:11.5px;color:var(--ink-2);font-weight:600')}>
        <Icon name="sparkle" className="icon" stroke="var(--orange)" /> <b>{tr({ en: 'How this works', mk: 'Како работи' })}:</b> {tr({ en: 'Letta agent scans your live data each visit — overdue actions, missing forms, trending OOx, near-expiry standards. Findings link to the source view.', mk: 'Letta агентот скенира во живо — задоцнети активности, недостасуваат обрасци, OOx тренд.' })}
      </div>
    </div>
  );
}
