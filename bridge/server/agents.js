// Agents on routines. An agent is a named brief pointed at a folder, launched
// headlessly (no PTY) by a schedule or by hand; every launch is a run whose
// output is kept for review. Nothing here is interactive: an agent either
// finishes on its own permission level or fails, and you read the result.
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { newId } from './store.js';
import { getProvider, buildEnv } from './providers.js';
import { createWorktree, repoRoot } from './worktrees.js';
import { parseCron, matches, nextRun } from './cron.js';

export const PERMISSIONS = ['plan', 'edit', 'full'];
const MAX_OUTPUT = 400 * 1024;
const MAX_RUNS_PER_AGENT = 50;

export function headlessArgv(provider, brief, permission) {
  const p = permission;
  switch (provider.id) {
    case 'claude': case 'moonshot': case 'moonshot-code':
      return ['-p', brief, '--output-format', 'text', ...(p === 'full' ? ['--dangerously-skip-permissions'] : ['--permission-mode', p === 'edit' ? 'acceptEdits' : 'plan'])];
    case 'codex': return ['exec', ...(p === 'full' ? ['--dangerously-bypass-approvals-and-sandbox'] : p === 'edit' ? ['--full-auto'] : ['--sandbox', 'read-only']), brief];
    case 'gemini': return ['-p', brief, ...(p === 'full' ? ['--yolo'] : p === 'edit' ? ['--approval-mode', 'auto_edit'] : [])];
    case 'opencode': return ['run', brief];
    case 'aider': return ['--message', brief, '--yes-always', ...(p === 'plan' ? ['--dry-run'] : [])];
    case 'shell': return ['-lc', brief];
    default: throw new Error(`no headless profile for ${provider.id}`);
  }
}

export class AgentService {
  constructor({ store, vault, shell, projectsRoot, onChange = () => {} }) {
    this.store = store; this.vault = vault; this.shell = shell; this.projectsRoot = projectsRoot;
    this.onChange = onChange; this.procs = new Map(); this.fired = new Map(); this.timer = null;
  }
  raw() { return this.store.read('agents', []); }
  list() { return this.raw().map((a) => this.decorate(a)); }
  get(id) { const a = this.raw().find((x) => x.id === id); if (!a) throw new Error(`agent ${id} not found`); return this.decorate(a); }
  decorate(a) {
    let nextRunAt = null, cronError = null;
    if (a.cron) { try { nextRunAt = a.enabled ? nextRun(a.cron)?.toISOString() ?? null : null; } catch (e) { cronError = e.message; } }
    return { ...a, nextRunAt, cronError, running: [...this.procs.keys()].some((rid) => this.runsRaw().find((r) => r.id === rid)?.agentId === a.id) };
  }
  validate(patch) {
    if (patch.cron) parseCron(patch.cron);
    if ('permission' in patch && !PERMISSIONS.includes(patch.permission)) throw new Error(`permission must be one of ${PERMISSIONS.join(', ')}`);
    if ('providerId' in patch) getProvider(patch.providerId);
    if ('isolation' in patch && !['shared', 'worktree'].includes(patch.isolation)) throw new Error('isolation must be shared or worktree');
  }
  create({ name, brief, providerId = 'claude', authMode = 'subscription', credentialId = null, cwd, isolation = 'shared', permission = 'plan', cron = '', enabled = false }) {
    if (!name?.trim()) throw new Error('name is required');
    if (!brief?.trim()) throw new Error('brief is required');
    const a = { id: newId('agent'), name: name.trim(), brief, providerId, authMode, credentialId, cwd: cwd || this.projectsRoot, isolation, permission, cron: cron || '', enabled: Boolean(enabled), createdAt: new Date().toISOString(), lastRunAt: null };
    this.validate(a);
    this.store.update('agents', [], (l) => [...l, a]);
    const d = this.decorate(a); this.onChange('agent', d); return d;
  }
  update(id, patch) {
    this.validate(patch);
    const allowed = ['name', 'brief', 'providerId', 'authMode', 'credentialId', 'cwd', 'isolation', 'permission', 'cron', 'enabled'];
    let out;
    this.store.update('agents', [], (l) => l.map((a) => { if (a.id !== id) return a; out = { ...a }; for (const k of allowed) if (k in patch) out[k] = patch[k]; return out; }));
    if (!out) throw new Error(`agent ${id} not found`);
    const d = this.decorate(out); this.onChange('agent', d); return d;
  }
  remove(id) {
    this.get(id);
    for (const r of this.runs(id)) if (r.status === 'running') this.cancel(r.id);
    this.store.update('agents', [], (l) => l.filter((a) => a.id !== id));
    this.store.update('runs', [], (l) => l.filter((r) => r.agentId !== id));
    this.onChange('agent_removed', { id });
  }

  runsRaw() { return this.store.read('runs', []); }
  strip({ output, ...r }) { return { ...r, outputBytes: output?.length || 0 }; }
  runs(agentId) { return this.runsRaw().filter((r) => !agentId || r.agentId === agentId).map((r) => this.strip(r)).sort((a, b) => b.startedAt.localeCompare(a.startedAt)); }
  run(runId) { const r = this.runsRaw().find((x) => x.id === runId); if (!r) throw new Error(`run ${runId} not found`); return r; }
  patchRun(id, fn) { let out; this.store.update('runs', [], (l) => l.map((r) => (r.id === id ? (out = fn({ ...r })) : r))); return out; }
  review(runId, reviewed = true) { const r = this.patchRun(runId, (x) => ({ ...x, reviewed })); if (!r) throw new Error(`run ${runId} not found`); this.onChange('run', this.strip(r)); return this.strip(r); }

  async launch(agentId, trigger = 'manual') {
    const a = this.get(agentId);
    if (this.runs(agentId).some((r) => r.status === 'running')) throw new Error(`${a.name} is already running`);
    const provider = getProvider(a.providerId);
    if (!existsSync(a.cwd)) throw new Error(`folder ${a.cwd} does not exist`);
    let cwd = a.cwd, worktree = null;
    if (a.isolation === 'worktree') {
      if (!(await repoRoot(a.cwd))) throw new Error(`${a.cwd} is not a git repository; use shared isolation`);
      worktree = await createWorktree({ repoPath: a.cwd, taskTitle: a.name, agentTag: `run-${a.providerId}` });
      cwd = worktree.path;
    }
    const secret = a.authMode === 'key' ? this.vault.reveal(a.credentialId) : null;
    const env = buildEnv(provider, a.authMode, secret, { BRIDGE_AGENT: a.name, CI: '1' });
    const command = provider.bin || this.shell;
    const argv = headlessArgv(provider, a.brief, a.permission);
    const run = { id: newId('run'), agentId: a.id, agentName: a.name, trigger, startedAt: new Date().toISOString(), finishedAt: null, status: 'running', exitCode: null, cwd, worktree,
      command: `${command} ${argv.map((x) => (x.length > 60 ? x.slice(0, 57) + '…' : x)).join(' ')}`, output: '', reviewed: false };
    this.store.update('runs', [], (l) => {
      const mine = l.filter((r) => r.agentId === a.id).sort((x, y) => x.startedAt.localeCompare(y.startedAt));
      const drop = new Set(mine.slice(0, Math.max(0, mine.length - MAX_RUNS_PER_AGENT + 1)).map((r) => r.id));
      return [...l.filter((r) => !drop.has(r.id)), run];
    });
    this.store.update('agents', [], (l) => l.map((x) => (x.id === a.id ? { ...x, lastRunAt: run.startedAt } : x)));
    this.onChange('run', this.strip(run));

    const child = spawn(command, argv, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'] });
    this.procs.set(run.id, child);
    let buf = '', flush = null;
    const onData = (d) => {
      buf += d.toString(); if (buf.length > MAX_OUTPUT) buf = buf.slice(-MAX_OUTPUT);
      if (!flush) flush = setTimeout(() => { flush = null; this.patchRun(run.id, (r) => ({ ...r, output: buf })); this.onChange('run_output', { id: run.id, bytes: buf.length }); }, 500);
    };
    child.stdout.on('data', onData); child.stderr.on('data', onData);
    child.on('error', (e) => { buf += `\n[bridge] failed to start: ${e.message}\n`; });
    child.on('close', (code, signal) => {
      clearTimeout(flush); this.procs.delete(run.id);
      const r = this.patchRun(run.id, (x) => ({ ...x, output: buf, status: code === 0 ? 'done' : 'failed', exitCode: code ?? (signal ? 128 : 1), finishedAt: new Date().toISOString() }));
      if (r) this.onChange('run', this.strip(r));
      this.onChange('agent', this.get(a.id));
    });
    return this.strip(run);
  }
  cancel(runId) { const c = this.procs.get(runId); if (c) c.kill('SIGTERM'); return Boolean(c); }

  // Fire each enabled agent at most once per matching minute.
  tick(now = new Date()) {
    const stamp = [now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), now.getMinutes()].join('-');
    const fired = [];
    for (const a of this.raw()) {
      if (!a.enabled || !a.cron) continue;
      let c; try { c = parseCron(a.cron); } catch { continue; }
      if (!matches(c, now) || this.fired.get(a.id) === stamp) continue;
      this.fired.set(a.id, stamp); fired.push(a.id);
      this.launch(a.id, 'schedule').catch((e) => {
        const run = { id: newId('run'), agentId: a.id, agentName: a.name, trigger: 'schedule', startedAt: now.toISOString(), finishedAt: now.toISOString(), status: 'failed', exitCode: 1, cwd: a.cwd, worktree: null, command: '', output: `[bridge] could not launch: ${e.message}\n`, reviewed: false };
        this.store.update('runs', [], (l) => [...l, run]); this.onChange('run', this.strip(run));
      });
    }
    return fired;
  }
  start() { if (!this.timer) { this.timer = setInterval(() => this.tick(), 20_000); this.timer.unref?.(); } }
  stop() { clearInterval(this.timer); this.timer = null; for (const c of this.procs.values()) c.kill('SIGTERM'); }
}
