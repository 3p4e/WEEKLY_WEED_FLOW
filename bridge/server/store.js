// Tiny durable JSON store: one file per collection, atomic replace on write.
// Deliberately not a database — the platform is single-operator and the data
// (tasks, layout, encrypted credentials) is a few kilobytes.
import { readFileSync, writeFileSync, renameSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

export class Store {
  constructor(dir) {
    this.dir = dir;
    mkdirSync(dir, { recursive: true, mode: 0o700 });
    this.cache = new Map();
  }
  file(name) { return join(this.dir, `${name}.json`); }
  read(name, fallback) {
    if (this.cache.has(name)) return this.cache.get(name);
    const f = this.file(name);
    let value = fallback;
    if (existsSync(f)) {
      try { value = JSON.parse(readFileSync(f, 'utf8')); }
      catch (e) { throw new Error(`store: ${f} is corrupt: ${e.message}`); }
    }
    this.cache.set(name, value);
    return value;
  }
  write(name, value) {
    const f = this.file(name);
    const tmp = `${f}.${process.pid}.tmp`;
    writeFileSync(tmp, JSON.stringify(value, null, 2), { mode: 0o600 });
    renameSync(tmp, f);
    this.cache.set(name, value);
    return value;
  }
  update(name, fallback, fn) {
    const current = this.read(name, fallback);
    const next = fn(current) ?? current;
    return this.write(name, next);
  }
}

export function newId(prefix) {
  const t = Date.now().toString(36);
  const r = Math.random().toString(36).slice(2, 8);
  return `${prefix}_${t}${r}`;
}
