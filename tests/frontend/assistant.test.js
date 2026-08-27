'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/assistant.js — GF.assistant.provider() / statusInfo() / complete()

   The 'gateway' branch used to call GF.ai._post()/GF.ai._user() — neither
   function exists anywhere in this codebase — selected via
   GF.state.aiProvider === 'gateway' + GF.state.aiBase. It was unreachable in
   the shipped app for two independent reasons: integrate.js unconditionally
   overrides provider()/statusInfo()/complete() with the real backend path
   the instant it loads, AND no screen in web/gf/*.js ever writes
   gf_ai_base/gf_ai_provider to begin with (confirmed dead in
   docs/AI-FEATURE-INVENTORY-2026-08-23.md). Removed rather than implemented.

   These tests exercise the file BEFORE integrate.js would ever load (the
   pre-override fallback state), and prove: (a) 'gateway' can no longer be
   reached at all, however aiProvider/aiBase are set, and (b) the 'builtin'
   path (window.claude) is untouched by the removal.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF } = require('./helpers/gf-window.js');

function setup(storage) {
  return loadGF({ files: ['data.js', 'core.js', 'assistant.js'], storage: storage || {} });
}

test('provider() is "none" with no window.claude and no aiBase/aiProvider set', () => {
  const h = setup();
  assert.equal(h.GF.assistant.provider(), 'none');
  h.close();
});

test('provider() never returns "gateway", even when aiProvider/aiBase are explicitly set to select it', () => {
  const h = setup({ gf_ai_provider: 'gateway', gf_ai_base: 'https://example.test' });
  assert.equal(h.GF.state.aiProvider, 'gateway');
  assert.equal(h.GF.state.aiBase, 'https://example.test');
  // The old code would have returned 'gateway' here — the whole point of the
  // fix is that this configuration can no longer select the dead branch.
  assert.equal(h.GF.assistant.provider(), 'none');
  h.close();
});

test('provider() returns "builtin" when window.claude.complete exists, regardless of aiBase', () => {
  const h = setup({ gf_ai_base: 'https://example.test' });
  h.window.claude = { complete: async () => 'ok' };
  assert.equal(h.GF.assistant.provider(), 'builtin');
  h.close();
});

test('statusInfo() never produces a "gateway" status line', () => {
  const h = setup({ gf_ai_provider: 'gateway', gf_ai_base: 'https://example.test' });
  const info = h.GF.assistant.statusInfo();
  assert.equal(info.on, false);
  assert.doesNotMatch(info.label, /Gateway|Сервер/);
  h.close();
});

test('complete() throws "no-ai" when no builtin is present, without ever touching GF.ai', () => {
  const h = setup({ gf_ai_provider: 'gateway', gf_ai_base: 'https://example.test' });
  // GF.ai is not defined at all in this load (only integrate.js creates it) —
  // if the removed 'gateway' branch were still reachable it would throw a
  // TypeError reading GF.ai._post, not the clean Error('no-ai') asserted here.
  assert.equal(h.window.GF.ai, undefined);
  return assert.rejects(h.GF.assistant.complete('hello'), (e) => e.message === 'no-ai');
});

test('complete() calls window.claude.complete on the builtin path', async () => {
  const h = setup();
  let seenPrompt = null;
  h.window.claude = { complete: async (p) => { seenPrompt = p; return 'the answer'; } };
  const r = await h.GF.assistant.complete('what is up');
  assert.equal(r, 'the answer');
  assert.equal(seenPrompt, 'what is up');
  h.close();
});
