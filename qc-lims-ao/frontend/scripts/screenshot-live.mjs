// Live screenshot capture — drives the SPA served same-origin by FastAPI
// (which mounts frontend/dist) with a real login, so the QC screens render
// data fetched from the backend. Usage: node scripts/screenshot-live.mjs <baseURL> <outDir>
import puppeteer from 'puppeteer';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const BASE = process.argv[2] || 'http://127.0.0.1:8000';
const OUT = process.argv[3] || 'docs/screenshots';
const EMAIL = process.env.QC_EMAIL || 'elena@purelyplant.eu';
const PASS = process.env.QC_PASS || 'Password123!';
mkdirSync(OUT, { recursive: true });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  headless: 'new',
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

await page.goto(BASE, { waitUntil: 'networkidle2', timeout: 30000 });

// Log in via the API, store token + api base, then reload so the SPA boots authed.
const ok = await page.evaluate(async (email, password) => {
  const r = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) return false;
  const j = await r.json();
  localStorage.setItem('gf_token', j.access_token);
  localStorage.setItem('api_base', location.origin);
  localStorage.setItem('app_mode', 'qc');
  return true;
}, EMAIL, PASS);
console.log('login primed:', ok);

await page.reload({ waitUntil: 'networkidle2' });
await wait(1500); // let loadFromAPI populate live collections

async function nav(label) {
  await page.evaluate((lbl) => {
    const el = [...document.querySelectorAll('.nav-item, .mode-switch span, span')]
      .find((e) => e.textContent.trim() === lbl || e.textContent.trim().startsWith(lbl));
    if (el) el.click();
  }, label);
  await wait(500);
}
async function snap(name) {
  await wait(300);
  await page.screenshot({ path: join(OUT, `${name}.png`) });
  console.log('captured', name);
}

await snap('02-qc-dashboard');
for (const [label, name] of [
  ['Specifications', '04-qc-specifications'],
  ['Sample Requests', '13-qc-rqs'],
  ['Progressive Review', '14-qc-review'],
  ['Stability', '05-qc-stability'],
  ['Water QC', '06-qc-water'],
  ['Transport', '07-qc-transport'],
  ['CAPA', '10-qc-capa'],
  ['Genealogy', '09-qc-genealogy'],
  ['Knowledge', '11-qc-knowledge'],
  ['AI Audit', '15-qc-aiaudit'],
  ['Audit Trail', '12-qc-audit'],
]) {
  await nav(label);
  await snap(name);
}

await browser.close();
console.log('done');
