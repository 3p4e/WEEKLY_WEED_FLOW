// Runtime configuration. Everything is overridable by environment variable;
// secrets that are not supplied are generated once and persisted under the
// data directory with 0600 permissions, so a bare `npm start` is usable and a
// production deploy can pin them explicitly.
import { mkdirSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { randomBytes } from 'node:crypto';
import { homedir } from 'node:os';

const env = process.env;

export const DATA_DIR = resolve(env.BRIDGE_DATA_DIR || join(process.cwd(), 'data'));
mkdirSync(DATA_DIR, { recursive: true, mode: 0o700 });

function persistedSecret(envName, fileName, bytes) {
  if (env[envName]) return env[envName];
  const file = join(DATA_DIR, fileName);
  if (existsSync(file)) return readFileSync(file, 'utf8').trim();
  const value = randomBytes(bytes).toString('hex');
  writeFileSync(file, value + '\n', { mode: 0o600 });
  return value;
}

export const HOST = env.BRIDGE_HOST || '127.0.0.1';
export const PORT = Number(env.BRIDGE_PORT || 7788);
// Bearer token every HTTP and WebSocket request must carry. The app hands out
// interactive shells, so it must never run unauthenticated.
export const TOKEN = persistedSecret('BRIDGE_TOKEN', 'token', 24);
// 32-byte AES-256-GCM key for the credential vault.
export const MASTER_KEY = Buffer.from(persistedSecret('BRIDGE_MASTER_KEY', 'master.key', 32), 'hex');
if (MASTER_KEY.length !== 32) throw new Error('BRIDGE_MASTER_KEY must be 32 bytes hex (64 chars)');
// Where task worktrees are created when a task has no repo of its own.
export const PROJECTS_ROOT = resolve(env.BRIDGE_PROJECTS_ROOT || join(homedir(), 'projects'));
// Per-session scrollback kept server-side for late-joining browser tabs.
export const SCROLLBACK_BYTES = Number(env.BRIDGE_SCROLLBACK_BYTES || 256 * 1024);
export const MAX_SESSIONS = Number(env.BRIDGE_MAX_SESSIONS || 16);
export const SHELL = env.BRIDGE_SHELL || env.SHELL || '/bin/bash';
