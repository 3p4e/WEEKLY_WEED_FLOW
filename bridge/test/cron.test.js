import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseCron, matches, nextRun } from '../server/cron.js';

test('presets and fields parse; bad input throws', () => {
  assert.equal(parseCron('@weekdays').src, '0 9 * * 1-5');
  assert.deepEqual([...parseCron('*/15 9-10 * * mon,fri').min], [0, 15, 30, 45]);
  assert.deepEqual([...parseCron('0 0 * * 7').dow], [0]);
  assert.throws(() => parseCron('61 * * * *'), /range/);
  assert.throws(() => parseCron('* * * *'), /5 fields/);
  assert.throws(() => parseCron('a b c d e'), /bad cron/);
});

test('matches and nextRun', () => {
  const c = parseCron('30 14 * * 1-5');
  assert.equal(matches(c, new Date(2026, 8, 3, 14, 30)), true);   // Thu
  assert.equal(matches(c, new Date(2026, 8, 5, 14, 30)), false);  // Sat
  assert.equal(matches(c, new Date(2026, 8, 3, 14, 31)), false);
  const n = nextRun('30 14 * * 1-5', new Date(2026, 8, 4, 15, 0)); // Fri 15:00 -> Mon 14:30
  assert.equal(n.getDay(), 1); assert.equal(n.getHours(), 14); assert.equal(n.getMinutes(), 30);
  assert.equal(nextRun('0 0 30 2 *', new Date(2026, 0, 1)), null); // Feb 30 never
});
