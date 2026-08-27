/* record-workflow.cjs — ONE connected batch across every department, recorded
   with on-screen captions.

   A single parent task ("Batch WC-0426 · Wedding Crasher") is delegated as
   seven department stages (subtasks), each with its own checklist
   (sub-subtasks). The recorder drives:
     00  COO  — batch kickoff: shows the whole delegated tree, delegates one
                more coordination subtask live, leaves a coordination note
     01-07    — each department manager works their stage on camera: opens it,
                logs work with a note, creates a live sub-subtask, plans next
                week's follow-on; QC also compiles + locks the QC report
     08  COO  — operations review: status board + batch drill-down + hours
     09  CEO  — strategic summary: KPIs, week-over-week
     10  Owner— the whole picture: drill to source task, export interactive HTML
   Every clip carries a baked-in caption bar + a chapter lower-third so the
   viewer always knows who is on screen and what is happening.

   Videos land in ../../.demo-videos/<nn>-<name>.webm. Run with the local e2e
   harness up on :8091:  node record-workflow.cjs                              */
const { chromium } = require('playwright-core');
const { execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const { BATCH, STAGES } = require('./workflow-story.cjs');

const BASE = 'http://localhost:8091';
const OUT = path.join(__dirname, '..', '..', '.demo-videos');
const PW = 'Demo-2026-Mass!';
// EXEC_ONLY_SUF re-records just the three executive clips against an org that
// a previous full run already seeded (skips seeding + account creation).
const EXEC_ONLY = process.env.EXEC_ONLY_SUF || '';
const SUF = EXEC_ONLY || Date.now().toString(36).slice(-4);
const EXEC_PATH = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

/* ── week math (this Monday / next Monday, facility local) ─────────────── */
const mondayISO = (off = 0) => {
  const d = new Date();
  const dow = (d.getDay() + 6) % 7;          // 0 = Monday
  d.setDate(d.getDate() - dow + off * 7);
  return d.toISOString().slice(0, 10);
};
const WEEK = mondayISO(0);
const THU = (() => { const d = new Date(WEEK); d.setDate(d.getDate() + 3); return d.toISOString().slice(0, 10); })();

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

/* ── cast ─────────────────────────────────────────────────────────────── */
const DEPTS = [
  ['cultivation', 'Cultivation', 'Одгледување'], ['production', 'Production', 'Производство'],
  ['qc', 'Quality Control', 'Контрола на квалитет'], ['quality_assurance', 'Quality Assurance', 'Обезбедување квалитет'],
  ['logistics', 'Warehouse & Logistics', 'Магацин и логистика'], ['security', 'Security', 'Обезбедување'],
  ['tooling', 'Maintenance & Utilities', 'Одржување'],
];
const MGRS = {
  'm.cultivation': { role: 'CU_MGR', dept: 'cultivation', name: 'Maja Cvetkovska', tag: 'CULTIVATION' },
  'm.production':  { role: 'PR_MGR', dept: 'production', name: 'Petar Ristov', tag: 'PRODUCTION' },
  'm.qc':          { role: 'QC_MGR', dept: 'qc', name: 'Blagoj Nikolov', tag: 'QUALITY CONTROL' },
  'm.qa':          { role: 'QA_MGR', dept: 'quality_assurance', name: 'Ana Stojanova', tag: 'QUALITY ASSURANCE' },
  'm.logistics':   { role: 'WH_MGR', dept: 'logistics', name: 'Goran Iliev', tag: 'LOGISTICS' },
  'm.security':    { role: 'SE_MGR', dept: 'security', name: 'Nikola Trajkov', tag: 'SECURITY' },
  'm.tooling':     { role: 'MU_MGR', dept: 'tooling', name: 'Igor Dimov', tag: 'MAINTENANCE' },
};
const EXECS = [
  { u: 'coo.demo', role: 'COO', name: 'Elena Markova', tag: 'OPERATIONS (COO)' },
  { u: 'ceo.demo', role: 'CEO', name: 'Aleksandar Petrov', tag: 'CEO' },
  { u: 'owner.demo', role: 'OWNER', name: 'The Owner', tag: 'OWNER' },
];
const DEPT_NAME = Object.fromEntries(DEPTS.map(([c, n]) => [c, n]));

/* usernames unique per run; each manager also gets a display name for captions */
const uname = {}; // logical -> actual (suffixed)
for (const k of Object.keys(MGRS)) uname[k] = k + '.' + SUF;
for (const e of EXECS) uname[e.u] = e.u + '.' + SUF;

/* ── caption / chapter overlay (baked into the recording) ─────────────── */
/* Styled via CSSOM only (no <style>/style attrs) so it passes the app CSP. */
async function injectCaptions(page) {
  await page.evaluate(() => {
    if (document.getElementById('demo-cap')) return;
    const S = (el, o) => { for (const k in o) el.style[k] = o[k]; };
    const cyan = '#5ec8f0';

    // Chapter lower-third (top-left): tag + person/role.
    const chap = document.createElement('div');
    chap.id = 'demo-chap';
    S(chap, {
      position: 'fixed', top: '18px', left: '18px', zIndex: '2147483647',
      padding: '10px 16px 10px 14px', borderLeft: '3px solid ' + cyan,
      background: 'rgba(5,11,24,.82)', backdropFilter: 'blur(6px)',
      font: "600 13px/1.3 'Saira Condensed','Titillium Web',system-ui,sans-serif",
      color: '#cfe9f6', letterSpacing: '.06em', textTransform: 'uppercase',
      boxShadow: '0 4px 22px rgba(0,0,0,.45)', pointerEvents: 'none',
      clipPath: 'polygon(0 0,100% 0,100% 100%,10px 100%,0 calc(100% - 10px))',
    });
    const c1 = document.createElement('div'); c1.id = 'demo-chap-1';
    S(c1, { color: cyan, fontSize: '12px', letterSpacing: '.14em' });
    const c2 = document.createElement('div'); c2.id = 'demo-chap-2';
    S(c2, { fontSize: '17px', letterSpacing: '.04em', marginTop: '2px', textTransform: 'none' });
    chap.appendChild(c1); chap.appendChild(c2); document.body.appendChild(chap);

    // Caption bar (bottom-center): the running narration.
    const cap = document.createElement('div');
    cap.id = 'demo-cap';
    S(cap, {
      position: 'fixed', left: '50%', bottom: '30px', transform: 'translateX(-50%)',
      zIndex: '2147483647', maxWidth: '1080px', width: 'calc(100% - 120px)',
      padding: '14px 22px', borderLeft: '3px solid ' + cyan,
      background: 'rgba(5,11,24,.86)', backdropFilter: 'blur(8px)',
      font: "500 19px/1.42 'Titillium Web',system-ui,sans-serif",
      color: '#eaf6fd', textAlign: 'center', letterSpacing: '.01em',
      boxShadow: '0 6px 30px rgba(0,0,0,.5)', pointerEvents: 'none',
      opacity: '0', transition: 'opacity .35s ease',
      clipPath: 'polygon(14px 0,100% 0,100% calc(100% - 14px),calc(100% - 14px) 100%,0 100%,0 14px)',
    });
    document.body.appendChild(cap);

    // Title card (full-bleed chapter intro), hidden by default.
    const t = document.createElement('div');
    t.id = 'demo-title';
    S(t, {
      position: 'fixed', inset: '0', zIndex: '2147483646', display: 'flex',
      flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      gap: '14px', background: 'radial-gradient(120% 90% at 50% 30%,rgba(10,28,51,.97),rgba(5,11,24,.99))',
      opacity: '0', transition: 'opacity .4s ease', pointerEvents: 'none',
    });
    const tt = document.createElement('div'); tt.id = 'demo-title-tag';
    S(tt, { color: cyan, font: "700 15px/1 'Saira Condensed',sans-serif", letterSpacing: '.4em', textTransform: 'uppercase' });
    const th = document.createElement('div'); th.id = 'demo-title-h';
    S(th, { color: '#eaf6fd', font: "700 40px/1.15 'Saira Condensed','Titillium Web',sans-serif", letterSpacing: '.02em', textAlign: 'center', maxWidth: '80%' });
    const ts = document.createElement('div'); ts.id = 'demo-title-s';
    S(ts, { color: '#9fc4da', font: "400 20px/1.4 'Titillium Web',sans-serif", textAlign: 'center', maxWidth: '70%' });
    const tb = document.createElement('div');
    S(tb, { marginTop: '10px', color: '#6f93a8', font: "600 13px/1 'Saira Condensed',sans-serif", letterSpacing: '.24em', textTransform: 'uppercase' });
    tb.textContent = 'Weekly Weed Flow · Purely Plant';
    t.appendChild(tt); t.appendChild(th); t.appendChild(ts); t.appendChild(tb);
    document.body.appendChild(t);
  });
}
const setChapter = (page, tag, who) =>
  page.evaluate(([tag, who]) => {
    const a = document.getElementById('demo-chap-1'), b = document.getElementById('demo-chap-2');
    if (a) a.textContent = tag; if (b) b.textContent = who;
  }, [tag, who]);
async function titleCard(page, tag, head, sub, hold = 2600) {
  await page.evaluate(([tag, head, sub]) => {
    document.getElementById('demo-title-tag').textContent = tag;
    document.getElementById('demo-title-h').textContent = head;
    document.getElementById('demo-title-s').textContent = sub;
    document.getElementById('demo-title').style.opacity = '1';
  }, [tag, head, sub]);
  await page.waitForTimeout(hold);
  await page.evaluate(() => { document.getElementById('demo-title').style.opacity = '0'; });
  await page.waitForTimeout(500);
}
async function say(page, text, hold) {
  // hold scales with reading length; generous so captions are legible.
  const ms = hold || Math.min(7000, Math.max(2100, 45 * text.split(/\s+/).length + 900));
  await page.evaluate((t) => {
    const c = document.getElementById('demo-cap');
    if (!c) return; c.textContent = t; c.style.opacity = '1';
  }, text);
  await page.waitForTimeout(ms);
}
const capOff = (page) => page.evaluate(() => { const c = document.getElementById('demo-cap'); if (c) c.style.opacity = '0'; });

/* ── generic UI helpers ──────────────────────────────────────────────── */
const pause = (page, ms = 800) => page.waitForTimeout(ms);
const closeModals = async (page) => {
  for (let i = 0; i < 3 && await page.locator('.overlay.open').count(); i++) {
    await page.keyboard.press('Escape'); await page.waitForTimeout(320);
  }
};
async function uiLogin(page, username) {
  await page.route(/https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/, (r) => r.abort());
  await page.goto(BASE + '/');
  const stage = page.locator('#gf-leaf-stage'), user = page.locator('#wwf-u');
  await stage.click().catch(() => {});
  for (let i = 0; i < 20 && !(await user.isVisible().catch(() => false)); i++) {
    await stage.press('Enter').catch(() => {}); await page.waitForTimeout(400);
  }
  await user.fill(username);
  await page.locator('#wwf-p').fill(PW);
  await pause(page, 400);
  await page.getByRole('button', { name: 'Authenticate' }).click();
  await page.locator('#wwf-login').waitFor({ state: 'hidden', timeout: 20000 });
  await pause(page, 1200);
  await injectCaptions(page);
}
const gotoMyWeek = async (page) => {
  await closeModals(page);
  await page.locator('.nav-item', { hasText: /My Week|Моја недела/ }).first().click();
  await pause(page, 900);
};
const batchCard = (page) =>
  page.locator('.card', { has: page.locator('.card-title', { hasText: /Batch WC-0426/ }) }).first();

/* Open the add-modal already parented to a stage (there is no inline
   "add sub-subtask" button on tree rows, so we open the real create modal
   programmatically — same form, same API path). */
async function createSubOnCamera(page, weekVar, parentId, deptId, title) {
  await page.evaluate(([w, pid]) => GF.openAdd(w === 'sel' ? GF.state.selWeek : w, pid), [weekVar, parentId]);
  await pause(page, 700);
  const dsel = page.locator('#add-dept');
  if (await dsel.count()) await dsel.selectOption(deptId).catch(() => {});
  await pause(page, 300);
  await page.locator('#add-title').click();
  await page.locator('#add-title').pressSequentially(title, { delay: 16 });
  await pause(page, 500);
  await page.getByRole('button', { name: /Create task|Креирај/ }).click();
  await pause(page, 1100);
}
async function createTopTask(page, title, attrs) {
  await closeModals(page);
  await page.locator('#newtask-btn').click();
  await pause(page, 600);
  await page.locator('#add-title').click();
  await page.locator('#add-title').pressSequentially(title, { delay: 16 });
  for (const [k, v] of Object.entries(attrs || {})) {
    const el = page.locator('#attr-f-' + k);
    if (!(await el.count())) continue;
    const tag = await el.evaluate((e) => e.tagName);
    if (tag === 'SELECT') await el.selectOption(v).catch(() => {});
    else { await el.click(); await el.pressSequentially(String(v), { delay: 24 }); }
    await pause(page, 220);
  }
  await pause(page, 400);
  await page.getByRole('button', { name: /Create task|Креирај/ }).click();
  await pause(page, 1100);
}

/* ── manager story: work one stage of the batch on camera ─────────────── */
async function managerStory(page, mgrKey, stage, ids) {
  const m = MGRS[mgrKey];
  const st = stage.stage;
  await uiLogin(page, uname[mgrKey]);
  await setChapter(page, m.tag, `${m.name} · ${m.role.replace('_', ' ')}`);
  await titleCard(page, `Stage ${stage.order} of 7 · ${m.tag}`, st.title,
    `${m.name} picks up batch ${BATCH.ref} for the ${DEPT_NAME[stage.code]} stage.`);
  await pause(page, 1000);
  await say(page, `${m.name} manages ${DEPT_NAME[stage.code]}. She lands on her department home, then opens this week's board.`);

  // Board → find the shared batch, expand into this department's stage + checklist.
  await gotoMyWeek(page);
  await say(page, `The whole company is working one batch: ${BATCH.ref}, Wedding Crasher. Here it is on the board — every department is a delegated stage beneath it.`);
  const card = batchCard(page);
  if (await card.count()) {
    await card.locator('.sub-prog.tree-toggle').first().click().catch(() => {}); // expand the tree
    await pause(page, 900);
    await say(page, `Expanding the batch reveals ${DEPT_NAME[stage.code]}'s stage: "${st.title}".`);
    const stageRow = page.locator('.tree-row', { hasText: st.title.slice(0, 28) }).first();
    if (await stageRow.count()) {
      await stageRow.locator('.tree-toggle').first().click().catch(() => {}); // expand checklist
      await pause(page, 900);
      await say(page, `Beneath the stage sits its checklist of sub-tasks — each a concrete step with its own description.`);
    }
  }

  // Log work + a note on the first checklist sub-subtask.
  const firstSub = page.locator('.tree-row', { hasText: stage.subs[0].title.slice(0, 26) }).first();
  if (await firstSub.count()) {
    await firstSub.click(); await pause(page, 900);   // opens the worklog modal
    await say(page, `Opening a step logs the real work. Quick chips add the hours; a note captures what happened.`);
    for (const chip of ['+½h', '+1h']) {
      const b = page.getByRole('button', { name: chip });
      if (await b.count()) { await b.first().click(); await pause(page, 350); }
    }
    const note = page.locator('#wl-note');
    if (await note.count()) { await note.click(); await note.pressSequentially(`${st.title.split('—')[0].trim()} — first pass complete, batch ${BATCH.ref}.`, { delay: 12 }); await pause(page, 400); }
    await page.getByRole('button', { name: /Log work|Внеси/ }).last().click().catch(() => {});
    await pause(page, 1100);
    await closeModals(page);
  }

  // Create a new sub-subtask live (real create modal, parented to the stage).
  if (stage.liveSub && ids.stageByCode[stage.code]) {
    await say(page, `A new step comes up mid-batch — she adds it as a sub-task right under the stage.`);
    await createSubOnCamera(page, 'sel', ids.stageByCode[stage.code], ids.deptByCode[stage.code], stage.liveSub.title);
    await say(page, `"${stage.liveSub.title}" is now part of the ${BATCH.ref} tree, visible to everyone tracking the batch.`);
  }

  // Handoff caption.
  if (stage.handoffTo) {
    await say(page, `${DEPT_NAME[stage.code]} is done — the batch hands off to ${DEPT_NAME[stage.handoffTo]} next.`);
  } else {
    await say(page, `${DEPT_NAME[stage.code]} closes the loop — the batch has shipped under full chain of custody.`);
  }

  // Plan next week.
  await closeModals(page);
  await page.locator('body').press('ArrowRight'); await pause(page, 900);
  await say(page, `Looking ahead: ${m.name} plans next week's work — "${stage.next.title}".`);
  await createTopTask(page, stage.next.title, stage.next.attrs);
  await page.locator('body').press('ArrowLeft'); await pause(page, 700);

  // QC compiles + locks the weekly report on camera.
  if (stage.locksReport) {
    page.on('dialog', (d) => d.accept());
    await closeModals(page);
    await say(page, `As the QC lead, Blagoj also compiles the weekly QC report — the app drafts it, he approves each section, then locks and submits it.`);
    await page.locator('.nav-item', { hasText: /^Report|Извештај$/ }).first().click();
    await pause(page, 1200);
    const compile = page.getByRole('button', { name: /Compile document|Состави документ/ });
    if (await compile.count()) {
      await compile.click(); await pause(page, 2500);
      const approveAll = page.getByRole('button', { name: /Approve all|Одобри ги/ });
      if (await approveAll.count()) { await approveAll.click(); await pause(page, 1600); }
      await say(page, `Every section approved — locking makes it the immutable weekly record for ${DEPT_NAME.qc}.`);
      const lock = page.getByRole('button', { name: /Lock & submit|Заклучи/ });
      if (await lock.count()) { await lock.click(); await pause(page, 1900); }
    }
  }
  await capOff(page); await pause(page, 700);
}

/* ── COO kickoff (video 00) ───────────────────────────────────────────── */
async function kickoffStory(page, ids) {
  await uiLogin(page, uname['coo.demo']);
  await setChapter(page, 'OPERATIONS (COO)', 'Elena Markova · Chief Operating Officer');
  await titleCard(page, 'Batch kickoff', BATCH.title.replace(/^Batch /, ''),
    'The COO opens one batch and delegates a stage to every department.');
  await say(page, `Elena, the COO, coordinates the batch. One task — ${BATCH.ref}, Wedding Crasher — will move through all seven departments.`);
  await gotoMyWeek(page);
  const card = batchCard(page);
  if (await card.count()) {
    await card.locator('.card-title').click(); await pause(page, 700);          // expand card body
    await card.locator('.sub-prog.tree-toggle').first().click().catch(() => {}); // expand the tree
    await pause(page, 1000);
    await say(page, `The batch fans out into seven delegated stages — Cultivation, Maintenance, Production, QC, QA, Logistics and Security — in the exact order the flower moves through the site.`);
    // Expand two stages to reveal their checklists.
    const rows = page.locator('.card .tree-row .tree-toggle');
    const n = Math.min(await rows.count(), 2);
    for (let i = 0; i < n; i++) { await rows.nth(i).click().catch(() => {}); await pause(page, 900); }
    await say(page, `Each stage carries its own checklist of sub-tasks, with titles and descriptions written for that department's real work.`);
  }
  // Delegate one more coordination subtask live via the batch card's Add subtask.
  await say(page, `Elena adds one more piece live — a cross-department coordination sync — and delegates it to Quality Assurance.`);
  const addBtn = card.getByRole('button', { name: /Add subtask|Додади/ }).first();
  if (await addBtn.count()) {
    await addBtn.click(); await pause(page, 700);
    const dsel = page.locator('#add-dept');
    if (await dsel.count()) await dsel.selectOption(ids.deptByCode['quality_assurance']).catch(() => {});
    await pause(page, 300);
    await page.locator('#add-title').click();
    await page.locator('#add-title').pressSequentially('Coordination sync — cross-department batch stand-up', { delay: 15 });
    await pause(page, 500);
    await page.getByRole('button', { name: /Create task|Креирај/ }).click();
    await pause(page, 1100);
  }
  // Coordination note on the batch (exec note gets highlighted styling).
  await closeModals(page);
  await say(page, `A note from the COO is highlighted for everyone on the batch — the target is release and dispatch by Thursday.`);
  const cardAgain = batchCard(page);
  if (await cardAgain.count()) {
    if (!(await cardAgain.locator('.card-body').count())) { await cardAgain.locator('.card-title').click(); await pause(page, 600); }
    const noteInput = cardAgain.locator('input[id^="note-"]').first();
    if (await noteInput.count()) {
      await noteInput.click();
      await noteInput.pressSequentially('All seven stages delegated. Target release + dispatch Thursday 14:00. — COO', { delay: 12 });
      await pause(page, 400); await noteInput.press('Enter'); await pause(page, 1200);
    }
  }
  await say(page, `That is the whole idea: one batch, seven departments, every stage traceable back to this single task.`);
  await capOff(page); await pause(page, 700);
}

/* ── exec review (COO ops / CEO / Owner) ──────────────────────────────── */
const expandSection = async (page, label) => {
  const head = page.locator('.xr-sec-head', { hasText: label }).first();
  if (!(await head.count())) return false;
  await head.scrollIntoViewIfNeeded().catch(() => {});
  await head.click();
  await pause(page, 1700);   // the department's document loads asynchronously
  return true;
};
async function execReview(page, e) {
  const isOwner = e.role === 'OWNER', isCoo = e.role === 'COO';
  await uiLogin(page, uname[e.u]);
  await setChapter(page, e.tag, `${e.name} · ${e.role}`);
  const intro = isOwner ? 'The whole picture — every department, one batch, one screen.'
    : isCoo ? 'Operations review — where every stage of the batch stands right now.'
    : 'The strategic view — outcomes and momentum, not the mechanics.';
  await titleCard(page, e.tag, isOwner ? 'Owner review' : isCoo ? 'Operations review' : 'Executive summary', intro);
  await pause(page, 800);
  await page.evaluate(() => GF.setView('execreport')); await pause(page, 2400);
  await say(page, `${e.name} opens the Executive Report. The band across the top rolls up the whole week — tasks, completion, on-time rate and logged hours — and the board below shows every department's submission: submitted, draft, or still missing.`);

  // Expand the department sections that carry content (chip status Draft /
  // Submitted). Headers are clickable rows, not <details>.
  const want = isOwner ? ['Org-wide document', 'Cultivation', 'Quality Control']
    : isCoo ? ['Cultivation', 'Production', 'Quality Control']
    : ['Cultivation', 'Quality Control'];
  for (let i = 0; i < want.length; i++) {
    const ok = await expandSection(page, want[i]);
    if (ok && i === 0) await say(page, `Expanding a department opens its metrics grid and a plain-language narrative — the very figures the managers entered against batch ${BATCH.ref}.`);
  }

  // Drill into a task inside an expanded section.
  const task = page.locator('.xr-task summary').first();
  if (await task.count()) {
    await task.scrollIntoViewIfNeeded().catch(() => {});
    await task.click(); await pause(page, 1400);
    await say(page, `Drilling into a task reveals its progress notes — with author names — and the hours logged against it. Every number traces back to a real entry.`);
  }

  // Toggle the AI-drafted narrative off, then back on (re-renders the view).
  const aiOn = page.getByRole('button', { name: /AI shown|AI прикажано/ }).first();
  if (await aiOn.count()) {
    await aiOn.scrollIntoViewIfNeeded().catch(() => {});
    await say(page, `The AI-drafted passages can be hidden entirely — executives can read only the raw human record whenever they prefer.`);
    await aiOn.click(); await pause(page, 1300);
    const aiOff = page.getByRole('button', { name: /AI hidden|AI скриено/ }).first();
    if (await aiOff.count()) { await aiOff.click(); await pause(page, 900); }
  }

  if (isCoo) await say(page, `For operations this is the single pane of glass — the batch, its seven stages, and exactly where the work sits mid-week.`);

  if (isOwner) {
    // Deep link: jump from a report figure to its source task on the board.
    if (!(await page.locator('.xr-task summary').count())) await expandSection(page, 'Cultivation');
    const jump = page.getByRole('button', { name: /Open in board|Отвори на табла/ }).first();
    if (await jump.count()) {
      await jump.scrollIntoViewIfNeeded().catch(() => {});
      await say(page, `Every figure links to its source — one click jumps from the report straight to that task on the board.`);
      await jump.click(); await pause(page, 2100);
      await page.evaluate(() => GF.setView('execreport')); await pause(page, 1900);
    }
    // Export the whole thing as one self-contained interactive HTML file.
    if (!(await page.locator('.xr-exports').count())) await expandSection(page, 'Org-wide document');
    const dl = page.waitForEvent('download', { timeout: 15000 }).catch(() => null);
    const btn = page.getByRole('button', { name: /Interactive HTML|Интерактивен/ }).first();
    if (await btn.count()) {
      await btn.scrollIntoViewIfNeeded().catch(() => {});
      await say(page, `And the whole report exports as one self-contained interactive HTML file — no login, works offline, still expandable.`);
      await btn.click(); const d = await dl; if (d) await d.saveAs(path.join(OUT, 'owner-export.html'));
      await pause(page, 1300);
    }
    await say(page, `The owner can hand that single file to a partner or a regulator — or explore the planning tools directly.`);
    await page.evaluate(() => GF.setView('workload')); await pause(page, 1900);
    await page.evaluate(() => GF.setView('calendar')); await pause(page, 1900);
    await say(page, `From one delegated batch to the boardroom view — that is Weekly Weed Flow, end to end.`);
  }
  await capOff(page); await pause(page, 700);
}

/* ── seed the whole batch tree via the COO (batch coordinator) ─────────── */
async function seedBatch(coo, ids) {
  const mk = (body, tok) => api('POST', '/tasks', { week_start: WEEK, ...body }, tok || coo);
  const patch = (id, body, tok) => api('PATCH', '/tasks/' + id, body, tok || coo);
  const sess = (id, hours, note, tok) => api('POST', '/tasks/' + id + '/sessions',
    { started_at: `${WEEK}T08:30:00`, hours, note, source: 'manual' }, tok || coo);

  // Parent batch (home department = production; the through-line of a batch).
  const batch = await mk({
    title: BATCH.title, description: BATCH.desc, department_id: ids.deptByCode['production'],
    reference_code: BATCH.ref, due_date: THU, estimated_hours: BATCH.est,
    attributes: { batch_ref: BATCH.ref, process_step: 'Coordination' },
  });
  ids.batchId = batch.id;
  await patch(batch.id, { status: 'ongoing' });

  // A realistic mid-week status per stage (early stages further along).
  const STAGE_STATUS = { cultivation: 'completed', tooling: 'ongoing', production: 'ongoing', qc: 'pending', quality_assurance: 'pending', logistics: 'pending', security: 'pending' };
  const SUB_DONE = { cultivation: 3, tooling: 2, production: 1, qc: 0, quality_assurance: 0, logistics: 0, security: 0 };
  const HOURS = { cultivation: [3, 4, 2], tooling: [2, 1.5], production: [3.5] };

  ids.stageByCode = {};
  for (const s of STAGES) {
    const stage = await mk({
      title: s.stage.title, description: s.stage.desc, department_id: ids.deptByCode[s.code],
      parent_id: batch.id, reference_code: BATCH.ref, due_date: THU,
      estimated_hours: s.stage.est, attributes: s.stage.attrs,
    });
    ids.stageByCode[s.code] = stage.id;
    await patch(stage.id, { status: STAGE_STATUS[s.code] || 'pending' });
    const doneN = SUB_DONE[s.code] || 0;
    let i = 0;
    for (const sub of s.subs) {
      const child = await mk({
        title: sub.title, description: sub.desc, department_id: ids.deptByCode[s.code],
        parent_id: stage.id, reference_code: BATCH.ref,
      });
      if (i < doneN) await patch(child.id, { status: 'completed' });
      // seed a couple of real work sessions on completed early-stage steps
      if (HOURS[s.code] && HOURS[s.code][i] != null) await sess(child.id, HOURS[s.code][i], `${sub.title} — logged.`).catch(() => {});
      i++;
    }
  }
}

/* ── main ────────────────────────────────────────────────────────────── */
(async () => {
  // Fast path: re-record only the three executive clips against an already
  // seeded org (keeps the seven manager clips already in OUT).
  if (EXEC_ONLY) {
    const browser = await chromium.launch({ executablePath: EXEC_PATH, args: ['--no-sandbox'] });
    const execClips = [
      { idx: 8, name: 'coo-review', e: EXECS[0] },
      { idx: 9, name: 'ceo', e: EXECS[1] },
      { idx: 10, name: 'owner', e: EXECS[2] },
    ];
    for (const c of execClips) {
      const label = String(c.idx).padStart(2, '0') + '-' + c.name;
      const ctx = await browser.newContext({
        viewport: { width: 1440, height: 900 },
        recordVideo: { dir: OUT, size: { width: 1440, height: 900 } }, acceptDownloads: true,
      });
      const page = await ctx.newPage();
      try { await execReview(page, c.e); console.log('recorded:', label); }
      catch (err) { console.log('CLIP ERROR', label, err.message.slice(0, 200)); await page.screenshot({ path: path.join(OUT, label + '-error.png') }).catch(() => {}); }
      const video = page.video(); await ctx.close();
      if (video) { const p = await video.path(); fs.renameSync(p, path.join(OUT, label + '.webm')); }
    }
    await browser.close();
    console.log('DONE (exec-only). videos in', OUT);
    return;
  }

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

  // 2) departments
  const existing = await api('GET', '/departments', null, admin);
  const deptByCode = Object.fromEntries(existing.map((d) => [d.code, d.id]));
  for (const [code, name, mk] of DEPTS) {
    if (!deptByCode[code]) deptByCode[code] = (await api('POST', '/departments', { code, name, name_mk: mk }, admin)).id;
  }
  console.log('departments:', Object.keys(deptByCode).join(','));

  // 3) accounts (7 managers + 3 execs = 10 creates, under the 20/window throttle)
  const mkAccount = async (logical, role, deptCode) => {
    const r = await api('POST', '/auth/users', {
      username: uname[logical], full_name: (MGRS[logical] || EXECS.find((e) => e.u === logical)).name,
      role, department_id: deptCode ? deptByCode[deptCode] : null,
    }, admin);
    const tmp = (await api('POST', '/auth/login', { email: uname[logical], password: r.otp })).access_token;
    await api('POST', '/auth/change-password', { new_password: PW }, tmp);
    console.log('account ready:', uname[logical], role);
  };
  for (const [k, m] of Object.entries(MGRS)) await mkAccount(k, m.role, m.dept);
  for (const e of EXECS) await mkAccount(e.u, e.role, null);

  // 4) seed the connected batch tree (as the COO / batch coordinator)
  const coo = await loginTok(uname['coo.demo'], PW);
  const ids = { deptByCode };
  await seedBatch(coo, ids);
  console.log('batch seeded:', ids.batchId, 'stages:', Object.keys(ids.stageByCode).join(','));

  // 5) pre-compile department + org report drafts so the exec board shows variety
  for (const k of ['m.cultivation', 'm.production', 'm.qa']) {
    const t = await loginTok(uname[k], PW);
    await api('POST', '/reports/documents/compile', { kind: 'report' }, t).catch((e) => console.log('compile', k, e.message));
  }
  await api('POST', '/reports/documents/compile', { kind: 'report' }, coo).catch((e) => console.log('compile org', e.message));
  console.log('report drafts compiled');

  // 6) record — one context (=one video) per clip
  const browser = await chromium.launch({ executablePath: EXEC_PATH, args: ['--no-sandbox'] });
  const clips = [];
  clips.push({ name: 'kickoff-coo', fn: (p) => kickoffStory(p, ids) });
  for (const s of STAGES) clips.push({ name: s.code, fn: (p) => managerStory(p, s.mgr, s, ids) });
  clips.push({ name: 'coo-review', fn: (p) => execReview(p, EXECS[0]) });
  clips.push({ name: 'ceo', fn: (p) => execReview(p, EXECS[1]) });
  clips.push({ name: 'owner', fn: (p) => execReview(p, EXECS[2]) });

  let idx = 0;
  for (const clip of clips) {
    const label = String(idx).padStart(2, '0') + '-' + clip.name;
    const ctx = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      recordVideo: { dir: OUT, size: { width: 1440, height: 900 } },
      acceptDownloads: true,
    });
    const page = await ctx.newPage();
    try { await clip.fn(page); console.log('recorded:', label); }
    catch (e) {
      console.log('CLIP ERROR', label, e.message.slice(0, 200));
      await page.screenshot({ path: path.join(OUT, label + '-error.png') }).catch(() => {});
    }
    const video = page.video();
    await ctx.close();
    if (video) { const p = await video.path(); fs.renameSync(p, path.join(OUT, label + '.webm')); }
    idx++;
  }
  await browser.close();
  console.log('DONE. videos in', OUT);
})();
