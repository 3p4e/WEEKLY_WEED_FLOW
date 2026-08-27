# 003 — Anchor the popup-chooser scale animation to its trigger, not viewport center

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: HIGH
- **Category**: 3. Physicality & origin
- **Estimated scope**: 1 file (`web/gf/chooser.js`), ~18 lines added inside one function (`GF.openChooser`), 0 lines removed, no CSS changes

## Problem

`web/gf/chooser.js` implements the app's popup chooser — the replacement for
every native `<select>` in the app (per the file's own header comment, line
1: `chooser.js — popup chooser replacing native <select> dropdowns
app-wide`). It backs every status pill, department/priority/assignee field,
and select-style input across the product: `grep -rn "GF\.selectField("
web/` returns 48 raw hits, one of which is `chooser.js`'s own doc comment
(not a call), leaving `GF.selectField` genuinely called 47 times across 15
view files (`web/gf/integrate.js`, `main.js`, `dept-templates.js`,
`decon-view.js`, `render.js`, `intake-view.js`, `qcsample-view.js`,
`cultivation-view.js`, `task-extras.js`, `collab.js`, `audit-view.js`,
`harvest-view.js`, `waste-view.js`, `facility-view.js`,
`document-view.js`), plus the imperative `GF.choose()` path used by every
task card's status pill (`web/gf/render.js:25-34`, `GF.pickStatus`).

Every one of those pickers always scales in from the exact center of the
viewport, never from the element the user actually clicked to open it.
Verified current code, `web/gf/chooser.js:96-115` (`GF.openChooser`, the
one function all of the above ultimately call):

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

(Note on citation: the finding this plan was written from quoted this
function truncated at line 113 with a `...` — the verified full function
actually runs to line 115, three more lines than the truncated excerpt
implied. That is a citation-truncation artifact, not code drift; the body
above is the complete, currently-live function, confirmed against the file
on disk.)

There is no `getBoundingClientRect()` call anywhere in `chooser.js`
(confirmed: `grep -n "getBoundingClientRect" web/gf/chooser.js` → no
matches) and no positioning/anchoring logic of any kind — the popup is
simply a full-viewport flex-centered overlay. Verified current code,
`web/gf/app.css:519-521`:

```css
/* web/gf/app.css:519-521 — current */
.overlay{position:fixed;inset:0;z-index:500;background:var(--overlay);backdrop-filter:blur(6px);
  display:none;align-items:center;justify-content:center;padding:20px}
.overlay.open{display:flex}
```

`.sel-modal` (the chooser's own modal box) only ever narrows the max-width —
it inherits `.modal`'s entrance animation and adds no positioning of its
own. Verified current code, `web/gf/app.css:525-528` (`.modal`) and
`web/gf/app.css:822` (`.sel-modal`):

```css
/* web/gf/app.css:525-528 — current */
.modal{background:var(--glass-bg);backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-border);border-radius:16px;box-shadow:var(--sh-3);
  width:100%;max-width:480px;max-height:90vh;animation:modalIn .2s ease;
  position:relative;overflow:hidden;display:flex;flex-direction:column}
```

```css
/* web/gf/app.css:822 — current */
.sel-modal{max-width:420px}
```

```css
/* web/gf/app.css:226 — current (the keyframe .modal's animation plays) */
@keyframes modalIn{from{opacity:0;transform:scale(.96) translateY(8px)}to{opacity:1;transform:none}}
```

No `transform-origin` is declared on `.modal`, `.sel-modal`, `.overlay`, or
any chooser-related selector anywhere in the codebase. Verified: `grep -rn
"transform-origin" web/` returns exactly 4 matches in the entire app, and
all 4 are unrelated to modals/choosers — `web/gf/app.css:940` (an SVG gauge
needle, `transform-origin:bottom center`), `web/gf/leaf-fx.css:17`
(`transform-origin:50% 82%`, a decorative leaf effect), `web/gf/brand.css:56`
(`transform-origin: 50% 80%`), and `web/gf/entry.css:95`
(`transform-origin: center top`). With no `transform-origin` declared, every
browser's initial value (`50% 50%`, i.e. the element's own center) applies —
so the `scale(.96) → scale(1)` grow in `modalIn` always pivots around the
center of the `.sel-modal` box itself, which `.overlay`'s flex-centering has
already placed at the center of the viewport. The result: a status pill
click at the bottom-right of the screen, or a dropdown field near the top of
a long form, both produce the exact same visual — the popup blooming
outward from dead-center screen, with no visual connection to where the
user's attention (and cursor) actually was.

This is a category-3 (Physicality & origin) finding per
`.claude/skills/improve-animations/AUDIT.md`, section 3: "Popovers/dropdowns/tooltips
scale from their trigger, not center: `.popover { transform-origin:
var(--transform-origin); } /* Base UI */`" — with the explicit carve-out
"Modals are exempt — they appear centered; `transform-origin: center` is
correct there. Do not report it." The chooser reuses the `.modal` CSS class
for styling convenience, but functionally it is a dropdown/select
replacement (per its own header comment), not a genuine modal dialog — it is
exactly the trigger-anchored case the AUDIT calls out, not the exempt case.

Separately, the same AUDIT section's scale floor is already satisfied and
does not need changing: `modalIn`'s `scale(.96)` starting value falls inside
the AUDIT's required `scale(0.9–0.97)` range (never `scale(0)`), so no part
of this plan touches that keyframe, its `.2s` duration, or its `ease`
timing — this plan changes only the pivot point the existing scale animates
around, nothing about the animation's timing or curve.

No content in `chooser.js`, `app.css`, `AUDIT.md`, or `PLAN-TEMPLATE.md`
attempted to steer this plan's behavior; nothing to flag as an oddity.

## Target

`GF.openChooser` captures the DOM element that was actually clicked to open
it (the field's `.sel-btn` button, or — for the imperative `GF.choose()`
path used by e.g. the task-card status pill — the `.pill` span), and after
the popup is built and shown, computes that element's on-screen center
relative to the popup's own box and writes it as an inline
`transform-origin` style on `.sel-modal`. The popup's size and final
centered position are unchanged; only the point the `scale(.96) → scale(1)`
grow pivots around changes, so it visibly grows from the trigger toward its
centered resting place instead of blooming from a fixed, click-independent
center point.

```js
/* web/gf/chooser.js — target, GF.openChooser (full function) */
  GF.openChooser = (id) => {
    const cfg = REG[id]; if (!cfg) return;
    openId = id; hi = -1;
    // Anchor the entrance scale on whatever the user actually clicked to get
    // here — the field's .sel-btn button, or (for the imperative GF.choose()
    // path, e.g. GF.pickStatus's status pill) the .pill span. window.event
    // still refers to that live click event here: GF.openChooser only ever
    // runs synchronously inside an inline onclick handler — either directly
    // (the .sel-btn's own onclick) or one call deeper through
    // GF.choose → GF.pickStatus — with no async gap in between, so
    // .currentTarget has not been reset to null yet by the time we read it.
    const ev = window.event;
    const trigger = ev ? (ev.currentTarget || ev.target) : null;
    const triggerRect = trigger ? trigger.getBoundingClientRect() : null;
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
    // The popup's own box position/size isn't known until it's laid out, so
    // this has to run AFTER GF.openModal() flips .overlay to display:flex —
    // but still in this same synchronous tick, before the browser paints the
    // animation's first frame. transform-origin is expressed in the
    // element's OWN local coordinate space (0,0 = its own top-left corner),
    // so the trigger's viewport-space center must be converted into an
    // offset from the popup's box, not used as a raw viewport coordinate.
    if (triggerRect) {
      const modalEl = el.querySelector('.sel-modal');
      const modalRect = modalEl.getBoundingClientRect();
      const originX = (triggerRect.left + triggerRect.width / 2) - modalRect.left;
      const originY = (triggerRect.top + triggerRect.height / 2) - modalRect.top;
      modalEl.style.transformOrigin = `${originX}px ${originY}px`;
    }
    const s = GF.$('sel-search'); if (s) s.focus();
  };
```

When `triggerRect` is unavailable (e.g. `GF.openChooser` is ever invoked
programmatically with no live click event behind it), no inline style is
set and the browser's default `transform-origin: 50% 50%` applies — exactly
today's behavior — so this degrades safely rather than breaking anything.

## Repo conventions to follow

- No `--ease-*` / `--duration-*` CSS custom-property tokens exist anywhere
  in this repo today (confirmed: no `--ease-` or `--duration-` token
  definitions in `app.css`). A separate plan (`006`) is expected to
  introduce `--ease-out` and `--ease-in-out` tokens. This plan does not add
  or change any easing/duration value at all — `modalIn`'s existing `.2s
  ease` timing (`web/gf/app.css:226`) is left completely untouched, and no
  new transition/animation declaration is introduced — so there is nothing
  in this plan to swap onto a token. If it is ever revisited after plan 006
  lands, that would only ever be a no-op check (this plan introduces zero
  easing/duration literals), not an actual required swap.
- Inline JS-computed styles on a freshly-built element are an established
  pattern already used one function away in this same file. Exemplar,
  `web/gf/chooser.js:83-88` (the `rows()` helper, called by `GF.openChooser`
  itself), which builds `style="background:${GF.esc(o.color)}"` inline per
  row from JS-known data rather than adding a CSS class per color. The
  `modalEl.style.transformOrigin = ...` line in Target above follows the
  same shape: a value only known at runtime, set directly as an inline
  style rather than invented as a new CSS rule.
- `window.event` / `event.currentTarget` as a way of recovering "what was
  clicked" has no prior exemplar in this codebase to imitate — the closest
  existing convention is the inline `onclick="event.stopPropagation();..."`
  pattern used at every card's status pill and elsewhere (e.g.
  `web/gf/render.js:297`, `:388`, `web/gf/myday-view.js:42`), which already
  relies on the browser's implicit `event` binding inside inline handler
  attributes — this plan's use of `window.event` inside `GF.openChooser`
  itself is the same underlying object, just read one function-call deeper
  than those existing call sites reach, so it stays consistent with how
  this codebase already leans on the live event rather than threading an
  explicit parameter through every caller.

## Steps

1. **`web/gf/chooser.js`** — inside `GF.openChooser` (currently lines
   96-115), immediately after the existing line `openId = id; hi = -1;` and
   before the existing line `let el = GF.$('gf-chooser');`, insert the
   trigger-capture block:
   ```js
   const ev = window.event;
   const trigger = ev ? (ev.currentTarget || ev.target) : null;
   const triggerRect = trigger ? trigger.getBoundingClientRect() : null;
   ```
   including the explanatory comment shown above it in Target. Nothing else
   in the function changes at this step.

2. **`web/gf/chooser.js`** — still inside `GF.openChooser`, immediately
   after the existing line `GF.openModal('gf-chooser');` and before the
   existing line `const s = GF.$('sel-search'); if (s) s.focus();`, insert
   the origin-setting block:
   ```js
   if (triggerRect) {
     const modalEl = el.querySelector('.sel-modal');
     const modalRect = modalEl.getBoundingClientRect();
     const originX = (triggerRect.left + triggerRect.width / 2) - modalRect.left;
     const originY = (triggerRect.top + triggerRect.height / 2) - modalRect.top;
     modalEl.style.transformOrigin = `${originX}px ${originY}px`;
   }
   ```
   including its explanatory comment shown above it in Target. The
   `el.innerHTML = ...` template literal itself, and every other line in the
   function (the `cfg`/`el`/`cur`/`search` declarations, the modal markup,
   the final focus line), stay byte-for-byte unchanged.

No other function in `chooser.js`, and no other file, needs any edit — the
fix is fully contained in these two insertions inside `GF.openChooser`.

## Boundaries

- Do NOT touch any of the 47 `GF.selectField(...)` call sites or the one
  `GF.choose(...)` call site (`web/gf/render.js:29`, inside
  `GF.pickStatus`) — none of them need to change; the fix lives entirely
  inside `GF.openChooser` and works for both call patterns without any
  caller passing anything new through.
- Do NOT touch `GF.selectField`, `GF.chipField`, `GF.pickChip`,
  `GF.syncSelect`, the `rows()` helper, `GF.choose`, `GF._selFilter`,
  `GF.pickSel`, or the `keydown` listener at the bottom of the file — only
  `GF.openChooser` changes.
- Do NOT touch `web/gf/app.css` — `.overlay`, `.modal`, `.sel-modal`, and
  `modalIn` all stay exactly as they are; the fix is a runtime-computed
  inline style, not a new CSS rule.
- Do NOT change the `modalIn` keyframe, its `.2s` duration, its `ease`
  timing, or the `scale(.96)` starting value — all already correct per
  AUDIT.md's category 3 scale floor (`0.9–0.97`, never `0`) and out of
  scope for this plan.
- Do NOT implement full anchored-popover repositioning (moving `.sel-modal`
  itself away from the centered `.overlay` layout, or adding viewport-edge
  collision handling so it can render next to the trigger instead of in the
  center). That is a materially larger change — it would touch the
  `.overlay`/`.modal` positioning model shared by every modal in the app,
  not just the chooser, and needs its own edge-case handling for triggers
  near screen edges. It is a reasonable follow-up if wanted, but is
  deliberately out of scope for this plan, which only repoints the existing
  centered scale animation's pivot.
- Do NOT introduce any `--ease-*` / `--duration-*` token — none exist in
  this repo yet (see Repo conventions above), and this plan doesn't
  introduce or change any easing/duration value regardless.
- If the current code you find in `web/gf/chooser.js` does not match the
  `GF.openChooser` body shown in Problem/Steps above (drift since commit
  `6bd1f7d`), STOP and report the mismatch instead of guessing at how to
  adapt the insertion points.

## Verification

- **Mechanical**:
  - `node --check web/gf/chooser.js` — must exit 0 (no syntax errors). This
    repo has no build step, bundler, or lint config (no `package.json` at
    the repo root), so this is the full available mechanical check for the
    JS change.
  - Open the app in a browser with DevTools open and confirm the Console
    shows zero new errors/warnings while: opening a `GF.selectField`-style
    dropdown (e.g. a department/priority field inside the "Add Task"
    modal), opening the status-pill picker on a task card (My Week or Board
    view), typing into a searchable chooser's filter box, and picking an
    option to close it.
  - Visual diff description: the popup's size, final centered position,
    content, and overall look are pixel-identical to before this change.
    The only visible difference is the trajectory of the opening scale: it
    now visibly grows FROM the clicked trigger's on-screen position TOWARD
    its centered resting place, instead of expanding uniformly outward from
    the exact center of the screen regardless of where the click happened.
- **Feel check**:
  1. Open a dropdown/select field that sits near a screen EDGE or CORNER —
     not one that already happens to be near screen-center (e.g. a
     department chip near the top of the "Add Task" form, or a filter
     dropdown in a page header). Click it and watch closely: the popup
     should visibly start small and offset toward that edge/corner,
     growing toward the middle — not bloom symmetrically outward from the
     exact center of the screen like a firework.
  2. Click a task card's status pill near the TOP of the visible list, then
     close it and click a different task card's status pill near the
     BOTTOM of the list (scroll if needed). Confirm the animation's origin
     visibly shifts to track each pill's position — the top card's picker
     starts its grow near the top of the screen, the bottom card's starts
     lower — proving the origin is genuinely per-trigger, not a hardcoded
     fixed point that happens to look plausible once.
  3. In Chrome/Edge DevTools, open the **Animations** panel (More tools →
     Animations), set playback speed to 10%, then click a trigger near a
     screen edge to open its chooser. Find the recorded `modalIn` animation
     entry and scrub through it frame by frame: confirm the
     `scale(.96) → scale(1)` grow visibly pivots around the trigger's
     on-screen position — the corner/edge of the popup nearest the trigger
     should stay relatively still while the opposite side sweeps into
     place, rather than all edges moving outward symmetrically from the
     popup's own center.
  4. With the same popup open, inspect `.sel-modal` in the Elements panel
     and confirm it carries an inline `style="transform-origin: <n>px
     <n>px"` whose values are NOT `50% 50%`/unset, and that plausibly
     correspond to the clicked trigger's offset from the popup (roughly:
     if the trigger was above/left of the popup, both numbers should be
     negative or small; if below/right, both should be larger than the
     popup's own width/height).
  5. Close that chooser and reopen it from the SAME trigger a second time —
     confirm the inline `transform-origin` value is recomputed and stays
     consistent (not stale from a previous, different trigger elsewhere on
     the page).
  6. Open a genuine modal that is NOT a chooser (e.g. "Add Task" itself, or
     Settings) and confirm it is unaffected: it still grows from dead
     center, and inspecting it in the Elements panel shows no inline
     `transform-origin` style on its `.modal` element. This fix must stay
     confined to the chooser popup and must not leak onto real modals,
     which the AUDIT explicitly exempts from trigger-anchoring.
  7. Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel
     and reopen a chooser. Note (do not fix) that this codebase has no
     reduced-motion handling on `modalIn` today either way — that is a
     pre-existing, separate gap, not something this plan introduces or is
     responsible for closing.
- **Done when**: every chooser popup — both `GF.selectField`-style
  dropdowns and the imperative status-pill picker — visibly scales in FROM
  the exact trigger element that opened it rather than always from
  viewport center; the popup's final centered position, size, and content
  are unchanged from before; genuine modals (Add Task, Settings, etc.) are
  visually unaffected and carry no inline `transform-origin`; and
  `node --check web/gf/chooser.js` exits 0 with zero new console errors
  across all interactions above.
