# 015 — Give the Inbox/Activity tab switch a fade+rise entrance instead of an instant teleport

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: LOW
- **Category**: 8. Missed opportunities (a state change — swapping the notifications list between the "Inbox" and "Activity" tabs — currently teleports with zero transition, exactly the "content swaps" case AUDIT.md's category 8 calls out) — informed by 2. Easing & duration (duration/curve selection for the new entrance) and 7. Cohesion & tokens (AUDIT.md's crossfade-masking guidance is considered below and deliberately not used, since this plan implements a one-directional entrance, not a two-state overlapping crossfade — see the naming note in Problem)
- **Estimated scope**: 2 files, ~10 lines total. `web/gf/app.css`: 2 new `@keyframes`, 1 new class rule, 1 line appended to the existing `@media (prefers-reduced-motion: reduce)` block. `web/gf/notifications-view.js`: 1 one-word class-string edit (append `ntf-list-enter` to a single existing `class` attribute). No new dependencies, no build step, no markup restructuring beyond that one class addition.

## Problem

### Naming note (read this first)

This plan's filename says "crossfade," but per this repo's own scoping decision (see
Target), it does **not** implement a true crossfade — a true crossfade would require
keeping the outgoing (old-tab) content and the incoming (new-tab) content in the DOM
at the same time so their opacities can cross over each other, which is a bigger
architectural change than this small plan takes on. What follows instead is a
one-directional "new content fades and rises into place" entrance, applied to the list
container as a whole. Treat "crossfade" in the filename as the informal name of the
UX seam being fixed (the tab swap), not a literal description of the technique used.

### The tab switch teleports the entire list with zero transition

Verified current code, `web/gf/notifications-view.js:175-176` (inside `GF.views.inbox`,
the `tab()` local helper that renders each of the two tab buttons):

```js
/* web/gf/notifications-view.js:175-176 — current */
    const tab = (id, lbl) => `<button class="btn btn-sm ntf-tab ${st.tab === id ? 'btn-primary on' : ''}"
      onclick="GF.WWF._notif.tab='${id}';GF.render.all()">${lbl}</button>`;
```

Clicking either tab button mutates `GF.WWF._notif.tab` directly, then calls
`GF.render.all()`. Verified current code, `web/gf/render.js:36-57` (`GF.render.all`):

```js
/* web/gf/render.js:36-57 — current */
GF.render = {
  all() {
    this.sidebar(); this.header();
    // The exec view is executive-only; if a stale gf_view lands a non-exec here
    // (e.g. a shared browser), fall back to My Week. Same bounce for the
    // department home when the user has no department (execs, QP, ADMIN).
    if (GF.state.view === 'exec' && !(GF.isExec && GF.isExec())) GF.state.view = 'mywork';
    if (GF.state.view === 'depthome' && !(GF.hasDeptHome && GF.hasDeptHome())) GF.state.view = 'mywork';
    const v = GF.state.view;
    const show = (id, on) => { const el = GF.$(id); if (el) el.style.display = on ? '' : 'none'; };
    const weekViews = v === 'mywork' || v === 'board' || v === 'timeline';
    show('week-strip', v !== 'team' && v !== 'calendar');   // calendar is month-scoped
    show('day-pills', v === 'mywork' || v === 'board');
    show('telemetry', v === 'mywork');
    if (v !== 'team' && v !== 'calendar') { this.weekStrip(); }
    if (v === 'mywork' || v === 'board') this.dayPills();
    if (v === 'mywork') this.telemetry();

    if (v === 'mywork') { this.panels(); }
    else if (GF.views && GF.views[v]) { GF.$('panels').innerHTML = GF.views[v](); }
    else { this.panels(); }
  },
```

For the `'inbox'` view, `GF.views.inbox` exists (registered in `notifications-view.js`),
so line 55's branch runs: `GF.$('panels').innerHTML = GF.views[v]();` — the **entire**
`#panels` subtree, including whichever tab's list was previously showing, is destroyed
and replaced by a brand-new string of HTML in one assignment. This is the same
full-innerHTML-replace mechanism `plans/001-card-render-replay.md` and
`plans/013-task-completion-feedback.md` document for `#panels`' other renders — but
unlike those two plans' targets, there is currently **no dormant CSS transition
anywhere in this component to reconnect**. Verified current code,
`web/gf/app.css:851-864` (the complete "Inbox / activity feed" CSS block):

```css
/* web/gf/app.css:851-864 — current, complete block, no transition/animation anywhere in it */
.ntf-bar{display:flex;align-items:center;gap:8px;margin:6px 4px 10px}
.ntf-list{display:flex;flex-direction:column;gap:6px;max-width:860px}
.ntf-day{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);margin:10px 4px 2px}
.ntf{display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--glass-border);
  border-left:3px solid var(--primary);border-radius:10px;background:var(--surface-2);cursor:pointer}
.ntf.unread{background:var(--primary-soft)}
.ntf.unread .ntf-tt::before{content:'';display:inline-block;width:7px;height:7px;border-radius:50%;
  background:var(--primary);margin-right:7px;box-shadow:0 0 8px var(--primary)}
.ntf-feed{cursor:default;border-left-color:var(--glass-border)}
.ntf-b{flex:1;min-width:0}
.ntf-tt{font-size:13.5px;color:var(--ink);overflow:hidden;text-overflow:ellipsis}
.ntf-meta{display:flex;gap:10px;align-items:center;font-size:11px;color:var(--ink-3);margin-top:2px}
.ntf-reason{border:1px solid var(--glass-border);border-radius:99px;padding:1px 8px}
```

No `transition` or `animation` declaration exists on `.ntf-bar`, `.ntf-list`, `.ntf`,
`.ntf-day`, or any related selector in this file. This is confirmed additive work, not
a reconnection job.

### The exact wrapper element to target

`GF.views.inbox` (`web/gf/notifications-view.js:172-198`) builds the tab bar, an
optional reason-filter row, and then the list content. Verified current code,
`web/gf/notifications-view.js:190-194` — this is the specific `<div>` that needs to
gain the new entrance, and the only place in this function it appears:

```js
/* web/gf/notifications-view.js:190-194 — current */
      <div class="ntf-list">${!st.loaded
        ? `<div class="mw-skel" style="height:52px;margin-bottom:8px"></div>
           <div class="mw-skel" style="height:52px;margin-bottom:8px"></div>
           <div class="mw-skel" style="height:52px"></div>`
        : st.tab === 'inbox' ? grouped(items, itemRow) : grouped(st.feed, feedRow)}</div>
```

This single `<div class="ntf-list">` wraps whichever content is current: the loading
skeleton on first load, or `grouped(items, itemRow)` (Inbox) / `grouped(st.feed,
feedRow)` (Activity) once loaded. It is exactly the "content swap" container — switch
tabs, and this div's entire innerHTML (and, because of the full `render.all()`
replace above, the div node itself) is different on the next render.

`.ntf-list` is **not** unique to this spot, though — the same class also wraps the
"Recent" mini-list inside the Team digest panel. Verified current code,
`web/gf/notifications-view.js:157` (inside `digestPanel()`):

```js
/* web/gf/notifications-view.js:157 — current */
          <div class="ntf-list">${grouped((dg.recent || []).slice(0, 12), feedRow)}</div>
```

Styling the bare `.ntf-list` class directly would also animate the digest panel's
recent-activity list every time it re-renders (opening the panel, switching its
daily/weekly window) — a different UX seam this plan was not asked to touch. See
Target/Boundaries for how this plan avoids that.

### Why this does not need the guard plan 001 requires for `cardIn` — read before "fixing" this

`plans/001-card-render-replay.md` flags `.card`'s `cardIn` entrance because
`web/gf/render.js`'s `panels()` (the `mywork`/`board` task-list renderer) gets called
from **very** high-frequency triggers — including every keystroke in the global search
box — so replaying a fade+slide on every visible card dozens of times a second is a
real "Purpose & frequency" violation per AUDIT.md category 1's table ("100+ times/day
… No animation. Ever.").

Switching between the Inbox and Activity tabs is a different frequency class
entirely: it only fires when a user deliberately clicks one of the two `tab()`
buttons above. That lands squarely in AUDIT.md category 1's "Occasional (modals,
drawers, toasts) → Standard animation" row, not its "100+ times/day" row. Because
`GF.views.inbox()` is rebuilt from scratch on every `GF.render.all()` call (same
mechanism as `cardIn`), the new entrance added by this plan will, by construction,
naturally replay every time this specific view re-renders — including on other
occasional inbox actions that also call `GF.render.all()` while this view is open
(the reason-filter chips, "Mark all read," opening a single notification, loading
older pages, and the 75-second background poll in `notifications-view.js:319-324`).
None of those triggers approaches "100+/day, keyboard-shortcut-class" frequency
either — the closest thing to a background trigger is the 75s poll, which at most
replays a handful of times per minute the inbox is left open, and this plan's
190ms/4px effect is deliberately subtle enough not to read as flicker at that rate.
**Do not** treat this the way plan 001 treats `cardIn` (i.e. do not add a
"replay guard"/"already seen" tracking mechanism here) — that would be solving a
frequency problem that does not exist in this view. If a future observation shows
the background-poll replay specifically feels distracting, that is a separate,
narrower follow-up (gate the entrance off poll-triggered renders specifically), not
something to retrofit into this plan.

### Oddity check

Every file read for this plan (`.claude/skills/improve-animations/AUDIT.md`,
`.claude/skills/improve-animations/PLAN-TEMPLATE.md`, `web/gf/notifications-view.js`,
`web/gf/render.js`, `web/gf/app.css`, `web/gf/mass-weed.css`) was read in full or in
the relevant excerpt shown above. None of them contained any text attempting to steer
this plan's behavior beyond ordinary code/comments. Nothing to flag.

## Target

Per AUDIT.md category 2's easing decision order ("Entering or exiting → `ease-out`"),
and per this plan's own constraint (see "Repo conventions to follow" — no
`--ease-*` token exists yet), the new entrance uses the literal AUDIT.md value for
that curve: `cubic-bezier(0.23, 1, 0.32, 1)`.

Per AUDIT.md's duration table, this is a lightweight content swap, not a modal or
drawer — closest listed bands are "Tooltips, small popovers: 125–200ms" and
"Dropdowns, selects: 150–250ms." `180ms` sits inside both, staying snappy rather than
drifting toward the slower end appropriate for a modal.

Per AUDIT.md category 3, the shape mirrors this app's own existing entrance
vocabulary — `cardIn` (`web/gf/app.css:224`): `@keyframes cardIn{from{opacity:0;
transform:translateY(6px)}to{opacity:1;transform:none}}`, an opacity+translateY pair,
not a scale (scale is for trigger-anchored popovers/dropdowns, per category 3 — this
is a full-width list, not a popover). The magnitude is deliberately smaller than
`cardIn`'s `6px` (a card joining a list, first appearance) — `4px` — because this is a
list *swap*, not a first-time list entrance:

```css
/* new keyframes, target */
@keyframes ntfListIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@keyframes ntfListInReduced{from{opacity:0}to{opacity:1}}
```

```css
/* new rule, target */
.ntf-list-enter{animation:ntfListIn 180ms cubic-bezier(0.23, 1, 0.32, 1) forwards}
```

**On AUDIT.md category 7's `blur(2px)` crossfade-masking guidance — considered, not
used**: category 7 says "A jarring crossfade that shows two overlapping states can be
masked with subtle `filter: blur(2px)` during the transition." That technique exists
to hide the double-exposure of a *true* crossfade, where old and new content are both
visible and interpolating opacity at once. This plan's fix is a one-directional
entrance on a freshly-inserted node — there is only ever one state on screen at a
time (the old list is already gone by the time the new node with `.ntf-list-enter`
is inserted), so there is nothing to double-expose and no blur is needed. Do not add
`filter: blur(...)` to `.ntf-list-enter`.

Reduced motion: per AUDIT.md category 6 ("Reduced motion means fewer and gentler
animations, not zero — keep transitions that aid comprehension, remove position
changes"), the existing single `@media (prefers-reduced-motion: reduce)` block gains
one line, following its own established pattern (each existing line overrides a
single property on a rule declared elsewhere in the file — see
`plans/013-task-completion-feedback.md`'s Target section 3 for the same pattern
applied to a different rule):

```css
/* web/gf/app.css — target, inside the existing @media (prefers-reduced-motion: reduce) block */
.ntf-list-enter{animation-name:ntfListInReduced}
```

Finally, the wrapper `<div>` at `web/gf/notifications-view.js:190` gains the new
class, and only that one — the digest panel's `.ntf-list` at
`web/gf/notifications-view.js:157` is untouched:

```js
/* web/gf/notifications-view.js:190 — target */
      <div class="ntf-list ntf-list-enter">${!st.loaded
```

## Repo conventions to follow

- **No `--ease-*`/`--duration-*` CSS custom-property token system exists in this repo
  yet** (confirmed: no `--ease-` or `--duration-` custom property anywhere in
  `app.css`). A separate plan, `plans/006-easing-duration-tokens.md`, is expected to
  introduce `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` and
  `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)`. This plan uses the literal
  `cubic-bezier(0.23, 1, 0.32, 1)` value directly in `.ntf-list-enter`, per AUDIT.md —
  do not invent or reference a token that doesn't exist yet. Once plan 006 has landed,
  `cubic-bezier(0.23, 1, 0.32, 1)` in `.ntf-list-enter` could be swapped for
  `var(--ease-out)`, but that swap is out of scope for this plan and must not be made
  as part of it.
- **`cardIn`'s opacity+translateY shape is this app's exemplar for entrances**
  (`web/gf/app.css:224`: `@keyframes cardIn{from{opacity:0;transform:translateY(6px)}
  to{opacity:1;transform:none}}`, applied via `web/gf/app.css:396`:
  `animation:cardIn .25s ease forwards`). `ntfListIn`/`.ntf-list-enter` follow the same
  two-part shape (a `@keyframes` pairing `opacity` with a `transform`, applied via an
  `animation:` shorthand ending in `forwards`) — just with this plan's own duration and
  curve values (AUDIT.md's literal `--ease-out` bezier, not `cardIn`'s bare `ease`).
- **The single existing `@media (prefers-reduced-motion: reduce)` block**
  (`web/gf/app.css:980-984`) is where all reduced-motion handling in this repo lives —
  extend it in place; do not add a second `@media (prefers-reduced-motion)` block
  elsewhere in the file. Its existing convention is one selector per line, each
  overriding a single property (e.g. `.mw-spinner{animation-duration:1.6s}`) on a rule
  declared elsewhere — `.ntf-list-enter{animation-name:ntfListInReduced}` follows that
  exact shape.
- **`.ntf-list` is a shared class with a second, out-of-scope use site**
  (`web/gf/notifications-view.js:157`, the digest panel's "Recent" list). This plan
  adds a second, dedicated class (`ntf-list-enter`) alongside the existing `ntf-list`
  class at the one wrapper this plan targets, rather than editing the shared
  `.ntf-list{...}` rule itself — the same "add a modifier class alongside the shared
  base class" pattern `plans/013-task-completion-feedback.md` uses for
  `.card--just-completed` alongside `.card`.
- **Keyframes live together in one block** (`web/gf/app.css:223-233`, the
  `/* ── Keyframes ── */` comment through `gf-energy-sweep`) — add new keyframes there,
  grouped with the other entrance keyframes (`cardIn`, `expandIn`, `modalIn`,
  `toastIn`), not scattered elsewhere in the file.

## Steps

1. **`web/gf/app.css`** — in the keyframes block, immediately after
   `@keyframes toastIn{from{opacity:0;transform:translateX(30px)}to{opacity:1;
   transform:none}}` (currently line 227) and before `@keyframes spin{to{transform:
   rotate(360deg)}}` (currently line 228), insert two new keyframes exactly as shown
   in Target:
   ```css
   @keyframes ntfListIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
   @keyframes ntfListInReduced{from{opacity:0}to{opacity:1}}
   ```
2. **`web/gf/app.css`** — immediately after `.ntf-list{display:flex;flex-direction:
   column;gap:6px;max-width:860px}` (currently line 853) and before
   `.ntf-day{...}` (currently line 854), insert the new rule exactly as shown in
   Target:
   ```css
   .ntf-list-enter{animation:ntfListIn 180ms cubic-bezier(0.23, 1, 0.32, 1) forwards}
   ```
3. **`web/gf/app.css`** — inside the existing `@media (prefers-reduced-motion:
   reduce){...}` block (currently lines 980-984), add one new line after the three
   existing lines and before the block's closing `}`:
   ```css
   .ntf-list-enter{animation-name:ntfListInReduced}
   ```
   Do not touch the three existing lines in that block
   (`.mw-spinner{...}`, `.mw-skel{...}`, `.tree-row.s-working .tp-fill,.card.s-working
   .card-actions .track > span{...}`).
4. **`web/gf/notifications-view.js`** — inside `GF.views.inbox`, change the wrapper
   `<div>`'s class attribute (currently line 190:
   `<div class="ntf-list">${!st.loaded`) to add the new class, exactly as shown in
   Target:
   ```js
         <div class="ntf-list ntf-list-enter">${!st.loaded
   ```
   Change nothing else on this line or in the surrounding template literal. Do not
   touch the digest panel's separate `<div class="ntf-list">` at line 157.

## Boundaries

- Do NOT edit `web/gf/notifications-view.js:157` (the digest panel's "Recent"
  `.ntf-list`) — it keeps its bare `ntf-list` class, unanimated, as it is today.
- Do NOT edit the `.ntf-list{...}` base rule (`web/gf/app.css:853`) itself — all new
  behavior lives in the new, separate `.ntf-list-enter` class.
- Do NOT add any animation to `itemRow`, `feedRow`, or `grouped` (individual
  notification rows) — this plan animates exactly one container element per render,
  never N rows. No stagger.
- Do NOT implement a true two-state crossfade (keeping both the outgoing and
  incoming list content in the DOM simultaneously) and do NOT add
  `filter: blur(...)` — both are explicitly out of scope; see Target's note on
  AUDIT.md category 7.
- Do NOT add a "replay guard" / "already animated" tracking mechanism (the kind
  `plans/001-card-render-replay.md` adds for `cardIn`) — this view's re-render
  frequency does not warrant one; see Problem's frequency discussion.
- Do NOT introduce or reference `--ease-out`/`--ease-in-out`/any `--duration-*`
  token, and do NOT swap the literal `cubic-bezier(0.23, 1, 0.32, 1)` for
  `var(--ease-out)`, even if `plans/006-easing-duration-tokens.md` has already landed
  in this tree when this plan is executed — that swap is explicitly out of scope.
- Do NOT modify `cardIn`, `expandIn`, `modalIn`, `toastIn`, or any other existing
  keyframe or rule in `web/gf/app.css`.
- Do NOT touch `web/gf/mass-weed.css` — its only notifications-related rules style
  `.ntf-tab` (`:473`, `:475`), not `.ntf-list`; the new animation uses only
  `opacity`/`transform`, which need no theme-specific override.
- Do NOT add new dependencies or a build step.
- If any cited line number or current-code excerpt doesn't match what you find in the
  file (drift since commit `6bd1f7d`), STOP and report the mismatch instead of
  guessing at how to adapt it.

## Verification

- **Mechanical**:
  - `node --check web/gf/notifications-view.js` — must exit 0. (This plan touches no
    other `.js` file.)
  - `web/gf/app.css` has no syntax checker available in this repo (no build step, no
    `package.json` at the repo root). Visually confirm every rule you added or edited
    has balanced `{`/`}` and every declaration ends in `;` or is the last one in its
    block.
  - Open the app in a browser, navigate to the Inbox view, open DevTools' Console.
    Click the "Activity" tab, then "Inbox" again, several times. Confirm zero new
    console errors or warnings.
  - Visual diff description: before this change, clicking "Inbox"/"Activity" swaps
    the entire list instantly with no motion — old rows vanish, new rows appear
    already fully formed. After this change, the same instant data swap happens, but
    the new list's content briefly (180ms) fades up from ~4px below into its resting
    position as one unit — the whole list moves together, not row by row.
- **Feel check**:
  1. Switch Inbox → Activity → Inbox → Activity a few times at normal speed. Confirm
     each switch shows the new list content ease in — fast start, soft settle, no
     bounce or overshoot (this is what `cubic-bezier(0.23, 1, 0.32, 1)` should look
     like) — and that it completes well under a quarter second.
  2. Confirm the motion applies to the **list as a single block**, not to individual
     notification rows — nothing should stagger row-by-row; the whole `.ntf-list`
     should move and fade as one unit.
  3. Open the "Team digest" panel (click its header) and switch its Daily/Weekly
     window. Confirm the digest's own "Recent" mini-list does **not** get this
     entrance — it should still swap instantly, exactly as before this plan
     (documented scope boundary, not a bug).
  4. Click a reason-filter chip (e.g. "Comment") while on the Inbox tab. Confirm the
     same entrance also plays here — this is an accepted, harmless side effect (the
     filter chip also triggers a full `.ntf-list` rebuild through the same
     `GF.render.all()` path), not something to suppress.
  5. In Chrome/Edge DevTools, open the **Animations** panel (More tools →
     Animations), set playback speed to **10%**, then switch tabs again. Confirm an
     `ntfListIn` animation entry appears on the list container; scrub through it and
     confirm opacity ramps 0→1 while the vertical position eases from +4px to 0 with
     a fast-start/slow-finish curve — no linear crawl, no bounce past 0.
  6. Toggle `prefers-reduced-motion: reduce` (DevTools Rendering panel → Emulate CSS
     media feature `prefers-reduced-motion`), then switch tabs again. Confirm the
     list still fades in (opacity 0→1) but no longer visibly shifts vertical position
     — confirms the `ntfListInReduced` override (`animation-name` swap) is winning.
  7. Rapid-fire click between the two tabs as fast as possible several times in a
     row. Confirm no console errors, and no list is ever left stuck mid-fade or
     half-transparent — because each switch fully replaces the DOM node (a fresh
     `@keyframes` play on a brand-new element every time, not an interrupted
     transition), overlapping clicks cannot leave a node in a broken intermediate
     state.
- **Done when**: switching between the Inbox and Activity tabs plays the ~180ms
  fade+4px-rise entrance on the notification list container exactly once per switch,
  as a single block (no per-row stagger); the digest panel's own "Recent" list is
  unaffected; `prefers-reduced-motion: reduce` keeps the opacity fade but drops the
  vertical movement; rapid tab-switching never leaves the list stuck mid-animation;
  `node --check web/gf/notifications-view.js` passes; and no new console errors
  appear from switching tabs.
