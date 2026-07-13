/* record-demos.cjs — scripted, video-recorded walkthroughs for the owner demo.
   Seeds a fresh org on the local e2e harness, creates the 7 department
   managers + CEO/COO/Owner via the real API, then drives each account through
   its story with Playwright video recording:
     · each manager: dept home → create a current-week task with dept fields
       → 2 subtasks → log work → plan a task for NEXT week
     · QC manager additionally compiles + approves + locks the weekly report
     · CEO/COO/Owner: executive report — status board, drill-down, AI toggle,
       deep link to source task, HTML export (owner)
   Videos land in ../../.demo-videos/<nn>-<account>.webm. Run:
     node record-demos.cjs   (harness on :8091 must be running)              */
const { chromium } = require('playwright-core');
const { execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const BASE = 'http://localhost:8091';
const OUT = path.join(__dirname, '..', '..', '.demo-videos');
const PW = 'Demo-2026-Mass!';
const SUF = Date.now().toString(36).slice(-4);
const EXEC_PATH = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

/* ── API helpers ─────────────────────────────────────────────────────── */
const api = async (method, p, body, tok) => {
  const r = await fetch(BASE + p, {
    method,
    headers: { 'Content-Type': 'application/json', ...(tok ? { Authorization: 'Bearer ' + tok } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await r.text();
  let data; try { data = JSON.parse(text); } catch { data = text; }
  if (!r.ok) throw new Error(`${method} ${p} -> ${r.status}: ${text.slice(0, 200)}`);
  return data;
};
const loginTok = async (u, p) => (await api('POST', '/auth/login', { email: u, password: p })).access_token;

/* ── The cast + made-up demo data ────────────────────────────────────── */
const DEPTS = [
  ['cultivation', 'Cultivation', 'Одгледување'], ['production', 'Production', 'Производство'],
  ['qc', 'Quality Control', 'Контрола на квалитет'], ['quality_assurance', 'Quality Assurance', 'Обезбедување квалитет'],
  ['logistics', 'Warehouse & Logistics', 'Магацин и логистика'], ['security', 'Security', 'Обезбедување'],
  ['tooling', 'Maintenance & Utilities', 'Одржување'],
];
const CAST = [
  { u: 'm.cultivation', role: 'CU_MGR', dept: 'cultivation', name: 'Maja Cvetkovska',
    task: { title: 'Defoliate Flower Room 2 — Wedding Crasher', attrs: { room: 'GR-F2', strain: 'Wedding Crasher', plant_count: '96' } },
    subs: ['Sanitize shears and collection bins', 'Log canopy density after defoliation'],
    next: { title: 'Transplant clones to veg — batch WC-26-08', attrs: { room: 'GR-V1', strain: 'Wedding Crasher' } } },
  { u: 'm.production', role: 'PR_MGR', dept: 'production', name: 'Petar Ristov',
    task: { title: 'Package batch P060112 — 1g pre-rolls', attrs: { batch_ref: 'P060112', process_step: 'Packaging' } },
    subs: ['Verify seal integrity on first 50 units', 'Reconcile label count vs batch record'],
    next: { title: 'Line changeover and cleaning verification', attrs: { batch_ref: 'P060118' } } },
  { u: 'm.qc', role: 'QC_MGR', dept: 'qc', name: 'Blagoj Nikolov',
    task: { title: 'Sample batch P060098 for micro panel', attrs: { sample_ref: 'S-2026-0713', batch_ref: 'P060098' } },
    subs: ['Label and log samples in the sample logbook', 'Arrange courier to the external lab'],
    next: { title: 'HPLC potency run — calibration first', attrs: { sample_ref: 'S-2026-0721' } },
    locksReport: true },
  { u: 'm.qa', role: 'QA_MGR', dept: 'quality_assurance', name: 'Ana Stojanova',
    task: { title: 'CAPA-2026-014 — label reconciliation deviation', attrs: { capa_ref: 'CAPA-2026-014', doc_ref: 'QASOP 031' } },
    subs: ['Root-cause analysis with production lead', 'Draft corrective action for sign-off'],
    next: { title: 'Annual review — Labeling & Label Control SOP', attrs: { doc_ref: 'QASOP 031' } } },
  { u: 'm.logistics', role: 'WH_MGR', dept: 'logistics', name: 'Goran Iliev',
    task: { title: 'Receive nutrient shipment — PO-778', attrs: { flow: 'in', batch_ref: 'PO-778' } },
    subs: ['Quarantine incoming pallets pending QC release', 'Update stock ledger and bin locations'],
    next: { title: 'Dispatch order to Skopje pharmacy — chain of custody', attrs: { flow: 'out' } } },
  { u: 'm.security', role: 'SE_MGR', dept: 'security', name: 'Nikola Trajkov',
    task: { title: 'Perimeter patrol audit — north fence', attrs: { area: 'North fence', incident_type: 'Patrol' } },
    subs: ['Photograph and log fence sensor states'],
    next: { title: 'Camera firmware updates — zone C', attrs: { area: 'Zone C' } } },
  { u: 'm.tooling', role: 'MU_MGR', dept: 'tooling', name: 'Igor Dimov',
    task: { title: 'Preventive maintenance — HVAC AHU-2', attrs: { equipment_ref: 'AHU-2', maintenance_type: 'Preventive' } },
    subs: ['Replace filters and log differential pressure', 'Test alarm relay after service'],
    next: { title: 'Calibrate scales — production line', attrs: { equipment_ref: 'SCL-01' } } },
  { u: 'ceo.demo', role: 'CEO', dept: null, name: 'Aleksandar Petrov' },
  { u: 'coo.demo', role: 'COO', dept: null, name: 'Elena Markova' },
  { u: 'owner.demo', role: 'OWNER', dept: null, name: 'The Owner' },
];

/* ── UI helpers ──────────────────────────────────────────────────────── */
const pause = (page, ms = 800) => page.waitForTimeout(ms);
const closeModals = async (page) => {
  for (let i = 0; i < 3 && await page.locator('.overlay.open').count(); i++) {
    await page.keyboard.press('Escape'); await page.waitForTimeout(350);
  }
};

async function uiLogin(page, username) {
  await page.route(/https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/, (r) => r.abort());
  await page.goto(BASE + '/');
  const stage = page.locator('#gf-leaf-stage');
  const user = page.locator('#wwf-u');
  await stage.click().catch(() => {});
  for (let i = 0; i < 20 && !(await user.isVisible().catch(() => false)); i++) {
    await stage.press('Enter').catch(() => {});
    await page.waitForTimeout(400);
  }
  await user.fill(username);
  await page.locator('#wwf-p').fill(PW);
  await pause(page, 500);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.locator('#wwf-login').waitFor({ state: 'hidden', timeout: 20000 });
  await pause(page, 1400);
}

async function fillAttrs(page, attrs) {
  for (const [k, v] of Object.entries(attrs || {})) {
    const el = page.locator('#attr-f-' + k);
    if (!(await el.count())) continue;
    const tag = await el.evaluate((e) => e.tagName);
    if (tag === 'SELECT') await el.selectOption(v).catch(() => {});
    else { await el.click(); await el.pressSequentially(String(v), { delay: 28 }); }
    await pause(page, 250);
  }
}

async function createTask(page, title, attrs) {
  await closeModals(page);
  await page.locator('#newtask-btn').click();
  await pause(page, 600);
  await page.locator('#add-title').click();
  await page.locator('#add-title').pressSequentially(title, { delay: 18 });
  await fillAttrs(page, attrs);
  await pause(page, 500);
  await page.getByRole('button', { name: /Create task|Креирај/ }).click();
  await pause(page, 1200);
}

async function managerStory(page, m) {
  await uiLogin(page, m.u);                       // lands on dept home
  await pause(page, 1600);                        // let the home panels breathe
  await createTask(page, m.task.title, m.task.attrs);

  // Board: expand the card, add the subtasks, log some work.
  await page.locator('.nav-item', { hasText: /My Week|Моја недела/ }).click();
  await pause(page, 900);
  const card = page.locator('.card', { has: page.locator('.card-title', { hasText: m.task.title }) }).first();
  await card.locator('.card-title').click();
  await pause(page, 800);
  for (const sub of m.subs) {
    await card.getByRole('button', { name: /Add subtask|Додади/ }).first().click();
    await pause(page, 500);
    await page.locator('#add-title').pressSequentially(sub, { delay: 16 });
    await pause(page, 300);
    await page.getByRole('button', { name: /Create task|Креирај/ }).click();
    await pause(page, 900);
  }
  // Quick work log with the new +½h chips.
  const logBtn = card.getByRole('button', { name: /Log work|Работа/ }).first();
  if (await logBtn.count()) {
    await logBtn.click(); await pause(page, 600);
    await page.getByRole('button', { name: '+½h' }).click(); await pause(page, 300);
    await page.getByRole('button', { name: '+1h' }).click(); await pause(page, 300);
    await page.locator('#wl-note').pressSequentially('Completed first pass, second pass tomorrow.', { delay: 14 });
    await pause(page, 400);
    await page.getByRole('button', { name: /Log work|Внеси/ }).last().click();
    await pause(page, 1100);        // the modal stays open showing the session list
    await closeModals(page);
  }
  // NEXT week: plan ahead.
  await closeModals(page);
  await page.locator('body').press('ArrowRight');
  await pause(page, 900);
  await createTask(page, m.next.title, m.next.attrs);
  await pause(page, 600);
  await page.locator('body').press('ArrowLeft');
  await pause(page, 800);

  if (m.locksReport) {                            // QC compiles + locks on camera
    page.on('dialog', (d) => d.accept());
    await closeModals(page);
    await page.locator('.nav-item', { hasText: /^Report|Извештај$/ }).first().click();
    await pause(page, 1200);
    const compile = page.getByRole('button', { name: /Compile document|Состави документ/ });
    if (await compile.count()) {
      await compile.click();
      await pause(page, 2500);
      const approveAll = page.getByRole('button', { name: /Approve all|Одобри ги/ });
      if (await approveAll.count()) { await approveAll.click(); await pause(page, 1500); }
      const lock = page.getByRole('button', { name: /Lock & submit|Заклучи/ });
      if (await lock.count()) { await lock.click(); await pause(page, 1800); }
    }
  }
  await pause(page, 800);
}

async function execStory(page, m, isOwner) {
  await uiLogin(page, m.u);                       // execs land on Exec Overview
  await pause(page, 2000);
  await page.evaluate(() => GF.setView('execreport'));
  await pause(page, 2200);                        // status board loads
  // Expand the first two department sections with content.
  const secs = page.locator('.xr-sec summary');
  const n = Math.min(await secs.count(), isOwner ? 3 : 2);
  for (let i = 0; i < n; i++) { await secs.nth(i).click(); await pause(page, 1100); }
  // Drill into a task, show notes + hours.
  const task = page.locator('.xr-task summary').first();
  if (await task.count()) { await task.click(); await pause(page, 1300); }
  // Human-narrative-only toggle.
  const ai = page.getByRole('button', { name: /AI shown|AI прикажано/ }).first();
  if (await ai.count()) { await ai.click(); await pause(page, 1200); await page.getByRole('button', { name: /AI hidden|AI скриено/ }).first().click(); await pause(page, 800); }
  if (isOwner) {
    // Deep link: open the cited task on the board, then come back.
    const jump = page.getByRole('button', { name: /Open in board|Отвори на табла/ }).first();
    if (await jump.count()) { await jump.click(); await pause(page, 1800); await page.evaluate(() => GF.setView('execreport')); await pause(page, 1500); }
    // Export the standalone interactive HTML.
    const dl = page.waitForEvent('download', { timeout: 15000 }).catch(() => null);
    const btn = page.getByRole('button', { name: /Interactive HTML|Интерактивен/ }).first();
    if (await btn.count()) { await btn.click(); const d = await dl; if (d) await d.saveAs(path.join(OUT, 'owner-export.html')); await pause(page, 1200); }
    // A peek at the new coordination tools.
    await page.evaluate(() => GF.setView('workload')); await pause(page, 1800);
    await page.evaluate(() => GF.setView('calendar')); await pause(page, 1800);
  }
  await pause(page, 800);
}

/* ── main ────────────────────────────────────────────────────────────── */
(async () => {
  for (const m of CAST) m.u = m.u + '.' + SUF;   // usernames are globally unique across runs

  fs.rmSync(OUT, { recursive: true, force: true }); fs.mkdirSync(OUT, { recursive: true });

  // 1) fresh org + admin
  const backendDir = path.join(__dirname, '..', '..', 'backend');
  const seed = JSON.parse(execFileSync(
    path.join(backendDir, '.venv', 'bin', 'python'),
    [path.join(backendDir, 'scripts', 'seed_e2e_org.py')],
    { env: { ...process.env,
      USERS_ADMIN_DATABASE_URL: 'postgresql://app_admin:testpw_admin@localhost:5432/wwf_users_test',
      TASKS_ADMIN_DATABASE_URL: 'postgresql://app_admin:testpw_admin@localhost:5432/wwf_tasks_test' },
      encoding: 'utf-8' }).trim().split('\n').pop());
  const admin = await loginTok(seed.username, seed.password);
  console.log('org seeded, admin ok');

  // 2) departments (cultivation exists from the seeder)
  const existing = await api('GET', '/departments', null, admin);
  const byCode = Object.fromEntries(existing.map((d) => [d.code, d.id]));
  for (const [code, name, mk] of DEPTS) {
    if (!byCode[code]) {
      const d = await api('POST', '/departments', { code, name, name_mk: mk }, admin);
      byCode[code] = d.id;
    }
  }
  console.log('departments:', Object.keys(byCode).join(','));

  // 3) accounts (10 creates — under the 20/window throttle)
  for (const m of CAST) {
    const r = await api('POST', '/auth/users', {
      username: m.u, full_name: m.name, role: m.role,
      department_id: m.dept ? byCode[m.dept] : null,
    }, admin);
    const tmp = (await api('POST', '/auth/login', { email: m.u, password: r.otp })).access_token;
    await api('POST', '/auth/change-password', { new_password: PW }, tmp);
    console.log('account ready:', m.u, m.role);
  }

  // 4) pre-compile draft documents for CU + PR + QA (+ org-wide as owner) so
  //    the executive status board shows locked/draft/missing variety.
  for (const u of ['m.cultivation', 'm.production', 'm.qa']) {
    const t = await loginTok(u, PW);
    await api('POST', '/reports/documents/compile', { kind: 'report' }, t).catch((e) => console.log('compile', u, e.message));
  }
  const ownerTok = await loginTok('owner.demo', PW);
  await api('POST', '/reports/documents/compile', { kind: 'report' }, ownerTok).catch((e) => console.log('compile org', e.message));
  console.log('draft documents compiled');

  // 5) record each account
  const browser = await chromium.launch({ executablePath: EXEC_PATH, args: ['--no-sandbox'] });
  let idx = 1;
  for (const m of CAST) {
    const label = String(idx).padStart(2, '0') + '-' + m.u.replace(/\./g, '-');
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      recordVideo: { dir: OUT, size: { width: 1440, height: 900 } },
      acceptDownloads: true,
    });
    const page = await ctx.newPage();
    try {
      if (m.dept) await managerStory(page, m);
      else await execStory(page, m, m.role === 'OWNER');
      console.log('recorded:', m.u);
    } catch (e) {
      console.log('STORY ERROR', m.u, e.message.slice(0, 200));
      await page.screenshot({ path: path.join(OUT, label + '-error.png') }).catch(() => {});
    }
    const video = page.video();
    await ctx.close();
    if (video) {
      const p = await video.path();
      fs.renameSync(p, path.join(OUT, label + '.webm'));
    }
    idx++;
  }
  await browser.close();
  console.log('DONE. videos in', OUT);
})();
