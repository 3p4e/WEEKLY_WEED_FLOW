/* codefield.js — a text input whose constant leading part is already there.

   Structured identifiers in this facility carry a fixed head and a short
   varying tail: an SOP code is <DEPT>SOP_<NNN>, so only the number is really
   being entered. Typing the head every time is work the machine can do, and
   work a person can get subtly wrong — a hyphen where the house uses an
   underscore produces a code that looks right, sorts differently and matches
   nothing.

   So the head is pre-filled, the caret lands after it however the field is
   clicked or tapped, and the head cannot be deleted by editing. What the
   field reads back through GF.$(id).value is the WHOLE code, head included,
   so callers are unchanged.

   Deliberately NOT a general input mask: it does not enforce the tail's
   shape, because this app's own corpus shows the tail varying more than any
   single pattern would allow, and a mask that rejects a legitimate code is
   worse than no mask. It fixes only the part that is genuinely constant.

   The conventions themselves live at the CALL SITES, each with the evidence
   for it — never guessed here. A field whose convention nobody has
   established passes no prefix and behaves as an ordinary input.

   Global: GF.codeField(id, cfg) → markup string
   cfg: { prefix, value, placeholder?, maxlength?, oninput?, style? }        */
window.GF = window.GF || {};

(function () {
  const PRE = {};   // id → prefix (re-declared on every render, like chooser.js)

  GF.codeField = (id, cfg) => {
    cfg = cfg || {};
    const prefix = String(cfg.prefix || '');
    PRE[id] = prefix;
    let v = cfg.value != null ? String(cfg.value) : '';
    // An existing value that predates the convention is shown as it is: this
    // control completes a code, it does not rewrite one already recorded.
    if (prefix && !v) v = prefix;
    return `<input id="${id}" class="${GF.esc(cfg.cls || 'qms-search')}"`
      + ` value="${GF.esc(v)}"`
      + (cfg.placeholder ? ` placeholder="${GF.esc(cfg.placeholder)}"` : '')
      + (cfg.maxlength ? ` maxlength="${+cfg.maxlength}"` : '')
      + (cfg.style ? ` style="${GF.esc(cfg.style)}"` : '')
      + ` autocomplete="off" spellcheck="false"`
      + ` onfocus="GF._codeCaret('${id}')" onclick="GF._codeCaret('${id}')"`
      + ` oninput="GF._codeGuard('${id}')${cfg.oninput ? ';' + cfg.oninput : ''}">`;
  };

  // Put the caret after the constant head — "the pointer continues from that
  // spot onward". Only ever moves it FORWARD out of the prefix: a caret the
  // user placed further along their own typing is left alone, and a real
  // selection (drag, select-all) is not collapsed under them.
  GF._codeCaret = (id) => {
    const el = GF.$(id), prefix = PRE[id];
    if (!el || !prefix) return;
    if (el.value.indexOf(prefix) !== 0) return;      // value diverged; don't fight it
    if (el.selectionStart !== el.selectionEnd) return;
    if (el.selectionStart < prefix.length) {
      try { el.setSelectionRange(prefix.length, prefix.length); } catch (e) { /* detached */ }
    }
  };

  // Editing that eats into the head puts it back, caret just after it. Without
  // this, one held backspace turns QCSOP_012 into 012 — a code that is not
  // wrong-looking enough to notice.
  GF._codeGuard = (id) => {
    const el = GF.$(id), prefix = PRE[id];
    if (!el || !prefix) return;
    if (el.value.indexOf(prefix) === 0) return;
    // Keep whatever of the tail survived, rather than discarding their typing.
    // The head can be damaged from either end — deleting backwards from the
    // caret eats its END (QCSOP_012 → QCSOP012), while deleting forwards, or
    // pasting over it, eats its START (QCSOP_012 → SOP_012). Strip whichever
    // surviving fragment the value opens with, longest first, or the repair
    // re-prepends the head onto a piece of itself: QCSOP_ + SOP_012.
    let tail = el.value, best = 0;
    for (let i = prefix.length; i > 0; i--) {
      if (tail.indexOf(prefix.slice(0, i)) === 0) { best = i; break; }   // end eaten
    }
    for (let j = 1; j < prefix.length; j++) {
      const suf = prefix.slice(j);
      if (suf.length > best && tail.indexOf(suf) === 0) { best = suf.length; break; }
    }
    tail = tail.slice(best);
    el.value = prefix + tail;
    try { el.setSelectionRange(prefix.length + tail.length, prefix.length + tail.length); }
    catch (e) { /* detached */ }
  };

  // ── A batch code with the cultivar as its constant head ────────────────
  // The facility's batch number is <cultivar code><MMYY><nn> — GP072501 in the
  // owner's example (2026-09-05) — and the cultivation batch form already
  // pre-fills the cultivar code as the fixed head. The QC forms that name a
  // batch (sample, incoming CoA, OOS) were plain text (review 2026-09-27,
  // INS-12). This control puts a strain chooser in front of the same code
  // field: pick the strain, its code is there, type the tail. With no strain
  // chosen it behaves as an ordinary input, and an existing value keeps its
  // spelling — its strain is preselected when its head matches a known code.
  //
  // Global: GF.batchCodeField(id, cfg) → markup string
  // cfg: { cultivars: [{code, name, is_active}], value, placeholder?,
  //        oninput?, cls?, selPlaceholder?, selTitle?, maxlength? }
  GF.batchCodeField = (id, cfg) => {
    cfg = cfg || {};
    const cvs = (cfg.cultivars || []).filter(c => c && c.code && c.is_active !== false);
    const v = cfg.value != null ? String(cfg.value) : '';
    const head = cvs.map(c => String(c.code)).sort((a, b) => b.length - a.length)
      .find(code => v.indexOf(code) === 0) || '';
    const sel = `<select id="${id}-cv" class="${GF.esc(cfg.selCls || 'qcs-cv')}" title="${GF.esc(cfg.selTitle || '')}"`
      + ` onchange="GF._batchCvPick('${id}')">`
      + `<option value="">${GF.esc(cfg.selPlaceholder || '')}</option>`
      + cvs.map(c => `<option value="${GF.esc(c.code)}"${String(c.code) === head ? ' selected' : ''}>${
          GF.esc(String(c.code) + (c.name ? ' · ' + c.name : ''))}</option>`).join('')
      + `</select>`;
    return sel + GF.codeField(id, { prefix: head, value: v, placeholder: cfg.placeholder,
      maxlength: cfg.maxlength || 64, oninput: cfg.oninput, style: cfg.style, cls: cfg.cls || 'qcs-code' });
  };

  // The strain changed: swap the head, keep whatever tail was typed, caret
  // after the head. The input event is re-fired so a view's own oninput
  // (draft keeping, parent lookups) sees the new value.
  GF._batchCvPick = (id) => {
    const el = GF.$(id), sel = GF.$(id + '-cv');
    if (!el || !sel) return;
    const old = PRE[id] || '', next = String(sel.value || '');
    let tail = el.value;
    if (old && tail.indexOf(old) === 0) tail = tail.slice(old.length);
    PRE[id] = next;
    el.value = next + tail;
    try { el.setSelectionRange(next.length + tail.length, next.length + tail.length); } catch (e) { /* detached */ }
    try { el.dispatchEvent(new Event('input', { bubbles: true })); } catch (e) { /* no Event */ }
    if (el.focus) el.focus();
  };

  // The cultivar list for the chooser, fetched once per session and shared by
  // every form. Returns what is known NOW ([] until the first answer lands)
  // and calls every registered onLoad when it does, so a form rendered
  // before the answer re-renders with the strains in. Reset on login
  // (integrate.js resetCaches) — cultivars are organisation data.
  let cvCache = null, cvPending = null;
  const cvWaiters = [];
  GF.batchCodeCultivars = (onLoad) => {
    if (cvCache) return cvCache;
    if (onLoad) cvWaiters.push(onLoad);
    if (!cvPending && GF.API && GF.API.cultivars) {
      cvPending = GF.API.cultivars()
        .then(r => {
          cvCache = (r && r.cultivars) || [];
          const ws = cvWaiters.splice(0);
          ws.forEach(fn => { try { fn(cvCache); } catch (e) { /* a view's re-render must not break the others */ } });
          return cvCache;
        })
        .catch(() => { cvPending = null; return []; });
    }
    return [];
  };
  GF.batchCodeCultivars.reset = () => { cvCache = null; cvPending = null; cvWaiters.length = 0; };
})();
