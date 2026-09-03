// Task board + agent launching. A task is the unit of work; any number of
// agents (sessions) can be launched on it, each in its own worktree
// ("isolated") or in the task's checkout directly ("shared"). A swarm is just
// several launches with role prompts on the same task.
import { join } from 'node:path';
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { newId } from './store.js';
import { getProvider, buildEnv } from './providers.js';
import { createWorktree, repoRoot, removeWorktree } from './worktrees.js';

export const STATUSES = ['backlog', 'in_progress', 'review', 'done'];

export const ROLES = {
  solo: 'You own this task end to end: plan briefly, implement, run the relevant tests, and summarise what you changed.',
  architect: 'You are the ARCHITECT. Do not write production code. Read the codebase, produce a concrete implementation plan with file-level steps and risks, and write it to the shared task notes file so the implementer can follow it.',
  implementer: 'You are the IMPLEMENTER. Follow the plan in the shared task notes if one exists (wait for it / re-read it if it is still empty), implement the change in this worktree, run tests, and record progress in the notes file.',
  reviewer: 'You are the REVIEWER. Do not implement the feature. Review the diff in this worktree and the sibling worktrees under ../ for correctness, security and test coverage; write findings to the shared task notes file.',
  tester: 'You are the TESTER. Write and run tests that pin down the intended behaviour of the task; report failures and gaps in the shared task notes file.',
};

export class TaskService {
  constructor({ store, vault, sessions, shell, projectsRoot }) {
    this.store = store; this.vault = vault; this.sessions = sessions;
    this.shell = shell; this.projectsRoot = projectsRoot;
    sessions.on('change', (s) => { if (s.status === 'exited') this.touch(s.taskId); });
  }
  list() { return this.store.read('tasks', []); }
  get(id) { const t = this.list().find((x) => x.id === id); if (!t) throw new Error(`task ${id} not found`); return t; }
  touch(taskId) {
    if (!taskId) return;
    this.store.update('tasks', [], (ts) => ts.map((t) => (t.id === taskId ? { ...t, updatedAt: new Date().toISOString() } : t)));
  }
  create({ title, description = '', repoPath, baseRef = null, status = 'backlog' }) {
    if (!title?.trim()) throw new Error('title is required');
    if (!STATUSES.includes(status)) throw new Error(`bad status ${status}`);
    const task = {
      id: newId('task'), title: title.trim(), description, status,
      repoPath: repoPath || this.projectsRoot, baseRef,
      createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), agents: [],
    };
    this.store.update('tasks', [], (ts) => [...ts, task]);
    return task;
  }
  update(id, patch) {
    const allowed = ['title', 'description', 'status', 'repoPath', 'baseRef'];
    if (patch.status && !STATUSES.includes(patch.status)) throw new Error(`bad status ${patch.status}`);
    let out;
    this.store.update('tasks', [], (ts) => ts.map((t) => {
      if (t.id !== id) return t;
      out = { ...t, updatedAt: new Date().toISOString() };
      for (const k of allowed) if (k in patch) out[k] = patch[k];
      return out;
    }));
    if (!out) throw new Error(`task ${id} not found`);
    return out;
  }
  async remove(id, { removeWorktrees = false } = {}) {
    const t = this.get(id);
    for (const a of t.agents) {
      try { this.sessions.remove(a.sessionId); } catch { /* already gone */ }
      if (removeWorktrees && a.worktree) { try { await removeWorktree({ ...a.worktree, deleteBranch: false }); } catch { /* ignore */ } }
    }
    this.store.update('tasks', [], (ts) => ts.filter((x) => x.id !== id));
  }

  // Shared notes file: one per task at <repo root>/.bridge/tasks/<id>.md. Every
  // agent on the task is told its absolute path, so agents in different
  // worktrees coordinate through it (plan → progress → review findings).
  notesPath(root, task) {
    const dir = join(root, '.bridge', 'tasks');
    mkdirSync(dir, { recursive: true });
    const file = join(dir, `${task.id}.md`);
    if (!existsSync(file)) {
      writeFileSync(file, `# ${task.title}\n\nStatus: ${task.status}\n\n## Description\n\n${task.description || '(none)'}\n\n## Plan\n\n## Progress\n\n## Review findings\n`);
    }
    return file;
  }

  buildPrompt(task, role, ctx) {
    const lines = [
      `Task: ${task.title}`,
      task.description ? `\n${task.description}\n` : '',
      `Role: ${ROLES[role] || ROLES.solo}`,
      `Working directory: ${ctx.cwd}${ctx.branch ? ` (git branch ${ctx.branch}, based on ${ctx.base})` : ''}.`,
      ctx.notes ? `Shared task notes (read first, append your progress, other agents on this task read it too): ${ctx.notes}` : '',
      ctx.siblings ? `Other agents are working on this same task in parallel: ${ctx.siblings}. Do not duplicate their work; coordinate through the notes file.` : '',
    ];
    return lines.filter(Boolean).join('\n');
  }

  async launch(taskId, { providerId, authMode = 'inherit', credentialId = null, role = 'solo', isolation = 'worktree', title } = {}) {
    const task = this.get(taskId);
    const provider = getProvider(providerId);
    if (!(role in ROLES)) throw new Error(`unknown role ${role}`);
    const root = await repoRoot(task.repoPath);
    let cwd = task.repoPath, worktree = null;
    if (isolation === 'worktree') {
      if (!root) throw new Error(`task repo ${task.repoPath} is not a git repository — use isolation "shared" or point the task at a repo`);
      worktree = await createWorktree({ repoPath: task.repoPath, taskTitle: task.title, agentTag: `${providerId}-${role}`, baseRef: task.baseRef });
      cwd = worktree.path;
    } else if (!existsSync(cwd)) {
      throw new Error(`directory ${cwd} does not exist`);
    }
    const notes = root ? this.notesPath(root, task) : null;
    const siblings = task.agents.filter((a) => this.sessions.sessions.get(a.sessionId)?.status === 'running')
      .map((a) => `${a.providerId}/${a.role}`).join(', ');
    const prompt = provider.id === 'shell' ? null
      : this.buildPrompt(task, role, { cwd, branch: worktree?.branch, base: worktree?.base, notes, siblings });
    const secret = authMode === 'key' ? this.vault.reveal(credentialId) : null;
    if (secret && provider.keyEnv && secret.envVar !== provider.keyEnv) {
      // Allowed (e.g. an OpenRouter key for OpenCode), but say so in the pane.
      console.warn(`[bridge] credential ${credentialId} sets ${secret.envVar}; ${provider.name} usually expects ${provider.keyEnv}`);
    }
    const env = buildEnv(provider, authMode, secret, { BRIDGE_TASK_ID: task.id, BRIDGE_TASK_NOTES: notes || '' });
    const command = provider.bin || this.shell;
    const argv = provider.argv(prompt);
    const session = this.sessions.spawn({
      title: title || `${provider.name} · ${role} · ${task.title}`,
      providerId, taskId: task.id, role, authMode, credentialId, cwd, worktree, command, argv, env,
    });
    const agent = { sessionId: session.id, providerId, role, isolation, worktree, launchedAt: session.createdAt };
    this.store.update('tasks', [], (ts) => ts.map((t) => (t.id === task.id
      ? { ...t, status: t.status === 'backlog' ? 'in_progress' : t.status, updatedAt: new Date().toISOString(), agents: [...t.agents, agent] }
      : t)));
    return { session: session.toJSON(), task: this.get(task.id) };
  }

  // Launch a team on one task. `plan` is [{providerId, role, authMode, credentialId}]
  // or omitted for the default architect / implementer / reviewer trio.
  async swarm(taskId, { plan, providerId, authMode = 'inherit', credentialId = null, isolation = 'worktree' } = {}) {
    const team = plan?.length ? plan : ['architect', 'implementer', 'reviewer'].map((role) => ({ role, providerId, authMode, credentialId }));
    const out = [];
    for (const member of team) {
      out.push(await this.launch(taskId, { ...member, providerId: member.providerId || providerId, isolation }));
    }
    return out;
  }

  // Standalone pane not bound to a task (plain shell or agent in a directory).
  async launchFree({ providerId = 'shell', cwd, authMode = 'inherit', credentialId = null, title, prompt = null }) {
    const provider = getProvider(providerId);
    cwd = cwd || this.projectsRoot;
    if (!existsSync(cwd)) throw new Error(`directory ${cwd} does not exist`);
    const secret = authMode === 'key' ? this.vault.reveal(credentialId) : null;
    const env = buildEnv(provider, authMode, secret);
    return this.sessions.spawn({
      title: title || `${provider.name} · ${cwd.split('/').pop()}`,
      providerId, authMode, credentialId, cwd, command: provider.bin || this.shell, argv: provider.argv(prompt), env,
    }).toJSON();
  }
}
