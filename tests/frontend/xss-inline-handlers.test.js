'use strict';

/* ══════════════════════════════════════════════════════════════════════
   Record data inside inline event handlers — review 2026-09-27, FE-04.

   `onclick="fn('${GF.esc(value)}')"` looks escaped and is not: GF.esc is
   HTML escaping, and the browser decodes those entities back BEFORE the
   attribute text is parsed as JavaScript. A swab code of
       S1');window.__pwned='yes';('
   therefore rendered as a syntactically valid handler and ran when an
   ADMIN clicked "Enter result" — a stored XSS from a QA writer into an
   administrator's session (decon-view.js:712 at the time).

   The fix is a rule, not a patch: data rides in data- attributes (which stay
   HTML-escaped data) and a listener reads it back. Three things are pinned
   here, against the real sources:
     1. the original payload, through the real swab-results modal — the
        markup survives, nothing executes, and the form receives the code
        exactly as stored;
     2. the genealogy links, which used to strip quotes and so both stayed
        breakable (a backslash) and navigated to a different code than the
        one printed;
     3. a guard over every web/gf file: no inline handler may interpolate a
        free-text record field into a JS string literal, escaped or not.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadGF, GF_DIR } = require('./helpers/gf-window.js');

const PAYLOAD = "S1');window.__pwned='yes';('<script>window.__pwned2=1</script>\\";

const PRE_DECON = `
  window.GF = window.GF || {};
  window.GF.views = window.GF.views || {};
  window.GF.WWF = window.GF.WWF || {};
  window.GF.WWF._registerFullPageView = function () {};
  window.GF.render = { all: function () {} };
  window.GF.viewHead = function () { return ''; };
  window.GF.API = { user: { role: 'QA_MGR' } };
`;

function loadDecon() {
  const h = loadGF({ files: ['data.js', 'core.js', 'decon-view.js'], preScript: PRE_DECON });
  const w = h.window;
  w.GF.toast = () => {};
  w.GF.WWF._ensureModal = function (id) {
    if (w.document.getElementById(id)) return;
    const wrap = w.document.createElement('div');
    wrap.id = id;
    wrap.innerHTML = '<div id="' + id + '-title"></div><div id="' + id + '-body"></div>';
    w.document.body.appendChild(wrap);
  };
  w.GF.openModal = () => {};
  w.GF.closeModal = () => {};
  w.GF.t = (k) => k;
  w.GF.selectField = (id, cfg) => '<input type="hidden" id="' + id + '" value="' + (cfg.value || '') + '">';
  return h;
}

test('a hostile swab code neither breaks the swab-results markup nor executes', async () => {
  const h = loadDecon();
  const w = h.window;
  w.GF.API.deconSwabs = async () => ({ swabs: [
    { id: 'sw-1', cycle_id: 'c1', swab_code: PAYLOAD, location_desc: 'drain rim', result: 'pending', ct_value: null },
  ] });
  const opened = [];
  const realForm = w.GF.WWF.deconSwabResultForm;
  w.GF.WWF.deconSwabResultForm = (id, code) => { opened.push([id, code]); realForm(id, code); };

  await w.GF.WWF.deconSwabList('r1', 'c1');

  const body = w.document.getElementById('dc-swablist-modal-body');
  // The markup is intact: exactly one action button, and no script element
  // came out of the code text.
  const btns = body.querySelectorAll('button');
  assert.equal(btns.length, 1, 'the row renders one action button');
  assert.equal(body.querySelectorAll('script').length, 0, 'no <script> element from the code');
  assert.equal(btns[0].getAttribute('onclick'), null, 'no inline handler carries the data');
  assert.equal(btns[0].dataset.code, PAYLOAD, 'the code rides as a data- attribute, verbatim');
  // The visible code is the stored text, escaped.
  assert.equal(body.querySelector('strong').textContent, PAYLOAD);

  btns[0].click();

  assert.equal(w.__pwned, undefined, 'the payload must not run');
  assert.equal(w.__pwned2, undefined, 'the inline script must not run');
  assert.deepEqual(opened, [['sw-1', PAYLOAD]], 'the form opens with the exact stored code');
  assert.equal(w.document.getElementById('dc-res-modal-title').textContent.endsWith(PAYLOAD), true,
    'the result form names the swab as text');
  h.close();
});

test('opening the swab list twice binds one listener, not two', async () => {
  const h = loadDecon();
  const w = h.window;
  w.GF.API.deconSwabs = async () => ({ swabs: [
    { id: 'sw-1', cycle_id: 'c1', swab_code: 'RR-01-001', result: 'pending' },
  ] });
  let opened = 0;
  w.GF.WWF.deconSwabResultForm = () => { opened++; };
  await w.GF.WWF.deconSwabList('r1', 'c1');
  await w.GF.WWF.deconSwabList('r1', 'c1');
  w.document.querySelector('[data-act="swab-result"]').click();
  assert.equal(opened, 1);
  h.close();
});

test('genealogy links carry the batch code as data and navigate to that exact code', () => {
  const PRE = `
    window.GF = window.GF || {};
    window.GF.views = window.GF.views || {};
    window.GF.WWF = window.GF.WWF || {};
    window.GF.WWF._registerFullPageView = function () {};
    window.GF.render = { all: function () {} };
    window.GF.viewHead = function () { return ''; };
    window.GF.API = { user: { role: 'QC_MGR' } };
  `;
  const h = loadGF({ files: ['data.js', 'core.js', 'qcgenealogy-view.js'], preScript: PRE });
  const w = h.window;
  const hostile = "AB-1'\\);alert(1);('";
  w.GF.WWF._qcgen.data = {
    ancestors: [{ batch_id: hostile, depth: 1 }], descendants: [],
    parents: [{ id: 'e1', relation: 'CULTIVATION', parent_batch_id: hostile, child_batch_id: 'P-1' }],
    children: [],
  };
  w.document.body.innerHTML = w.GF.views.qcgenealogy();
  const gone = [];
  w.GF.WWF.qcGenGo = (b) => gone.push(b);
  const link = w.document.querySelector('a[data-batch]');
  const chip = w.document.querySelector('span[data-batch]');
  assert.ok(link && chip);
  assert.equal(link.textContent, hostile, 'the printed code is the stored one');
  assert.doesNotMatch(link.getAttribute('onclick'), /\$\{|alert/, 'the handler text is static');
  link.click(); chip.click();
  assert.deepEqual(gone, [hostile, hostile], 'navigation uses the exact code, not a quote-stripped one');
  h.close();
});

/* ── The rule, enforced over every shipped source file ──────────────────
   An inline handler may name ids and enum values; it may never carry a
   free-text record field inside a JS string literal, GF.esc'd or not. The
   denylist names the fields a person types; anything new that is typed by a
   person belongs on it. A bare `.code` is deliberately absent: cultivation
   batch and plant codes are constrained server-side to [A-Za-z0-9_-] and
   cannot carry a quote, so cultivation-view.js's `b.code` / `p.code` handler
   arguments are identifiers, not text. `grade` / `alias` are the facility
   layout's free-text room grade and its alias (LayoutPatch, review
   2026-09-27, R2-FE-15). */
const FREE_TEXT = /\.(swab_code|filename|batch_id|batch_code|title|name|full_name|note|notes|reason|subject|location|location_desc|content|comment|username|email|label|desc|description|room_name|campaign|manifest_code|to_location|from_location|lab_name|action_taken|transfer_reason|sample_condition|carrier_ref|strain|cultivar|preview|remark|message|grade|alias|code)\b/;

test('no inline handler in web/gf interpolates a free-text record field into a JS string', () => {
  const offenders = [];
  for (const f of fs.readdirSync(GF_DIR).filter(n => n.endsWith('.js'))) {
    const src = fs.readFileSync(path.join(GF_DIR, f), 'utf8');
    const lines = src.split('\n');
    lines.forEach((line, i) => {
      const re = /\bon[a-z]+="([^"]*)"/g;
      let m;
      while ((m = re.exec(line))) {
        const handler = m[1];
        // Interpolations that land INSIDE a quoted JS string: '${…}' or "…${…}…"
        const inner = /'[^']*\$\{([^}]*)\}[^']*'/g;
        let k;
        while ((k = inner.exec(handler))) {
          if (FREE_TEXT.test(k[1])) offenders.push(`${f}:${i + 1}: ${k[0]}`);
        }
      }
    });
  }
  assert.deepEqual(offenders, [], 'inline handlers carrying record text:\n' + offenders.join('\n'));
});
