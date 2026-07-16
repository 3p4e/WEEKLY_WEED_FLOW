// Sample Transport / Chain-of-Custody screen (PP-QC-SOP-012) — ported from the
// prototype qc/sprint3.js (QC.render.transport + QC.render.transportDetail),
// preserving the inline styles via the css() string→object helper.
import { useState, useEffect } from 'react';
import { css } from '../../lib/style.js';
import { Icon } from '../../lib/icons.jsx';

// ── Screen-specific seed data (ported from sprint3.js) ──
const DOCS = {
  SOP_TRANSPORT: 'PP-QC-SOP-012 v1.0',
  SOP_LIFECYCLE: 'PP-QC-SOP-001 v3.0',
  FORM_SAR: 'PP-QC-SOP-012-A01',
  FORM_MOIA: 'PP-QC-SOP-012-A02',
  FORM_TM_COC: 'PP-QC-SOP-012-A03',
  FORM_COO: 'PP-QC-SOP-012-A04',
  FORM_FIN: 'PP-QC-SOP-012-A05',
};

const EXT_LABS = [
  { id: 'ukim', name: 'UKIM Faculty of Pharmacy', code: 'LT-083', tests: ['THC', 'CBD', 'Cannabinoid profile'], controlled: true },
  { id: 'ijz', name: 'IJZ Institute for Public Health', code: 'LT-005', tests: ['Microbiology', 'Heavy metals'], controlled: false },
  { id: 'agilent', name: 'Agilent MK', code: 'LT-112', tests: ['Pesticides', 'Mycotoxins', 'Heavy metals'], controlled: false },
  { id: 'phytolab', name: 'PhytoLab EU', code: 'LT-EU-208', tests: ['Full panel', 'Cannabinoid profile'], controlled: true },
];

const SEED_TRANSPORTS = [
  { id: 'TR-PP-2025-0042', sample_id: 'GG1024_03', batch_id: 'GG1024', lab: 'ukim', tests: ['THC', 'CBD'],
    status: 'in_transit', sar: true, moia: true, tmcoc: true, coo: true, fin: false,
    created: '2025-10-22', shipped: '2025-10-23', expected: '2025-10-26', tracking: 'PP-COURIER-44193' },
  { id: 'TR-PP-2025-0041', sample_id: 'BSS1024_02', batch_id: 'BSS1024', lab: 'agilent', tests: ['Pesticides', 'Heavy metals'],
    status: 'received', sar: true, moia: false, tmcoc: true, coo: true, fin: true,
    created: '2025-11-15', shipped: '2025-11-15', expected: '2025-11-20', tracking: 'PP-COURIER-44188' },
  { id: 'TR-PP-2025-0040', sample_id: 'HPA1024_02', batch_id: 'HPA1024', lab: 'phytolab', tests: ['Full panel'],
    status: 'draft', sar: false, moia: false, tmcoc: false, coo: false, fin: false,
    created: '2025-11-20', shipped: '', expected: '', tracking: '' },
];

// ── Status badge ──
const TransportBadge = ({ st }) => {
  const c = st === 'draft' ? 'var(--ink-3)' : st === 'in_transit' ? 'var(--orange)' : st === 'received' ? 'var(--green)' : 'var(--blue)';
  return (
    <span className="pill" style={css(`color:${c};background:${c}18;font-size:11px;padding:3px 9px`)}>
      <span className="dot" style={{ background: c }} />{st.replace('_', ' ')}
    </span>
  );
};

export function Transport({ qc, lang, labels, onToast }) {
  const tr = (o) => (lang === 'mk' ? o.mk : o.en);
  const [transports, setTransports] = useState(() =>
    JSON.parse(JSON.stringify(qc.transports ?? SEED_TRANSPORTS))
  );
  const [selTransport, setSelTransport] = useState(null);
  // Re-sync when live data arrives from the backend after mount.
  useEffect(() => {
    if (qc.transports) setTransports(JSON.parse(JSON.stringify(qc.transports)));
  }, [qc.transports]);

  const toggleForm = (tid, key) => {
    setTransports((arr) => arr.map((t) => (t.id === tid ? { ...t, [key]: !t[key] } : t)));
    const t = transports.find((x) => x.id === tid);
    const nextVal = t ? !t[key] : true;
    onToast(`${key.toUpperCase()} ${nextVal ? 'completed' : 'reset'}`, 'success');
  };
  const shipTransport = (tid) => {
    setTransports((arr) => arr.map((t) => (t.id === tid ? { ...t, status: 'in_transit', shipped: new Date().toISOString().slice(0, 10) } : t)));
    onToast(lang === 'mk' ? 'Транспортот е испратен ✓' : 'Transport shipped ✓', 'success');
  };

  // ── Detail view ──
  if (selTransport) {
    const t = transports.find((x) => x.id === selTransport);
    if (!t) return null;
    const lab = EXT_LABS.find((l) => l.id === t.lab);
    const forms = [
      { key: 'sar', ref: DOCS.FORM_SAR, en: 'Sample Analysis Request', mk: 'Барање за анализа' },
      { key: 'moia', ref: DOCS.FORM_MOIA, en: 'MoIA Notification (controlled)', mk: 'МВР Известување', warn: lab?.controlled },
      { key: 'tmcoc', ref: DOCS.FORM_TM_COC, en: 'Transport Manifest + CoC', mk: 'Манифест + Ланец' },
      { key: 'coo', ref: DOCS.FORM_COO, en: 'Contractor Order (COO)', mk: 'Договорна нарачка' },
      { key: 'fin', ref: DOCS.FORM_FIN, en: 'Financial Construction', mk: 'Финансиска конструкција' },
    ];
    return (
      <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
        <div className="row mono" style={css('gap:6px;font-size:11px;color:var(--ink-3);margin-bottom:10px')}>
          <span style={{ cursor: 'pointer' }} onClick={() => setSelTransport(null)}>{lang === 'mk' ? 'Транспорт' : 'Transport'}</span>
          <Icon name="chevR" className="icon" stroke="var(--ink-3)" /><span style={{ color: 'var(--ink)' }}>{t.id}</span>
        </div>
        <div className="row" style={css('gap:8px;margin-bottom:6px')}>
          <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{t.id}</h1><TransportBadge st={t.status} />
          {lab?.controlled ? <span className="pill" style={css('background:var(--red-soft);color:#C0353A;font-size:11px;font-weight:700')}>⚠ Controlled substance</span> : null}
        </div>
        <div className="mono" style={css('font-size:12px;color:var(--ink-2);font-weight:600;margin-bottom:16px')}>{t.sample_id} · {t.batch_id} → {lab?.name} ({lab?.code})</div>

        <div style={css('display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px')}>
          {[['Lab', lab?.name], ['Tests', t.tests.join(', ')], ['Created', t.created], ['Shipped', t.shipped || '—'], ['Expected', t.expected || '—'], ['Tracking', t.tracking || '—']].map(([l, v]) => (
            <div key={l} style={css('background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:10px 14px')}>
              <div style={css('font-size:10px;font-weight:700;color:var(--ink-3);text-transform:uppercase;letter-spacing:.4px')}>{l}</div>
              <div style={css('font-weight:700;font-size:13px;margin-top:2px')}>{v}</div>
            </div>
          ))}
        </div>

        <div style={css('font-size:11px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:8px')}>{lang === 'mk' ? 'Потребни обрасци' : 'Required forms'}</div>
        <div style={css('display:flex;flex-direction:column;gap:8px')}>
          {forms.map((f) => {
            const done = t[f.key];
            return (
              <div key={f.key} className="row" style={css(`gap:12px;padding:13px 16px;border-radius:11px;background:var(--surface);border:1px solid ${done ? '#B8E6C8' : 'var(--line)'};border-left:4px solid ${done ? 'var(--green)' : f.warn ? 'var(--red)' : 'var(--ink-3)'}`)}>
                <span style={css(`width:26px;height:26px;border-radius:999px;background:${done ? 'var(--green)' : 'var(--surface-3)'};display:flex;align-items:center;justify-content:center;flex-shrink:0`)}>
                  {done ? <Icon name="check" className="icon" stroke="#fff" /> : <Icon name="clock" className="icon" stroke="var(--ink-3)" />}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={css('font-weight:700;font-size:13.5px')}>{tr(f)}</div>
                  <div className="mono" style={css('font-size:11px;color:var(--ink-3);margin-top:1px')}>{f.ref}</div>
                </div>
                {f.warn && !done ? <span className="pill" style={css('background:var(--red-soft);color:#C0353A;font-size:10px;font-weight:700')}>Required</span> : null}
                <button className="btn btn-sm" onClick={() => toggleForm(t.id, f.key)}>{done ? (lang === 'mk' ? 'Преглед' : 'View') : (lang === 'mk' ? 'Пополни' : 'Complete')}</button>
              </div>
            );
          })}
        </div>

        {forms.every((f) => t[f.key]) ? (
          <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => shipTransport(t.id)}>
            <Icon name="forward" className="icon" stroke="#fff" />{lang === 'mk' ? 'Испрати и потпиши манифест' : 'Ship & e-Sign manifest'}
          </button>
        ) : null}
        <div style={css('margin-top:14px;font-size:10px;color:var(--ink-3);font-weight:600;display:flex;gap:14px;flex-wrap:wrap')}>
          <span className="mono">{DOCS.SOP_TRANSPORT}</span><span className="mono">{DOCS.SOP_LIFECYCLE}</span>
        </div>
      </div>
    );
  }

  // ── List view ──
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Транспорт на примероци' : 'Sample Transport'}</h1>
        <span className="pill" style={css('background:var(--blue-soft);color:var(--blue-700);margin-left:8px')}>{transports.length}</span>
        <div className="spacer" />
        <button className="btn btn-primary btn-sm">+ {lang === 'mk' ? 'Нов транспорт' : 'New transport'}</button>
      </div>
      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh-1)')}>
        <div style={css('display:grid;grid-template-columns:160px 130px 1fr 130px 110px 100px;padding:8px 16px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase')}>
          <div>Transport ID</div><div>Sample</div><div>Lab</div><div>Tests</div><div>Status</div><div>Forms</div>
        </div>
        {transports.map((t, i) => {
          const lab = EXT_LABS.find((l) => l.id === t.lab);
          const forms = [t.sar, t.moia, t.tmcoc, t.coo, t.fin].filter(Boolean).length;
          return (
            <div key={t.id} style={css(`display:grid;grid-template-columns:160px 130px 1fr 130px 110px 100px;padding:11px 16px;border-bottom:${i < transports.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12.5px;font-weight:600;align-items:center;cursor:pointer`)} onClick={() => setSelTransport(t.id)}>
              <div className="mono" style={css('font-weight:700;color:var(--blue)')}>{t.id}</div>
              <div className="mono" style={css('font-size:11px;color:var(--ink-2)')}>{t.sample_id}</div>
              <div><div style={{ fontWeight: 700 }}>{lab?.name || t.lab}</div><div className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{lab?.code || ''}</div></div>
              <div style={css('font-size:11.5px;color:var(--ink-2)')}>{t.tests.join(', ')}</div>
              <div><TransportBadge st={t.status} /></div>
              <div className="mono" style={css(`font-size:11px;color:${forms === 5 ? 'var(--green)' : forms >= 3 ? 'var(--orange)' : 'var(--red)'}`)}>{forms}/5 {forms === 5 ? '✓' : ''}</div>
            </div>
          );
        })}
      </div>
      <div style={css('margin-top:12px;font-size:11px;color:var(--ink-3);font-weight:600')}>
        <span className="mono">{DOCS.SOP_TRANSPORT}</span> · {lang === 'mk' ? '5 анекс обрасци' : '5 annex forms'}:{' '}
        <span className="mono">{DOCS.FORM_SAR}</span>, <span className="mono">{DOCS.FORM_MOIA}</span>,{' '}
        <span className="mono">{DOCS.FORM_TM_COC}</span>, <span className="mono">{DOCS.FORM_COO}</span>,{' '}
        <span className="mono">{DOCS.FORM_FIN}</span>
      </div>
    </div>
  );
}
