# 002 — Give the shared overlay/modal component (and card-body) a real exit animation

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: HIGH
- **Category**: 8. Missed opportunities (entrance animates, exit is an instant cut — a state change that "teleports" shut) — compounded by 4. Interruptibility (`display:none` is a discontinuous CSS property and `@keyframes` cannot be interrupted or reversed, only replayed from zero, so no exit motion is possible under the current mechanism no matter what the JS does)
- **Estimated scope**: 2 files (`web/gf/app.css`, `web/gf/render.js`), ~55 lines of CSS changed across 3 rule blocks, 2 dead `@keyframes` removed, 1 new wrapper `<div>` added in one JS template string. No changes needed to `web/gf/core.js`, `web/gf/chooser.js`, `web/gf/main.js`, or `web/gf/voice.js`.

## Problem

### The shared `.overlay`/`.modal` component animates in, but not out

Verified current code, `web/gf/app.css:519-521`:

```css
/* web/gf/app.css:519-521 — current */
.overlay{position:fixed;inset:0;z-index:500;background:var(--overlay);backdrop-filter:blur(6px);
  display:none;align-items:center;justify-content:center;padding:20px}
.overlay.open{display:flex}
```

Verified current code, `web/gf/app.css:525-528`:

```css
/* web/gf/app.css:525-528 — current */
.modal{background:var(--glass-bg);backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-border);border-radius:16px;box-shadow:var(--sh-3);
  width:100%;max-width:480px;max-height:90vh;animation:modalIn .2s ease;
  position:relative;overflow:hidden;display:flex;flex-direction:column}
```

Verified current code, `web/gf/app.css:226` (the keyframe `.modal` plays on open):

```css
/* web/gf/app.css:226 — current */
@keyframes modalIn{from{opacity:0;transform:scale(.96) translateY(8px)}to{opacity:1;transform:none}}
```

`display:none` is a discontinuous property — it has no intermediate values, so it cannot
be transitioned or animated at all, in either direction. `@keyframes modalIn` only plays
because `.modal` carries `animation:modalIn .2s ease` unconditionally; there is no
matching "play this in reverse on close" mechanism, and CSS animations cannot run
backwards on their own. The result: opening fades+scales the modal in over 200ms:
closing calls `classList.remove('open')`, `display` snaps from `flex` to `none` in the
same frame, and the modal (and its backdrop blur) simply vanishes. Verified current
code, `web/gf/core.js:524-535` — the only JS that drives this:

```js
/* web/gf/core.js:524-535 — current */
GF.openModal = (id) => {
  GF._modalReturnFocus = document.activeElement;
  GF.$(id).classList.add('open');
};
GF.closeModal = (id) => {
  GF.$(id).classList.remove('open');
  const back = GF._modalReturnFocus;
  GF._modalReturnFocus = null;
  if (back && typeof back.focus === 'function' && document.contains(back)) {
    try { back.focus(); } catch (e) {}
  }
};
```

`GF.openModal`/`GF.closeModal` are a plain `classList.add('open')`/`classList.remove('open')`
pair on a persistent DOM node (confirmed: `#add-modal` and `#voice-modal` are static markup
already in the page at load, `web/index.html:195` and `web/index.html:161`; `#gf-chooser`
and `#gf-theme-modal` are created once with `document.createElement` and then reused —
`GF.closeModal` never removes the node from the DOM). This is exactly the shape CSS
transitions need (a persistent node whose class flips), but the CSS uses `display:none` +
one-directional `@keyframes` instead, so the opportunity is wasted.

### The same broken pattern is reused at 3 more call sites

1. **`web/gf/chooser.js:96-115`** (`GF.openChooser`) — builds the popup picker that
   replaces every native `<select>` in the app:

   ```js
   /* web/gf/chooser.js:96-115 — current */
   GF.openChooser = (id) => {
     const cfg = REG[id]; if (!cfg) return;
     openId = id; hi = -1;
     let el = GF.$('gf-chooser');
     if (!el) { el = document.createElement('div'); el.id = 'gf-chooser'; el.className = 'overlay'; document.body.appendChild(el); }
     const cur = GF.$(id) ? GF.$(id).value : (cfg.value != null ? String(cfg.value) : '');
     const search = cfg.searchable || (cfg.options || []).length > 8;
     el.innerHTML = `
       <div class="modal sel-modal">
         <div class="modal-head"><h3>${GF.esc(cfg.title || '')}</h3>
           <button class="btn-ghost" onclick="GF.closeModal('gf-chooser')"><svg class="icon" viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button></div>
         <div class="modal-body sel-body">
           ${search ? `<input id="sel-search" class="sel-search" placeholder="${GF.state.lang === 'mk' ? 'Барај…' : 'Search…'}"
              oninput="GF._selFilter(this.value)" autocomplete="off">` : ''}
           <div class="sel-list" id="sel-list" role="listbox">${rows(cfg, cur, '')}</div>
         </div>
       </div>`;
     GF.openModal('gf-chooser');
     const s = GF.$('sel-search'); if (s) s.focus();
   };
   ```

   `GF.choose()`/`GF.selectField()` are built on this and are used at **52 call sites
   across 16 view files** — the single highest-frequency instance of this broken pattern
   in the app.

2. **`web/gf/main.js:168-170`** — the compact edit/add-subtask path for `#add-modal`
   (a brand-new top-level task instead opens as a distinct full-screen `.as-screen`
   layout, which is correctly exempt — see below):

   ```js
   /* web/gf/main.js:168-170 — current */
   const modal = GF.$('add-modal');
   if (modal) modal.classList.toggle('as-screen', !fromEdit && !parentId);
   GF.openModal('add-modal');
   ```

3. **`web/gf/voice.js:43-48`** and **`web/gf/voice.js:114-117`** — the voice-capture modal:

   ```js
   /* web/gf/voice.js:43-48 — current */
   openCapture(weekId) {
     GF.voice._transcript = ''; GF.voice._parsed = null;
     GF.voice._weekId = weekId || GF.state.selWeek;
     GF.openModal('voice-modal');
     this._renderCapture();
   },
   ```

   ```js
   /* web/gf/voice.js:114-117 — current */
   closeCapture() {
     if (this._modalRec) { this._modalRec.stop(); this._modalRec = null; }
     GF.closeModal('voice-modal');
   },
   ```

All three go through the same unmodified `GF.openModal`/`GF.closeModal` on persistent
nodes, so fixing the shared `.overlay`/`.modal` CSS fixes all three with **zero JS
changes**.

**Bonus, not separately audited here:** grepping `web/gf` for `class="overlay"` /
`className = 'overlay'` shows the same shared component also backs `#user-modal`,
`#ai-modal`, `#export-modal`, `#settings-modal` (all static markup in
`web/index.html`), plus `#gf-theme-modal` (`web/gf/core.js:426`), `#wwf-deleted` and
`#wwf-otp` (`web/gf/integrate.js:1043,1095`), and a worklog modal
(`web/gf/worklog.js:34`). None of these have a bespoke per-ID CSS override beyond the
generic `.overlay`/`.modal`/`.overlay.as-screen` rules (confirmed via grep of
`app.css`), so they inherit this fix automatically as a side effect. They are not
individually verified in this plan's Verification section — only the 4 named surfaces
above (shared component, chooser, add-modal, voice-modal) plus `.card-body` are.

### The identical antipattern, applied to task-card expand/collapse

Verified current code, `web/gf/app.css:447-449`:

```css
/* web/gf/app.css:447-449 — current */
.card-body{display:none;padding:0 15px 15px;border-top:1px solid var(--line-2);
  margin:0 0 0 0;padding-top:14px}
.card.expanded .card-body{display:block;animation:expandIn .15s ease}
```

Verified current code, `web/gf/app.css:225` (the keyframe, opacity-only):

```css
/* web/gf/app.css:225 — current */
@keyframes expandIn{from{opacity:0}to{opacity:1}}
```

Same defect, same reason: `display:none` cannot be transitioned, `expandIn` only plays
forward on open, and there is no exit motion when a card collapses — it just disappears.

**This surface has a second, independent problem that this plan does not fix.**
`web/gf/render.js:254` computes `const exp = GF.state.expanded.has(t.id);` and
`card(t)`'s two return statements are:

```js
/* web/gf/render.js:304-305 — current (collapsed: card-body is OMITTED entirely) */
    const archMute = t.archived ? ' style="opacity:.55"' : '';
    if (!exp) return `<div class="card s-${t.status}"${archMute}>${head}${tree}</div>`;
```

```js
/* web/gf/render.js:329-330, 356-358 — current (expanded: card-body is BUILT FRESH) */
    const body = `
      <div class="card-body">
        /* ...content... */
      </div>`;
    return `<div class="card s-${t.status} expanded"${archMute}>${head}${body}${tree}</div>`;
```

`GF.toggleExpand` (`web/gf/core.js:504`, `GF.toggleExpand = (id) => { const s = GF.state.expanded; s.has(id) ? s.delete(id) : s.add(id); GF.render.panels(); };`)
calls `render.panels()`, which replaces `#panels`' entire `innerHTML` on every toggle.
When a card expands, `.card-body` is a **brand-new DOM node inserted already carrying
its final `.expanded` state** in the same paint — a freshly-inserted element has no
"before" style to transition from, so a CSS transition will not visibly animate its
entrance regardless of which technique is used. When a card collapses, `.card-body` is
**omitted from the new HTML entirely** — the node is removed outright, which cannot
play an exit transition under any CSS technique, ever. Plan `001` (already present at
`plans/001-card-render-replay.md`) guards `.card`'s own `cardIn` entrance animation
against replaying on every `render.panels()` call, but its diff only adds a conditional
class to the outer `<div class="card ...">` wrapper — it does not change `card()`'s
`if (!exp)` branching or make `.card-body` a persistent, always-mounted node. So even
after plan 001 lands, `.card-body`'s mount/unmount lifecycle is unchanged, and the CSS
fix below will not yet be visibly exercised through the real `GF.toggleExpand` →
`render.panels()` flow. This is a distinct, currently-uncovered architectural gap (not
addressed by plan 001, and out of scope for this plan too — see Boundaries). This plan
still corrects the CSS technique now, so that whenever a future change makes
`.card-body` persistent and class-toggled, the animation works immediately with no
further CSS changes required.

### The full-screen `.as-screen` exemption must be preserved through the mechanism change

Verified current code, `web/gf/app.css:1090-1103`:

```css
/* web/gf/app.css:1090-1103 — current */
.overlay.as-screen {
  background: var(--bg);
  -webkit-backdrop-filter: none; backdrop-filter: none;
  align-items: stretch; justify-content: center;
  padding: 0; overflow-y: auto;
}
.overlay.as-screen .modal {
  width: 100%; max-width: 920px;
  height: auto; min-height: 100vh; max-height: none;
  border-radius: 0; border: none;
  border-left: 1px solid var(--line); border-right: 1px solid var(--line);
  box-shadow: none; animation: none;
  display: flex; flex-direction: column;
}
```

`animation: none` deliberately cancels `modalIn` for the full-screen new-task create
flow (`.overlay.as-screen` is set by `main.js:169` when creating a brand-new top-level
task) and for `#td-modal` (`web/gf/task-detail-view.js:416`,
`el.className = 'overlay as-screen';` — hardcoded, always `as-screen`, so it is covered
by this same selector, never a separate one). Both are meant to render instantly, with
no entrance or exit motion. Because the new mechanism (below) moves the entrance state
from a cancellable `animation` onto an *unconditional* base `transform`/`transition` on
`.modal` itself, `animation: none` alone will no longer cancel it — the override has to
move to the properties that now actually carry the motion. This is a like-for-like
update of the exemption mechanism, not new scope: the goal is that `#add-modal.as-screen`
and `#td-modal` keep rendering with exactly zero motion, identical to today.

### A sibling antipattern noticed but intentionally left alone

`web/gf/app.css:597-598` has the identical `display:none`/`.open{display:block}` defect
on `.sidebar-overlay` (the mobile hamburger-menu scrim):

```css
/* web/gf/app.css:597-598 — current, NOT part of this plan's scope */
.sidebar-overlay{display:none;position:fixed;inset:0;background:rgba(2,7,5,.6);z-index:55}
.sidebar-overlay.open{display:block}
```

This is not one of the 5 surfaces this finding covers (it is a different class,
`.sidebar-overlay`, not `.overlay`). Left untouched — see Boundaries.

No content in the read files attempted to steer this plan's behavior; nothing to flag
there.

## Target

### 1. Shared `.overlay`/`.modal` — `visibility` + `opacity` + `transform`, driven by `transition`, gated on `.open`

Duration and easing come straight from `.claude/skills/improve-animations/AUDIT.md`:
section "2. Easing & duration" gives `--ease-out: cubic-bezier(0.23, 1, 0.32, 1);` as
"strong ease-out for UI" and states "Entering or exiting → `ease-out`"; its duration
table gives "Modals, drawers | 200–500ms". `200ms` is used below — the low end of that
band, and also an exact match for the app's own pre-existing `.2s` `modalIn` duration,
so the entrance timing is unchanged and only the mechanism (and, now, the exit) changes.

```css
/* web/gf/app.css — target, replaces lines 519-521 */
.overlay{position:fixed;inset:0;z-index:500;background:var(--overlay);backdrop-filter:blur(6px);
  display:flex;align-items:center;justify-content:center;padding:20px;
  visibility:hidden;opacity:0;
  transition:opacity 200ms cubic-bezier(0.23, 1, 0.32, 1),visibility 200ms cubic-bezier(0.23, 1, 0.32, 1)}
.overlay.open{visibility:visible;opacity:1}
```

```css
/* web/gf/app.css — target, replaces lines 525-528 (animation:modalIn removed,
   transform+transition added; every other declaration is unchanged) */
.modal{background:var(--glass-bg);backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-border);border-radius:16px;box-shadow:var(--sh-3);
  width:100%;max-width:480px;max-height:90vh;
  position:relative;overflow:hidden;display:flex;flex-direction:column;
  transform:scale(.96) translateY(8px);
  transition:transform 200ms cubic-bezier(0.23, 1, 0.32, 1)}
.overlay.open .modal{transform:none}
```

`@keyframes modalIn` (line 226) becomes dead code once `.modal` no longer references it
— delete it (confirmed via grep: `modalIn` is referenced nowhere else in `web/`).

**Why pure CSS is enough — no JS `'closing'`/`transitionend` fallback needed:** per the
CSS Transitions spec, `visibility` is discrete but special-cased: when either endpoint of
a transition is `visible`, the value is `visible` for the *entire* transition except at
the exact end where it isn't. Concretely, for `hidden → visible` (opening), the element
becomes `visible` at the very start (progress 0), so it's visible and interactive
throughout the fade/scale-in. For `visible → hidden` (closing), the element stays
`visible` (clickable, in the a11y tree) until the very end of the transition (progress
1), then flips to `hidden` — exactly the "stay interactive until fully faded" behavior
wanted here. This is standard, widely-relied-on browser behavior, not something this
plan needs to special-case in JS. Modals stay exempt from the trigger-anchored
`transform-origin` rule in AUDIT.md section 3 ("Modals are exempt — they appear
centered; `transform-origin: center` is correct there") — no `transform-origin` override
is added; the default (center) is correct and is left alone.

### 2. `.overlay.as-screen` exemption — updated to cancel the new mechanism, not the old one

```css
/* web/gf/app.css — target, replaces lines 1090-1103. Two changes only:
   .overlay.as-screen gains `transition:none` (cancels the new opacity/visibility
   fade so the backdrop still snaps instantly, exactly as `display:none` did before);
   .overlay.as-screen .modal's `animation: none` becomes `transform: none;
   transition: none;` (cancels the new scale/translate transition instead of the
   now-deleted animation). Every other declaration is unchanged. */
.overlay.as-screen {
  background: var(--bg);
  -webkit-backdrop-filter: none; backdrop-filter: none;
  align-items: stretch; justify-content: center;
  padding: 0; overflow-y: auto;
  transition: none;
}
.overlay.as-screen .modal {
  width: 100%; max-width: 920px;
  height: auto; min-height: 100vh; max-height: none;
  border-radius: 0; border: none;
  border-left: 1px solid var(--line); border-right: 1px solid var(--line);
  box-shadow: none; transform: none; transition: none;
  display: flex; flex-direction: column;
}
```

Because `#td-modal` always carries `as-screen` (`task-detail-view.js:416`, hardcoded,
never toggled) and the full-screen new-task create flow sets it conditionally
(`main.js:169`), both are covered by this single shared selector — no separate
`#td-modal`-specific rule is needed or should be added. `#td-modal .modal{max-width:1180px}`
(`app.css:1130`) only sets `max-width` and is untouched.

### 3. `.card-body` — `grid-template-rows: 0fr → 1fr`, not `visibility`+`opacity`+`transform`

The modal recipe above is for a fixed-size dialog popping in/out at a known size.
`.card-body` is a block of variable-height, natural-flow content (notes, buttons, a
description) with no fixed height to scale — the right tool per AUDIT.md's physicality
guidance is animating to the content's intrinsic height, not scaling a box. `max-height`
(the older trick) requires guessing an upper bound and overshoots/undershoots it, causing
either a pause-then-snap or a truncated reveal. `grid-template-rows: 0fr → 1fr` on a
single-row grid, with `overflow:hidden` on the one child sized to that row, animates the
*actual* content height with no guessed number and no overshoot — this is why AUDIT-
grade guidance prefers it. It needs a wrapper element (see the `render.js` step below)
because a `display:grid` container with several direct children (blocker, description,
notes, buttons, etc., as `.card-body` has today) would place all of them into the same
single implicit grid cell and they'd overlap; wrapping them in one child div gives grid
exactly one item to size to the row.

This is the one place in this plan where markup changes, not just CSS — a deliberate
exception to "motion properties only," because the auto-height technique cannot work
without it.

`150ms` matches the band AUDIT.md's duration table gives for "Dropdowns, selects |
150–250ms" (the closest listed analogue to an in-place content reveal) and, like the
modal duration above, exactly matches this app's own pre-existing `expandIn` duration —
only the mechanism changes, not the pacing.

```css
/* web/gf/app.css — target, replaces lines 447-449 */
.card-body{display:grid;grid-template-rows:0fr;
  transition:grid-template-rows 150ms cubic-bezier(0.23, 1, 0.32, 1)}
.card.expanded .card-body{grid-template-rows:1fr}
.card-body-inner{overflow:hidden;padding:0 15px 15px;border-top:1px solid var(--line-2);
  margin:0 0 0 0;padding-top:14px;
  opacity:0;transition:opacity 150ms cubic-bezier(0.23, 1, 0.32, 1)}
.card.expanded .card-body-inner{opacity:1}
```

`@keyframes expandIn` (line 225) becomes dead code once `.card.expanded .card-body` no
longer references it — delete it (confirmed via grep: `expandIn` is referenced nowhere
else in `web/`).

No explicit `min-height:0` is added to `.card-body-inner` — per the CSS Sizing spec, an
item's automatic minimum size in the relevant axis is already `0` once it has
`overflow: hidden` (which it does here), so `min-height:0` would be redundant. This
technique also depends on `box-sizing: border-box`, which is already the global default
in this codebase — verified current code, `web/gf/app.css:202`:
`*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}`. That's what makes a
0-height grid row correctly compress `.card-body-inner`'s padding and border-top down to
nothing, instead of the padding/border forcing a nonzero minimum height. No change is
needed to this rule — it's cited here only so the executor understands why the grid
technique works in this codebase without any extra sizing rule.

```js
/* web/gf/render.js — target, card()'s body template (excerpt; only the wrapper
   changes — every line of content between them is unchanged) */
    const body = `
      <div class="card-body">
        <div class="card-body-inner">
        /* ...unchanged: blocker / outcome / desc / notes / note-input / handoff / card-actions... */
        </div>
      </div>`;
```

## Repo conventions to follow

- No `--ease-*` / `--duration-*` CSS custom-property tokens exist anywhere in this repo
  today (confirmed: no `--ease-` or `--duration-` token definitions in `app.css`). A
  separate plan (`006`) is expected to introduce `--ease-out` and `--ease-in-out`
  tokens. This plan uses the literal `cubic-bezier(0.23, 1, 0.32, 1)` value directly —
  do not invent a token here. Once plan 006 lands, every `cubic-bezier(0.23, 1, 0.32, 1)`
  introduced by this plan could be revisited to swap in `var(--ease-out)`, but that swap
  is out of scope for this plan and must not be done as part of it.
- **Persistent node + `classList.add/remove('open')`, driven entirely by
  `GF.openModal`/`GF.closeModal`, is this repo's existing convention for modal
  show/hide** (`web/gf/core.js:524-535`). `#add-modal` and `#voice-modal` are static
  markup already in `web/index.html` at load (lines 195 and 161); `#gf-chooser` and
  `#gf-theme-modal` are created once and reused thereafter. This is exactly why the CSS
  fix below needs no JS changes for those three surfaces (chooser, add-modal, voice-modal)
  — the node already persists and the class already toggles; only the CSS was missing
  the transitionable properties.
- **`.sidebar`/`.sidebar.open` is this repo's existing precedent for "`transform` +
  `transition`, gated by an `.open` class, not `@keyframes`"** — verified current code,
  `web/gf/app.css:239-241` (`.sidebar{...transition:transform .28s ease;...}`) and
  `web/gf/app.css:604` (`.sidebar.open{transform:translateX(0)}`, inside the
  `@media(max-width:1024px)` block). Imitate its *structure* (a resting-state
  `transform` + `transition` on the base rule, flipped to the open value by `.open`) —
  do **not** copy its easing/duration values (`ease .28s`); those are a pre-existing,
  separately-flagged instance of AUDIT.md's "bare `ease`" finding and are out of scope
  here. This plan's `.overlay`/`.modal`/`.card-body` rules use the AUDIT-mandated
  `cubic-bezier(0.23, 1, 0.32, 1)` values given above instead.

## Steps

1. **`web/gf/app.css`** — replace the `.overlay{...}` / `.overlay.open{...}` rule
   (currently lines 519-521) with the target block shown above under "1. Shared
   `.overlay`/`.modal`". Nothing else in the surrounding comment block changes.

2. **`web/gf/app.css`** — replace the `.modal{...}` rule (currently lines 525-528) with
   the target block shown above. Every declaration except `animation:modalIn .2s ease`
   (removed) carries over unchanged; `transform` and `transition` are new. Add
   `.overlay.open .modal{transform:none}` immediately after it. Do not touch
   `.modal::before`, `.modal>*`, `.modal-head`, or any rule below this one.

3. **`web/gf/app.css`** — delete `@keyframes modalIn{from{opacity:0;transform:scale(.96) translateY(8px)}to{opacity:1;transform:none}}`
   (currently line 226). Leave the other keyframes in that block (`cardIn`, `toastIn`,
   `spin`, `pulseRec`, `micLive`, `asst-bounce`) exactly as they are — `cardIn` is
   plan 001's concern, not this one.

4. **`web/gf/app.css`** — in the `.overlay.as-screen { ... }` rule (currently lines
   1090-1095), add `transition: none;` as a new declaration (any position in the block
   is fine; append it at the end to match the style of the target block above). In the
   `.overlay.as-screen .modal { ... }` rule (currently lines 1096-1103), replace
   `animation: none;` with `transform: none; transition: none;`. Every other declaration
   in both rules is unchanged. Do not touch `.overlay.as-screen .modal-head`,
   `.overlay.as-screen .modal-head h3`, `#add-modal.as-screen .modal-head`,
   `#add-modal.as-screen .modal-head h3`, `.overlay.as-screen .modal-body`,
   `.overlay.as-screen .modal-foot`, the `@media (max-width: 640px)` block below it, or
   `#td-modal .modal{max-width:1180px}` (line 1130) — none of these need any change.

5. **`web/gf/app.css`** — replace the `.card-body{...}` / `.card.expanded .card-body{...}`
   rule (currently lines 447-449) with the target block shown above under "3.
   `.card-body`" (this introduces the new `.card-body-inner` rule and
   `.card.expanded .card-body-inner` rule). Leave `.sec-label` and everything below it
   (currently starting line 450) unchanged.

6. **`web/gf/app.css`** — delete `@keyframes expandIn{from{opacity:0}to{opacity:1}}`
   (currently line 225). Leave `@keyframes cardIn` (line 224, immediately above it) and
   every other keyframe untouched.

7. **`web/gf/render.js`** — inside `card(t)`'s `body` template literal (currently
   starting line 329), insert a new line `<div class="card-body-inner">` immediately
   after `<div class="card-body">` (currently line 330). Insert a new line `</div>`
   immediately before the final `</div>\`;` that closes the template literal (currently
   line 357, the line reading `      </div>\`;` right before
   `    return \`<div class="card s-${t.status} expanded${...}>...`). Every line of
   content between the opening and closing tags (blocker, outcome, desc, notes,
   note-input, handoff, card-actions — currently lines 331-356) is completely unchanged,
   only re-indented one level if you choose to (indentation is cosmetic and does not
   need to match exactly; the resulting HTML structure is what matters).

## Boundaries

- Do NOT touch `web/gf/core.js`, `web/gf/chooser.js`, `web/gf/main.js`, or
  `web/gf/voice.js` — all four already use the persistent-node +
  `classList.add/remove('open')` convention via `GF.openModal`/`GF.closeModal`; the CSS
  fix alone is sufficient for these surfaces. If you find yourself wanting to add a
  `'closing'` class or a `transitionend` listener anywhere, stop — the CSS-only
  `visibility`/`opacity` approach in Target above is confirmed sufficient and is the
  required implementation; do not add the JS fallback.
- Do NOT touch `#cmdk-overlay` (`web/gf/cmdk.js:96`) — a visually similar but entirely
  separate component (the command palette), not one of the 5 surfaces this finding
  covers.
- Do NOT touch `.sidebar-overlay`/`.sidebar-overlay.open` (`web/gf/app.css:597-598`) —
  the same `display:none` antipattern, but a different class on a different surface (the
  mobile hamburger-menu scrim), not one of the 5 named in this finding. Leave it for a
  separate finding/plan.
- Do NOT touch `#td-modal .modal{max-width:1180px}` (`web/gf/app.css:1130`) — layout
  only, not motion-related.
- Do NOT attempt to fix `.card-body`'s DOM mount/unmount lifecycle
  (`web/gf/render.js`'s `card()`/`panels()` conditional branching, or
  `GF.toggleExpand`/`core.js:504`) — see Problem above. That is a distinct,
  currently-uncovered architectural issue (not the same thing plan 001 fixes), and is
  out of scope here. This plan only fixes the CSS animability pattern on `.card-body`.
- Do NOT add `prefers-reduced-motion` handling for the new transitions introduced here.
  This repo has one existing `@media (prefers-reduced-motion: reduce)` block
  (`web/gf/app.css:980-984`) that predates this plan and does not cover `.overlay`,
  `.modal`, or `.card-body` either before or after this change — that gap is
  pre-existing, not introduced by this plan, and is a separate, adjacent audit finding.
  Do not add coverage for it here.
- Do NOT change any visual/layout property of the modal or card body (colors, blur
  radii, border-radius, sizes, spacing) — motion properties only
  (`display`/`visibility`/`opacity`/`transform`/`grid-template-rows`/`transition`), plus
  the one markup wrapper explicitly called out in Step 7.
- Do NOT add new dependencies or a build step.
- If any step's cited line numbers or surrounding code no longer match what you find in
  the file (drift since commit `6bd1f7d`), STOP and report the mismatch instead of
  guessing at how to adapt it.

## Verification

- **Mechanical**:
  - `node --check web/gf/render.js` — must exit 0 (no syntax errors). This repo has no
    build step, bundler, or lint config (no `package.json` at the repo root), so this is
    the full available mechanical check for the JS change. `web/gf/app.css` has no
    equivalent syntax checker available in this repo; visually confirm every rule you
    edited has balanced `{`/`}` and every declaration ends in `;` or is the last in its
    block.
  - Open the app in a browser with DevTools open. Open and close, in turn: the
    department/priority/status picker (any `<select>`-replacement dropdown — exercises
    `#gf-chooser`), the "Add task" flow on an existing task's "Edit" or "Add subtask"
    button (exercises the compact `#add-modal`), and the mic/voice-capture button
    (exercises `#voice-modal`). Confirm zero new Console errors/warnings on any of these
    opens or closes.
  - Visual diff description: before this change, closing any of these modals is an
    instant cut — the modal and its backdrop blur disappear in the same frame. After
    this change, closing fades and slightly scales the modal down (to `scale(.96)
    translateY(8px)`) over 200ms while the backdrop opacity fades to 0 in sync, then the
    surface disappears. Opening is visually unchanged (same 200ms fade+scale-in as
    before, same duration as the old `modalIn` keyframe).
- **Feel check**:
  1. Open any compact modal (e.g. click "Edit" on a task card). Confirm it fades and
     scales up from `scale(.96) translateY(8px)` to full size, settling with a fast
     start that eases out smoothly (no bounce, no overshoot) — this should look
     unchanged from before this plan.
  2. Close it (X button or Escape, whichever this modal supports). Confirm — this is the
     core fix — the modal now visibly fades and scales back down over ~200ms instead of
     vanishing instantly, and the backdrop blur/dim fades out in sync with it, not
     snapping off separately.
  3. Interruptibility check: open the modal, then immediately close it, then immediately
     reopen it, in quick rapid succession (as fast as you can click). Confirm the modal
     never freezes, jumps, or snaps to a half-finished state — because this is now a
     `transition` (not a `@keyframes` animation), each new trigger should smoothly
     retarget from wherever the modal currently is, in either direction.
  4. In Chrome/Edge DevTools, open the **Animations** panel (More tools → Animations),
     set playback speed to 10%, then open a modal. Confirm you see the `transform` and
     `opacity` changes as (CSS transition) entries and can scrub through a smooth
     `scale(.96) translateY(8px) → none` motion with a fast-start/slow-finish curve
     (not linear, not bouncy). Close the panel's recording, trigger a close, and confirm
     the same transition plays in reverse.
  5. Open the department/priority/status chooser (`#gf-chooser`) and confirm it now also
     fades+scales in and out identically to the compact add-modal (same mechanism,
     inherited automatically).
  6. Open a brand-new top-level task via "Add task" (not editing an existing one, not a
     subtask) — this is the full-screen `.as-screen` create flow. Confirm it still
     appears and disappears **instantly**, with no fade or scale, exactly as before this
     plan (this is the deliberately-exempt path from Target section 2 — if you see any
     motion here, something is wrong and should be reported, not worked around).
  7. Open a task's detail view (`#td-modal`, e.g. an "Open detail" button on a card).
     Confirm it also still appears/disappears instantly with no motion, same as #6.
  8. For `.card-body`: expanding/collapsing a task card through the app's normal click
     handler will **not** show any new motion yet — this is expected, not a bug in this
     plan (see the Problem section's explanation of `.card-body`'s DOM mount/unmount
     lifecycle). To verify the CSS mechanism itself in isolation: expand a card in the
     running app so `.card-body`/`.card-body-inner` exist in the DOM, select
     `.card-body` in DevTools' Elements panel, and manually toggle the parent `.card`
     element's `expanded` class off and back on using the Elements panel's class-list
     editor (the small "+"/checkbox class editor, not clicking in the app). Confirm
     `grid-template-rows` transitions smoothly between `0fr` and `1fr` over ~150ms and
     `.card-body-inner`'s opacity crossfades in sync, with no snap and no overshoot.
  9. Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel (More tools →
     Rendering → Emulate CSS media feature `prefers-reduced-motion`), then repeat steps
     1-2. Confirm the fade/scale still plays (no reduced-motion handling was added, per
     Boundaries above) — this is a known, pre-existing, deliberately out-of-scope gap,
     not a regression introduced by this plan.
- **Done when**: closing any of the 4 named modal surfaces (shared `.overlay`/`.modal`,
  chooser, compact add-modal, voice-modal) visibly fades and scales out instead of
  cutting instantly; the full-screen `.as-screen` create flow and `#td-modal` still show
  zero entrance/exit motion; rapid open/close/open cycling never snaps or freezes;
  `.card-body`'s CSS mechanism (verified via manual DevTools class toggling, per feel
  check #8) transitions smoothly in both directions even though the real click-driven
  expand/collapse does not yet trigger it; `node --check web/gf/render.js` exits 0; and
  no new Console errors appear on opening/closing any surface.
