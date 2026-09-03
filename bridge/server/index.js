import { createServer } from 'node:http';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as config from './config.js';
import { Store } from './store.js';
import { Vault } from './vault.js';
import { SessionManager } from './sessions.js';
import { TaskService } from './tasks.js';
import { AgentService } from './agents.js';
import { ChatService } from './chat.js';
import { createApi } from './api.js';

const here = dirname(fileURLToPath(import.meta.url));
const publicDir = join(here, '..', 'public');

const store = new Store(config.DATA_DIR);
const vault = new Vault(store, config.MASTER_KEY);
const sessions = new SessionManager({ maxSessions: config.MAX_SESSIONS, scrollback: config.SCROLLBACK_BYTES });
const tasks = new TaskService({ store, vault, sessions, shell: config.SHELL, projectsRoot: config.PROJECTS_ROOT });
const agents = new AgentService({ store, vault, shell: config.SHELL, projectsRoot: config.PROJECTS_ROOT });
const chat = new ChatService({ store, vault, dataDir: config.DATA_DIR });
const api = createApi({ config, store, vault, sessions, tasks, agents, chat, publicDir });

// Any run left "running" by a previous process is dead now.
store.update('runs', [], (l) => l.map((r) => (r.status === 'running' ? { ...r, status: 'failed', exitCode: -1, finishedAt: new Date().toISOString(), output: (r.output || '') + '\n[bridge] server restarted while this run was in progress\n' } : r)));
agents.start();

const server = createServer(api.handle);
server.on('upgrade', api.upgrade);
server.listen(config.PORT, config.HOST, () => {
  console.log(`[bridge] listening on http://${config.HOST}:${config.PORT}`);
  console.log(`[bridge] open http://${config.HOST}:${config.PORT}/?token=${config.TOKEN}`);
  console.log(`[bridge] data dir ${config.DATA_DIR}; projects root ${config.PROJECTS_ROOT}`);
  if (config.HOST !== '127.0.0.1' && config.HOST !== 'localhost') console.warn('[bridge] WARNING: bound to a non-loopback address. This app hands out shells — put it behind TLS and keep the token secret.');
});
for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => { console.log(`[bridge] ${sig}: shutting down`); agents.stop(); sessions.shutdown(); server.close(() => process.exit(0)); setTimeout(() => process.exit(0), 2000).unref(); });
}
