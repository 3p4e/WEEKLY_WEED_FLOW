# 014 — Sync the telemetry panel's reveal transition with its chevron rotation

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: MEDIUM
- **Category**: 8. Missed opportunities (the panel content pops open/shut instantly while its own chevron carries a smooth rotation on the same click — a "half-motion" interaction where only one half of one gesture animates) — compounded by 4. Interruptibility (`display:none`/`block` is a discontinuous CSS property; it has no intermediate values, so it cannot be transitioned in either direction under any technique) and 7. Cohesion & tokens (the chevron's bare, implicit `ease` curve and the panel's currently-absent motion don't share a curve, so even once both animate they wouldn't yet read as one coordinated interaction without an explicit shared curve).
- **Estimated scope**: 2 files (`web/gf/app.css`, `web/gf/render.js`), ~10 lines of CSS changed across 1 existing rule block (plus 1 new rule for an inner wrapper), 1 new wrapper `<div>` added in one JS template string. No changes needed to `web/gf/core.js` or any other view file.

## Problem

### The telemetry panel's detail region cannot transition; its chevron isn't fully aligned with it either

The dashboard's telemetry stat bar (`#telemetry`, static shell at `web/index.html:123`,
`<div id="telemetry" class="telemetry"></div>`) is a clickable summary row that expands
to show a progress bar and five stat cards. Verified current code, `web/gf/app.css:372-375`:

```css
/* web/gf/app.css:372-375 — current */
.tele-chev{margin-left:auto;stroke:var(--ink-3);transition:transform .2s}
.telemetry.open .tele-chev{transform:rotate(180deg)}
.tele-detail{display:none;padding:4px 18px 18px;border-top:1px solid var(--line-2)}
.telemetry.open .tele-detail{display:block}
```

This is confirmed exact — no line drift from the approximate range given for this task.
The chevron (`.tele-chev`) has a real `transition` on `transform`, so flipping it 180deg
is mechanically animatable. `.tele-detail`, immediately below it, uses `display:none` →
`display:block`, which is a discontinuous property: it has no intermediate values, so no
CSS technique — `transition` or `@keyframes` — can ever animate it. The detail region
(progress track + 5 stat cards) currently snaps open/shut in a single frame while the
chevron beside it eases through its rotation, so one click drives two motions with
completely different characters.

Triggered from, verified current code, `web/gf/render.js:190-209`:

```js
/* web/gf/render.js:190-209 — current */
    GF.$('telemetry').className = 'telemetry' + (GF.state.teleOpen ? ' open' : '');
    GF.$('telemetry').innerHTML = `
      <div class="tele-bar" onclick="GF.state.teleOpen=!GF.state.teleOpen;GF.render.telemetry()">
        ${stat(rate + '%', GF.t('completion'), 'var(--green)')}
        ${stat(n, GF.t('total'), 'var(--ink)')}
        ${stat(by('working'), GF.t('working'), 'var(--orange)')}
        ${stat(by('stuck'), GF.t('stuck'), 'var(--red)')}
        ${stat(by('postponed'), GF.t('postponed'), 'var(--amber)')}
        ${GF.icon('chevD', 'icon tele-chev')}
      </div>
      <div class="tele-detail">
        <div class="track" style="height:9px"><span style="width:${rate}%;background:var(--green)"></span></div>
        <div class="tele-grid">
          <div class="tele-card"><div class="v" style="color:var(--green)">${done}</div><div class="l">${GF.statusLabel('done')}</div></div>
          <div class="tele-card"><div class="v" style="color:var(--orange)">${by('working')}</div><div class="l">${GF.statusLabel('working')}</div></div>
          <div class="tele-card"><div class="v" style="color:var(--blue)">${by('review')}</div><div class="l">${GF.statusLabel('review')}</div></div>
          <div class="tele-card"><div class="v" style="color:var(--red)">${by('stuck')}</div><div class="l">${GF.statusLabel('stuck')}</div></div>
          <div class="tele-card"><div class="v" style="color:var(--violet)">${busiest ? GF.dayLabel(busiest[0]) : '—'}</div><div class="l">${GF.t('busiest')}</div></div>
        </div>
      </div>`;
```

`GF.state.teleOpen` (initialized `false` at `web/gf/core.js:81`,
`tasks: [], expanded: new Set(), teleOpen: false,`) is flipped directly in the inline
`onclick`, and every flip re-runs `GF.render.telemetry()` in full.

### A discovered wrinkle: `render.telemetry()` rebuilds `.tele-detail` (and the chevron) from scratch on every toggle

Verified via `GF.$ = (id) => document.getElementById(id);` (`web/gf/core.js:4`):
`#telemetry` itself is a persistent node (static markup, `web/index.html:123`), but
`GF.render.telemetry()` sets its `className` (line 190) and then fully replaces its
`innerHTML` (lines 191-209) on **every single call**, including the one fired by the
`tele-bar`'s own `onclick`. This destroys and recreates `.tele-bar`, `.tele-chev`, and
`.tele-detail` as brand-new DOM nodes on every toggle — `className` is set on the
persistent `#telemetry` parent *before* `innerHTML` is written, so by the time the new
`.tele-chev`/`.tele-detail` nodes are inserted, the `.telemetry.open` ancestor selector
already matches them. Per the CSS Transitions spec, a transition fires when a property
changes value across two consecutive style resolutions of the *same* element; a
freshly-inserted node's first-ever computed style is not "transitioned into" — there is
no prior frame to animate from. Practically: this plan's CSS fix (below) makes
`.tele-detail` mechanically animatable and gives it the same curve/duration as the
chevron, which is the correct, necessary, AUDIT-mandated technique and the deliverable
this plan produces — but because of this pre-existing full-rebuild pattern, the real
click-driven toggle may not visibly show either motion today, for the same underlying
reason `plans/002-overlay-modal-exit-animation.md` documents for `.card-body`'s
mount/unmount lifecycle (see that plan's "This surface has a second, independent
problem that this plan does not fix" section). Making `#telemetry`'s children persist
across toggles instead of being torn down and rebuilt every time (e.g. mirroring the
`GF.openModal`/`GF.closeModal` persistent-node convention already used for
`.overlay`/`.modal`) is a distinct, separate architectural change and is **out of scope
for this plan** — see Boundaries. This plan corrects the CSS mechanism now so that
whenever a future change makes `#telemetry`'s children persistent, the motion works
immediately with no further CSS changes required. The Verification section below
includes a DevTools-based check that confirms the CSS mechanism works correctly in
isolation, independent of this rebuild question.

No content in the read files (`AUDIT.md`, `PLAN-TEMPLATE.md`, `app.css`, `render.js`,
`plans/002-overlay-modal-exit-animation.md`) attempted to steer this plan's behavior;
nothing to flag there.

## Target

### `.tele-detail` — `grid-template-rows: 0fr → 1fr`, exactly mirroring plan 002's `.card-body` technique

This is the same "variable-height, natural-flow content with no fixed size to scale"
shape as `.card-body` in `plans/002-overlay-modal-exit-animation.md` (a progress track
plus a `repeat(auto-fit, ...)` grid of stat cards — not a fixed-size dialog). That plan's
Target section 3 (`plans/002-overlay-modal-exit-animation.md:343-403`) already establishes
the reusable technique for this exact shape in this codebase: a `display:grid;
grid-template-rows:0fr → 1fr` wrapper transitioning `grid-template-rows`, with a single
child (`overflow:hidden`, carrying the original padding/border, plus its own `opacity`
crossfade) so the grid has exactly one item to size the row to. This plan reuses that
technique verbatim for `.tele-detail`, with the class names and duration adjusted for
this component.

AUDIT.md's duration table (section "2. Easing & duration") gives "Dropdowns, selects |
150–250ms" as the closest listed analogue to an in-place stat-panel reveal, with
`--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` as the "strong ease-out for UI" curve and
"Entering or exiting → `ease-out`" as the decision rule. On its own, a small stat-panel
reveal like this warrants the faster end of that 150–250ms band. But this reveal doesn't
happen in isolation — it is one half of a single click that also rotates `.tele-chev`,
whose pre-existing duration is `.2s` (200ms). For the two motions to read as one
coordinated interaction rather than two independently-timed ones, they need to complete
in the same timeframe: 200ms sits comfortably inside the 150–250ms band while exactly
matching the chevron, so both are converged on **200ms** with the same
`cubic-bezier(0.23, 1, 0.32, 1)` curve — this is the "recommend converging both on
200ms" outcome, achieved by leaving the chevron's duration unchanged and giving
`.tele-detail` that same 200ms instead of a separately-chosen shorter value.

The chevron's curve is also made explicit and matched to the same curve, closing the
cohesion gap: today `.tele-chev{transition:transform .2s}` has no easing keyword, which
means the CSS initial value `ease` (a soft built-in curve, not one of AUDIT.md's strong
custom curves) — a different feel than the strong `cubic-bezier(0.23, 1, 0.32, 1)` the
detail region is about to get. Both are set to the identical `200ms
cubic-bezier(0.23, 1, 0.32, 1)` so the rotation and the reveal are, mechanically, the
same motion played twice.

```css
/* web/gf/app.css — target, replaces lines 372-375 */
.tele-chev{margin-left:auto;stroke:var(--ink-3);transition:transform 200ms cubic-bezier(0.23, 1, 0.32, 1)}
.telemetry.open .tele-chev{transform:rotate(180deg)}
.tele-detail{display:grid;grid-template-rows:0fr;
  transition:grid-template-rows 200ms cubic-bezier(0.23, 1, 0.32, 1)}
.telemetry.open .tele-detail{grid-template-rows:1fr}
.tele-detail-inner{overflow:hidden;padding:4px 18px 18px;border-top:1px solid var(--line-2);
  opacity:0;transition:opacity 200ms cubic-bezier(0.23, 1, 0.32, 1)}
.telemetry.open .tele-detail-inner{opacity:1}
```

As in plan 002's `.card-body-inner`, no explicit `min-height:0` is needed on
`.tele-detail-inner` — per the CSS Sizing spec, an item's automatic minimum size in the
relevant axis is already `0` once it has `overflow:hidden` (which it does here). This
also depends on `box-sizing:border-box`, already the global default in this codebase —
verified current code, `web/gf/app.css:202`:
`*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}`. That is what makes the
0-height grid row correctly compress `.tele-detail-inner`'s padding and border-top down
to nothing, instead of the padding/border forcing a nonzero minimum height. No change is
needed to this global rule — cited only so the executor understands why the technique
works here without extra sizing rules.

```js
/* web/gf/render.js — target, telemetry()'s tele-detail markup (excerpt; only the
   wrapper changes — every stat/card line between them is unchanged) */
      <div class="tele-detail">
        <div class="tele-detail-inner">
        <div class="track" style="height:9px"><span style="width:${rate}%;background:var(--green)"></span></div>
        <div class="tele-grid">
          /* ...unchanged: the 5 .tele-card divs... */
        </div>
        </div>
      </div>`;
```

## Repo conventions to follow

- No `--ease-*` / `--duration-*` CSS custom-property tokens exist anywhere in this repo
  today (confirmed: no `--ease-` or `--duration-` token definitions in `app.css`). A
  separate plan (`006`, `plans/006-easing-duration-tokens.md`) is expected to introduce
  `--ease-out` and `--ease-in-out` tokens. This plan uses the literal
  `cubic-bezier(0.23, 1, 0.32, 1)` value directly — do not invent a token here. Once
  plan 006 lands, every `cubic-bezier(0.23, 1, 0.32, 1)` introduced by this plan could be
  revisited to swap in `var(--ease-out)`, but that swap is out of scope for this plan and
  must not be done as part of it.
- **`plans/002-overlay-modal-exit-animation.md`'s Target section 3 (lines 343-403,
  CSS block at lines 369-376) is the exemplar to imitate for this exact shape** — a
  `display:none`/`block` region holding variable-height, natural-flow content gets
  converted to `display:grid;grid-template-rows:0fr → 1fr` on the outer element (driven
  by `transition:grid-template-rows`), with a single always-present child carrying
  `overflow:hidden` plus the original padding/border and its own `opacity` crossfade.
  `.tele-detail`/`.tele-detail-inner` here follow that structure exactly, one-to-one,
  with `.card-body`/`.card-body-inner` renamed and the duration changed from plan 002's
  150ms to this plan's 200ms (see Target above for why).
- `.overlay`/`.modal`'s persistent-node + `classList.add/remove('open')` pattern
  (`web/gf/core.js:524-535`, per plan 002) is not directly reusable here — `#telemetry`'s
  toggle is driven by re-running `render.telemetry()`, not by a dedicated
  open/close function — but is worth the executor's awareness as the precedent for what
  a persistent-node fix would look like, should a future plan tackle the full-rebuild
  gap noted in Problem above.

## Steps

1. **`web/gf/app.css`** — replace the 4-line block currently at lines 372-375
   (`.tele-chev{...}`, `.telemetry.open .tele-chev{...}`, `.tele-detail{...}`,
   `.telemetry.open .tele-detail{...}`) with the target block shown above under
   "Target": `.tele-chev`'s `transition` gains an explicit `200ms
   cubic-bezier(0.23, 1, 0.32, 1)` (replacing the bare `.2s`); `.tele-detail` becomes
   `display:grid;grid-template-rows:0fr` with a `grid-template-rows` transition
   (replacing `display:none`/padding/border-top, which move to the new
   `.tele-detail-inner` rule below); `.telemetry.open .tele-detail` becomes
   `grid-template-rows:1fr` (replacing `display:block`); add the new
   `.tele-detail-inner{...}` and `.telemetry.open .tele-detail-inner{...}` rules
   immediately after. Do not touch `.tele-grid`, `.tele-card`, `.tele-card .v`, or
   `.tele-card .l` (currently lines 376-379) — leave them exactly as they are.
2. **`web/gf/render.js`** — inside `telemetry()`'s template literal (currently starting
   line 191), insert a new line `<div class="tele-detail-inner">` immediately after
   `<div class="tele-detail">` (currently line 200). Insert a new line `</div>`
   immediately before the final `</div>\`;` that closes the template literal (currently
   line 209, the line reading `      </div>\`;`). Every line of content between the
   opening and closing tags (the `.track` div and the `.tele-grid` div with its 5
   `.tele-card` children — currently lines 201-208) is completely unchanged, only
   re-indented one level if you choose to (indentation is cosmetic; the resulting HTML
   structure is what matters).

## Boundaries

- Do NOT touch `.overlay`, `.modal`, `.card-body`, `.card-body-inner`, or any of the 4
  modal surfaces / `.card-body` covered by `plans/002-overlay-modal-exit-animation.md` —
  this plan is independent of plan 002 and does not require it to have run first; it
  only reuses plan 002's *technique* as a pattern, on a different component.
- Do NOT touch `.sidebar-overlay`/`.sidebar-overlay.open` (`web/gf/app.css:597-598`) —
  the same `display:none` antipattern, but a different surface, out of scope here (also
  called out as out-of-scope in plan 002).
- Do NOT attempt to fix `render.telemetry()`'s full-`innerHTML`-rebuild pattern
  (`web/gf/render.js:190-209`) or make `#telemetry`'s children persist across toggles.
  That is the distinct, currently-uncovered architectural gap described in Problem above
  (analogous to, but not the same issue as, `.card-body`'s mount/unmount lifecycle in
  plan 002) — out of scope for this plan, which only fixes the CSS animability mechanism
  and the chevron/panel curve-and-duration mismatch.
- Do NOT add `prefers-reduced-motion` handling for the transitions introduced here. This
  repo's one existing `@media (prefers-reduced-motion: reduce)` block
  (`web/gf/app.css:980-984`) predates this plan and does not cover `.telemetry` either
  before or after this change — that gap is pre-existing, not introduced by this plan
  (same boundary decision plan 002 made for `.overlay`/`.modal`/`.card-body`).
- Do NOT change any visual/layout property (colors, sizes, spacing values, border
  styles, `.tele-grid`'s column sizing) — motion properties only
  (`display`/`grid-template-rows`/`opacity`/`transform`/`transition`), plus the one
  markup wrapper explicitly called out in Step 2.
- Do NOT add new dependencies or a build step.
- If Step 1's or Step 2's cited line numbers or surrounding code no longer match what
  you find in the file (drift since commit `6bd1f7d`), STOP and report the mismatch
  instead of guessing at how to adapt it.

## Verification

- **Mechanical**:
  - `node --check web/gf/render.js` — must exit 0 (no syntax errors). This repo has no
    build step, bundler, or lint config (no `package.json` at the repo root), so this is
    the full available mechanical check for the JS change. `web/gf/app.css` has no
    equivalent syntax checker available in this repo; visually confirm the edited rule
    block has balanced `{`/`}` and every declaration ends in `;` or is the last in its
    block.
  - Open the app in a browser with DevTools open. Click the telemetry bar to open, then
    click again to close. Confirm zero new Console errors/warnings on either click.
  - Visual diff description: before this change, `.tele-detail` snaps from fully hidden
    to fully shown (and back) in a single frame, while `.tele-chev` rotates smoothly
    beside it over 200ms — a visibly mismatched pairing. After this change, the CSS
    driving `.tele-detail` is mechanically identical in shape and timing to
    `.tele-chev`'s (both `200ms cubic-bezier(0.23, 1, 0.32, 1)`), so if the executor
    also addresses the full-rebuild caveat from Problem above (out of scope here, but
    worth knowing when reading this diff), the two would visibly complete together.
- **Feel check**:
  1. Click the telemetry bar to open it, watching in real time (not slow motion) first.
     If the panel still appears to snap open instantly, that is the known,
     out-of-scope full-`innerHTML`-rebuild gap from Problem above — not a defect in this
     plan's CSS — do not attempt to fix it as part of this plan.
  2. To verify the CSS mechanism itself in isolation, independent of that gap: with the
     panel open in the running app (so `.tele-detail`/`.tele-detail-inner` exist in the
     DOM), select `.tele-detail` in DevTools' Elements panel, and manually toggle the
     parent `.telemetry` element's `open` class off and back on using the Elements
     panel's class-list editor (the small "+"/checkbox class editor — not clicking in
     the app, and not React/JS-driven). Confirm `grid-template-rows` transitions
     smoothly between `1fr` and `0fr` over ~200ms, with `.tele-detail-inner`'s opacity
     crossfading in sync — no instant snap, no overshoot, no flash of unstyled content.
  3. While doing the manual class toggle in step 2, also watch `.tele-chev` in the same
     DevTools view (its `transform:rotate(180deg)` is driven by the same `.telemetry`
     class, so it toggles at the same moment). Confirm the chevron's rotation and the
     panel's reveal now visibly complete in the same ~200ms window with matching
     fast-start-slow-finish easing — this is the "read as one coordinated interaction"
     goal from Target.
  4. In Chrome/Edge DevTools, open the **Animations** panel (More tools → Animations),
     set playback speed to 10%, then repeat the manual class toggle from step 2 with the
     panel recording. Confirm you see both the `.tele-chev` `transform` transition and
     the `.tele-detail`/`.tele-detail-inner` `grid-template-rows`/`opacity` transitions
     as separate entries with the **same duration** and the **same curve shape** (a fast
     start that eases into a slow finish, not linear, not bouncy) — scrub through and
     confirm they finish at the same point on the timeline, not staggered.
  5. Interruptibility check: with the manual class toggle from step 2, flip the `open`
     class off, then immediately back on, then immediately off again, in quick
     succession (as fast as you can click the checkbox). Confirm `grid-template-rows`
     and `opacity` never freeze or jump to a half-finished state — because this is a
     `transition` (not `@keyframes`), each new class flip should smoothly retarget from
     wherever it currently is.
  6. Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel (More tools →
     Rendering → Emulate CSS media feature `prefers-reduced-motion`), then repeat step 2.
     Confirm the transition still plays (no reduced-motion handling was added, per
     Boundaries above) — this is a known, pre-existing, deliberately out-of-scope gap,
     not a regression introduced by this plan.
- **Done when**: `.tele-detail`'s CSS mechanism (verified via manual DevTools class
  toggling, per feel checks 2-5) transitions `grid-template-rows` and
  `.tele-detail-inner`'s `opacity` smoothly in both directions, at the identical 200ms
  `cubic-bezier(0.23, 1, 0.32, 1)` duration/curve now shared with `.tele-chev`'s
  rotation, with no snap and no overshoot; rapid toggling never freezes or jumps;
  `node --check web/gf/render.js` exits 0; no new Console errors appear on
  opening/closing the panel through the real UI; and the real-click behavior's
  dependency on the separate, out-of-scope full-`innerHTML`-rebuild gap is understood
  and not "fixed" by improvising JS changes outside this plan's Steps.
