// Chat: threads that are not tied to a project. Two engines, both sandboxed:
//   api        — Anthropic Messages API with a key from the vault (or the
//                server's ANTHROPIC_API_KEY). No tools are offered, so the model
//                cannot read or write anything.
//   claude-cli — `claude -p` run inside an EMPTY per-thread directory with every
//                tool disallowed: it rides the operator's subscription login but
//                has nothing to look at and nothing it can call.
// Either way the engine cannot pretend it is inside your codebase; the system
// prompt says so and the sandbox makes it true.
import Anthropic from '@anthropic-ai/sdk';
import { spawn } from 'node:child_process';
import { mkdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { newId } from './store.js';
import { which } from './providers.js';

export const ENGINES = ['api', 'claude-cli'];
export const DEFAULT_MODEL = 'claude-opus-5';
const CLI_TOOLS_OFF = 'Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch,Agent,NotebookEdit,Skill,TodoWrite,KillShell,BashOutput';
export const SYSTEM = 'You are Bridge Chat: a conversation, not a repository. You have no tools, no filesystem and no access to any codebase or project. Anything you know about the user\'s files is only what they paste or attach here. Never claim to have run code, read a repo or changed a file. Answer directly and keep the thread useful.';
const MAX_TEXT_ATTACH = 400 * 1024;

export class ChatService {
  constructor({ store, vault, dataDir, onChange = () => {}, claudeBin = null }) {
    this.store = store; this.vault = vault; this.onChange = onChange; this.claudeBin = claudeBin;
    this.sandboxRoot = join(dataDir, 'chat-sandbox');
    mkdirSync(this.sandboxRoot, { recursive: true, mode: 0o700 });
  }
  list() { return this.store.read('threads', []).map(({ messages, ...t }) => ({ ...t, messageCount: messages.length, last: messages.at(-1)?.text?.slice(0, 120) || '' })); }
  get(id) { const t = this.store.read('threads', []).find((x) => x.id === id); if (!t) throw new Error(`thread ${id} not found`); return t; }
  create({ title = 'New thread', engine = 'api', model = DEFAULT_MODEL, credentialId = null, context = null } = {}) {
    if (!ENGINES.includes(engine)) throw new Error(`engine must be ${ENGINES.join(' or ')}`);
    const t = { id: newId('thr'), title, engine, model: model || DEFAULT_MODEL, credentialId, context, claudeSessionId: null, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), messages: [] };
    this.store.update('threads', [], (l) => [t, ...l]);
    return t;
  }
  update(id, patch) {
    if (patch.engine && !ENGINES.includes(patch.engine)) throw new Error('bad engine');
    let out;
    this.store.update('threads', [], (l) => l.map((t) => (t.id === id ? (out = { ...t, ...pick(patch, ['title', 'engine', 'model', 'credentialId']), updatedAt: new Date().toISOString() }) : t)));
    if (!out) throw new Error(`thread ${id} not found`);
    return out;
  }
  remove(id) { this.get(id); this.store.update('threads', [], (l) => l.filter((t) => t.id !== id)); rmSync(join(this.sandboxRoot, id), { recursive: true, force: true }); }
  append(id, msg) { let out; this.store.update('threads', [], (l) => l.map((t) => (t.id === id ? (out = { ...t, updatedAt: new Date().toISOString(), messages: [...t.messages, msg] }) : t))); return out; }

  // attachments: [{name, type, data(base64)}]
  async send(id, { text = '', attachments = [] } = {}) {
    const t = this.get(id);
    if (!text.trim() && !attachments.length) throw new Error('empty message');
    const user = { id: newId('msg'), role: 'user', ts: new Date().toISOString(), text, attachments: attachments.map((a) => ({ name: a.name, type: a.type, size: Buffer.from(a.data || '', 'base64').length })) };
    this.append(id, user);
    if (t.messages.length === 0 && text.trim()) this.update(id, { title: text.trim().slice(0, 60) });
    let reply;
    try { reply = t.engine === 'claude-cli' ? await this.viaCli(this.get(id), text, attachments) : await this.viaApi(this.get(id), text, attachments); }
    catch (e) { reply = { text: '', error: e.message }; }
    const assistant = { id: newId('msg'), role: 'assistant', ts: new Date().toISOString(), text: reply.text || '', error: reply.error || null, model: reply.model || null, usage: reply.usage || null, cost: reply.cost ?? null, stop: reply.stop || null };
    const thread = this.append(id, assistant);
    this.onChange('thread', { id, updatedAt: thread.updatedAt });
    return { user, assistant, thread: this.get(id) };
  }

  apiKey(t) {
    if (t.credentialId) return this.vault.reveal(t.credentialId).value;
    if (process.env.ANTHROPIC_API_KEY) return process.env.ANTHROPIC_API_KEY;
    throw new Error('no API key: pick a vault key for this thread, or switch the thread to the Claude CLI engine');
  }
  blocksFor(text, attachments) {
    const blocks = [];
    for (const a of attachments) {
      if (a.type?.startsWith('image/')) blocks.push({ type: 'image', source: { type: 'base64', media_type: a.type, data: a.data } });
      else if (a.type === 'application/pdf') blocks.push({ type: 'document', source: { type: 'base64', media_type: 'application/pdf', data: a.data }, title: a.name });
      else {
        const body = Buffer.from(a.data || '', 'base64');
        if (body.length > MAX_TEXT_ATTACH) throw new Error(`${a.name} is too large to inline (${body.length} bytes); attach it as a PDF or trim it`);
        blocks.push({ type: 'text', text: `<file name="${a.name}">\n${body.toString('utf8')}\n</file>` });
      }
    }
    if (text.trim() || !blocks.length) blocks.push({ type: 'text', text: text || '(attachment)' });
    return blocks;
  }
  async viaApi(t, text, attachments) {
    const client = new Anthropic({ apiKey: this.apiKey(t) });
    const history = t.messages.slice(0, -1).filter((m) => m.text && !m.error).map((m) => ({ role: m.role, content: m.text }));
    const res = await client.messages.create({ model: t.model || DEFAULT_MODEL, max_tokens: 16000, system: SYSTEM, messages: [...history, { role: 'user', content: this.blocksFor(text, attachments) }] });
    if (res.stop_reason === 'refusal') return { text: '', error: `The model declined this request${res.stop_details?.category ? ` (${res.stop_details.category})` : ''}.`, model: res.model };
    return { text: res.content.filter((b) => b.type === 'text').map((b) => b.text).join('\n'), model: res.model, usage: { input: res.usage.input_tokens, output: res.usage.output_tokens }, stop: res.stop_reason };
  }
  viaCli(t, text, attachments) {
    const bin = this.claudeBin || which('claude');
    if (!bin) throw new Error('claude CLI is not installed on this host');
    const dir = join(this.sandboxRoot, t.id);
    mkdirSync(dir, { recursive: true, mode: 0o700 });
    let prompt = text;
    for (const a of attachments) {
      if (a.type?.startsWith('image/') || a.type === 'application/pdf') throw new Error(`${a.name}: images and PDFs need the API engine; the CLI engine takes text files only`);
      const body = Buffer.from(a.data || '', 'base64');
      if (body.length > MAX_TEXT_ATTACH) throw new Error(`${a.name} is too large to inline`);
      prompt += `\n\n<file name="${a.name}">\n${body.toString('utf8')}\n</file>`;
    }
    const argv = ['-p', prompt, '--output-format', 'json', '--disallowedTools', CLI_TOOLS_OFF, '--append-system-prompt', SYSTEM,
      ...(t.model && t.model !== DEFAULT_MODEL ? ['--model', t.model] : []), ...(t.claudeSessionId ? ['--resume', t.claudeSessionId] : [])];
    const env = { ...process.env }; delete env.BRIDGE_TOKEN; delete env.BRIDGE_MASTER_KEY; delete env.ANTHROPIC_API_KEY; // subscription login only
    return new Promise((resolve, reject) => {
      const child = spawn(bin, argv, { cwd: dir, env, stdio: ['ignore', 'pipe', 'pipe'] });
      let out = '', err = '';
      child.stdout.on('data', (d) => { out += d; }); child.stderr.on('data', (d) => { err += d; });
      child.on('error', reject);
      child.on('close', (code) => {
        let j; try { j = JSON.parse(out); } catch { return reject(new Error((err || out || `claude exited ${code}`).trim().slice(0, 500))); }
        if (j.session_id) this.store.update('threads', [], (l) => l.map((x) => (x.id === t.id ? { ...x, claudeSessionId: j.session_id } : x)));
        if (j.is_error) return reject(new Error(String(j.result || 'claude reported an error').slice(0, 500)));
        resolve({ text: String(j.result || ''), model: j.modelUsage ? Object.keys(j.modelUsage)[0] : null, cost: j.total_cost_usd ?? null, usage: j.usage ? { input: j.usage.input_tokens, output: j.usage.output_tokens } : null, stop: j.stop_reason || null });
      });
    });
  }
}
function pick(o, keys) { const r = {}; for (const k of keys) if (k in o) r[k] = o[k]; return r; }
