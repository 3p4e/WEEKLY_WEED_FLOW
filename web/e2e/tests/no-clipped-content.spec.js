// @ts-check
// Regression test for the bug class behind the sidebar-clipping incident: a
// container holds JS-built, variable-length content (a growing list, a chat
// thread, a modal body) whose length isn't fixed at design time, but the
// container's CSS gives it no scroll affordance — so once the content
// outgrows the box, the excess renders off-screen with literally no way for
// a human to reach it. No existing e2e test caught that bug, because both
// styles of existing test bypass the problem:
//   - control-wiring.spec.js drives navigation via `GF.setView(key)` calls,
//     never touching the DOM nav element at all;
//   - a Playwright `.locator(...).click()` auto-scrolls its target into view
//     via the browser's native scrollIntoView, which works on an
//     `overflow:hidden` ancestor exactly as well as on `overflow:auto` — so
//     even a click-based test "reaches" a control a real mouse/trackpad
//     never could, because there's no visible scrollbar and no wheel-scroll
//     response on `overflow:hidden`.
// This spec instead asserts the structural CSS invariant directly: for every
// known "may grow past its box" container, if its content actually overflows
// (scrollHeight > clientHeight), the container's own overflow-y must be
// `auto` or `scroll` — never `hidden` or the default `visible` bleeding into
// a clipped ancestor. That holds regardless of which specific list grows
// next, so it generalizes past the one container (`.side-scroll`) this
// incident happened to hit.
//
// Viewport is deliberately capped at a realistic in-browser height (chrome —
// address bar + bookmarks bar — eats real space on an ordinary laptop
// window), not Playwright's roomier default, because the original bug only
// manifested once total nav-item height exceeded the space actually left
// for the page.
const { test, expect } = require('@playwright/test');
const { seedOrg, login } = require('../seed');

/** @type {{username: string, password: string}} */
let creds;

test.beforeAll(() => {
  creds = seedOrg();
});

// selector -> how to get an instance of it on screen (assumed already logged in)
const REGIONS = [
  { name: 'sidebar nav + department rail', selector: '.side-scroll' },
  { name: 'primary content column', selector: '.workspace' },
];

async function overflowReport(page, selector) {
  return page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const cs = getComputedStyle(el);
    return {
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
      overflowY: cs.overflowY,
      clipped: el.scrollHeight > el.clientHeight + 2, // subpixel slack
    };
  }, selector);
}

test('no growing region clips content without a scroll affordance', async ({ page }) => {
  // Realistic short window: real browser chrome (address bar, bookmarks bar)
  // leaves noticeably less than a bare 900px of page height on an ordinary
  // laptop display — this is what actually exposed the sidebar bug.
  // Height lowered 820 -> 760 (2026-08-05): at 820 the admin nav rail overflowed
  // by only a few px, so the line-91 sanity guard below sat right on the +2
  // subpixel threshold and flipped on CI font/render variance (a frontend batch
  // that touched no nav/sidebar/global CSS still tripped it). 760 keeps the nav
  // overflowing by a comfortable margin — the author-anticipated "shorter
  // viewport" maintenance (see the note at the sanity check). Both measured
  // regions are overflow-y:auto, so the real invariant is unaffected by height.
  await page.setViewportSize({ width: 1440, height: 760 });
  await login(page, creds.username, creds.password);
  await page.waitForSelector('.side-scroll', { timeout: 10_000 });

  const findings = [];
  for (const { name, selector } of REGIONS) {
    const r = await overflowReport(page, selector);
    if (!r) continue; // region not present in this view — fine, checked elsewhere
    findings.push({ name, selector, ...r });
  }

  const violations = findings.filter((f) => f.clipped && !['auto', 'scroll'].includes(f.overflowY));
  if (violations.length) {
    console.log('Clipped-without-scroll regions found:\n' + violations
      .map((v) => `  ${v.name} (${v.selector}): scrollHeight=${v.scrollHeight} clientHeight=${v.clientHeight} overflow-y=${v.overflowY}`)
      .join('\n'));
  }
  expect(violations, 'every region whose content overflows its box must allow auto/scroll').toEqual([]);

  // Sanity check the assertion is actually exercised, not vacuously true
  // because nothing overflowed at this viewport size (an admin account's
  // full nav — Operations/Management/QMS Studio/System — is long enough to
  // guarantee this on a 820px-tall window; if this ever stops being true,
  // the check above stops proving anything and needs a taller nav or a
  // shorter viewport to keep testing the real scenario).
  const sidebarReport = findings.find((f) => f.selector === '.side-scroll');
  expect(sidebarReport, 'sidebar region must have been measured').toBeTruthy();
  expect(sidebarReport.clipped, 'the nav rail should be tall enough to overflow at this viewport — otherwise this test is not exercising the bug it exists to catch').toBe(true);
});
