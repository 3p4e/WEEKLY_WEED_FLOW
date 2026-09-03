import { test, after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';
// Wait until the session's accumulated output satisfies `pred` (pty data and
// the exit event are delivered on independent channels, so "after exit" is not
// a safe moment to read output).
async function waitFor(session, pred, ms = 5000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) { if (pred(session.snapshot())) return session.snapshot(); await new Promise((r) => setTimeout(r, 50)); }
  throw new Error(`timed out waiting for output; got:\n${session.snapshot()}`);
}
import { Store } from '../server/store.js';
import { Vault } from '../server/vault.js';
import { SessionManager } from '../server/sessions.js';
import { TaskService, ROLES } from '../server/tasks.js';
import { randomBytes } from 'node:crypto';

function mkRepo() {
  const dir = mkdtempSync(`${tmpdir()}/bridge-repo-`);
  const g = (...a) => execFileSync('git', a, { cwd: dir, env: { ...process.env, GIT_AUTHOR_NAME: 't', GIT_AUTHOR_EMAIL: 't@t', GIT_COMMITTER_NAME: 't', GIT_COMMITTER_EMAIL: 't@t' } });
  g('init', '-q', '-b', 'main'); writeFileSync(`${dir}/a.txt`, 'a\n'); g('add', '.'); g('commit', '-q', '-m', 'init');
  return dir;
}

const store = new Store(mkdtempSync(`${tmpdir()}/bridge-data-`));
const vault = new Vault(store, randomBytes(32));
const sessions = new SessionManager({ maxSessions: 4, scrollback: 4096 });
const svc = new TaskService({ store, vault, sessions, shell: '/bin/sh', projectsRoot: tmpdir() });
after(() => sessions.shutdown());

test('task CRUD with status validation', () => {
  const t = svc.create({ title: '  Ship it ', description: 'd', repoPath: tmpdir() });
  assert.equal(t.title, 'Ship it'); assert.equal(t.status, 'backlog');
  assert.equal(svc.update(t.id, { status: 'review' }).status, 'review');
  assert.throws(() => svc.update(t.id, { status: 'nope' }));
  assert.throws(() => svc.create({ title: '' }));
});

test('launching two shell agents on one task: separate worktrees, shared notes, prompt content', async () => {
  const repo = mkRepo();
  const t = svc.create({ title: 'Add login', description: 'Users must log in.', repoPath: repo });
  const a = await svc.launch(t.id, { providerId: 'shell', role: 'implementer' });
  const b = await svc.launch(t.id, { providerId: 'shell', role: 'reviewer' });
  assert.equal(a.task.status, 'in_progress');
  assert.equal(b.task.agents.length, 2);
  assert.notEqual(a.session.worktree.path, b.session.worktree.path);
  assert.ok(a.session.cwd.startsWith(`${repo}/.bridge/worktrees/`));
  const notes = `${repo}/.bridge/tasks/${t.id}.md`;
  assert.ok(existsSync(notes));
  assert.match(readFileSync(notes, 'utf8'), /Add login[\s\S]*Users must log in/);
  const prompt = svc.buildPrompt(svc.get(t.id), 'reviewer', { cwd: b.session.cwd, branch: b.session.worktree.branch, base: 'main', notes, siblings: 'shell/implementer' });
  assert.match(prompt, /Role: You are the REVIEWER/); assert.match(prompt, /shell\/implementer/); assert.match(prompt, new RegExp(notes.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  // the session is a live pty in the worktree
  const s = sessions.get(a.session.id);
  s.write('pwd; echo BRIDGE_TASK_ID=$BRIDGE_TASK_ID; echo DONE_MARKER; exit\n');
  const out = await waitFor(s, (o) => o.includes('DONE_MARKER\r') || o.includes('DONE_MARKER\n'));
  assert.match(out, new RegExp(a.session.cwd.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.match(out, new RegExp(`BRIDGE_TASK_ID=${t.id}`));
  await waitFor(s, () => s.status === 'exited');
});

test('key mode injects a vault credential into the agent env', async () => {
  const c = vault.add({ name: 'k', envVar: 'ANTHROPIC_API_KEY', value: 'sk-test-injected' });
  const t = svc.create({ title: 'Keyed', repoPath: tmpdir() });
  const r = await svc.launch(t.id, { providerId: 'shell', authMode: 'key', credentialId: c.id, isolation: 'shared' });
  const s = sessions.get(r.session.id);
  s.write('echo KEY=$ANTHROPIC_API_KEY; echo TOK=[$BRIDGE_TOKEN]; exit\n');
  const out = await waitFor(s, (o) => /TOK=\[/.test(o));
  assert.match(out, /KEY=sk-test-injected/);
  assert.match(out, /TOK=\[\]/);
  await assert.rejects(svc.launch(t.id, { providerId: 'shell', authMode: 'key', credentialId: null, isolation: 'shared' }), /credential/);
});

test('worktree isolation refuses a non-git directory; swarm launches the trio', async () => {
  const t = svc.create({ title: 'NoRepo', repoPath: tmpdir() });
  await assert.rejects(svc.launch(t.id, { providerId: 'shell' }), /not a git repository/);
  const repo = mkRepo();
  const t2 = svc.create({ title: 'Swarm me', repoPath: repo });
  // free up the session budget first
  for (const s of sessions.list()) sessions.remove(s.id);
  const team = await svc.swarm(t2.id, { providerId: 'shell' });
  assert.deepEqual(team.map((x) => x.session.role), ['architect', 'implementer', 'reviewer']);
  assert.equal(new Set(team.map((x) => x.session.worktree.branch)).size, 3);
  assert.ok(Object.keys(ROLES).includes('architect'));
});

test('session manager enforces the limit and keeps scrollback for late attachers', async () => {
  for (const s of sessions.list()) sessions.remove(s.id);
  const s = await svc.launchFree({ providerId: 'shell', cwd: tmpdir() });
  const live = sessions.get(s.id);
  live.write('echo HELLO_SCROLLBACK\n');
  await waitFor(live, (o) => /HELLO_SCROLLBACK\r?\n/.test(o));
  assert.ok(!('pty' in live.toJSON()));
  await svc.launchFree({ providerId: 'shell', cwd: tmpdir() });
  await svc.launchFree({ providerId: 'shell', cwd: tmpdir() });
  await svc.launchFree({ providerId: 'shell', cwd: tmpdir() });
  await assert.rejects(svc.launchFree({ providerId: 'shell', cwd: tmpdir() }), /limit/);
});
