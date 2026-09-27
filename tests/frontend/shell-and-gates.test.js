'use strict';

/* ══════════════════════════════════════════════════════════════════════
   The smaller findings of review 2026-09-27, pinned:

   FE-13  sw.js installs the shell with cache: 'reload' (nginx serves js/css
          with expires 5m, so a plain addAll could store a still-fresh OLD
          file under the NEW version), and the shell list, index.html and
          the files on disk agree.
   FE-14  AI Intake is gated like its route (POST /intake/extract is
          elevated-only); the report's document panel renders nothing for a
          base USER instead of "Couldn't load … Insufficient role" + Retry.
   FE-17  GF.daysSince is the one "days in phase" rule, on the facility day.
   FE-21  the retired QMS stubs are out of the shell; the demo-era state
          (aiBase / aiProvider / GF.setUser) is gone.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { loadGF, GF_DIR } = require('./helpers/gf-window.js');

const WEB = path.resolve(GF_DIR, '..');

/* ── FE-13 / FE-21: the service worker and the shell ─────────────────── */

test('the service worker installs the shell past the HTTP cache', () => {
  const sw = fs.readFileSync(path.join(WEB, 'sw.js'), 'utf8');
  assert.match(sw, /c\.addAll\(SHELL\.map\(\(u\) => new Request\(u, \{ cache: 'reload' \}\)\)\)/,
    'addAll must fetch with cache: reload, or a fresh-but-old copy is stored under the new VERSION');
});

test('index.html scripts, the sw.js shell and the files on disk agree', () => {
  const sw = fs.readFileSync(path.join(WEB, 'sw.js'), 'utf8');
  const html = fs.readFileSync(path.join(WEB, 'index.html'), 'utf8');
  const shellBlock = sw.slice(sw.indexOf('const SHELL = ['), sw.indexOf('];', sw.indexOf('const SHELL = [')));
  const shellJs = [...shellBlock.matchAll(/'\/gf\/([^']+\.js)'/g)].map(m => m[1]).filter(n => !n.startsWith('vendor/'));
  const htmlJs = [...html.matchAll(/<script src="gf\/([^"]+\.js)"><\/script>/g)].map(m => m[1]).filter(n => !n.startsWith('vendor/'));
  const onDisk = fs.readdirSync(GF_DIR).filter(n => n.endsWith('.js'));
  const sortedEq = (a, b, msg) => assert.deepEqual([...a].sort(), [...b].sort(), msg);
  sortedEq(shellJs, htmlJs, 'every script index.html loads is precached, and nothing else is');
  sortedEq(htmlJs, onDisk, 'every web/gf/*.js on disk is loaded by index.html, and nothing missing is listed');
  for (const stub of ['qmsregistry-view.js', 'qmsknow-view.js']) {
    assert.ok(!onDisk.includes(stub), `${stub} was a retired stub and is gone`);
  }
});

test('the four unreferenced leaf assets are gone and nothing references them', () => {
  for (const f of ['PP_Leaf.svg', 'PP_Leaf_3D.glb', 'pp-leaf-outline.svg', 'pp-leaf.svg']) {
    assert.ok(!fs.existsSync(path.join(WEB, 'assets', f)), `${f} removed`);
  }
  const all = [fs.readFileSync(path.join(WEB, 'index.html'), 'utf8'), fs.readFileSync(path.join(WEB, 'sw.js'), 'utf8')]
    .concat(fs.readdirSync(GF_DIR).filter(n => /\.(js|css)$/.test(n)).map(n => fs.readFileSync(path.join(GF_DIR, n), 'utf8')));
  assert.ok(!all.some(s => /PP_Leaf|pp-leaf-outline|pp-leaf\.svg/.test(s)));
});

/* ── FE-14: gates that match the server ──────────────────────────────── */

test('AI Intake registers with the elevated gate its route enforces', () => {
  const PRE = `
    window.GF = window.GF || {};
    window.GF.views = window.GF.views || {};
    window.GF.WWF = window.GF.WWF || {};
    window.GF.WWF._registerFullPageView = function (spec) { window.__reg = spec; };
    window.GF.API = { user: { role: 'USER' } };
  `;
  const h = loadGF({ files: ['data.js', 'core.js', 'intake-view.js'], preScript: PRE });
  const spec = h.window.__reg;
  assert.equal(spec.key, 'intake');
  assert.equal(spec.guard(), false, 'a base USER gets 403 on Extract, so the screen is not offered');
  h.window.GF.API.user = { role: 'QA_MGR' };
  assert.equal(spec.guard(), true);
  h.close();
});

function loadDoc(role) {
  const PRE = `
    const ELEVATED_ROLES = ['ADMIN','OWNER','CEO','COO','QA_MGR','QC_MGR','PR_MGR','WH_MGR','SE_MGR','CU_MGR','IR_MGR','MU_MGR','QP'];
    window.GF = window.GF || {};
    window.GF.WWF = window.GF.WWF || {};
    window.GF.WWF._report = { mode: 'report', refDate: '' };
    window.GF.API = { user: { role: '${role}' }, base: '', token: 't' };
    window.GF.dateField = function (id) { return '<input type="hidden" id="' + id + '">'; };
    window.GF.selectField = function (id) { return '<input type="hidden" id="' + id + '">'; };
  `;
  const h = loadGF({ files: ['data.js', 'core.js', 'document-view.js'], preScript: PRE,
                     bodyHtml: '<div id="report-doc"></div>' });
  h.window.GF.WWF._report = { mode: 'report', refDate: '' };
  return h;
}

test('the report document panel is not requested, and renders nothing, for a base USER', async () => {
  const h = loadDoc('USER');
  const w = h.window;
  let called = 0;
  w.GF.API.getDocument = async () => { called++; return {}; };
  await w.GF.WWF.loadDocument();
  assert.equal(called, 0, 'GET /reports/documents is elevated-only; a USER must not be sent to it');
  assert.equal(w.document.getElementById('report-doc').innerHTML, '', 'no "Insufficient role" panel, no Retry');
  h.close();
});

test('an elevated role still loads the document panel', async () => {
  const h = loadDoc('QA_MGR');
  const w = h.window;
  let called = 0;
  w.GF.API.getDocument = async () => { called++; return { id: 'd1', status: 'draft', kind: 'report', week_start: '2026-07-24', content: {} }; };
  await w.GF.WWF.loadDocument();
  assert.equal(called, 1);
  assert.match(w.document.getElementById('report-doc').innerHTML, /DRAFT/);
  h.close();
});

/* ── FE-17: one "days in phase" rule ─────────────────────────────────── */

test('GF.daysSince counts whole days to the facility today', () => {
  const h = loadGF({ files: ['data.js', 'core.js'] });
  const GF = h.GF;
  GF.API = { user: { facility_tz: 'Europe/Skopje' } };   // harness today: 2026-07-30
  assert.equal(GF.daysSince('2026-07-28'), 2);
  assert.equal(GF.daysSince('2026-07-30'), 0, 'a phase entered today is day 0, before and after noon');
  assert.equal(GF.daysSince('2026-07-30T00:00:00'), 0, 'a stamp is read by its day');
  assert.equal(GF.daysSince('2026-08-01'), -2);
  assert.equal(GF.daysSince(''), null);
  assert.equal(GF.daysSince('not a day'), null);
  h.close();
});

/* ── FE-21: demo-era state is gone ───────────────────────────────────── */

test('core.js no longer carries the demo-era AI state or GF.setUser', () => {
  const h = loadGF({ files: ['data.js', 'core.js'] });
  assert.equal('aiBase' in h.GF.state, false);
  assert.equal('aiProvider' in h.GF.state, false);
  assert.equal(h.GF.setUser, undefined);
  h.close();
});
