// @ts-check
// Preventive smoke test for the class of bug where a control is wired to a
// missing/misspelled handler, a view errors on render, or an inline handler
// references a GF.* function that doesn't exist. Runs entirely in DEMO mode
// (in-memory API, no seeded org) so it can walk every nav view + key modals
// cheaply and assert:
//   1. no uncaught page errors while navigating the whole app,
//   2. every inline on*-handler's GF.<path>(...) call resolves to a function,
//   3. every nav view renders a non-empty main region.
// It does NOT judge labels-vs-intent (that needs human/AI review) — it catches
// the mechanical dead-control + render-crash failures unit tests miss.
const { test, expect } = require('@playwright/test');

// Attributes that carry inline JS handlers in the shell.
const HANDLER_ATTRS = ['onclick', 'onchange', 'onkeydown', 'oninput', 'onsubmit', 'onkeyup'];

async function enterDemo(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.goto('/');
  await page.waitForFunction(() => window['GF'] && window['GF'].WWF && typeof window['GF'].WWF.showLogin === 'function');
  // Splash → reveal → enter demo (routes all API in-memory).
  await page.locator('#gf-leaf-stage').click().catch(() => {});
  await page.waitForTimeout(300);
  await page.evaluate(() => window['GF'].DEMO.enter());
  await page.waitForFunction(() => window['GF'].API && window['GF'].API._demoWrapped && window['GF'].DEMO.active());
  await page.waitForTimeout(1500);
  return errors;
}

// In page context: scan the live DOM for on*-handlers, extract every
// GF.<dotted.path>( call, and return those whose target is not a function.
async function unresolvedHandlers(page) {
  return await page.evaluate((attrs) => {
    const bad = [];
    const resolve = (path) => path.split('.').reduce((o, k) => (o == null ? o : o[k]), window);
    const els = document.querySelectorAll('*');
    for (const el of els) {
      for (const attr of attrs) {
        const v = el.getAttribute && el.getAttribute(attr);
        if (!v) continue;
        // match GF.a.b.c(  — a called member expression rooted at GF
        const calls = v.match(/GF\.[\w$.]+(?=\s*\()/g) || [];
        for (const c of calls) {
          let fn;
          try { fn = resolve(c); } catch (e) { fn = undefined; }
          if (typeof fn !== 'function') {
            bad.push({ path: c, attr, tag: el.tagName.toLowerCase(),
              label: (el.textContent || '').trim().slice(0, 40) });
          }
        }
      }
    }
    // de-dupe by path
    const seen = new Set(); const out = [];
    for (const b of bad) { if (!seen.has(b.path)) { seen.add(b.path); out.push(b); } }
    return out;
  }, HANDLER_ATTRS);
}

test('every nav view renders and every inline handler resolves (demo mode)', async ({ page }) => {
  const errors = await enterDemo(page);

  // Discover view keys straight from the sidebar's own setView(...) handlers,
  // so this stays correct as views are added/removed.
  const views = await page.evaluate(() => {
    const keys = new Set();
    document.querySelectorAll('[onclick]').forEach((el) => {
      const m = (el.getAttribute('onclick') || '').match(/GF\.setView\((['"])([\w-]+)\1\)/);
      if (m) keys.add(m[2]);
    });
    return [...keys];
  });
  expect(views.length, 'should discover nav views from the sidebar').toBeGreaterThan(3);

  /** @type {Record<string, any[]>} */
  const perView = {};
  for (const key of views) {
    await page.evaluate((k) => window['GF'].setView(k), key);
    await page.waitForTimeout(700);
    // main region should render something
    const mainLen = await page.evaluate(() => {
      const m = document.querySelector('#main, #app-main, main, #panels, #view-root') || document.body;
      return (m && m.textContent ? m.textContent.trim().length : 0);
    });
    expect(mainLen, `view "${key}" should render non-empty content`).toBeGreaterThan(0);
    perView[key] = await unresolvedHandlers(page);
  }

  // A couple of key modals that aren't reached by setView.
  await page.evaluate(() => window['GF'].setView('report'));
  await page.waitForTimeout(400);
  await page.evaluate(() => { try { window['GF'].export.open('report'); } catch (e) {} });
  await page.waitForTimeout(300);
  perView['export-modal'] = await unresolvedHandlers(page);
  await page.evaluate(() => { try { window['GF'].closeModal('export-modal'); } catch (e) {} });

  // Aggregate + report clearly.
  const dead = [];
  for (const [view, list] of Object.entries(perView)) {
    for (const b of list) dead.push(`  [${view}] <${b.tag} ${b.attr}> "${b.label}" → ${b.path} (not a function)`);
  }
  if (dead.length) console.log('Dead controls found:\n' + dead.join('\n'));
  expect(dead, 'no inline handler should reference a missing GF.* function').toEqual([]);

  const realErrors = errors.filter((e) => !/ServiceWorker|Failed to register/i.test(e));
  if (realErrors.length) console.log('Page errors:\n  ' + realErrors.join('\n  '));
  expect(realErrors, 'no uncaught page errors while walking all views').toEqual([]);
});
