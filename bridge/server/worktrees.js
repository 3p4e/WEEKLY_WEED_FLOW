// Git worktree management. Every agent that works on a task in "isolated" mode
// gets its own worktree + branch under <repo>/.bridge/worktrees/, so two agents
// on the same task (or on different tasks in one repo) never write into each
// other's checkout. Merging back is a normal git operation the operator does.
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { join } from 'node:path';
import { mkdirSync, existsSync, appendFileSync, readFileSync } from 'node:fs';

const run = promisify(execFile);

export async function git(cwd, args) {
  const { stdout } = await run('git', args, { cwd, maxBuffer: 8 * 1024 * 1024 });
  return stdout.trim();
}

export async function repoRoot(path) {
  try { return await git(path, ['rev-parse', '--show-toplevel']); }
  catch { return null; }
}

export function slug(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40) || 'task';
}

function ensureIgnored(root) {
  // Keep worktrees out of the repo's own status without touching tracked files.
  const excl = join(root, '.git', 'info', 'exclude');
  try {
    const cur = existsSync(excl) ? readFileSync(excl, 'utf8') : '';
    if (!cur.includes('.bridge/')) appendFileSync(excl, '\n.bridge/\n');
  } catch { /* .git may be a file (this repo is itself a worktree) — harmless */ }
}

export async function createWorktree({ repoPath, taskTitle, agentTag, baseRef }) {
  const root = await repoRoot(repoPath);
  if (!root) throw new Error(`${repoPath} is not inside a git repository`);
  ensureIgnored(root);
  const dir = join(root, '.bridge', 'worktrees');
  mkdirSync(dir, { recursive: true });
  const name = `${slug(taskTitle)}-${slug(agentTag)}-${Date.now().toString(36).slice(-4)}`;
  const branch = `bridge/${name}`;
  const path = join(dir, name);
  const base = baseRef || (await git(root, ['rev-parse', '--abbrev-ref', 'HEAD']));
  await git(root, ['worktree', 'add', '-b', branch, path, base]);
  return { root, path, branch, base };
}

export async function removeWorktree({ root, path, branch, deleteBranch = false }) {
  await git(root, ['worktree', 'remove', '--force', path]);
  if (deleteBranch && branch) {
    try { await git(root, ['branch', '-D', branch]); } catch { /* already gone */ }
  }
}

export async function listWorktrees(repoPath) {
  const root = await repoRoot(repoPath);
  if (!root) return [];
  const out = await git(root, ['worktree', 'list', '--porcelain']);
  const items = [];
  let cur = null;
  for (const line of out.split('\n')) {
    if (line.startsWith('worktree ')) { cur = { path: line.slice(9) }; items.push(cur); }
    else if (cur && line.startsWith('branch ')) cur.branch = line.slice(7).replace('refs/heads/', '');
    else if (cur && line.startsWith('HEAD ')) cur.head = line.slice(5);
  }
  return items;
}

export async function status(path) {
  try {
    const [branch, porcelain, ahead] = await Promise.all([
      git(path, ['rev-parse', '--abbrev-ref', 'HEAD']),
      git(path, ['status', '--porcelain']),
      git(path, ['rev-list', '--count', '@{upstream}..HEAD']).catch(() => null),
    ]);
    return { branch, dirty: porcelain.split('\n').filter(Boolean).length, ahead: ahead === null ? null : Number(ahead) };
  } catch (e) { return { error: e.message }; }
}
