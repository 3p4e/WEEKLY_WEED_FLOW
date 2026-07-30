'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/core.js — GF.t / AL / GF.dep / GF.depName / GF.depAbbr
                    GF.statusLabel / GF.prLabel / GF.dayLabel
                    GF.taskTypeLabel / GF.roleLabel

   The UI is bilingual EN / MK and the active language comes from
   localStorage['gf_lang'] — a value the user's browser owns, not a value the
   app validates. The label helpers do NOT all handle that the same way: some
   fall back to English for an unknown language, some return `undefined` and
   would paint the literal word "undefined" into the page. That asymmetry is
   invisible without a test, and it is a real reachable state (a stale key, a
   shared browser, a hand-edited value), so it is pinned below rather than
   assumed away.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

test('the active language is read from localStorage at load time and defaults to en', () => {
  const en = loadGF();
  assert.equal(en.GF.state.lang, 'en');
  en.close();
  const mk = loadGF({ storage: { gf_lang: 'mk' } });
  assert.equal(mk.GF.state.lang, 'mk');
  mk.close();
});

test('GF.t resolves the active language, then English, then the key itself', () => {
  const h = loadGF({ storage: { gf_lang: 'mk' } });
  assert.equal(h.GF.t('my_week'), 'Моја недела');
  h.GF.state.lang = 'en';
  assert.equal(h.GF.t('my_week'), 'My Week');
  // A key that exists in en but not in mk falls through to en rather than
  // rendering empty — the dictionaries are hand-maintained and drift.
  h.GF.state.lang = 'mk';
  h.GF.I18N.en.only_in_en = 'English only';
  assert.equal(h.GF.t('only_in_en'), 'English only');
  // An unknown key renders as the key. Ugly on screen, but visible and
  // debuggable — far better than an empty label.
  assert.equal(h.GF.t('no_such_key'), 'no_such_key');
  h.close();
});

test('GF.t survives an unsupported gf_lang value by falling back to English', () => {
  // GF.I18N['de'] is undefined; the `GF.I18N[lang] &&` guard is what stops this
  // from throwing on every single label during render.
  const h = loadGF({ storage: { gf_lang: 'de' } });
  assert.equal(h.GF.state.lang, 'de');
  assert.equal(h.GF.t('my_week'), 'My Week');
  assert.equal(h.GF.t('export'), 'Export');
  h.close();
});

test('AL picks the Macedonian arm only for lang === "mk"', () => {
  const h = loadGF();
  // AL is the ad-hoc bilingual picker ~40 view files call unqualified. It is
  // strictly an equality test against 'mk', so every other value — including a
  // regional variant like 'mk-MK' — silently gets English.
  assert.equal(h.global('AL("en", "mk")'), 'en');
  h.GF.state.lang = 'mk';
  assert.equal(h.global('AL("en", "mk")'), 'mk');
  h.GF.state.lang = 'mk-MK';
  assert.equal(h.global('AL("en", "mk")'), 'en');
  h.close();
});

test('GF.dep falls back to the first department for an unknown or missing id', () => {
  const h = loadGF();
  assert.equal(h.GF.dep('qc').name, 'Quality Control');
  // Never undefined: every caller does `GF.dep(t.dept).name` with no guard, so
  // the fallback is what keeps a stale dept id from throwing mid-render. It
  // does mean a bad id is displayed as Cloning & Nursery rather than flagged.
  assert.equal(h.GF.dep('no-such-dept').id, 'clone');
  assert.equal(h.GF.dep(undefined).id, 'clone');
  assert.equal(h.GF.dep(null).id, 'clone');
  h.close();
});

test('GF.depName switches language; GF.depAbbr is language-neutral', () => {
  const h = loadGF();
  assert.equal(h.GF.depName('qc'), 'Quality Control');
  h.GF.state.lang = 'mk';
  assert.equal(h.GF.depName('qc'), 'Контрола на квалитет');

  // GF.DEPTS from data.js has no `abbr` — integrate.js adds it when it remaps
  // the real backend departments. depAbbr must therefore degrade to the full
  // name, which is exactly the pre-login / offline-fallback state.
  assert.equal(h.GF.depAbbr('qc'), 'Quality Control');
  h.GF.DEPTS = [{ id: 'qc', code: 'quality_control', name: 'Quality Control', mk: 'КК', abbr: 'QC' }];
  assert.equal(h.GF.depAbbr('qc'), 'QC');
  h.GF.state.lang = 'en';
  assert.equal(h.GF.depAbbr('qc'), 'QC', 'the abbreviation must not change with the language');
  h.close();
});

test('status / priority / day / type / role labels translate, and unknown keys pass through', () => {
  const h = loadGF();
  assert.equal(h.GF.statusLabel('working'), 'Working on it');
  assert.equal(h.GF.prLabel('critical'), 'Critical');
  assert.equal(h.GF.dayLabel('Wed'), 'Wed');
  assert.equal(h.GF.taskTypeLabel('validation'), 'Validation');
  assert.equal(h.GF.roleLabel('qa_mgr'), 'QA Manager');

  h.GF.state.lang = 'mk';
  assert.equal(h.GF.statusLabel('working'), 'Во тек');
  assert.equal(h.GF.prLabel('critical'), 'Критичен');
  assert.equal(h.GF.dayLabel('Wed'), 'Сре');
  assert.equal(h.GF.taskTypeLabel('validation'), 'Валидација');
  assert.equal(h.GF.roleLabel('qa_mgr'), 'Менаџер за КО');

  // Unknown values echo back rather than rendering empty. 'ongoing' and
  // 'normal' are the RAW BACKEND enum values that integrate.js maps away; if
  // that mapping is ever bypassed the UI shows the raw token, which is at
  // least recognisable in a screenshot.
  assert.equal(h.GF.statusLabel('ongoing'), 'ongoing');
  assert.equal(h.GF.prLabel('normal'), 'normal');
  assert.equal(h.GF.dayLabel('Xyz'), 'Xyz');
  assert.equal(h.GF.taskTypeLabel('nope'), 'nope');
  assert.equal(h.GF.roleLabel('nope'), 'nope');
  h.close();
});

test('an unsupported gf_lang yields undefined status/priority labels but not the others', () => {
  const h = loadGF({ storage: { gf_lang: 'de' } });
  // Three different fallback strategies coexist in the same file:
  //   GF.t / GF.taskTypeLabel  -> explicit `|| …en` chain
  //   GF.roleLabel             -> explicit `|| GF.ROLES[r].en`
  //   GF.depName / GF.dayLabel -> `lang === 'mk' ? mk : en` ternary, i.e. any
  //                               non-mk value lands on English by construction
  //   GF.statusLabel / prLabel -> index the language directly, NO fallback
  // Only the last pair yields undefined, and it is reachable: gf_lang is
  // user-writable localStorage. undefined is what puts the literal word
  // "undefined" on a status pill and in the report's status column.
  assert.equal(h.GF.roleLabel('qa_mgr'), 'QA Manager');
  assert.equal(h.GF.t('my_week'), 'My Week');
  assert.equal(h.GF.taskTypeLabel('validation'), 'Validation');
  assert.equal(h.GF.depName('qc'), 'Quality Control');
  assert.equal(h.GF.dayLabel('Wed'), 'Wed');
  assert.equal(h.GF.statusLabel('working'), undefined);
  assert.equal(h.GF.prLabel('critical'), undefined);
  h.close();
});

test('GF.dayLabel translates only the seven known day tokens, by index', () => {
  const h = loadGF({ storage: { gf_lang: 'mk' } });
  const en = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const mk = ['Пон', 'Вто', 'Сре', 'Чет', 'Пет', 'Саб', 'Нед'];
  // The two arrays are matched positionally, so a reorder of either one
  // mistranslates every day without any error surfacing.
  assert.deepEqual(Array.from(en, d => h.GF.dayLabel(d)), mk);
  assert.deepEqual(Array.from(h.GF.DAYS), en);
  h.close();
});

test('the six-state status cycle order matches the status dictionary exactly', () => {
  const h = loadGF();
  // GF.STATUS_ORDER drives GF.cycleStatus and the status picker; GF.STATUS
  // supplies the labels. A state present in one and absent from the other is
  // either an unreachable status or an unlabelled pill.
  assert.deepEqual(Array.from(h.GF.STATUS_ORDER).sort(), Object.keys(h.GF.STATUS).sort());
  for (const s of h.GF.STATUS_ORDER) {
    assert.equal(typeof h.GF.STATUS[s].en, 'string', `${s} needs an English label`);
    assert.equal(typeof h.GF.STATUS[s].mk, 'string', `${s} needs a Macedonian label`);
  }
  h.close();
});

test('every role in the role picker has both translations, and every perms role has a label', () => {
  const h = loadGF();
  for (const [role, labels] of Object.entries(h.GF.ROLES)) {
    assert.equal(typeof labels.en, 'string', `${role}: en label`);
    assert.equal(typeof labels.mk, 'string', `${role}: mk label`);
  }
  // A role that can be assigned but has no permissions row silently drops to
  // `operator`; a role with permissions but no label renders as its raw token.
  for (const role of Object.keys(h.GF.PERMS)) {
    assert.notEqual(h.GF.ROLES[role], undefined, `GF.PERMS has '${role}' but GF.ROLES does not`);
  }
  for (const role of Object.keys(h.GF.ROLES)) {
    assert.notEqual(h.GF.PERMS[role], undefined, `GF.ROLES has '${role}' but GF.PERMS does not`);
  }
  h.close();
});

test('every task-type token has both translations', () => {
  const h = loadGF();
  for (const [type, labels] of Object.entries(h.GF.TASK_TYPE_LABELS)) {
    assert.equal(typeof labels.en, 'string', `${type}: en label`);
    assert.equal(typeof labels.mk, 'string', `${type}: mk label`);
  }
  h.close();
});

test('GF.icon emits a path for a known icon and an empty path for an unknown one', () => {
  const h = loadGF();
  // Icons are interpolated into `<path d="…">`; an unknown name must produce
  // d="" rather than d="undefined", which renders as a console SVG parse error
  // on every affected node.
  assert.match(h.GF.icon('search'), /^<svg class="icon" viewBox="0 0 20 20"><path d="M17 17/);
  assert.equal(h.GF.icon('no-such-icon'), '<svg class="icon" viewBox="0 0 20 20"><path d=""/></svg>');
  assert.equal(h.GF.icon('search', 'big').includes('class="big"'), true);
  assert.equal(h.GF.icon('search', 'icon', '#E5484D').includes('style="stroke:#E5484D"'), true);
  h.close();
});
