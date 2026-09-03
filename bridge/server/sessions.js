// PTY session manager. A session is one agent (or shell) process attached to a
// pseudo-terminal, with a server-side scrollback ring so any number of browser
// panes can attach/detach without losing output, and so a page reload does not
// kill the agent.
import pty from 'node-pty';
import { EventEmitter } from 'node:events';
import { newId } from './store.js';

export class Session extends EventEmitter {
  constructor(opts) {
    super();
    this.id = newId('sess');
    this.title = opts.title;
    this.providerId = opts.providerId;
    this.taskId = opts.taskId || null;
    this.role = opts.role || null;
    this.authMode = opts.authMode || 'inherit';
    this.credentialId = opts.credentialId || null;
    this.cwd = opts.cwd;
    this.worktree = opts.worktree || null;   // {root, path, branch, base} or null
    this.command = opts.command;
    this.argv = opts.argv;
    this.createdAt = new Date().toISOString();
    this.status = 'running';
    this.exitCode = null;
    this.maxScrollback = opts.scrollback;
    this.chunks = []; this.bytes = 0;
    this.clients = new Set();
    this.cols = 120; this.rows = 32;
    this.pty = pty.spawn(opts.command, opts.argv, {
      name: 'xterm-256color', cols: this.cols, rows: this.rows,
      cwd: opts.cwd, env: opts.env,
    });
    this.pid = this.pty.pid;
    this.pty.onData((d) => { this.push(d); this.emit('data', d); });
    this.pty.onExit(({ exitCode }) => {
      this.status = 'exited'; this.exitCode = exitCode; this.endedAt = new Date().toISOString();
      this.push(`\r\n\x1b[2m[bridge] process exited with code ${exitCode}\x1b[0m\r\n`);
      this.emit('exit', exitCode);
    });
  }
  push(d) {
    this.chunks.push(d); this.bytes += d.length;
    while (this.bytes > this.maxScrollback && this.chunks.length > 1) this.bytes -= this.chunks.shift().length;
  }
  snapshot() { return this.chunks.join(''); }
  write(d) { if (this.status === 'running') this.pty.write(d); }
  resize(cols, rows) {
    cols = Math.max(2, Math.min(500, cols | 0)); rows = Math.max(2, Math.min(200, rows | 0));
    this.cols = cols; this.rows = rows;
    if (this.status === 'running') { try { this.pty.resize(cols, rows); } catch { /* raced with exit */ } }
  }
  kill(signal = 'SIGTERM') { if (this.status === 'running') { try { this.pty.kill(signal); } catch { /* gone */ } } }
  toJSON() {
    const { pty: _p, chunks: _c, clients: _cl, ...rest } = this;
    return { ...rest, clientCount: this.clients.size, bytes: this.bytes };
  }
}

export class SessionManager extends EventEmitter {
  constructor({ maxSessions, scrollback }) {
    super();
    this.max = maxSessions; this.scrollback = scrollback;
    this.sessions = new Map();
  }
  list() { return [...this.sessions.values()].map((s) => s.toJSON()); }
  get(id) { const s = this.sessions.get(id); if (!s) throw new Error(`session ${id} not found`); return s; }
  running() { return [...this.sessions.values()].filter((s) => s.status === 'running').length; }
  spawn(opts) {
    if (this.running() >= this.max) throw new Error(`session limit reached (${this.max})`);
    const s = new Session({ ...opts, scrollback: this.scrollback });
    this.sessions.set(s.id, s);
    s.on('exit', () => this.emit('change', s.toJSON()));
    this.emit('change', s.toJSON());
    return s;
  }
  remove(id) {
    const s = this.get(id);
    s.kill('SIGKILL');
    this.sessions.delete(id);
    this.emit('removed', id);
    return s;
  }
  shutdown() { for (const s of this.sessions.values()) s.kill('SIGHUP'); }
}
