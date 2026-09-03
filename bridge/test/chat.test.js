import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, chmodSync, existsSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';
import { Store } from '../server/store.js';
import { Vault } from '../server/vault.js';
import { ChatService } from '../server/chat.js';

// A fake `claude` that records its argv and cwd and answers like the real
// `--output-format json` does, so the CLI engine is tested end to end without
// a network or a login.
const dir = mkdtempSync(`${tmpdir()}/bridge-chat-`);
const fake = join(dir, 'claude');
writeFileSync(fake, `#!/bin/sh
printf '%s\\n' "$@" > "$PWD/argv.txt"
ls -A "$PWD" | grep -v -e argv.txt -e listing.txt > "$PWD/listing.txt"
echo '{"type":"result","is_error":false,"result":"pong from fake","session_id":"sess-123","total_cost_usd":0.001,"modelUsage":{"claude-opus-5":{}},"usage":{"input_tokens":5,"output_tokens":2},"stop_reason":"end_turn"}'
`);
chmodSync(fake, 0o755);

const store = new Store(join(dir, 'data'));
const vault = new Vault(store, randomBytes(32));
const chat = new ChatService({ store, vault, dataDir: join(dir, 'data'), claudeBin: fake });

test('threads are created, titled from the first message, and listed without bodies', async () => {
  const t = chat.create({ engine: 'claude-cli' });
  assert.equal(t.messages.length, 0);
  const { assistant, thread } = await chat.send(t.id, { text: 'hello there, what is 2+2?' });
  assert.equal(assistant.text, 'pong from fake'); assert.equal(assistant.error, null); assert.equal(assistant.cost, 0.001);
  assert.equal(thread.title, 'hello there, what is 2+2?'); assert.equal(thread.claudeSessionId, 'sess-123');
  assert.equal(chat.list()[0].messageCount, 2);
  assert.ok(!('messages' in chat.list()[0]));
});

test('the CLI engine runs in an empty sandbox with every tool disallowed and resumes the session', async () => {
  const t = chat.create({ engine: 'claude-cli' });
  await chat.send(t.id, { text: 'first' });
  const sandbox = join(dir, 'data', 'chat-sandbox', t.id);
  const argv = (await import('node:fs')).readFileSync(join(sandbox, 'argv.txt'), 'utf8').split('\n');
  assert.equal(argv[0], '-p'); assert.ok(argv.includes('--disallowedTools')); assert.match(argv[argv.indexOf('--disallowedTools') + 1], /Bash,Edit,Write,Read/);
  assert.ok(!argv.includes('--resume'));
  assert.equal((await import('node:fs')).readFileSync(join(sandbox, 'listing.txt'), 'utf8').trim(), ''); // nothing to look at
  await chat.send(t.id, { text: 'second', attachments: [{ name: 'notes.txt', type: 'text/plain', data: Buffer.from('alpha beta').toString('base64') }] });
  const argv2 = (await import('node:fs')).readFileSync(join(sandbox, 'argv.txt'), 'utf8');
  assert.match(argv2, /--resume\nsess-123/); assert.match(argv2, /<file name="notes.txt">\nalpha beta/);
  chat.remove(t.id);
  assert.equal(existsSync(sandbox), false);
});

test('images are refused on the CLI engine; the API engine without a key fails cleanly into the thread', async () => {
  const t = chat.create({ engine: 'claude-cli' });
  const r = await chat.send(t.id, { text: 'look', attachments: [{ name: 'a.png', type: 'image/png', data: 'AAAA' }] });
  assert.match(r.assistant.error, /API engine/);
  delete process.env.ANTHROPIC_API_KEY;
  const t2 = chat.create({ engine: 'api' });
  const r2 = await chat.send(t2.id, { text: 'hi' });
  assert.match(r2.assistant.error, /no API key/);
  assert.equal(chat.get(t2.id).messages.length, 2);
  await assert.rejects(chat.send(t2.id, { text: '   ' }), /empty/);
  assert.throws(() => chat.create({ engine: 'magic' }), /engine/);
});

test('API engine builds image, pdf and text blocks', () => {
  const blocks = chat.blocksFor('q', [{ name: 'i.png', type: 'image/png', data: 'AAAA' }, { name: 'd.pdf', type: 'application/pdf', data: 'BBBB' }, { name: 't.md', type: 'text/markdown', data: Buffer.from('# hi').toString('base64') }]);
  assert.deepEqual(blocks.map((b) => b.type), ['image', 'document', 'text', 'text']);
  assert.match(blocks[2].text, /<file name="t.md">\n# hi/);
  assert.equal(blocks[3].text, 'q');
});
