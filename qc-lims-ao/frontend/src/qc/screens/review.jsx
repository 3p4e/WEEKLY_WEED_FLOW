// Progressive Review — live two-pane (analyst | reviewer) results validation.
// Ported from the prototype qc/p3.js (QC.render.review + QC.validateTier).
// No Submit button: results save live via qc.updateResult; reviewer pane reflects
// entries instantly with pass/alert/fail/error validation tiers.
import { css } from '../../lib/style.js';
import { Icon } from '../../lib/icons.jsx';
import { TEST_SPECS, PEOPLE } from '../data.js';
import { SEED_SPECS } from './specs.jsx';

// ── Validation tiers ──
// pass = within operational, alert = within release but outside operational,
// fail = outside release, error = unparseable / non-numeric where numeric required.
const TIER = {
  pass: { label: { en: 'Pass', mk: 'Поминува' }, color: 'var(--green)', bg: 'var(--green-soft)', fg: '#0B7A4B' },
  alert: { label: { en: 'Alert', mk: 'Внимание' }, color: 'var(--orange)', bg: 'var(--orange-soft)', fg: '#B45309' },
  fail: { label: { en: 'Fail', mk: 'Паѓа' }, color: 'var(--red)', bg: 'var(--red-soft)', fg: '#C0353A' },
  error: { label: { en: 'Error', mk: 'Грешка' }, color: 'var(--ink-3)', bg: 'var(--surface-3)', fg: 'var(--ink-2)' },
  empty: { label: { en: '—', mk: '—' }, color: 'var(--ink-3)', bg: 'transparent', fg: 'var(--ink-3)' },
};

// Validate a single result against a SpecParameter → { tier, message }.
function validateTier(p, val) {
  if (val == null || val === '') return { tier: 'empty', message: '' };
  if (!p) return { tier: 'pass', message: 'No spec linked' };

  if (p.type === 'CATEGORICAL' || p.type === 'TEXT') {
    const ok = /conform|nd|not detected|<loq|<lod/i.test(val);
    return ok ? { tier: 'pass', message: 'Conforms' } : { tier: 'fail', message: 'Non-conforming text result' };
  }

  if (/^<|nd|not detected/i.test(val.trim())) {
    if (p.type === 'NUMERIC_MAX' || p.type === 'NUMERIC_BOUNDED') return { tier: 'pass', message: 'Below LOQ — within max limit' };
    if (p.type === 'NUMERIC_MIN') return { tier: 'fail', message: 'Below LOQ but minimum required' };
  }

  const n = parseFloat(val);
  if (isNaN(n)) return { tier: 'error', message: 'Non-numeric value — expected ' + (p.unit || 'number') };

  const relMin = p.rel_min, relMax = p.rel_max;
  const inRelease = (relMin == null || n >= relMin) && (relMax == null || n <= relMax);
  if (!inRelease) {
    if (relMin != null && n < relMin) return { tier: 'fail', message: `Below release minimum (${relMin} ${p.unit || ''})` };
    if (relMax != null && n > relMax) return { tier: 'fail', message: `Above release maximum (${relMax} ${p.unit || ''})` };
  }

  const opMin = p.op_min, opMax = p.op_max;
  const inOp = (opMin == null || n >= opMin) && (opMax == null || n <= opMax);
  if (!inOp) {
    const delta = opMin != null && n < opMin ? `below operational min ${opMin}`
      : opMax != null && n > opMax ? `above operational max ${opMax}` : 'outside operational range';
    return { tier: 'alert', message: `Within spec but ${delta} ${p.unit || ''} — trend-monitor` };
  }
  return { tier: 'pass', message: 'Within operational range' };
}

function TierBadge({ tier, sm }) {
  const t = TIER[tier] || TIER.empty;
  const mark = tier === 'pass' ? '✓' : tier === 'alert' ? '⚠' : tier === 'fail' ? '✗' : tier === 'error' ? '!' : '';
  return (
    <span className="pill" style={css(`background:${t.bg};color:${t.fg};font-size:${sm ? 10 : 11}px;padding:${sm ? '2px 7px' : '3px 9px'};font-weight:700;gap:4px`)}>
      {mark} {t.label.en}
    </span>
  );
}

const StatusBadge = ({ st, labels }) => {
  const colorMap = { COLLECTED: 'var(--blue)', IN_TEST: 'var(--orange)', TESTED: 'var(--violet,#7A5BE0)', APPROVED: 'var(--green)', REJECTED: 'var(--red)' };
  const bgMap = { COLLECTED: 'var(--blue-soft)', IN_TEST: 'var(--orange-soft)', TESTED: 'var(--violet-soft,#ECE6FB)', APPROVED: 'var(--green-soft)', REJECTED: 'var(--red-soft)' };
  return (
    <span className="pill" style={css(`color:${colorMap[st] || 'var(--ink-3)'};background:${bgMap[st] || 'var(--surface-3)'};font-size:12px;padding:4px 10px`)}>
      <span className="dot" style={{ background: colorMap[st] || 'var(--ink-3)' }} />{labels.statusLabel(st)}
    </span>
  );
};

// ══════ PROGRESSIVE REVIEW ══════
export function Review({ qc, lang, labels, onToast }) {
  const s = qc.selSample ? qc.sample(qc.selSample) : qc.samples.find((x) => x.status === 'IN_TEST') || qc.samples[0];
  if (!s) return <div style={css('padding:40px;text-align:center;color:var(--ink-3)')}>No sample available.</div>;

  // Find linked spec (match material_code, else any ACTIVE).
  const spec = SEED_SPECS.find((x) => x.material_code === s.material_code && x.status === 'ACTIVE')
    || SEED_SPECS.find((x) => x.status === 'ACTIVE');
  const params = spec ? spec.params || [] : [];

  // Lookup spec param by TEST_SPECS row (best effort — match by test name).
  const paramFor = (t) => {
    if (!spec) return null;
    return params.find((p) => p.test === t.p || p.test === t.test) || null;
  };

  const liveTiers = TEST_SPECS.map((t) => {
    const val = (s.results || {})[t.id] || '';
    return { spec: t, val, v: validateTier(paramFor(t) || t, val) };
  });
  const stats = liveTiers.reduce((a, x) => { a[x.v.tier] = (a[x.v.tier] || 0) + 1; return a; }, {});
  const filled = liveTiers.filter((x) => x.val).length;
  const total = liveTiers.length;
  const pct = total ? Math.round((filled / total) * 100) : 0;
  const progColor = stats.fail ? 'var(--red)' : stats.alert ? 'var(--orange)' : 'var(--green)';
  const tierCols = '30px 1fr 110px 110px 70px';

  return (
    <div style={css('display:flex;flex-direction:column;height:100%')}>
      {/* Top bar: sample identity + live status banner */}
      <div style={css('padding:18px 26px 12px;background:var(--surface);border-bottom:1px solid var(--line)')}>
        <div className="row" style={css('gap:10px;margin-bottom:6px')}>
          <h1 style={css('font-size:22px;font-weight:800;margin:0')}>{lang === 'mk' ? 'Прогресивен преглед' : 'Progressive Review'}</h1>
          <StatusBadge st={s.status} labels={labels} />
          {spec && (
            <span className="pill mono" style={css('background:var(--blue-soft);color:var(--blue-700);font-size:11px')}>
              <Icon name="shield" className="icon" stroke="var(--blue)" />{spec.spec_id} v{spec.version}
            </span>
          )}
          <span className="pill" style={css('background:var(--green);color:#fff;font-size:10px;animation:pulse 2s infinite')}>● LIVE</span>
          <div className="spacer" />
          <span style={css('font-size:11px;color:var(--ink-3);font-weight:600')}>{lang === 'mk' ? 'Без копче — се зачувува автоматски' : 'No submit — saves live'}</span>
        </div>
        <div className="mono" style={css('font-size:12px;color:var(--ink-2);font-weight:600;margin-bottom:10px')}>
          {s.sample_id} · {s.batch_id} · {labels.materialName(s)}
        </div>
        {/* Progress + tier summary */}
        <div className="row" style={css('gap:14px')}>
          <div style={css('flex:1;max-width:280px')}>
            <div className="row" style={css('font-size:11px;color:var(--ink-3);margin-bottom:4px;font-weight:700')}>
              <span>{lang === 'mk' ? 'Внесено' : 'Entered'}</span><div className="spacer" /><span className="mono">{filled}/{total}</span>
            </div>
            <div style={css('height:6px;border-radius:999px;background:var(--surface-3);overflow:hidden')}><span style={css(`display:block;height:100%;border-radius:999px;width:${pct}%;background:${progColor}`)} /></div>
          </div>
          <div className="row" style={css('gap:8px')}>
            {['pass', 'alert', 'fail', 'error'].filter((t) => stats[t]).map((t) => (
              <span key={t} className="pill" style={css(`background:${TIER[t].bg};color:${TIER[t].fg};font-size:11px;padding:4px 9px;font-weight:700`)}>{TIER[t].label.en}: {stats[t]}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Two-pane: analyst | reviewer */}
      <div style={css('flex:1;display:flex;min-height:0')}>
        {/* Analyst pane */}
        <div style={css('flex:1;overflow:auto;padding:18px 22px')}>
          <div className="row" style={css('margin-bottom:10px')}>
            <span className="pill" style={css('background:var(--blue-soft);color:var(--blue-700);font-size:11px')}>
              <Icon name="user" className="icon" stroke="var(--blue)" />{lang === 'mk' ? 'Аналитичар' : 'Analyst'}: {(PEOPLE[s.analyst] || {}).name || '—'}
            </span>
            <div className="spacer" />
            <button className="btn btn-sm" onClick={() => onToast(lang === 'mk' ? 'Поврзете го АИ серверот во Поставки' : 'Connect the AI backend in Settings', 'info')}>
              <Icon name="sparkle" className="icon" stroke="var(--orange)" />AI fill
            </button>
          </div>
          <div style={css('border-radius:12px;overflow:hidden;border:1px solid var(--line);box-shadow:var(--sh-1);background:var(--surface)')}>
            <div style={css(`display:grid;grid-template-columns:${tierCols};padding:7px 14px;background:var(--surface-2);border-bottom:1px solid var(--line);font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase`)}>
              <div>#</div><div>{lang === 'mk' ? 'Параметар' : 'Parameter'}</div><div>Spec</div><div>{lang === 'mk' ? 'Резултат' : 'Result'}</div><div>Tier</div>
            </div>
            {liveTiers.map((row, i) => {
              const p = paramFor(row.spec);
              const specStr = p
                ? (p.type === 'NUMERIC_BOUNDED' ? `${p.rel_min}–${p.rel_max}` : p.type === 'NUMERIC_MAX' ? `≤${p.rel_max}` : p.type === 'NUMERIC_MIN' ? `≥${p.rel_min}` : 'Conform')
                : (row.spec.specLabel || row.spec.specMin + '–' + row.spec.specMax);
              const rowBg = row.v.tier === 'fail' ? 'var(--red-soft)' : row.v.tier === 'alert' ? 'var(--orange-soft-2)' : 'var(--surface)';
              return (
                <div key={row.spec.id} style={css(`display:grid;grid-template-columns:${tierCols};padding:8px 14px;border-bottom:${i < liveTiers.length - 1 ? '1px solid var(--line-2)' : 'none'};font-size:12px;font-weight:600;align-items:center;background:${rowBg};transition:background .2s`)}>
                  <div className="mono" style={css('font-size:10px;color:var(--ink-3)')}>{i + 1}</div>
                  <div>
                    <div style={{ fontWeight: 700 }}>{lang === 'mk' ? row.spec.mk || row.spec.p : row.spec.p}</div>
                    <div className="mono" style={css('font-size:9px;color:var(--ink-3)')}>{row.spec.method.slice(0, 22)}</div>
                  </div>
                  <div className="mono" style={css('font-size:10.5px;color:var(--ink-2)')}>{specStr} {row.spec.unit || ''}</div>
                  <div>
                    <input defaultValue={row.val} placeholder="…"
                      style={css('width:95px;border:1px solid var(--line);border-radius:7px;padding:5px 8px;font-size:12px;font-weight:700;font-family:var(--mono);background:var(--surface-2);outline:none')}
                      onBlur={(e) => qc.updateResult(s.id, row.spec.id, e.target.value)} />
                  </div>
                  <div><TierBadge tier={row.v.tier} sm /></div>
                </div>
              );
            })}
          </div>
          {(stats.fail || stats.alert) ? (
            <div style={css('margin-top:12px;padding:11px 14px;border-radius:10px;background:var(--surface);border:1px solid var(--line);font-size:11.5px;color:var(--ink-2)')}>
              <b style={css(`color:${stats.fail ? 'var(--red)' : 'var(--orange)'}`)}>
                {stats.fail ? (lang === 'mk' ? 'Откриени неуспеси' : 'Fails detected') : (lang === 'mk' ? 'Внимание — во границите но надвор од оперативни' : 'Alerts — within spec but outside operational range')}.
              </b>
              {liveTiers.filter((r) => r.v.tier === 'fail' || r.v.tier === 'alert').slice(0, 3).map((r, k) => (
                <div key={k} style={css('margin-top:4px')}><span className="mono" style={css('color:var(--ink)')}>{r.spec.p}:</span> {r.v.message}</div>
              ))}
            </div>
          ) : null}
        </div>

        {/* Reviewer pane */}
        <div style={css('width:380px;flex-shrink:0;border-left:1px solid var(--line);background:var(--surface-2);display:flex;flex-direction:column')}>
          <div className="row" style={css('padding:14px 18px;border-bottom:1px solid var(--line);background:var(--surface)')}>
            <span className="pill" style={css('background:var(--violet-soft,#ECE6FB);color:var(--violet,#7A5BE0);font-size:11px;padding:4px 9px')}>
              <Icon name="shield" className="icon" stroke="var(--violet,#7A5BE0)" />{lang === 'mk' ? 'Преглед на ревизор' : 'Reviewer view'}
            </span>
            <div className="spacer" />
            <span style={css('font-size:10px;color:var(--ink-3);font-weight:700')}>{lang === 'mk' ? 'Автоматско освежување' : 'Auto-refreshing'}</span>
          </div>
          <div style={css('flex:1;overflow:auto;padding:16px 18px')}>
            <div style={css('font-size:10px;font-weight:700;letter-spacing:.4px;color:var(--ink-3);text-transform:uppercase;margin-bottom:10px')}>{lang === 'mk' ? 'Уживо верификација' : 'Live verification'}</div>
            {liveTiers.filter((r) => r.val).length ? liveTiers.filter((r) => r.val).map((r, k) => (
              <div key={k} style={css(`background:var(--surface);border:1px solid var(--line);border-left:3px solid ${TIER[r.v.tier].color};border-radius:9px;padding:10px 12px;margin-bottom:7px`)}>
                <div className="row" style={css('gap:6px;margin-bottom:4px')}>
                  <span style={css('font-weight:700;font-size:12px')}>{lang === 'mk' ? r.spec.mk || r.spec.p : r.spec.p}</span>
                  <div className="spacer" /><TierBadge tier={r.v.tier} sm />
                </div>
                <div className="row" style={css('gap:8px;font-size:11px')}>
                  <span className="mono" style={css(`font-weight:700;color:${TIER[r.v.tier].color}`)}>{r.val}</span>
                  <span style={css('color:var(--ink-3)')}>{r.v.message}</span>
                </div>
              </div>
            )) : (
              <div style={css('text-align:center;padding:20px;color:var(--ink-3);font-size:12px')}>{lang === 'mk' ? 'Чекам внес од аналитичар…' : 'Waiting for analyst input…'}</div>
            )}

            {filled === total && total > 0 && (
              <div style={css(`margin-top:14px;padding:14px;background:${stats.fail ? 'var(--red-soft)' : 'var(--green-soft)'};border:1px solid ${stats.fail ? '#F3C5C7' : '#B8E6C8'};border-radius:11px`)}>
                <div style={css(`font-weight:800;font-size:13px;color:${stats.fail ? '#C0353A' : '#0B7A4B'};margin-bottom:4px`)}>
                  {stats.fail ? (lang === 'mk' ? 'OOS — потребна истрага' : 'OOS detected — investigation required') : (lang === 'mk' ? 'Сите параметри усогласени' : 'All parameters complete & within spec')}
                </div>
                <div style={css(`font-size:11px;color:${stats.fail ? '#9E3035' : '#0B7A4B'};opacity:.85;margin-bottom:10px`)}>{lang === 'mk' ? 'Спремно за QP преглед и е-потпис' : 'Ready for QP review and e-signature'}</div>
                {!s.esig ? (
                  <button className="btn btn-primary" style={css('width:100%;justify-content:center')} onClick={() => qc.applyEsig(s.id)}>
                    <Icon name="shield" className="icon" stroke="#fff" />{lang === 'mk' ? 'Верификувај и е-потпиши' : 'Verify & e-Sign'}
                  </button>
                ) : (
                  <div className="row" style={css('gap:8px;color:#0B7A4B;font-weight:700;font-size:12px')}>
                    <Icon name="check" className="icon" stroke="var(--green)" />{lang === 'mk' ? 'Е-потпишано од QP' : 'E-Signed by QP'}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }`}</style>
    </div>
  );
}
