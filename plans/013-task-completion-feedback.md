# 013 — Give task completion a real, deliberate feedback flash

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: HIGH
- **Category**: 8. Missed opportunities (marking a task done is the single highest-emotion, most-repeated payoff moment in a task-management app, and it currently renders with zero visual acknowledgment) — compounded by the same full-DOM-replace re-render mechanism plan 001 addresses (`web/gf/render.js`'s `panels()` calls `GF.$('panels').innerHTML = ...` on every status change, so a CSS `transition` already written for this exact state change — `web/gf/app.css:395` — structurally never sees an old/new state pair to interpolate, no matter which CSS technique is used)
- **Estimated scope**: 3 files (`web/gf/app.css`, `web/gf/render.js`, `web/gf/core.js`) — app.css: 2 new `@keyframes`, 1 new class rule, 1 line appended to the existing `@media (prefers-reduced-motion: reduce)` block, 1 extended existing rule (`.check`) (~20 lines total); render.js: 1 new helper function (`GF.flashCompleted`, ~14 lines incl. comment), 2 one-line `data-task-id` attribute additions inside `card()`, 1 one-line edit inside `pickStatus`'s `onPick`; core.js: `toggleDone` gains 2 lines. No new dependencies, no build step, no markup restructuring beyond the two new `data-task-id` attributes.

## Problem

### The reward moment — marking a task done — has no motion, on either the card or the checkbox

Verified current code, `web/gf/core.js:310-315` (`GF.toggleDone`):

```js
/* web/gf/core.js:310-315 — current */
GF.toggleDone = (id) => {
  const t = GF.task(id); if (!t) return;
  if (!GF.can('status', t)) return GF.denyToast();
  t.status = t.status === 'done' ? 'working' : 'done';
  GF.store.save(); GF.render.panels(); GF.render.telemetry();
};
```

Verified current code, `web/gf/render.js:25-34` (`GF.pickStatus`, the status-pill picker):

```js
/* web/gf/render.js:25-34 — current */
GF.pickStatus = (id) => {
  const t = GF.task(id); if (!t) return;
  if (!GF.can('status', t)) return GF.denyToast();
  if (!GF.choose) return GF.cycleStatus(id);
  GF.choose({
    title: GF.t('change_status'), value: t.status,
    options: GF.STATUS_ORDER.map(s => ({ v: s, label: GF.statusLabel(s), color: GF.STATUS_COLORS[s] })),
    onPick: (v) => { if (v !== t.status && GF.setStatus(id, v)) { GF.render.panels(); GF.render.telemetry(); } },
  });
};
```

Both paths end the same way: `GF.render.panels()`. Verified current code, `web/gf/render.js:212-223` — `panels()` rebuilds the entire panel list via one `innerHTML` assignment on every call:

```js
/* web/gf/render.js:212-223 — current (opening of panels(), showing the full-replace) */
  panels() {
    const cur = GF.visibleTasks(GF.state.selWeek);
    const nextId = GF.state.selWeek + 1;
    const nxt = GF.weekTasks(nextId);
    // Tags filter: every tag on this week's tasks, filtered client-side.
    const allTags = [...new Set(GF.weekTasks(GF.state.selWeek).flatMap(t => t.tags || []))].sort();
    const tagFilter = (allTags.length || GF.state.tagFilter) ? GF.selectField('tag-filter', {
      value: GF.state.tagFilter || '', inline: true, title: GF.t('all_tags'),
      options: [{ v: '', label: GF.t('all_tags') }].concat(allTags.map(tg => ({ v: tg, label: '#' + tg }))),
      onPick: (v) => GF.setTagFilter(v),
    }) : '';
    GF.$('panels').innerHTML = `
      <div class="panel">
      /* ...panel-head, panel-body (cur.map(t => this.card(t))), next-panel... */
```

`panels()` calls `this.card(t)` for every visible task, and `card(t)`'s two possible returns
(collapsed and expanded) both build a brand-new `<div class="card s-${t.status}">` already
carrying the **final** status class — verified current code:

```js
/* web/gf/render.js:305 — current (collapsed) */
    if (!exp) return `<div class="card s-${t.status}"${archMute}>${head}${tree}</div>`;
```

```js
/* web/gf/render.js:358 — current (expanded) */
    return `<div class="card s-${t.status} expanded"${archMute}>${head}${body}${tree}</div>`;
```

Meanwhile `web/gf/app.css:393-404` already carries a `transition` written for exactly this
class-driven color change, plus one status-color rule per status:

```css
/* web/gf/app.css:393-404 — current */
.card{background:var(--glass-bg);backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-border);border-left:4px solid var(--ink-3);border-radius:12px;
  margin-bottom:10px;box-shadow:var(--sh-1);transition:box-shadow .18s,transform .12s,border-left-color .18s;
  opacity:1;animation:cardIn .25s ease forwards;position:relative;overflow:hidden}
.card::before{content:'';position:absolute;inset:0;background:var(--scanlines);pointer-events:none;opacity:.35}
.card:hover{box-shadow:var(--sh-2);transform:translateY(-1px)}
.card.s-done{border-left-color:var(--green)}
.card.s-working{border-left-color:var(--orange)}
.card.s-review{border-left-color:var(--blue)}
.card.s-stuck{border-left-color:var(--red)}
.card.s-postponed{border-left-color:var(--amber)}
.card.s-pending{border-left-color:var(--ink-3)}
```

**Confirmed mechanism** (the "presumably" in this finding's brief is now verified): there is
no single reassigned CSS variable — each status has its own selector,
`.card.s-<status>{border-left-color:var(--<color>)}`, and `.card`'s base rule carries
`transition: ... border-left-color .18s`. If the same DOM node kept its identity while its
class changed from `s-pending`/`s-working`/etc. to `s-done`, this transition would smoothly
crossfade the left accent to green. It never gets the chance: because `panels()` replaces
`#panels`'s entire `innerHTML`, the "done" card is a **brand-new element inserted already
green** — a freshly-inserted node has no prior style to transition from, so the browser has
nothing to interpolate and the color change is instant, every time, silently. Same root cause
plan 001 (`plans/001-card-render-replay.md`) documents for the card's *entrance* animation;
here it silently defeats the *completion* transition instead.

The checkbox itself is worse off — it has no transition property at all. Verified current
code, `web/gf/app.css:411-413`:

```css
/* web/gf/app.css:411-413 — current */
.check{width:20px;height:20px;border-radius:6px;border:2px solid var(--line);flex-shrink:0;
  display:flex;align-items:center;justify-content:center;background:none;cursor:pointer}
.check.done{background:var(--primary);border-color:var(--primary)}
```

And the markup that renders it, verified current code, `web/gf/render.js:284-287`
(`card(t)`'s `head` template — the checkbox is the first child of `.card-head`):

```js
/* web/gf/render.js:284-287 — current */
    const head = `
      <div class="card-head" onclick="GF.toggleExpand('${t.id}')">
        <button class="check ${t.status === 'done' ? 'done' : ''}" onclick="event.stopPropagation();GF.toggleDone('${t.id}')">
          ${t.status === 'done' ? GF.icon('check', 'icon', '#03130C') : ''}</button>
```

Even setting the destroy/recreate issue aside, `.check`/`.check.done` have no `transition` at
all — so even in a hypothetical world where this button's node persisted across a re-render,
the fill color would still pop instantly rather than settle in.

### Cards have no stable identity in the DOM today — a gap that blocks the independent fix below

Neither of `card(t)`'s two return statements (`render.js:305`, `render.js:358`) put an `id` or
`data-*` attribute on the `<div class="card ...">` wrapper — confirmed by grepping
`web/gf/render.js` for `data-id`/`data-task`/`id="task-` (no matches). This matters because the
fix below intentionally does **not** rely on the outgoing (about-to-be-destroyed) node — it
looks up the newly-rendered node for the same task *after* `render.panels()` has already run,
and there is currently no attribute to look it up by. Step 1 below adds one.

### Subtask rows share the same two functions, but render through a different template with no hook

`web/gf/render.js:367-391` (`treeRows`, the indented subtask list under an expanded parent)
renders each subtask as a `<div class="tree-row s-${c.status}">`, and its own checkbox
(`render.js:379-380`) and status pill (`render.js:387-388`) call the exact same
`GF.toggleDone('${c.id}')` / `GF.pickStatus('${c.id}')` as top-level cards do. `.tree-row` is a
visually distinct, much narrower element (no left status border, no box-shadow) and is not
covered by this plan — see Boundaries.

### Oddity noticed while reading (per instructions, flagged and ignored, not acted on)

None of the read files (`web/gf/core.js`, `web/gf/render.js`, `web/gf/app.css`) contained any
text attempting to steer this plan's behavior. Nothing to flag.

## Target

### 1. A new, deliberate one-shot completion class on `.card`, decoupled from the render mechanism

Per AUDIT.md category 8 ("Missed opportunities"), this is exactly a "rare, high-emotion moment
(first-run, success, celebration)" — completing a task happens once per task, and the category
explicitly allows more delight budget here than on routine, high-frequency UI. Per AUDIT.md
category 2's decision order, this is a symmetric "grow, then settle back" motion — the closest
listed case is "Moving/morphing on screen → `ease-in-out`" — so this plan uses the exact
AUDIT.md literal value for that: `cubic-bezier(0.77, 0, 0.175, 1)`. Duration: `400ms`, the
midpoint of the 350–450ms band appropriate for a rare high-emotion moment (above the routine
"UI animations stay under 300ms" ceiling in AUDIT.md's duration table, which is why category 1
and category 8 both call out that rare/first-time/celebration moments get extra delight
budget — this is not a routine hover or button-press animation).

Per AUDIT.md category 3 ("Physicality & origin"): the scale stays inside the recommended
subtle range (`0.9–0.97` band is for *entrances*; for this in-place pulse the instruction
explicitly requested `scale(1.015)`, which is well inside "subtle" and nowhere near the
forbidden `scale(0)`).

```css
/* web/gf/app.css — target, new rules, placed immediately after .card.s-pending
   (currently line 404) and before .card-head (currently line 405) */
.card--just-completed{animation-name:cardComplete;animation-duration:400ms;
  animation-timing-function:cubic-bezier(0.77, 0, 0.175, 1)}
@keyframes cardComplete{
  0%{box-shadow:var(--sh-1);transform:scale(1)}
  40%{box-shadow:0 0 0 3px var(--green-soft),var(--sh-2);transform:scale(1.015)}
  100%{box-shadow:var(--sh-1);transform:scale(1)}
}
@keyframes cardCompleteReduced{
  0%{box-shadow:var(--sh-1)}
  40%{box-shadow:0 0 0 3px var(--green-soft),var(--sh-2)}
  100%{box-shadow:var(--sh-1)}
}
```

`var(--green)`/`var(--green-soft)` are this app's theme-aware "success" tokens, already
defined in every one of the three `:root` skins (`web/gf/app.css:46-48` default/dark,
`:134` `[data-theme="light"]`, `:171` `[data-theme="suma"]`) — using them means the glow is
automatically the correct "success green" in whichever theme is active, with zero extra CSS.
`rgba(var(--accent-rgb),…)` is deliberately **not** used for the glow: in the `suma` theme
`--accent-rgb` is cyan (`web/gf/app.css:163`: `--accent-rgb: 46,230,255;`) while `--green` is
still green (`:171`: `--green: #34D399;`) — `accent-rgb` would render a cyan "completion" glow
in that theme, which is wrong.

`cardCompleteReduced` exists only so the reduced-motion override (step 3) can drop the
`transform: scale(...)` half of the animation while keeping the box-shadow color feedback —
per AUDIT.md category 6: "Reduced motion means fewer and gentler animations, **not zero** —
keep transitions that aid comprehension, remove position changes."

### 2. `.check` gets a real transition (cheap, correct, and consistent with `.tree-row .check`)

Per AUDIT.md category 2's decision order, a state-driven fill-color change is "Hover / color
change → `ease`", with a duration in the "Button press feedback: 100–160ms" band (the
checkbox is a small button-like control). This repo already has a same-shaped exemplar at
`web/gf/app.css:988-990` (`.fac-room`): `transition:border-color .16s ease,box-shadow .16s
ease`. `.check`'s new rule imitates that shape and duration exactly:

```css
/* web/gf/app.css — target, replaces .check (currently lines 411-412); .check.done unchanged */
.check{width:20px;height:20px;border-radius:6px;border:2px solid var(--line);flex-shrink:0;
  display:flex;align-items:center;justify-content:center;background:none;cursor:pointer;
  transition:background-color .16s ease,border-color .16s ease}
.check.done{background:var(--primary);border-color:var(--primary)}
```

**Honest caveat, stated up front so it isn't mistaken for a bug later**: `.check` is shared by
both `.card-head .check` (`render.js:286`) and `.tree-row .check` (`render.js:379-380`), and
both are, today, always rendered fresh by a full `innerHTML` replace — exactly the same
destroy/recreate situation as `.card`'s pre-existing (also currently-inert)
`border-left-color` transition. This rule will **not** visibly animate during a real click in
the app's current architecture. It is included because it is cheap and correct regardless, and
it starts working with zero further CSS changes the moment any code path toggles
`.check`'s `done` class on a node that already exists in the DOM (e.g. if plan 001 ever changes
how `.card`/`.tree-row` nodes are kept alive across re-renders). See Verification for how to
confirm the rule works correctly in isolation despite this.

### 3. Extend the one existing reduced-motion block, in place

This repo has exactly one `@media (prefers-reduced-motion: reduce)` block. Verified current
code, `web/gf/app.css:980-984`:

```css
/* web/gf/app.css:980-984 — current */
@media (prefers-reduced-motion: reduce){
  .mw-spinner{animation-duration:1.6s}
  .mw-skel{animation:none}
  .tree-row.s-working .tp-fill,.card.s-working .card-actions .track > span{animation:none}
}
```

Add one more line, following its existing convention of overriding a single property on an
already-styled selector (`.mw-spinner{animation-duration:1.6s}` overrides only the duration of
a shorthand `animation` declared elsewhere) — this plan's addition overrides only
`animation-name`, which is enough to swap `.card--just-completed` onto the no-scale keyframe
while keeping the same duration/timing-function from `.card--just-completed`'s base rule
(added in step 1 above, and appearing earlier in the file, so this override wins by source
order):

```css
/* web/gf/app.css — target, one new line inside the existing block */
@media (prefers-reduced-motion: reduce){
  .mw-spinner{animation-duration:1.6s}
  .mw-skel{animation:none}
  .tree-row.s-working .tp-fill,.card.s-working .card-actions .track > span{animation:none}
  .card--just-completed{animation-name:cardCompleteReduced}
}
```

### 4. `data-task-id` on the card wrapper — the lookup hook the JS fix needs

```js
/* web/gf/render.js — target, replaces line 305 */
    if (!exp) return `<div class="card s-${t.status}" data-task-id="${t.id}"${archMute}>${head}${tree}</div>`;
```

```js
/* web/gf/render.js — target, replaces line 358 */
    return `<div class="card s-${t.status} expanded" data-task-id="${t.id}"${archMute}>${head}${body}${tree}</div>`;
```

### 5. `GF.flashCompleted` — the decoupled, render-mechanism-independent trigger

```js
/* web/gf/render.js — target, new standalone function, placed after GF.pickStatus
   (currently ending line 34) and before the GF.render = { ... } block (currently line 36) */
// One-shot "just completed" feedback, deliberately decoupled from render.panels()'s
// full innerHTML replace: that replace destroys the task's old card node and
// creates a new one already in its final (done) state, so a CSS transition on the
// outgoing node never gets an old/new pair to interpolate (see .card's
// border-left-color transition, app.css:395 — set up for exactly this and never
// fires). Call this AFTER render.panels() has already run for the same toggle. It
// waits one frame (so the freshly-rendered node is guaranteed to be attached),
// finds it by data-task-id, and toggles the .card--just-completed animation class
// (app.css). The 400 below must stay in sync with that class's animation-duration.
GF.flashCompleted = (id) => {
  requestAnimationFrame(() => {
    const el = document.querySelector(`[data-task-id="${id}"]`);
    if (!el) return;
    el.classList.add('card--just-completed');
    setTimeout(() => el.classList.remove('card--just-completed'), 400);
  });
};
```

### 6. The two call sites: capture "became done", render as normal, then flash

```js
/* web/gf/core.js — target, replaces lines 310-315 */
GF.toggleDone = (id) => {
  const t = GF.task(id); if (!t) return;
  if (!GF.can('status', t)) return GF.denyToast();
  const becameDone = t.status !== 'done';
  t.status = t.status === 'done' ? 'working' : 'done';
  GF.store.save(); GF.render.panels(); GF.render.telemetry();
  if (becameDone) GF.flashCompleted(id);
};
```

```js
/* web/gf/render.js — target, replaces the onPick line inside pickStatus
   (currently line 32) */
    onPick: (v) => { if (v !== t.status && GF.setStatus(id, v)) { GF.render.panels(); GF.render.telemetry(); if (v === 'done') GF.flashCompleted(id); } },
```

`GF.setStatus` (`core.js:302-309`, unchanged, not touched by this plan) already returns `false`
and does nothing if `t.status === status`, so `v === 'done'` immediately after a truthy
`GF.setStatus(id, v)` call can only mean the task just transitioned **into** `done` from some
other status — no separate "was it already done" check is needed here.

## Repo conventions to follow

- **No `--ease-*`/`--duration-*` token system exists in this repo yet** (confirmed: no
  `--ease-` or `--duration-` custom property anywhere in `app.css`). Plan `006`
  (`plans/006-easing-duration-tokens.md`) is expected to introduce `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`
  and `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)`. This plan uses the literal
  `cubic-bezier(0.77, 0, 0.175, 1)` value directly, per AUDIT.md — do not invent a token here.
  Once plan 006 has landed, `cubic-bezier(0.77, 0, 0.175, 1)` in `.card--just-completed`
  (added by this plan) could be swapped for `var(--ease-in-out)`, but that swap is out of
  scope for this plan and must not be made as part of it.
- **`.fac-room`'s short, comma-separated, per-property `ease` transition**
  (`web/gf/app.css:988-990`: `transition:border-color .16s ease,box-shadow .16s ease`) is the
  exemplar this plan's `.check` transition (Target section 2) imitates directly — same shape,
  same duration, same bare `ease`.
- **`--green`/`--green-soft` are this app's existing theme-aware "success" tokens**, defined
  once per skin (`web/gf/app.css:46-48`, `:134`, `:171`) — use them for any "success" color
  rather than a hardcoded hex, and never `rgba(var(--accent-rgb),…)` for a specifically-green
  effect (accent-rgb is not green in every theme — see Target section 1).
- **The single existing `@media (prefers-reduced-motion: reduce)` block**
  (`web/gf/app.css:980-984`) is where all reduced-motion handling in this repo lives — extend
  it in place (Target section 3); do not add a second `@media (prefers-reduced-motion)` block
  elsewhere in the file.
- **Task ids are already interpolated unescaped into attribute strings throughout
  `render.js`**, e.g. `onclick="event.stopPropagation();GF.toggleDone('${t.id}')"`
  (`render.js:286`). The new `data-task-id="${t.id}"` attribute (Target section 4) follows
  that same existing convention — do not wrap it in `GF.esc()`; nothing else in this file
  does for an id, and adding escaping here alone would be an inconsistent, unrequested
  change.
- **`GF.$` (`web/gf/core.js:4`: `GF.$ = (id) => document.getElementById(id);`) is this repo's
  existing single-element lookup helper**, but it is `id`-keyed and cards have no unique
  DOM `id` today (only a shared `class="card s-<status>"`). `GF.flashCompleted` therefore uses
  `document.querySelector('[data-task-id="..."]')` instead of inventing a colliding `id="..."`
  — do not add an `id` attribute to `.card` for this purpose.
- **`GF.toggleDone`/`GF.pickStatus` already call across files** (`core.js`'s `GF.toggleDone`
  already calls `GF.render.panels()`, which lives in `render.js`) — calling the new
  `GF.flashCompleted` (defined in `render.js`) from `core.js`'s `GF.toggleDone` is the same
  established cross-file calling pattern, not a new one. `web/gf/core.js` loads before
  `web/gf/render.js` (confirmed: `web/index.html:220` loads `gf/core.js`, `web/index.html:223`
  loads `gf/render.js`; the built copies `docs/GrowFlow Unified.html:259-260` and
  `docs/GrowFlow App.html:206-207` match), but since both are plain non-deferred `<script>`
  tags loaded before any user interaction is possible, `GF.flashCompleted` is always defined
  by the time a click can invoke `GF.toggleDone`.

## Steps

1. **`web/gf/render.js`** — inside `card(t)`, add `data-task-id="${t.id}"` to both wrapper
   `<div>`s: the collapsed return (currently line 305) and the expanded return (currently
   line 358), exactly as shown in Target section 4. This is a prerequisite for step 5 — do
   this first.

2. **`web/gf/app.css`** — immediately after `.card.s-pending{border-left-color:var(--ink-3)}`
   (currently line 404) and before `.card-head{...}` (currently line 405), insert the new
   `.card--just-completed` rule and the `cardComplete`/`cardCompleteReduced` `@keyframes`
   exactly as shown in Target section 1. Do not modify any of the six `.card.s-<status>`
   rules or `.card`'s own base rule (lines 393-396) — this is a wholly new, separate rule.

3. **`web/gf/app.css`** — inside the existing `@media (prefers-reduced-motion: reduce){...}`
   block (currently lines 980-984), add the one new line
   `.card--just-completed{animation-name:cardCompleteReduced}` as its own selector, after the
   three existing lines, exactly as shown in Target section 3. Do not touch the three
   existing lines in that block.

4. **`web/gf/app.css`** — replace `.check{...}` (currently lines 411-412) with the version
   shown in Target section 2 (adds `transition:background-color .16s ease,border-color .16s
   ease` as new declarations; every other declaration is unchanged). Leave
   `.check.done{background:var(--primary);border-color:var(--primary)}` (currently line 413)
   exactly as it is.

5. **`web/gf/render.js`** — immediately after `GF.pickStatus`'s closing `};` (currently ending
   line 34) and before `GF.render = {` (currently line 36), insert the new `GF.flashCompleted`
   function exactly as shown in Target section 5, including its explanatory comment.

6. **`web/gf/render.js`** — inside `GF.pickStatus`'s `GF.choose({...})` call, replace the
   `onPick` line (currently line 32:
   `onPick: (v) => { if (v !== t.status && GF.setStatus(id, v)) { GF.render.panels(); GF.render.telemetry(); } },`)
   with the version shown in Target section 6 (adds
   `if (v === 'done') GF.flashCompleted(id);` inside the same block, after the existing two
   calls). Nothing else in `GF.pickStatus` changes.

7. **`web/gf/core.js`** — replace `GF.toggleDone` (currently lines 310-315) with the version
   shown in Target section 6 (adds `const becameDone = t.status !== 'done';` before the
   existing status-flip line, and `if (becameDone) GF.flashCompleted(id);` after the existing
   `GF.store.save(); GF.render.panels(); GF.render.telemetry();` line). The status-flip logic
   itself (`t.status = t.status === 'done' ? 'working' : 'done';`) is unchanged.

## Boundaries

- Do NOT modify `GF.cycleStatus` (`core.js:295-301`) or `GF.setStatus` (`core.js:302-309`).
  `GF.cycleStatus` can also land a task on `'done'` (it cycles blindly through
  `GF.STATUS_ORDER`), and could plausibly get the same flash in a follow-up, but the brief
  for this plan scopes the fix to `GF.toggleDone` and `GF.pickStatus`'s `onPick` only — wiring
  `GF.cycleStatus` is out of scope here.
- Do NOT touch `web/gf/render.js`'s `treeRows` method (lines 367-391) or add `data-task-id` to
  `.tree-row` elements. Subtask completion goes through the same `GF.toggleDone`/
  `GF.pickStatus` functions this plan edits, but renders a `.tree-row`, not a `.card` — after
  this plan, completing a subtask from the tree will silently produce no flash (`GF.
  flashCompleted`'s `document.querySelector` finds no matching `[data-task-id]` node and the
  `if (!el) return;` guard no-ops safely — no error, just no visual feedback there). This is a
  deliberate, documented scope limit, not a bug to fix as part of this plan.
- Do NOT attempt to make `.card`'s pre-existing `border-left-color` transition
  (`app.css:395`) or the new `.check` transition (Target section 2 / Step 4) actually
  interpolate during the real click-driven `GF.toggleDone`/`GF.pickStatus` flow. Both remain
  structurally inert under the current full-`innerHTML`-replace re-render, by design — that is
  exactly why this plan adds the independent, JS-driven `.card--just-completed` flash instead
  of trying to fix those two transitions directly. Making them fire for real requires
  `render.panels()` to stop fully replacing existing DOM nodes, which is plan 001's concern,
  not this one.
- Do NOT swap the literal `cubic-bezier(0.77, 0, 0.175, 1)` value introduced in Target
  section 1 for `var(--ease-in-out)`, even if plan 006 has already landed in this tree when
  this plan is executed — that token swap is explicitly out of scope (see "Repo conventions
  to follow").
- Do NOT change markup/structure beyond the two `data-task-id` attribute additions in Step 1
  — no new wrapper elements, no new child nodes, no id attribute.
- Do NOT add any animation to the checkmark SVG glyph itself (`GF.icon('check', ...)` inside
  `.check`, `render.js:287`/`:380`) — it only exists in the DOM after a full re-render has
  already applied `.done`, so animating its appearance has the identical destroy/recreate
  problem this plan works around for the card, and was not requested.
- Do NOT add new dependencies or a build step.
- If any step's cited line numbers or current-code excerpt don't match what you find in the
  file (drift since commit `6bd1f7d`), STOP and report the mismatch instead of guessing at how
  to adapt it.

## Verification

- **Mechanical**:
  - `node --check web/gf/core.js` — must exit 0.
  - `node --check web/gf/render.js` — must exit 0.
  - `web/gf/app.css` has no syntax checker available in this repo (no build step, no
    `package.json` at the repo root). Visually confirm every rule you added or edited has
    balanced `{`/`}` and every declaration ends in `;` or is the last one in its block.
  - Open the app in a browser with DevTools' Console open. Mark a task done via the checkbox,
    then via the status-pill picker. Confirm zero new console errors or warnings from either
    action.
  - Visual diff description: before this change, clicking the checkbox or picking "Done"
    instantly swaps the card's left accent to green and fills the checkbox — no motion, no
    acknowledgment. After this change, the same instant swap happens, **plus** a brief (400ms)
    added flash on the card: a soft green ring blooms around its box-shadow and fades back
    while the card scales up ~1.5% and settles back to its original size — all within under
    half a second, and only on the card, not the checkbox (see the `.check` caveat below).
- **Feel check**:
  1. Mark a task done via its checkbox. Confirm the card visibly pulses — a soft green glow
     appears around its edge and the card grows very slightly larger then settles back —
     inside well under half a second. It should read as an acknowledgment, not a celebration:
     no bounce, no overshoot past the described values, no color outside the app's own green.
  2. Un-check a done task (click its checkbox again, sending it back to `working`). Confirm
     the flash does **not** play — only completions trigger it, not un-completions.
  3. Open the status pill on a non-done task and pick "Done" from the picker. Confirm the same
     flash plays. Then open the picker again on that now-done task and pick a different
     non-done status. Confirm **no** flash plays — only picking `'done'` triggers it.
  4. Rapid-fire the checkbox: done → not-done → done → not-done, as fast as you can click.
     Confirm the app never errors and no card is ever left stuck glowing or mid-pulse forever
     — each toggle's own `requestAnimationFrame` + `setTimeout` pair targets that toggle's own
     freshly-rendered node and cleans up after itself independently, so overlapping toggles
     never interfere with each other.
  5. In Chrome/Edge DevTools, open the **Animations** panel (More tools → Animations), set
     playback speed to 10%, then mark a task done. Confirm a `cardComplete` animation entry
     appears; scrub through it and confirm the box-shadow ring blooms in around the 40% mark
     and eases back out by 100% (not linear, no hard snap), and the scale change is barely
     perceptible (1.015×, not a jarring pop).
  6. Toggle `prefers-reduced-motion: reduce` (DevTools Rendering panel → Emulate CSS media
     feature `prefers-reduced-motion`), then mark another task done. Confirm the green
     box-shadow ring still flashes (comprehension-aiding feedback preserved) but the card no
     longer visibly changes size — the `.card--just-completed{animation-name:
     cardCompleteReduced}` override should be swapping out the scale half of the animation.
  7. With DevTools Elements panel open, mark a task done and inspect the newly-rendered card:
     confirm it carries `data-task-id="<that task's id>"` and briefly carries class
     `card--just-completed` (pause/inspect quickly, or add a temporary `debugger;` inside
     `GF.flashCompleted`'s `setTimeout` callback to catch the class removal — delete the
     `debugger;` before finishing).
  8. Confirm the checkbox itself still instantly fills solid on completion, with **no**
     visible transition during a real click — this is expected, not a bug (see Target
     section 2's caveat: the checkbox node is destroyed and recreated in its final state by
     the same full re-render as the card, so the new `.check` transition cannot yet run
     through the real click path). To confirm the CSS rule itself is correct in isolation:
     in DevTools Elements panel, select any `.check.done` element, then toggle the `done`
     class off and back on using the class-list editor (not by clicking in the app). Confirm
     the background/border color now visibly transitions over ~160ms instead of snapping.
  9. Expand a task that has subtasks and mark a subtask done from the tree row (its own
     checkbox or status pill). Confirm no error occurs and no flash plays on the subtask row —
     this is the documented Boundaries limitation (subtasks render as `.tree-row`, not
     `.card`, and have no `data-task-id` hook), not a regression to fix here.
- **Done when**: marking a top-level task done via either the checkbox or the status-picker
  plays the ~400ms green box-shadow + subtle-scale flash on the newly-rendered card exactly
  once per completion; the flash never fires on un-completion or on picking a non-done status;
  rapid toggling never leaves a card stuck glowing; `prefers-reduced-motion` keeps the color
  feedback but drops the scale; the `.check` transition is present and verified correct in
  isolation via DevTools even though it doesn't yet fire through a real click; subtask
  completions no longer error but also don't flash (documented, not fixed here); `node
  --check` passes on both `core.js` and `render.js`; and no new console errors appear from
  either completion path.
