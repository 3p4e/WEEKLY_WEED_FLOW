import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PROVIDERS, getProvider, buildEnv, which, detect } from '../server/providers.js';

test('subscription mode strips the vendor key; key mode injects it; workspace secrets never leak', () => {
  process.env.ANTHROPIC_API_KEY = 'from-server-env';
  process.env.BRIDGE_TOKEN = 'tok'; process.env.BRIDGE_MASTER_KEY = 'mk';
  const claude = getProvider('claude');
  const sub = buildEnv(claude, 'subscription', null);
  assert.equal('ANTHROPIC_API_KEY' in sub, false);
  const keyed = buildEnv(claude, 'key', { envVar: 'ANTHROPIC_API_KEY', value: 'sk-vault' });
  assert.equal(keyed.ANTHROPIC_API_KEY, 'sk-vault');
  const inh = buildEnv(claude, 'inherit', null);
  assert.equal(inh.ANTHROPIC_API_KEY, 'from-server-env');
  for (const e of [sub, keyed, inh]) { assert.equal('BRIDGE_TOKEN' in e, false); assert.equal('BRIDGE_MASTER_KEY' in e, false); }
  assert.throws(() => buildEnv(claude, 'key', null), /credential/);
  assert.throws(() => buildEnv(claude, 'weird', null), /auth mode/);
});

test('moonshot providers reuse the claude binary but redirect it via ANTHROPIC_BASE_URL', () => {
  const dev = getProvider('moonshot');
  const plan = getProvider('moonshot-code');
  assert.equal(dev.bin, 'claude'); assert.equal(plan.bin, 'claude');
  assert.equal(dev.subscription, null); assert.equal(plan.subscription, null);
  const devEnv = buildEnv(dev, 'key', { envVar: 'ANTHROPIC_AUTH_TOKEN', value: 'dev-token' });
  assert.equal(devEnv.ANTHROPIC_BASE_URL, 'https://api.moonshot.ai/anthropic');
  assert.equal(devEnv.ANTHROPIC_AUTH_TOKEN, 'dev-token');
  const planEnv = buildEnv(plan, 'key', { envVar: 'ANTHROPIC_AUTH_TOKEN', value: 'plan-token' });
  assert.equal(planEnv.ANTHROPIC_BASE_URL, 'https://api.kimi.com/coding');
  assert.equal(planEnv.ANTHROPIC_AUTH_TOKEN, 'plan-token');
});

test('argv seeds the CLI with the task prompt', () => {
  assert.deepEqual(getProvider('claude').argv('do x'), ['do x']);
  assert.deepEqual(getProvider('gemini').argv('do x'), ['-i', 'do x']);
  assert.deepEqual(getProvider('shell').argv('ignored'), []);
  assert.deepEqual(getProvider('claude').argv(null), []);
});

test('which + detect find executables on PATH', () => {
  assert.ok(which('sh'));
  assert.equal(which('definitely-not-a-binary-xyz'), null);
  const d = detect('/bin/sh');
  assert.equal(d.length, PROVIDERS.length);
  assert.equal(d.find((p) => p.id === 'shell').installed, true);
  assert.ok(d.every((p) => !('argv' in p)));
});
