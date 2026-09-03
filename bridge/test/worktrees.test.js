import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';
import { createWorktree, removeWorktree, listWorktrees, repoRoot, slug, status } from '../server/worktrees.js';

function mkRepo() {
  const dir = mkdtempSync(`${tmpdir()}/bridge-repo-`);
  const g = (...a) => execFileSync('git', a, { cwd: dir, env: { ...process.env, GIT_AUTHOR_NAME: 't', GIT_AUTHOR_EMAIL: 't@t', GIT_COMMITTER_NAME: 't', GIT_COMMITTER_EMAIL: 't@t' } });
  g('init', '-q', '-b', 'main'); writeFileSync(`${dir}/a.txt`, 'a\n'); g('add', '.'); g('commit', '-q', '-m', 'init');
  return dir;
}

test('slug', () => { assert.equal(slug('Fix: the Login bug!!'), 'fix-the-login-bug'); assert.equal(slug('***'), 'task'); });

test('two agents on one task get distinct worktrees and branches off the same base', async () => {
  const repo = mkRepo();
  assert.equal(await repoRoot(repo), repo);
  assert.equal(await repoRoot(tmpdir()), null);
  const a = await createWorktree({ repoPath: repo, taskTitle: 'Add login', agentTag: 'claude-implementer' });
  const b = await createWorktree({ repoPath: repo, taskTitle: 'Add login', agentTag: 'codex-reviewer' });
  assert.notEqual(a.path, b.path); assert.notEqual(a.branch, b.branch);
  assert.match(a.branch, /^bridge\/add-login-claude-implementer-/);
  assert.equal(a.base, 'main'); assert.equal(b.base, 'main');
  const list = await listWorktrees(repo);
  assert.equal(list.length, 3);
  writeFileSync(`${a.path}/new.txt`, 'x');
  const st = await status(a.path);
  assert.equal(st.branch, a.branch); assert.equal(st.dirty, 1);
  // main checkout is untouched and .bridge/ is excluded from status
  assert.equal(execFileSync('git', ['status', '--porcelain'], { cwd: repo }).toString().trim(), '');
  await removeWorktree({ ...a, deleteBranch: true });
  assert.equal((await listWorktrees(repo)).length, 2);
});
