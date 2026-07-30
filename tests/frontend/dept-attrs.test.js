'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/dept-templates.js — GF.deptCode / GF.deptTemplate
                              GF.collectDeptAttrs / GF.attrChips

   collectDeptAttrs is a data-LOSS risk, not a rendering risk. It reads the
   rendered per-department metadata inputs and produces the `attributes` object
   that is sent as a WHOLE-OBJECT PATCH, so anything it fails to carry over is
   deleted from the task on the server. Its own comment says so: keys outside
   the current template must survive ("captured/imported metadata"), while a
   template field cleared to '' must be removed. Those two requirements pull in
   opposite directions and there was nothing pinning either of them.

   This is the one place in the suite that needs real DOM nodes. They are the
   actual `<input id="attr-f-…">` elements GF.renderDeptFields emits — rendered
   by the real source, not hand-written — so the test reads the same DOM the
   browser would.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

const FILES = ['data.js', 'core.js', 'dept-templates.js'];

// Templates are keyed by the BACKEND department code, which data.js's seed
// GF.DEPTS does not carry — integrate.js adds `code` when it remaps the real
// departments (see its loadAll()). Reproducing that shape here is what makes
// GF.deptCode resolvable at all.
function withRealDepts(opts = {}) {
  const h = loadGF(Object.assign({ files: FILES }, opts));
  h.GF.DEPTS = [
    // `cultivation` is the one shipped template that is text + number only, so
    // its fields render without chooser.js's select widget (see renderAndCollect).
    { id: 'd-cu', code: 'cultivation', name: 'Cultivation', mk: 'Одгледување', abbr: 'CU' },
    { id: 'd-nc', code: 'no_such_code', name: 'Uncoded Dept', mk: 'Uncoded', abbr: 'NC' },
  ];
  return h;
}

test('GF.deptCode maps a department id to its backend code, or null', () => {
  const h = withRealDepts();
  assert.equal(h.GF.deptCode('d-cu'), 'cultivation');
  assert.equal(h.GF.deptCode('nope'), null);
  // The seed departments in data.js have no `code` at all, so before login
  // every lookup is null and no template resolves — the generic layout.
  h.GF.DEPTS = [{ id: 'clone', name: 'Cloning & Nursery' }];
  assert.equal(h.GF.deptCode('clone'), null);
  h.close();
});

test('GF.deptTemplate returns null rather than undefined for an unknown department', () => {
  const h = withRealDepts();
  // Every caller tests `if (!tpl)`, and one of them (renderDeptFields) then
  // reads tpl.fields.length — so a template that resolves to a truthy value
  // without a fields array would throw mid-render.
  const tpl = h.GF.deptTemplate('d-cu');
  assert.notEqual(tpl, null);
  assert.equal(Array.isArray(tpl.fields), true);
  assert.equal(h.GF.deptTemplate('d-nc'), null);
  assert.equal(h.GF.deptTemplate('nope'), null);
  assert.equal(h.GF.deptTemplate(undefined), null);
  h.close();
});

test('every shipped department template has the shape its renderers assume', () => {
  const h = withRealDepts();
  // renderDeptFields, collectDeptAttrs and attrChips all walk tpl.fields and
  // read .key/.type/.en; applyPreset walks tpl.presets and reads .en/.mk. A
  // hand-added template missing one of those fails at render time in the
  // browser and nowhere else.
  const codes = Object.keys(h.GF.DEPT_TEMPLATES);
  assert.equal(codes.length > 0, true);
  for (const code of codes) {
    const tpl = h.GF.DEPT_TEMPLATES[code];
    assert.equal(Array.isArray(tpl.fields), true, `${code}: fields must be an array`);
    for (const f of tpl.fields) {
      assert.equal(typeof f.key, 'string', `${code}: every field needs a key`);
      assert.equal(typeof f.en, 'string', `${code}.${f.key}: needs an English label`);
      assert.equal(typeof f.mk, 'string', `${code}.${f.key}: needs a Macedonian label`);
      if (f.type === 'select') {
        assert.equal(Array.isArray(f.opts), true, `${code}.${f.key}: a select needs opts`);
        for (const o of f.opts) {
          assert.equal(typeof o.v, 'string', `${code}.${f.key}: every option needs a value`);
          assert.equal(typeof o.en, 'string', `${code}.${f.key}: every option needs a label`);
        }
      }
    }
    for (const p of tpl.presets || []) {
      assert.equal(typeof p.en, 'string', `${code}: every preset needs an English title`);
      assert.equal(typeof p.mk, 'string', `${code}: every preset needs a Macedonian title`);
    }
  }
  h.close();
});

/* Render the real fields into the DOM, set some values, then collect. */
function renderAndCollect(deptId, values, base) {
  const h = withRealDepts();
  const doc = h.window.document;
  // GF.selectField comes from chooser.js, which is not loaded here; text and
  // number fields render without it, and the `cultivation` template is
  // text/number only (asserted below so this stays honest if it changes).
  const tpl = h.GF.deptTemplate(deptId);
  if (tpl) {
    assert.deepEqual(
      Array.from(new Set(Array.from(tpl.fields, f => f.type))).sort(),
      ['number', 'text'],
      'this fixture only renders text/number fields; a select would need chooser.js');
  }
  const host = doc.createElement('div');
  host.innerHTML = h.GF.renderDeptFields(deptId, {});
  doc.body.appendChild(host);
  for (const [key, v] of Object.entries(values)) {
    const el = doc.getElementById('attr-f-' + key);
    assert.notEqual(el, null, `renderDeptFields did not emit an input for '${key}'`);
    el.value = v;
  }
  const out = h.GF.collectDeptAttrs(deptId, base);
  const keys = Array.from(tpl ? tpl.fields : [], f => f.key);
  h.close();
  return { out, keys };
}

// Keys of the cultivation template, resolved from the real template rather
// than hard-coded, so a rename in dept-templates.js does not silently make
// these tests assert nothing.
function cultivationKeys() {
  const h = withRealDepts();
  const fields = h.GF.deptTemplate('d-cu').fields;
  const keys = {
    number: fields.find(f => f.type === 'number').key,
    text: fields.find(f => f.type === 'text').key,
  };
  h.close();
  return keys;
}

test('collectDeptAttrs types a number field as a Number and trims a text field', () => {
  const { number: numberKey, text: textKey } = cultivationKeys();
  const { out } = renderAndCollect('d-cu', { [numberKey]: '12', [textKey]: '  SOP-QC-014  ' });
  // The coercion matters because the value reaches a JSONB attributes column
  // that later gets summed/compared; a quoted "12" would sort as a string.
  assert.equal(out[numberKey], 12);
  assert.equal(typeof out[numberKey], 'number');
  assert.equal(out[textKey], 'SOP-QC-014');
});

test('a number field does NOT enforce its own min/step — collectDeptAttrs passes them through', () => {
  const { number: numberKey } = cultivationKeys();
  // renderDeptFields emits min="0" step="1" on number inputs, but those are
  // HTML *validity* constraints, and nothing in this path calls
  // checkValidity(). A negative or fractional plant_count therefore reaches
  // the payload as a well-typed Number. Pinned as observed behaviour: the
  // constraint exists in the markup and is not applied on save.
  assert.equal(renderAndCollect('d-cu', { [numberKey]: '-3' }).out[numberKey], -3);
  assert.equal(renderAndCollect('d-cu', { [numberKey]: '12.5' }).out[numberKey], 12.5);
  assert.equal(renderAndCollect('d-cu', { [numberKey]: '1e3' }).out[numberKey], 1000);
});

test('a number input sanitises non-numeric text to empty, so the key is dropped', () => {
  const { number: numberKey } = cultivationKeys();
  // This is the browser's own value-sanitisation for type="number" (jsdom
  // implements it), and it happens BEFORE collectDeptAttrs sees anything: the
  // element reports '' and the attribute is deleted. The practical consequence
  // is that collectDeptAttrs's string fallback — the `Number.isFinite(...)`
  // false branch — is unreachable for a number-typed template field through
  // this UI. Worth pinning because a future change to type="text" would
  // suddenly make that branch live and start writing strings into the column.
  for (const typed of ['n/a', '5-7', ' 12 ', 'twelve']) {
    const { out } = renderAndCollect('d-cu', { [numberKey]: typed }, { [numberKey]: 99 });
    assert.equal(Object.hasOwn(out, numberKey), false,
      `${JSON.stringify(typed)} is sanitised to '' by the number input and must clear the key`);
  }
});

test('collectDeptAttrs PRESERVES keys outside the current template', () => {
  const h = withRealDepts();
  const textKey = h.GF.deptTemplate('d-cu').fields.find(f => f.type === 'text').key;
  h.close();
  // The whole reason it takes `base`. These keys have no input rendered, so a
  // naive "read the form" implementation drops them — and because the save is
  // a whole-object PATCH, dropping them DELETES captured/imported metadata
  // from the task on the server. This is the assertion that guards that.
  const { out } = renderAndCollect('d-cu', { [textKey]: 'kept' }, {
    imported_ref: 'INV-2026-0044',
    captured_by: 'intake-scan',
    legacy_number: 7,
  });
  assert.equal(out.imported_ref, 'INV-2026-0044');
  assert.equal(out.captured_by, 'intake-scan');
  assert.equal(out.legacy_number, 7);
  assert.equal(out[textKey], 'kept');
});

test('collectDeptAttrs DELETES a template key whose input was cleared', () => {
  const h = withRealDepts();
  const textKey = h.GF.deptTemplate('d-cu').fields.find(f => f.type === 'text').key;
  h.close();
  // The other direction: clearing a field must actually remove the attribute,
  // not leave the previous value from `base` in place. `delete` (not `= ''`)
  // is what keeps an empty string out of the payload.
  const { out } = renderAndCollect('d-cu', { [textKey]: '' }, { [textKey]: 'old value', other: 'kept' });
  assert.equal(Object.hasOwn(out, textKey), false);
  assert.equal(out.other, 'kept');

  // Whitespace-only counts as cleared, because raw is trimmed before the test.
  const ws = renderAndCollect('d-cu', { [textKey]: '   ' }, { [textKey]: 'old value' });
  assert.equal(Object.hasOwn(ws.out, textKey), false);
});

test('collectDeptAttrs does not mutate the base object it was handed', () => {
  const h = withRealDepts();
  const textKey = h.GF.deptTemplate('d-cu').fields.find(f => f.type === 'text').key;
  h.close();
  // It is called with the LIVE task's attributes in edit mode, so mutating
  // `base` would corrupt the in-memory task even on a cancelled edit.
  const base = { [textKey]: 'original', keepme: 1 };
  const snapshot = JSON.stringify(base);
  renderAndCollect('d-cu', { [textKey]: '' }, base);
  assert.equal(JSON.stringify(base), snapshot);
});

test('collectDeptAttrs returns base untouched when no template or no inputs exist', () => {
  const h = withRealDepts();
  // The result is built with Object.assign in the jsdom realm, so it carries
  // that realm's Object.prototype; deepStrictEqual compares prototypes. Round
  // -tripping through JSON re-homes it and compares the data only.
  const plain = (o) => JSON.parse(JSON.stringify(o));
  // No template for this department: nothing is read, nothing is deleted.
  assert.deepEqual(plain(h.GF.collectDeptAttrs('d-nc', { a: 1 })), { a: 1 });
  assert.deepEqual(plain(h.GF.collectDeptAttrs('nope', { a: 1 })), { a: 1 });
  // A template WITH fields but no rendered inputs (the modal is closed) must
  // also leave existing values alone — `if (!el) return` is load-bearing,
  // because without it every save from a collapsed form would wipe the
  // department metadata.
  assert.deepEqual(plain(h.GF.collectDeptAttrs('d-cu', { a: 1 })), { a: 1 });
  // A missing base is the create path.
  assert.deepEqual(plain(h.GF.collectDeptAttrs('d-cu', undefined)), {});
  assert.deepEqual(plain(h.GF.collectDeptAttrs('d-cu', null)), {});
  h.close();
});

test('GF.renderDeptFields escapes the values and placeholders it puts in attributes', () => {
  const h = withRealDepts();
  const textKey = h.GF.deptTemplate('d-cu').fields.find(f => f.type === 'text').key;
  // Prefilled values in edit mode come straight from the stored attributes,
  // which may have been captured by the intake scanner rather than typed.
  const html = h.GF.renderDeptFields('d-cu', { [textKey]: '" onfocus="alert(1)' });
  assert.equal(html.includes('onfocus="alert(1)"'), false);
  assert.equal(html.includes('value="&quot; onfocus=&quot;alert(1)"'), true);
  assert.equal(h.GF.renderDeptFields('d-nc', {}), '', 'no template means no fields block');
  h.close();
});

test('GF.attrChips renders at most four chips, escaped and value-truncated', () => {
  const h = withRealDepts();
  // No template -> first three raw keys. With a template -> only chip:true
  // fields. Either way the cap is 4 and values are cut at 24 characters, which
  // is what keeps a pasted paragraph from stretching a board card off-screen.
  const many = { a: '1', b: '2', c: '3', d: '4', e: '5' };
  const raw = h.GF.attrChips({ dept: 'd-nc', attrs: many });
  assert.equal((raw.match(/attr-chip/g) || []).length, 3);

  const long = h.GF.attrChips({ dept: 'd-nc', attrs: { note: 'x'.repeat(80) } });
  assert.equal(long.includes('x'.repeat(24)), true);
  assert.equal(long.includes('x'.repeat(25)), false);

  const hostile = h.GF.attrChips({ dept: 'd-nc', attrs: { '<k>': '<script>alert(1)</script>' } });
  assert.equal(hostile.includes('<script>'), false);
  assert.equal(hostile.includes('&lt;script&gt;'), true);
  assert.equal(hostile.includes('title="&lt;k&gt;"'), true);

  // Non-object attrs (null from the API, or a stray string) must be ignored.
  assert.equal(h.GF.attrChips({ dept: 'd-nc', attrs: null }), '');
  assert.equal(h.GF.attrChips({ dept: 'd-nc', attrs: 'nope' }), '');
  assert.equal(h.GF.attrChips(undefined), '');
  h.close();
});

test('GF.attrChips shows a select field\'s LABEL, not its stored value', () => {
  const h = withRealDepts();
  // Find a template that actually has a chip:true select, so this test tracks
  // the shipped templates instead of a fixture.
  let found = null;
  for (const [code, tpl] of Object.entries(h.GF.DEPT_TEMPLATES)) {
    const f = tpl.fields.find(f => f.chip && f.type === 'select' && f.opts && f.opts.length);
    if (f) { found = { code, field: f }; break; }
  }
  if (!found) { h.close(); return; }   // no such template shipped; nothing to pin

  h.GF.DEPTS = [{ id: 'd-x', code: found.code, name: 'X', mk: 'X', abbr: 'X' }];
  const opt = found.field.opts[0];
  const chips = h.GF.attrChips({ dept: 'd-x', attrs: { [found.field.key]: opt.v } });
  assert.equal(chips.includes(h.GF.esc(opt.en)), true,
    `the chip must show the option label '${opt.en}', not the raw value '${opt.v}'`);
  h.GF.state.lang = 'mk';
  const mkChips = h.GF.attrChips({ dept: 'd-x', attrs: { [found.field.key]: opt.v } });
  assert.equal(mkChips.includes(h.GF.esc(opt.mk || opt.en)), true);
  h.close();
});
