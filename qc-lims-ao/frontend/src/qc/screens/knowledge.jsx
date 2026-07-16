// Knowledge Base — ported from qc/sprint5.js (QC.render.kb). SOP browser with an
// "Ask the SOPs" AI prompt box and a categorised SOP catalogue. The prototype's
// live Letta/Qdrant call has no backend here, so Ask routes to onToast like the
// AI Search screen in QcModule. Inline styles preserved verbatim via css().
import { useState } from 'react';
import { css } from '../../lib/style.js';
import { Icon } from '../../lib/icons.jsx';

// SOP document refs (the QC_LIMS_Ao SOP register).
const DOCS = {
  SOP_LIFECYCLE: 'PP-QC-SOP-001',
  SOP_SAMPLING: 'PP-QC-SOP-011',
  SOP_TRANSPORT: 'PP-QC-SOP-013',
  SOP_WATER: 'PP-QC-SOP-014',
  SOP_STABILITY: 'QCSOP 018 v02',
  SOP_OOX: 'QCSOP 019',
  SOP_SPECIFICATIONS: 'PP-QC-SOP-017',
  SOP_STP_CHEM: 'PP-QC-SOP-020',
  SOP_STP_MICRO: 'PP-QC-SOP-021',
  SOP_CANNABINOIDS: 'PP-QC-SOP-022',
  SOP_ENVIRONMENTAL: 'PP-QC-SOP-023',
};

const KB_SOPS = [
  { id: DOCS.SOP_LIFECYCLE, en: 'Laboratory Testing Lifecycle', mk: 'Животен циклус на тестирање', cat: 'master', sections: 7 },
  { id: DOCS.SOP_SAMPLING, en: 'QC Sampling, Handling & Documentation', mk: 'Земање мостри', cat: 'sampling', sections: 12 },
  { id: DOCS.SOP_TRANSPORT, en: 'Sample Transport to Outsourced Labs', mk: 'Транспорт до договорни лаборатории', cat: 'transport', sections: 12 },
  { id: DOCS.SOP_WATER, en: 'RO Water System QC', mk: 'РО систем — КК', cat: 'water', sections: 9 },
  { id: DOCS.SOP_STABILITY, en: 'Stability Study Management', mk: 'Управување со стабилност', cat: 'stability', sections: 14 },
  { id: DOCS.SOP_OOX, en: 'OOx Investigation (OOS / OOT / OAR)', mk: 'OOx истрага', cat: 'investig', sections: 8 },
  { id: DOCS.SOP_SPECIFICATIONS, en: 'Specification Development & Approval', mk: 'Развој на спецификации', cat: 'specs', sections: 6 },
  { id: DOCS.SOP_STP_CHEM, en: 'Physical-Chemical Test Procedures (STPa01-20)', mk: 'Физичко-хемиски тест процедури', cat: 'methods', sections: 11 },
  { id: DOCS.SOP_STP_MICRO, en: 'Microbiological Test Procedures', mk: 'Микробиолошки тест процедури', cat: 'methods', sections: 8 },
  { id: DOCS.SOP_CANNABINOIDS, en: 'Cannabinoid Determination', mk: 'Канабиноиди — определување', cat: 'methods', sections: 5 },
  { id: DOCS.SOP_ENVIRONMENTAL, en: 'Environmental Monitoring', mk: 'Еколошки мониторинг', cat: 'envi', sections: 7 },
];
const KB_CATS = { master: 'Master', sampling: 'Sampling', transport: 'Transport', water: 'Water', stability: 'Stability', investig: 'Investigations', specs: 'Specifications', methods: 'Test methods', envi: 'Environment' };

export function Knowledge({ lang, onToast }) {
  const tr = (o) => (o && typeof o === 'object' ? o[lang] || o.en : o);
  const [q, setQ] = useState(lang === 'mk' ? 'Што е тригер за SP-06 земање примерок?' : 'What triggers an SP-06 sampling event?');

  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{tr({ en: 'Knowledge Base', mk: 'База на знаење' })}</h1>
        <span className="pill" style={css('background:var(--blue-soft);color:var(--blue-700);margin-left:8px')}>{KB_SOPS.length} SOPs</span>
        <span className="pill" style={css('background:var(--orange);color:#fff;margin-left:4px')}><Icon name="sparkle" className="icon" stroke="#fff" /> Letta + Qdrant</span>
      </div>

      {/* Ask AI */}
      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:18px;box-shadow:var(--sh-2)')}>
        <div style={css('font-size:13px;font-weight:700;color:var(--ink-2);margin-bottom:10px')}>{tr({ en: 'Ask the SOPs — answers grounded in your approved procedures', mk: 'Прашај ги СОП-овите' })}</div>
        <div className="row" style={css('gap:10px')}>
          <div className="row" style={css('flex:1;gap:10px;background:var(--surface-2);border:1px solid var(--line);border-radius:12px;padding:11px 16px')}>
            <Icon name="sparkle" className="icon" stroke="var(--orange)" />
            <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') onToast(lang === 'mk' ? 'Поврзете го АИ серверот во Поставки' : 'Connect the AI backend in Settings', 'info'); }} style={css('flex:1;border:none;background:none;font-size:14px;font-weight:600;outline:none;font-family:var(--font)')} />
          </div>
          <button className="btn btn-primary" onClick={() => onToast(lang === 'mk' ? 'Поврзете го АИ серверот во Поставки' : 'Connect the AI backend in Settings', 'info')}><Icon name="arrowR" className="icon" stroke="#fff" />{tr({ en: 'Ask', mk: 'Прашај' })}</button>
        </div>
        <div style={css('margin-top:14px')} />
      </div>

      {/* SOP catalogue */}
      <div style={css('font-size:11px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:8px')}>{tr({ en: 'SOP catalogue', mk: 'Каталог на СОП' })}</div>
      <div style={css('display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px')}>
        {KB_SOPS.map((s) => (
          <div key={s.id} style={css('background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;cursor:pointer')} onClick={() => onToast(`${tr({ en: 'Opening', mk: 'Се отвора' })} ${s.id}`, 'info')}>
            <div className="row" style={css('gap:8px;margin-bottom:6px')}>
              <Icon name="doc" className="icon" stroke="var(--blue)" /><span className="mono" style={css('font-weight:800;font-size:11.5px;color:var(--blue)')}>{s.id}</span>
              <span className="pill" style={css('background:var(--surface-3);color:var(--ink-2);font-size:9.5px;padding:2px 6px;margin-left:auto;font-weight:700')}>{KB_CATS[s.cat] || s.cat}</span>
            </div>
            <div style={css('font-weight:700;font-size:13px;margin-bottom:3px')}>{tr(s)}</div>
            <div className="mono" style={css('font-size:10.5px;color:var(--ink-3)')}>{s.sections} {tr({ en: 'sections', mk: 'секции' })}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
