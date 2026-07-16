// Headless screenshot capture for the GrowFlow Unified app.
// Usage: node scripts/screenshot.mjs <baseURL> <outDir>
// Drives the running SPA (Vite dev or built+served) through its key screens and
// saves PNGs. Used to produce the docs/screenshots referenced in the README.

import puppeteer from 'puppeteer';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const BASE = process.argv[2] || 'http://127.0.0.1:5173';
const OUT = process.argv[3] || 'docs/screenshots';
mkdirSync(OUT, { recursive: true });

const shots = [];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });
page.on('console', (m) => { if (m.type() === 'error') console.log('  [page error]', m.text()); });

async function snap(name) {
  await wait(450);
  const file = join(OUT, `${name}.png`);
  await page.screenshot({ path: file });
  shots.push(file);
  console.log('captured', file);
}

// Click a sidebar nav item by its visible label text.
async function nav(label) {
  await page.evaluate((lbl) => {
    const el = [...document.querySelectorAll('.nav-item, .mode-switch span, span')]
      .find((e) => e.textContent.trim() === lbl || e.textContent.trim().startsWith(lbl));
    if (el) el.click();
  }, label);
  await wait(400);
}

console.log('Loading', BASE);
await page.goto(BASE, { waitUntil: 'networkidle2', timeout: 30000 });
await wait(800);

// Production mode (default)
await snap('01-production-board');

// Switch to QC Lab
await nav('QC Lab');
await snap('02-qc-dashboard');

// Walk the QC nav items that exist
for (const [label, name] of [
  ['Samples', '03-qc-samples'],
  ['Specifications', '04-qc-specifications'],
  ['Stability', '05-qc-stability'],
  ['Water QC', '06-qc-water'],
  ['Transport', '07-qc-transport'],
  ['OOS Investigation', '08-qc-oos'],
  ['Genealogy', '09-qc-genealogy'],
  ['CAPA', '10-qc-capa'],
  ['Knowledge', '11-qc-knowledge'],
  ['Audit Trail', '12-qc-audit'],
]) {
  await nav(label);
  await snap(name);
}

await browser.close();
console.log(`\nDone — ${shots.length} screenshots in ${OUT}`);
