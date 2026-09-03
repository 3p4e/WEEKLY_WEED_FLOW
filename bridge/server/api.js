// HTTP JSON API + static files + WebSocket endpoints, on node:http and `ws`.
// Every request must carry the bearer token (Authorization header, or ?token=
// for WebSocket upgrades where headers are not controllable).
import { readFile, stat } from 'node:fs/promises';
import { join, normalize, extname } from 'node:path';
import { timingSafeEqual } from 'node:crypto';
import { WebSocketServer } from 'ws';
import { detect } from './providers.js';
import { STATUSES, ROLES } from './tasks.js';
import { PERMISSIONS } from './agents.js';
import { ENGINES, DEFAULT_MODEL } from './chat.js';
import { PRESETS, nextRun } from './cron.js';
import { listWorktrees, status as wtStatus } from './worktrees.js';

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.map': 'application/json', '.webmanifest': 'application/manifest+json' };
const BODY_LIMIT = 1e6, BIG_BODY_LIMIT = 40e6;

export function tokenOk(given, expected) {
  if (typeof given !== 'string' || !given) return false;
  const a = Buffer.from(given), b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}
function send(res, code, body, headers = {}) {
  const data = typeof body === 'string' ? body : JSON.stringify(body);
  res.writeHead(code, { 'content-type': typeof body === 'string' ? 'text/plain; charset=utf-8' : 'application/json', 'cache-control': 'no-store', ...headers });
  res.end(data);
}
async function readJson(req, limit = BODY_LIMIT) {
  const chunks = []; let size = 0;
  for await (const c of req) { size += c.length; if (size > limit) throw Object.assign(new Error('body too large'), { status: 413 }); chunks.push(c); }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

export function createApi({ config, store, vault, sessions, tasks, agents, chat, publicDir }) {
  const routes = [];
  const route = (method, pattern, handler) => routes.push({ method, re: new RegExp(`^${pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)')}/?$`), handler });

  // ---- status / providers
  route('GET', '/api/status', () => ({
    version: '0.2.0', host: config.HOST, port: config.PORT, projectsRoot: config.PROJECTS_ROOT, maxSessions: config.MAX_SESSIONS,
    providers: detect(config.SHELL), statuses: STATUSES, roles: Object.keys(ROLES), permissions: PERMISSIONS, engines: ENGINES, defaultModel: DEFAULT_MODEL,
    cronPresets: PRESETS, hasServerKey: Boolean(process.env.ANTHROPIC_API_KEY),
    sessions: sessions.list().length, running: sessions.running(), agents: agents.list().length, threads: chat.list().length,
  }));

  // ---- credentials (never returns secret values)
  route('GET', '/api/credentials', () => vault.list());
  route('POST', '/api/credentials', async (req) => vault.add(await readJson(req)));
  route('DELETE', '/api/credentials/:id', (_r, p) => ({ removed: vault.remove(p.id) }));

  // ---- tasks (Code mode, workspace fold)
  route('GET', '/api/tasks', () => tasks.list());
  route('POST', '/api/tasks', async (req) => tasks.create(await readJson(req)));
  route('GET', '/api/tasks/:id', (_r, p) => tasks.get(p.id));
  route('PATCH', '/api/tasks/:id', async (req, p) => tasks.update(p.id, await readJson(req)));
  route('DELETE', '/api/tasks/:id', async (req, p, url) => { await tasks.remove(p.id, { removeWorktrees: url.searchParams.get('worktrees') === '1' }); return { removed: true }; });
  route('POST', '/api/tasks/:id/launch', async (req, p) => tasks.launch(p.id, await readJson(req)));
  route('POST', '/api/tasks/:id/swarm', async (req, p) => tasks.swarm(p.id, await readJson(req)));
  route('GET', '/api/tasks/:id/worktrees', async (_r, p) => { const t = tasks.get(p.id); const list = await listWorktrees(t.repoPath); return Promise.all(list.map(async (w) => ({ ...w, ...(await wtStatus(w.path)) }))); });

  // ---- terminal sessions (Code mode)
  route('GET', '/api/sessions', () => sessions.list());
  route('POST', '/api/sessions', async (req) => tasks.launchFree(await readJson(req)));
  route('GET', '/api/sessions/:id', (_r, p) => sessions.get(p.id).toJSON());
  route('POST', '/api/sessions/:id/input', async (req, p) => { const { data } = await readJson(req); sessions.get(p.id).write(String(data)); return { ok: true }; });
  route('POST', '/api/sessions/:id/kill', async (req, p) => { const { signal } = await readJson(req); sessions.get(p.id).kill(signal || 'SIGTERM'); return { ok: true }; });
  route('DELETE', '/api/sessions/:id', (_r, p) => { sessions.remove(p.id); return { removed: true }; });

  // ---- agents on routines (Agent mode)
  route('GET', '/api/agents', () => agents.list());
  route('POST', '/api/agents', async (req) => agents.create(await readJson(req)));
  route('GET', '/api/agents/:id', (_r, p) => agents.get(p.id));
  route('PATCH', '/api/agents/:id', async (req, p) => agents.update(p.id, await readJson(req)));
  route('DELETE', '/api/agents/:id', (_r, p) => { agents.remove(p.id); return { removed: true }; });
  route('POST', '/api/agents/:id/run', (_r, p) => agents.launch(p.id, 'manual'));
  route('GET', '/api/agents/:id/runs', (_r, p) => agents.runs(p.id));
  route('GET', '/api/runs', () => agents.runs());
  route('GET', '/api/runs/:id', (_r, p) => agents.run(p.id));
  route('POST', '/api/runs/:id/cancel', (_r, p) => ({ cancelled: agents.cancel(p.id) }));
  route('PATCH', '/api/runs/:id', async (req, p) => { const { reviewed } = await readJson(req); return agents.review(p.id, reviewed !== false); });
  route('POST', '/api/cron/preview', async (req) => { const { cron } = await readJson(req); try { const n = nextRun(cron); return { ok: true, next: n?.toISOString() ?? null }; } catch (e) { return { ok: false, error: e.message }; } });

  // ---- chat threads (Chat mode, and the Code-mode dock)
  route('GET', '/api/chat/threads', () => chat.list());
  route('POST', '/api/chat/threads', async (req) => chat.create(await readJson(req)));
  route('GET', '/api/chat/threads/:id', (_r, p) => chat.get(p.id));
  route('PATCH', '/api/chat/threads/:id', async (req, p) => chat.update(p.id, await readJson(req)));
  route('DELETE', '/api/chat/threads/:id', (_r, p) => { chat.remove(p.id); return { removed: true }; });
  route('POST', '/api/chat/threads/:id/messages', async (req, p) => chat.send(p.id, await readJson(req, BIG_BODY_LIMIT)));

  // ---- UI state (mode, panes, dock) persisted across reloads
  route('GET', '/api/layout', () => store.read('layout', { mode: 'code', panes: [], grid: 'grid' }));
  route('PUT', '/api/layout', async (req) => store.write('layout', await readJson(req)));

  async function serveStatic(req, res, pathname) {
    const rel = normalize(decodeURIComponent(pathname === '/' ? '/index.html' : pathname)).replace(/^(\.\.[/\\])+/, '');
    const file = join(publicDir, rel);
    if (!file.startsWith(publicDir)) return send(res, 403, 'forbidden');
    try {
      const st = await stat(file); if (!st.isFile()) throw new Error('not file');
      res.writeHead(200, { 'content-type': MIME[extname(file)] || 'application/octet-stream', 'cache-control': rel.includes('vendor') ? 'public, max-age=86400' : 'no-cache' });
      res.end(await readFile(file));
    } catch { send(res, 404, 'not found'); }
  }
  function authed(req, url) {
    const h = req.headers.authorization || '';
    return tokenOk(h.startsWith('Bearer ') ? h.slice(7) : url.searchParams.get('token'), config.TOKEN);
  }
  async function handle(req, res) {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    if (!url.pathname.startsWith('/api/')) return serveStatic(req, res, url.pathname);
    if (url.pathname === '/api/auth/check') return send(res, authed(req, url) ? 200 : 401, { ok: authed(req, url) });
    if (!authed(req, url)) return send(res, 401, { error: 'unauthorized' });
    for (const r of routes) {
      if (r.method !== req.method) continue;
      const m = r.re.exec(url.pathname); if (!m) continue;
      try { return send(res, 200, await r.handler(req, m.groups || {}, url)); }
      catch (e) { return send(res, e.status || 400, { error: e.message }); }
    }
    send(res, 404, { error: 'no such route' });
  }

  // ---- WebSockets: /ws/term/:id (terminal I/O) and /ws/events (state changes)
  const wss = new WebSocketServer({ noServer: true });
  const eventClients = new Set();
  const broadcast = (type, payload) => { const msg = JSON.stringify({ type, ...payload }); for (const c of eventClients) if (c.readyState === 1) c.send(msg); };
  sessions.on('change', (s) => broadcast('session', { session: s }));
  sessions.on('removed', (id) => broadcast('session_removed', { id }));
  agents.onChange = (type, payload) => broadcast(type, type === 'agent' ? { agent: payload } : type === 'run' ? { run: payload } : payload);
  chat.onChange = (type, payload) => broadcast(type, payload);

  function upgrade(req, socket, head) {
    const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    if (!authed(req, url)) { socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n'); socket.destroy(); return; }
    const term = /^\/ws\/term\/([^/]+)$/.exec(url.pathname);
    if (term) {
      let s; try { s = sessions.get(term[1]); } catch { socket.write('HTTP/1.1 404 Not Found\r\n\r\n'); socket.destroy(); return; }
      return wss.handleUpgrade(req, socket, head, (ws) => attachTerminal(ws, s));
    }
    if (url.pathname === '/ws/events') {
      return wss.handleUpgrade(req, socket, head, (ws) => { eventClients.add(ws); ws.on('close', () => eventClients.delete(ws)); ws.send(JSON.stringify({ type: 'hello', sessions: sessions.list(), tasks: tasks.list(), agents: agents.list() })); });
    }
    socket.write('HTTP/1.1 404 Not Found\r\n\r\n'); socket.destroy();
  }
  function attachTerminal(ws, s) {
    s.clients.add(ws);
    ws.send(JSON.stringify({ type: 'snapshot', data: s.snapshot(), session: s.toJSON() }));
    const onData = (d) => { if (ws.readyState === 1) ws.send(d); };
    const onExit = (code) => { if (ws.readyState === 1) ws.send(JSON.stringify({ type: 'exit', code })); };
    s.on('data', onData); s.on('exit', onExit);
    ws.on('message', (raw, isBinary) => {
      if (isBinary) return s.write(raw.toString('utf8'));
      const text = raw.toString('utf8');
      if (text[0] === '{') { try { const m = JSON.parse(text); if (m.type === 'input') return s.write(String(m.data)); if (m.type === 'resize') return s.resize(m.cols, m.rows); } catch { /* raw */ } }
      s.write(text);
    });
    ws.on('close', () => { s.clients.delete(ws); s.off('data', onData); s.off('exit', onExit); });
  }
  return { handle, upgrade, broadcast };
}
