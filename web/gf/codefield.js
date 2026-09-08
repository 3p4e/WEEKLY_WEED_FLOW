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
})();
