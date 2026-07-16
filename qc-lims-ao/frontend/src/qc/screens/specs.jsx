// Specifications — list + detail. Ported from the prototype qc/p1.js
// (QC.render.specs / QC.render.specDetail), preserving the inline styles
// (load-bearing for pixel parity) via the css() string→object helper.
import { useState } from 'react';
import { css } from '../../lib/style.js';
import { Icon } from '../../lib/icons.jsx';

// ── Spec enums (match backend) ──
const SpecStatusLabel = {
  DRAFT: { en: 'Draft', mk: 'Нацрт' }, ACTIVE: { en: 'Active', mk: 'Активна' },
  SUPERSEDED: { en: 'Superseded', mk: 'Заменета' }, WITHDRAWN: { en: 'Withdrawn', mk: 'Повлечена' },
};
const SpecStatusColor = { DRAFT: 'var(--ink-3)', ACTIVE: 'var(--green)', SUPERSEDED: 'var(--orange)', WITHDRAWN: 'var(--red)' };

// ── Seed specifications (versioning + approval + change control) ──
export const SEED_SPECS = [
  {
    id: 'PP-SPEC-FLOWER-001', spec_id: 'PP-SPEC-FLOWER-001', material_code: 'PP-MC-001', material_name_en: 'Cannabis Flower (Medical, dried)', material_name_mk: 'Канабис цвет (медицински, сушен)', version: 3, status: 'ACTIVE', effective_date: '2026-04-01', approved_by: 'jana',
    approvals: [{ role: 'AUTHOR', user: 'elena', status: 'APPROVED', signed: '2026-03-20' }, { role: 'QC_MANAGER', user: 'elena', status: 'APPROVED', signed: '2026-03-25' }, { role: 'QA', user: 'sofija', status: 'APPROVED', signed: '2026-03-28' }],
    params: [
      { test: 'THC Content', mk: 'ТХК', method: 'HPLC Ph.Eur. 2.2.29', type: 'NUMERIC_BOUNDED', rel_min: 18.0, rel_max: 25.0, op_min: 18.5, op_max: 24.5, unit: '% w/w', ref: 'Ph.Eur. cannabis flower' },
      { test: 'CBD Content', mk: 'ЦБД', method: 'HPLC Ph.Eur. 2.2.29', type: 'NUMERIC_MAX', rel_max: 1.0, unit: '% w/w', ref: 'Ph.Eur.' },
      { test: 'Water Activity', mk: 'Активност на вода', method: 'USP <922>', type: 'NUMERIC_MAX', rel_max: 0.65, op_max: 0.60, unit: 'Aw', ref: 'USP <922>' },
      { test: 'TYMC', mk: 'ТИМК', method: 'Ph.Eur. 2.6.12', type: 'NUMERIC_MAX', rel_max: 100, unit: 'CFU/g', ref: 'Ph.Eur. 2.6.12' },
      { test: 'Pesticide Residues', mk: 'Пестициди', method: 'GC-MS/MS', type: 'CATEGORICAL', unit: '', ref: 'EU 2019/1009' },
    ],
  },
  { id: 'PP-SPEC-FLOWER-001-v2', spec_id: 'PP-SPEC-FLOWER-001', material_code: 'PP-MC-001', material_name_en: 'Cannabis Flower (Medical, dried)', material_name_mk: 'Канабис цвет (медицински, сушен)', version: 2, status: 'SUPERSEDED', effective_date: '2025-10-01', approved_by: 'jana', approvals: [], params: [] },
  {
    id: 'PP-SPEC-WATER-002', spec_id: 'PP-SPEC-WATER-002', material_code: 'PP-MC-WTR', material_name_en: 'Purified Water (system)', material_name_mk: 'Прочистена вода', version: 1, status: 'ACTIVE', effective_date: '2026-01-15', approved_by: 'jana',
    approvals: [{ role: 'AUTHOR', user: 'stefan', status: 'APPROVED', signed: '2026-01-08' }, { role: 'QC_MANAGER', user: 'elena', status: 'APPROVED', signed: '2026-01-10' }, { role: 'QA', user: 'sofija', status: 'APPROVED', signed: '2026-01-12' }],
    params: [
      { test: 'Conductivity', mk: 'Спроводливост', method: 'Ph.Eur. 2.2.38', type: 'NUMERIC_MAX', rel_max: 5.1, unit: 'µS/cm', ref: 'Ph.Eur.' },
      { test: 'TOC', mk: 'ТОЦ', method: 'Ph.Eur. 2.2.44', type: 'NUMERIC_MAX', rel_max: 500, unit: 'ppb', ref: 'Ph.Eur.' },
      { test: 'TAMC', mk: 'ТАМК', method: 'Ph.Eur. 2.6.12', type: 'NUMERIC_MAX', rel_max: 100, unit: 'CFU/mL', ref: 'Ph.Eur.' },
    ],
  },
  {
    id: 'PP-SPEC-FLOWER-002-DRAFT', spec_id: 'PP-SPEC-FLOWER-002', material_code: 'PP-MC-002', material_name_en: 'Cannabis Flower (Extract grade)', material_name_mk: 'Канабис цвет (екстракт)', version: 1, status: 'DRAFT', effective_date: '2026-07-01', approved_by: '',
    approvals: [{ role: 'AUTHOR', user: 'elena', status: 'APPROVED', signed: '2026-05-30' }, { role: 'QC_MANAGER', user: 'elena', status: 'PENDING', signed: '' }, { role: 'QA', user: 'sofija', status: 'PENDING', signed: '' }],
    params: [{ test: 'THC Content', mk: 'ТХК', method: 'HPLC', type: 'NUMERIC_MIN', rel_min: 25.0, unit: '% w/w', ref: 'In-house' }],
    change: { type: 'MAJOR', variation: 'II', impact: 'New product grade — extract feedstock. Requires regulatory variation Type II.', regulatory: true, capa: '' },
  },
];

// ── Spec status badge ──
function SpecBadge({ st, lang }) {
  const c = SpecStatusColor[st];
  const lbl = SpecStatusLabel[st] || { en: st, mk: st };
  return (
    <span className="pill" style={css(`color:${c};background:${c}18;font-size:11px;padding:3px 9px`)}>
      {lang === 'mk' ? lbl.mk : lbl.en}
    </span>
  );
}

// ══════ SPECIFICATIONS LIST ══════
export function Specs({ qc, lang, labels, onToast }) {
  const [sel, setSel] = useState(null);
  if (sel) return <SpecDetail spec={sel} onBack={() => setSel(null)} onSelect={setSel} qc={qc} lang={lang} labels={labels} onToast={onToast} />;

  const SPECS = qc.specs ?? SEED_SPECS; // live data when loaded, else bundled seed
  const active = SPECS.filter((s) => s.status !== 'SUPERSEDED');
  const cols = '170px 1fr 70px 110px 100px 90px';
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row" style={css('margin-bottom:14px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Спецификации' : 'Specifications'}</h1>
        <span className="pill" style={css('background:var(--surface-3);color:var(--ink-2);margin-left:8px')}>{active.length}</span>
        <div className="spacer" />
        <button className="btn btn-primary btn-sm" onClick={() => onToast(lang === 'mk' ? 'Нова спец. — нацрт' : 'New spec — draft workflow', 'info')}>
          <Icon name="plus" className="icon" stroke="#fff" />{lang === 'mk' ? 'Нова' : 'New spec'}
        </button>
      </div>
      <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:var(--sh-1)')}>
        <div style={css(`display:grid;grid-template-columns:${cols};padding:8px 16px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase`)}>
          <div>Spec ID</div><div>{lang === 'mk' ? 'Материјал' : 'Material'}</div><div>Ver.</div><div>Status</div><div>{lang === 'mk' ? 'Важи од' : 'Effective'}</div><div>{lang === 'mk' ? 'Парам.' : 'Params'}</div>
        </div>
        {active.map((s, i) => (
          <div key={s.id} style={css(`display:grid;grid-template-columns:${cols};padding:11px 16px;border-bottom:${i < active.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12.5px;font-weight:600;align-items:center;cursor:pointer`)} onClick={() => setSel(s)}>
            <div className="mono" style={css('font-weight:700;color:var(--blue)')}>{s.spec_id}</div>
            <div>
              <div style={{ fontWeight: 700 }}>{lang === 'mk' ? s.material_name_mk : s.material_name_en}</div>
              <div className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{s.material_code}</div>
            </div>
            <div className="mono" style={{ fontWeight: 700 }}>v{s.version}</div>
            <div><SpecBadge st={s.status} lang={lang} /></div>
            <div className="mono" style={css('font-size:11px;color:var(--ink-3)')}>{s.effective_date}</div>
            <div className="mono" style={css('color:var(--ink-2)')}>{(s.params || []).length}</div>
          </div>
        ))}
      </div>
      <div style={css('font-size:11px;color:var(--ink-3);margin-top:12px;font-weight:600')}>
        {lang === 'mk' ? 'Синџир: Автор → QC Менаџер → QA. Поголеми измени бараат регулаторна варијација.' : 'Approval chain: Author → QC Manager → QA. MAJOR changes require regulatory variation (Type IA/IB/II).'}
      </div>
    </div>
  );
}

// ══════ SPECIFICATION DETAIL ══════
export function SpecDetail({ spec, onBack, onSelect, qc, lang, labels, onToast }) {
  const s = spec;
  if (!s) return null;
  const SPECS = qc.specs ?? SEED_SPECS;
  const versions = SPECS.filter((x) => x.spec_id === s.spec_id).sort((a, b) => b.version - a.version);
  const linkedSamples = qc.samples.filter((x) => x.batch_id && (x.results && Object.keys(x.results).length));
  return (
    <div style={css('padding:22px 26px;overflow:auto;height:100%')}>
      <div className="row mono" style={css('gap:6px;font-size:11px;color:var(--ink-3);margin-bottom:10px')}>
        <span style={{ cursor: 'pointer' }} onClick={onBack}>{lang === 'mk' ? 'Спецификации' : 'Specifications'}</span>
        <Icon name="chevR" className="icon" stroke="var(--ink-3)" /><span style={{ color: 'var(--ink)' }}>{s.spec_id} v{s.version}</span>
      </div>
      <div className="row" style={css('gap:8px;margin-bottom:6px')}>
        <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{s.spec_id}</h1>
        <span className="pill mono" style={css('background:var(--surface-3);color:var(--ink-2);font-size:12px')}>v{s.version}</span>
        <SpecBadge st={s.status} lang={lang} />
      </div>
      <div style={css('font-size:13px;color:var(--ink-2);font-weight:600;margin-bottom:18px')}>
        {lang === 'mk' ? s.material_name_mk : s.material_name_en} · {s.material_code} · {lang === 'mk' ? 'важи од' : 'effective'} {s.effective_date}
      </div>

      {s.change && (
        <div style={css('background:var(--orange-soft-2);border:1px solid var(--orange-soft);border-radius:12px;padding:14px 16px;margin-bottom:18px')}>
          <div className="row" style={css('gap:8px;margin-bottom:8px')}>
            <span style={css('font-weight:800;font-size:13px;color:var(--orange-700,#E2640A)')}>{lang === 'mk' ? 'Контрола на измени' : 'Change Control'}</span>
            <span className="pill" style={css('background:var(--orange);color:#fff;font-size:10px')}>{s.change.type}</span>
            {s.change.variation && <span className="pill" style={css('background:var(--surface);color:var(--ink-2);font-size:10px;border:1px solid var(--line)')}>Variation {s.change.variation}</span>}
            {s.change.regulatory && <span className="pill" style={css('background:var(--red-soft);color:#C0353A;font-size:10px')}>{lang === 'mk' ? 'Регулаторна најава' : 'Regulatory notification'}</span>}
          </div>
          <div style={css('font-size:12.5px;color:var(--ink);line-height:1.5')}>{s.change.impact}</div>
        </div>
      )}

      <div style={css('display:grid;grid-template-columns:1fr 300px;gap:18px')}>
        <div>
          <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:8px')}>{lang === 'mk' ? 'Параметри и граници' : 'Parameters & Limits'}</div>
          <div style={css('border-radius:12px;overflow:hidden;border:1px solid var(--line);box-shadow:var(--sh-1);background:var(--surface)')}>
            <div style={css('display:grid;grid-template-columns:1fr 150px 130px 110px;padding:7px 14px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase')}>
              <div>{lang === 'mk' ? 'Тест' : 'Test'}</div><div>{lang === 'mk' ? 'Метода' : 'Method'}</div><div>{lang === 'mk' ? 'Граница' : 'Release limit'}</div><div>{lang === 'mk' ? 'Оперативна' : 'Operational'}</div>
            </div>
            {(s.params || []).map((p, i) => {
              const rel = p.type === 'NUMERIC_BOUNDED' ? `${p.rel_min}–${p.rel_max} ${p.unit}` : p.type === 'NUMERIC_MAX' ? `≤ ${p.rel_max} ${p.unit}` : p.type === 'NUMERIC_MIN' ? `≥ ${p.rel_min} ${p.unit}` : 'Conform';
              const op = p.op_min != null || p.op_max != null ? `${p.op_min ?? ''}–${p.op_max ?? ''}` : '—';
              return (
                <div key={i} style={css(`display:grid;grid-template-columns:1fr 150px 130px 110px;padding:9px 14px;border-bottom:${i < s.params.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12px;font-weight:600;align-items:center`)}>
                  <div><div style={{ fontWeight: 700 }}>{lang === 'mk' ? p.mk : p.test}</div><div className="mono" style={css('font-size:9px;color:var(--ink-3)')}>{p.ref || ''}</div></div>
                  <div className="mono" style={css('font-size:10px;color:var(--ink-2)')}>{p.method}</div>
                  <div className="mono" style={css('font-size:11px;font-weight:700')}>{rel}</div>
                  <div className="mono" style={css('font-size:11px;color:var(--ink-3)')}>{op}</div>
                </div>
              );
            })}
          </div>
          <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin:18px 0 8px')}>{lang === 'mk' ? 'Поврзани примероци' : 'Linked samples (tested against this spec)'}</div>
          <div style={css('display:flex;flex-direction:column;gap:6px')}>
            {linkedSamples.slice(0, 3).map((x) => (
              <div key={x.id} className="row" style={css('gap:8px;padding:9px 12px;background:var(--surface);border:1px solid var(--line);border-radius:10px;cursor:pointer')} onClick={() => qc.viewSample(x.id)}>
                <span className="mono" style={css('font-weight:700;color:var(--blue);font-size:12px')}>{x.sample_id}</span>
                <span style={css('font-size:12px;color:var(--ink-2)')}>{labels.materialName(x)}</span>
                <div className="spacer" />
                <span className="pill" style={css('background:var(--surface-3);color:var(--ink-2);font-size:11px;padding:3px 9px')}>{labels.statusLabel(x.status)}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={css('display:flex;flex-direction:column;gap:16px')}>
          <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px')}>
            <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:12px')}>{lang === 'mk' ? 'Синџир на одобрување' : 'Approval chain'}</div>
            {(s.approvals || []).map((a, i) => (
              <div key={i} className="row" style={css('gap:10px;margin-bottom:12px')}>
                <span style={css(`width:22px;height:22px;border-radius:999px;background:${a.status === 'APPROVED' ? 'var(--green)' : a.status === 'REJECTED' ? 'var(--red)' : 'var(--surface-3)'};display:flex;align-items:center;justify-content:center;flex-shrink:0`)}>
                  {a.status === 'APPROVED' ? <Icon name="check" className="icon" stroke="#fff" /> : a.status === 'PENDING' ? <Icon name="clock" className="icon" stroke="var(--ink-3)" /> : <Icon name="x" className="icon" stroke="#fff" />}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={css('font-weight:700;font-size:12.5px')}>{a.role.replace('_', ' ')}</div>
                  <div style={css('font-size:11px;color:var(--ink-3)')}>{labels.personName(a.user)}{a.signed ? ' · ' + a.signed : ''}</div>
                </div>
              </div>
            ))}
          </div>
          <div style={css('background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px')}>
            <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:10px')}>{lang === 'mk' ? 'Историја на верзии' : 'Version history'}</div>
            {versions.map((v) => (
              <div key={v.id} className="row" style={css('gap:8px;margin-bottom:8px;font-size:12px;cursor:pointer')} onClick={() => onSelect(v)}>
                <span className="mono" style={css(`font-weight:700;color:${v.id === s.id ? 'var(--blue)' : 'var(--ink-2)'}`)}>v{v.version}</span>
                <SpecBadge st={v.status} lang={lang} />
                <div className="spacer" />
                <span className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{v.effective_date}</span>
              </div>
            ))}
          </div>
          {s.status === 'DRAFT' && (
            <button className="btn btn-primary" style={css('justify-content:center')} onClick={() => onToast(lang === 'mk' ? 'Спецификацијата активирана ✓' : 'Specification activated ✓', 'success')}>
              <Icon name="check" className="icon" stroke="#fff" />{lang === 'mk' ? 'Одобри и активирај' : 'Approve & Activate'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
