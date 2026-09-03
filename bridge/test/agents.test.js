import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';
import { Store } from '../server/store.js';
import { Vault } from '../server/vault.js';
import { AgentService, headlessArgv } from '../server/agents.js';
import { getProvider } from '../server/providers.js';

const store = new Store(mkdtempSync(`${tmpdir()}/bridge-agents-`));
const vault = new Vault(store, randomBytes(32));
const events = [];
const svc = new AgentService({ store, vault, shell: '/bin/sh', projectsRoot: tmpdir(), onChange: (t, p) => events.push([t, p]) });
after(() => svc.stop());

const settle = async (runId, ms = 5000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { const r = svc.run(runId); if (r.status !== 'running') return r; await new Promise((r) => setTimeout(r, 50)); } throw new Error('run did not finish'); };

test('headless profiles encode the permission level', () => {
  assert.deepEqual(headlessArgv(getProvider('claude'), 'do x', 'plan'), ['-p', 'do x', '--output-format', 'text', '--permission-mode', 'plan']);
  assert.deepEqual(headlessArgv(getProvider('claude'), 'do x', 'full'), ['-p', 'do x', '--output-format', 'text', '--dangerously-skip-permissions']);
  assert.deepEqual(headlessArgv(getProvider('codex'), 'do x', 'edit'), ['exec', '--full-auto', 'do x']);
  assert.deepEqual(headlessArgv(getProvider('shell'), 'echo hi', 'plan'), ['-lc', 'echo hi']);
});

test('create validates; a manual run captures output, exit code and review state', async () => {
  assert.throws(() => svc.create({ name: 'x', brief: 'y', cron: 'nope' }), /cron/);
  assert.throws(() => svc.create({ name: 'x', brief: 'y', permission: 'god' }), /permission/);
  const a = svc.create({ name: 'Nightly report', brief: 'echo REPORT=$BRIDGE_AGENT; echo TOK=[$BRIDGE_TOKEN]; exit 3', providerId: 'shell', authMode: 'inherit', cron: '@daily', enabled: true });
  assert.ok(a.nextRunAt); assert.equal(a.cronError, null);
  const run = await svc.launch(a.id);
  assert.equal(run.status, 'running'); assert.equal(run.trigger, 'manual');
  await assert.rejects(svc.launch(a.id), /already running/);
  const done = await settle(run.id);
  assert.equal(done.status, 'failed'); assert.equal(done.exitCode, 3);
  assert.match(done.output, /REPORT=Nightly report/); assert.match(done.output, /TOK=\[\]/);
  assert.equal(svc.runs(a.id)[0].reviewed, false);
  assert.equal(svc.review(run.id).reviewed, true);
  assert.equal(svc.get(a.id).lastRunAt, run.startedAt);
  assert.ok(events.some(([t, p]) => t === 'run' && p.id === run.id && p.status === 'failed'));
});

test('the scheduler fires once per matching minute and honours enabled', async () => {
  const a = svc.create({ name: 'Ticker', brief: 'echo tick', providerId: 'shell', authMode: 'inherit', cron: '*/1 * * * *', enabled: true });
  const now = new Date(2026, 8, 3, 10, 0);
  assert.deepEqual(svc.tick(now), [a.id]);
  assert.deepEqual(svc.tick(new Date(now.getTime() + 20_000)), []);        // same minute: no double fire
  const r = svc.runs(a.id)[0]; assert.equal(r.trigger, 'schedule');
  await settle(r.id);
  svc.update(a.id, { enabled: false });
  assert.deepEqual(svc.tick(new Date(now.getTime() + 60_000)), []);
  svc.update(a.id, { enabled: true });
  assert.deepEqual(svc.tick(new Date(now.getTime() + 60_000)), [a.id]);
  await settle(svc.runs(a.id)[0].id);
  assert.equal(svc.runs(a.id).length, 2);
  svc.remove(a.id);
  assert.equal(svc.runs(a.id).length, 0);
  assert.throws(() => svc.get(a.id));
});
