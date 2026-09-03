import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { randomBytes } from 'node:crypto';
import { Store } from '../server/store.js';
import { Vault, encrypt, decrypt, mask } from '../server/vault.js';

const key = randomBytes(32);

test('encrypt/decrypt round-trips and detects tampering', () => {
  const blob = encrypt(key, 'sk-ant-secret-value');
  assert.equal(decrypt(key, blob), 'sk-ant-secret-value');
  const bad = { ...blob, ct: Buffer.from('x' + Buffer.from(blob.ct, 'base64').toString('binary').slice(1), 'binary').toString('base64') };
  assert.throws(() => decrypt(key, bad));
  assert.throws(() => decrypt(randomBytes(32), blob));
});

test('mask hides the body of the secret', () => {
  assert.equal(mask('sk-ant-api03-abcdefgh'), 'sk-a…efgh');
  assert.equal(mask('short'), '••••');
});

test('vault never lists plaintext, reveal returns it, remove works', () => {
  const store = new Store(mkdtempSync(`${tmpdir()}/bridge-vault-`));
  const vault = new Vault(store, key);
  const c = vault.add({ name: 'anthropic', envVar: 'ANTHROPIC_API_KEY', value: 'sk-ant-1234567890' });
  assert.ok(!('blob' in c));
  assert.equal(JSON.stringify(vault.list()).includes('sk-ant-1234567890'), false);
  assert.deepEqual(vault.reveal(c.id), { envVar: 'ANTHROPIC_API_KEY', value: 'sk-ant-1234567890' });
  assert.throws(() => vault.add({ name: 'x', envVar: 'lowercase', value: 'v' }), /envVar/);
  assert.equal(vault.remove(c.id), true);
  assert.equal(vault.remove(c.id), false);
  assert.throws(() => vault.reveal(c.id));
});

test('store survives a reload from disk', () => {
  const dir = mkdtempSync(`${tmpdir()}/bridge-store-`);
  new Store(dir).write('tasks', [{ id: 1 }]);
  assert.deepEqual(new Store(dir).read('tasks', []), [{ id: 1 }]);
});
