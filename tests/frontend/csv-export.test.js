'use strict';

/* ══════════════════════════════════════════════════════════════════════
   web/gf/export.js — GF.export._csv

   This is the highest-risk untested code in the frontend: it is the only
   place in the app that writes a file a human then opens in Excel or Google
   Sheets, and it carries a SECURITY control — the leading-=+-@ guard that
   stops a task title from becoming a formula in the recipient's spreadsheet.
   A task title is free text typed by any operator, so removing that one line
   turns "export the weekly report" into arbitrary-formula delivery
   (=cmd|'/c calc'!A0 style DDE payloads, or WEBSERVICE() exfiltration of the
   surrounding cells). Nothing else in the repo covered it.

   Both directions are pinned deliberately: the guard must fire on a hostile
   title AND must leave an ordinary title byte-identical. A "fix" that quoted
   every field would pass a one-directional test while silently corrupting
   every export.
   ════════════════════════════════════════════════════════════════════ */

const test = require('node:test');
const assert = require('node:assert/strict');
const { loadGF, captureDownloads, csvFields } = require('./helpers/gf-window.js');

const FILES = ['data.js', 'core.js', 'export.js'];

const WEEK = { weekNum: 31, label: 'Jul 27 – Aug 2' };
const USER = { name: 'Marko Petrov', roleLabel: 'QA Manager' };
const BASE_TASK = {
  id: 'T-1A2B3', title: 'Harvest room 3', dept: 'qc', status: 'working', pr: 'high',
  type: 'lab', ref: 'SOP-QC-014', due: '2026-08-01', tags: [], archived: false,
  days: [], owner: 'ana', notes: [],
};

// Run the real _csv over one task and hand back the produced text plus the
// parsed rows. `GF.dep` and `GF.PEOPLE` are the real lookups from
// data.js/core.js; only the download boundary is recorded (see the harness).
function exportOne(taskOverrides, weekOverrides) {
  const h = loadGF({ files: FILES });
  const downloads = captureDownloads(h.GF);
  h.GF.PEOPLE.ana = { name: 'Ana Nikolova', roleLabel: 'QC Manager' };
  const task = Object.assign({}, BASE_TASK, taskOverrides);
  const week = Object.assign({}, WEEK, weekOverrides);
  h.GF.export._csv('GrowFlow_report_W31_marko', week, [task], USER);
  h.close();

  assert.equal(downloads.length, 1, '_csv must produce exactly one download');
  const csv = downloads[0].content;
  const lines = csv.split('\n');
  return {
    csv,
    download: downloads[0],
    lines,
    meta: csvFields(lines[0]),
    // 0 meta, 1 user, 2 blank, 3 column header, 4 first data row
    header: lines[3],
    row: csvFields(lines[4]),
  };
}

// Column positions in the fixed header row _csv emits.
const COL = {
  id: 0, title: 1, department: 2, status: 3, priority: 4, type: 5, reference: 6,
  due: 7, tags: 8, archived: 9, days: 10, owner: 11, notes: 12,
};

test('CSV formula injection: a title starting with = is neutralised with a leading quote', () => {
  // The canonical Excel DDE payload. Note the guard prefixes a quote and does
  // NOT touch the payload's own apostrophes (only double quotes get doubled),
  // so the cell text is exactly one added quote in front of the original.
  const payload = "=cmd|' /c calc'!A0";
  const { row } = exportOne({ title: payload });

  assert.equal(row[COL.title], `"'${payload}"`);
  // The assertion that actually catches the guard being deleted: without the
  // prefix the cell would be `"=cmd|' /c calc'!A0"`, which Excel evaluates.
  assert.notEqual(row[COL.title], `"${payload}"`);
  assert.equal(row[COL.title].startsWith(`"'`), true,
    'the neutralising quote must be INSIDE the CSV quoting, or the field is a formula again');
});

test('CSV formula injection: every one of the four dangerous lead characters is neutralised', () => {
  // The guard is /^[=+\-@]/ — all four must fire, and the guard must apply to
  // whatever the title happens to be, not just to something that looks like a
  // formula. `-5 C` and `+1 pallet` are perfectly ordinary operator input that
  // Excel still coerces; being prefixed is the guard working, not a bug.
  for (const title of ['=SUM(A1)', '+1 pallet received', '-5 C in dry room', '@SOP-QC-014']) {
    const { row } = exportOne({ title });
    assert.equal(row[COL.title], `"'${title}"`, `title ${JSON.stringify(title)} must be prefixed`);
  }
});

test('CSV formula injection: the guard applies to every escaped field, not only the title', () => {
  // Reference codes, tags and progress notes are free text too. The reference
  // field goes through the same esc(), so it must be neutralised as well.
  const { row } = exportOne({ ref: '=HYPERLINK("http://x","click")', tags: ['=1+1'] });
  assert.equal(row[COL.reference], `"'=HYPERLINK(""http://x"",""click"")"`);
  assert.equal(row[COL.tags], `"'=1+1"`);
});

test('CSV formula injection: an ordinary title is NOT mangled', () => {
  // The other direction. A guard that over-fires corrupts every export, and
  // that failure is invisible in a test that only checks hostile input.
  const { row } = exportOne({ title: 'Harvest room 3' });
  assert.equal(row[COL.title], '"Harvest room 3"');
  assert.equal(row[COL.title].includes("'"), false);
});

test('CSV formula injection: =+-@ anywhere but position 0 is left alone', () => {
  // /^[=+\-@]/ is anchored. Mid-string operators are not formulas and must
  // survive untouched, or reference codes and ranges get silently rewritten.
  for (const title of ['Room 3 = ready', 'pH 5.8-6.2', 'batch A+B', 'qa@purely']) {
    const { row } = exportOne({ title });
    assert.equal(row[COL.title], `"${title}"`, `title ${JSON.stringify(title)} must be untouched`);
  }
});

test('CSV quoting: embedded double quotes are doubled', () => {
  // RFC 4180 escaping. Without the doubling a title containing a quote ends
  // the field early and shifts every following column by one.
  const { row } = exportOne({ title: 'Room "A" swab' });
  assert.equal(row[COL.title], '"Room ""A"" swab"');
});

test('CSV quoting: a quote-and-formula title gets both treatments, prefix first', () => {
  // Order matters: the guard prepends the quote BEFORE the field is wrapped
  // and its double quotes are doubled, so the neutraliser can never itself be
  // doubled away.
  const { row } = exportOne({ title: '="a"&"b"' });
  assert.equal(row[COL.title], `"'=""a""&""b"""`);
});

test('CSV quoting: an embedded newline stays inside its quoted field', () => {
  // esc() does not strip newlines — the quoting is the only thing keeping a
  // multi-line title from becoming extra CSV rows.
  const { csv } = exportOne({ title: 'line one\nline two' });
  assert.equal(csv.includes('"line one\nline two"'), true);
  // Four structural lines + the two physical lines of the record + trailing.
  assert.equal(csv.split('\n').length, 7);
});

test('CSV starts with a UTF-8 BOM', () => {
  // Excel on Windows reads a BOM-less UTF-8 CSV as the legacy code page and
  // renders every Macedonian department name as mojibake. The BOM is the fix,
  // and it must be the very first code unit — even one character in front of
  // it (a stray header, a newline) defeats it.
  const { csv } = exportOne({});
  assert.equal(csv.charCodeAt(0), 0xFEFF);
  assert.equal(csv.startsWith('\uFEFF"'), true);
});

test('CSV meta rows carry the week and the exporting user', () => {
  const { meta, lines } = exportOne({}, { weekNum: 31, label: 'Jul 27 – Aug 2' });
  assert.equal(meta[0], '\uFEFF"GrowFlow Export"');
  assert.equal(meta[1], '"W31"');
  assert.equal(meta[2], '"Jul 27 – Aug 2"');
  // The 4th meta cell is new Date().toLocaleDateString(), whose format follows
  // the host ICU default locale, so only its presence is pinned here — the
  // exact rendering is not this module's contract.
  assert.match(meta[3], /^"[^"]+"$/);
  assert.equal(lines[1], '"User","Marko Petrov","QA Manager"');
  assert.equal(lines[2], '', 'a blank line separates the meta block from the table');
});

test('CSV column header is the exact 13-column contract', () => {
  // Anyone consuming these exports (or the auditors who receive them) keys off
  // this order; the data rows below are positional with no per-field labels.
  const { header, row } = exportOne({});
  assert.equal(header,
    'ID,Title,Department,Status,Priority,Type,Reference,Due Date,Tags,Archived,Days,Owner,Progress Notes');
  assert.equal(row.length, 13);
  assert.equal(header.split(',').length, row.length);
});

test('CSV data row resolves department and owner through the real GF lookups', () => {
  const { row } = exportOne({ dept: 'qc', owner: 'ana' });
  assert.equal(row[COL.department], '"Quality Control"');  // GF.dep('qc').name
  assert.equal(row[COL.owner], '"Ana Nikolova"');          // GF.PEOPLE.ana.name
});

test('CSV data row: an unknown owner id becomes an empty field, not "undefined"', () => {
  // esc(GF.PEOPLE[t.owner]?.name) — the optional chaining is what keeps a
  // deleted or not-yet-loaded person from printing the string "undefined".
  const { row } = exportOne({ owner: 'nobody' });
  assert.equal(row[COL.owner], '""');
});

test('CSV data row: an unknown department falls back to the first department', () => {
  // GF.dep() ends in `|| GF.DEPTS[0]`, so a stale dept id never throws — it
  // silently mislabels the row as Cloning & Nursery. Pinned as the shipped
  // behaviour so a change to that fallback is visible.
  const { row } = exportOne({ dept: 'no-such-dept' });
  assert.equal(row[COL.department], '"Cloning & Nursery"');
});

test('CSV data row: status, priority and archived are written UNQUOTED and unescaped', () => {
  // These three interpolate raw, bypassing esc() entirely. They are backend
  // enums today (and 'Y'/'N'), so nothing hostile can reach them — but that is
  // an invariant of the caller, not of this function, and it is exactly the
  // asymmetry a future contributor would not expect. Pinned so a change to
  // either side is deliberate.
  const { row } = exportOne({ status: 'working', pr: 'high', archived: false });
  assert.equal(row[COL.status], 'working');
  assert.equal(row[COL.priority], 'high');
  assert.equal(row[COL.archived], 'N');
  const archived = exportOne({ archived: true });
  assert.equal(archived.row[COL.archived], 'Y');
});

test('CSV data row: tags, days and progress notes are joined with their own separators', () => {
  const { row } = exportOne({
    tags: ['dry-room', 'urgent'],
    days: ['Mon', 'Tue', 'Fri'],
    notes: [{ d: '2026-07-28', n: 'started' }, { d: '2026-07-29', n: 'blocked on QC' }],
  });
  assert.equal(row[COL.tags], '"dry-room, urgent"');   // ', ' — comma+space
  assert.equal(row[COL.days], '"Mon,Tue,Fri"');        // ',' — bare comma
  assert.equal(row[COL.notes], '"2026-07-28: started | 2026-07-29: blocked on QC"');
});

test('CSV data row: absent tags/days/notes arrays produce empty fields, not a crash', () => {
  const { row } = exportOne({ tags: undefined, days: undefined, notes: undefined, ref: undefined, due: undefined });
  assert.equal(row[COL.tags], '""');
  assert.equal(row[COL.days], '""');
  assert.equal(row[COL.notes], '""');
  assert.equal(row[COL.reference], '""');
  assert.equal(row[COL.due], '""');
});

test('CSV escaping coerces falsy values to empty — including the number 0', () => {
  // esc() is `String(s || '')`, not the `s == null` guard GF.esc uses, so a
  // legitimate 0 exports as an empty cell. No live caller can currently pass 0
  // (ids are 'T-…' strings, weekNum is 1-based), so this is a latent trap
  // rather than a live bug — pinned here so the divergence from GF.esc is on
  // the record and cannot regress into a real data loss unnoticed.
  const h = loadGF({ files: FILES });
  const downloads = captureDownloads(h.GF);
  h.GF.export._csv('b', { weekNum: 0, label: '' }, [], USER);
  h.close();
  const meta = csvFields(downloads[0].content.split('\n')[0]);
  assert.equal(meta[1], '"W0"', 'string concatenation happens before esc(), so W0 survives');
  assert.equal(meta[2], '""', 'an empty label is indistinguishable from a missing one');
});

test('CSV filename and MIME type', () => {
  const { download } = exportOne({});
  assert.equal(download.name, 'GrowFlow_report_W31_marko.csv');
  assert.equal(download.mime, 'text/csv');
});

test('every exported task becomes exactly one record, in order', () => {
  const h = loadGF({ files: FILES });
  const downloads = captureDownloads(h.GF);
  const tasks = ['T-1', 'T-2', 'T-3'].map((id, i) =>
    Object.assign({}, BASE_TASK, { id, title: `task ${i}`, owner: 'nobody' }));
  h.GF.export._csv('b', WEEK, tasks, USER);
  h.close();
  const lines = downloads[0].content.split('\n');
  assert.equal(lines.length, 4 + tasks.length + 1);  // meta, user, blank, header, rows, trailing ''
  assert.deepEqual(lines.slice(4, 7).map(l => csvFields(l)[COL.id]), ['"T-1"', '"T-2"', '"T-3"']);
});

/* ── GF.export._json ──────────────────────────────────────────────────
   Same download path, no escaping to get wrong (JSON.stringify handles it),
   but the completion-rate arithmetic is its own hazard: a week with no tasks
   must not divide by zero. */

test('JSON export: telemetry rate rounds, and an empty week yields 0 not NaN', () => {
  const h = loadGF({ files: FILES });
  const downloads = captureDownloads(h.GF);

  h.GF.export._json('b', WEEK, [], USER);
  const empty = JSON.parse(downloads[0].content);
  assert.deepEqual(empty.telemetry, { total: 0, done: 0, rate: 0 });

  const three = ['done', 'done', 'working'].map((status, i) =>
    Object.assign({}, BASE_TASK, { id: `T-${i}`, status }));
  h.GF.export._json('b', WEEK, three, USER);
  const filled = JSON.parse(downloads[1].content);
  assert.deepEqual(filled.telemetry, { total: 3, done: 2, rate: 67 });  // 66.66 -> 67
  h.close();
});

test('JSON export: hostile text needs no neutralising and gets none', () => {
  // The formula guard is a spreadsheet concern only. JSON consumers do not
  // evaluate cells, so the title must round-trip byte-exact — a copy of the
  // CSV guard here would corrupt data for no benefit.
  const h = loadGF({ files: FILES });
  const downloads = captureDownloads(h.GF);
  const title = "=cmd|' /c calc'!A0";
  h.GF.export._json('b', WEEK, [Object.assign({}, BASE_TASK, { title })], USER);
  h.close();
  const parsed = JSON.parse(downloads[0].content);
  assert.equal(parsed.tasks[0].title, title);
  assert.equal(parsed.version, '1.0');
  assert.equal(downloads[0].mime, 'application/json');
  assert.equal(downloads[0].name, 'b.json');
});
