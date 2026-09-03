// Credential vault: outside API keys (Anthropic, OpenAI, Google, OpenRouter,
// anything) encrypted at rest with AES-256-GCM under the master key. Values are
// never returned to the browser — only a masked tail — and are decrypted solely
// to inject into the environment of an agent process at spawn time.
import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto';
import { newId } from './store.js';

const ALG = 'aes-256-gcm';

export function encrypt(key, plaintext) {
  const iv = randomBytes(12);
  const c = createCipheriv(ALG, key, iv);
  const ct = Buffer.concat([c.update(plaintext, 'utf8'), c.final()]);
  return { iv: iv.toString('base64'), ct: ct.toString('base64'), tag: c.getAuthTag().toString('base64') };
}

export function decrypt(key, blob) {
  const d = createDecipheriv(ALG, key, Buffer.from(blob.iv, 'base64'));
  d.setAuthTag(Buffer.from(blob.tag, 'base64'));
  return Buffer.concat([d.update(Buffer.from(blob.ct, 'base64')), d.final()]).toString('utf8');
}

export function mask(value) {
  if (!value) return '';
  if (value.length <= 8) return '••••';
  return `${value.slice(0, 4)}…${value.slice(-4)}`;
}

export class Vault {
  constructor(store, key) { this.store = store; this.key = key; }
  all() { return this.store.read('credentials', []); }
  list() {
    return this.all().map(({ blob, ...rest }) => rest);
  }
  add({ name, envVar, value, provider = null, note = '' }) {
    if (!name || !envVar || !value) throw new Error('name, envVar and value are required');
    if (!/^[A-Z][A-Z0-9_]*$/.test(envVar)) throw new Error('envVar must look like AN_ENV_VAR');
    const entry = {
      id: newId('cred'), name, envVar, provider, note,
      masked: mask(value), createdAt: new Date().toISOString(),
      blob: encrypt(this.key, value),
    };
    this.store.update('credentials', [], (list) => [...list, entry]);
    const { blob, ...safe } = entry;
    return safe;
  }
  remove(id) {
    let removed = false;
    this.store.update('credentials', [], (list) => list.filter((c) => (c.id === id ? (removed = true, false) : true)));
    return removed;
  }
  reveal(id) {
    const c = this.all().find((x) => x.id === id);
    if (!c) throw new Error(`credential ${id} not found`);
    return { envVar: c.envVar, value: decrypt(this.key, c.blob) };
  }
}
