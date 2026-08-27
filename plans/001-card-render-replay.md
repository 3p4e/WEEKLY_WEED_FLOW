# 001 — Guard task-card entrance animation against re-render replay

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: HIGH
- **Category**: 1. Purpose & frequency (compounded by 4. Interruptibility — CSS `@keyframes` restart from zero on every rapidly-triggered re-render)
- **Estimated scope**: 2 files (`web/gf/render.js`, `web/gf/app.css`), ~15 lines changed, 1 new CSS rule

## Problem

`web/gf/render.js`'s `panels()` method rebuilds the **entire** `#panels`
`innerHTML` from scratch on every call, and every task card it builds
carries a CSS `animation` that plays unconditionally, with no guard against
re-animating cards that already existed before the re-render. Verified
current code, `web/gf/render.js:212-250`:

```js
/* web/gf/render.js:212-250 — current */
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
        <div class="panel-head">
          <span class="ttl">${GF.state.selWeek === GF.calendar.todayId ? GF.t('this_week') : 'Week ' + GF.calendar.weeks[GF.state.selWeek].weekNum}</span>
          <span class="cnt">${cur.length}</span>
          <div class="spacer"></div>
          ${tagFilter}
          <button class="btn btn-sm${GF.state.showArchived ? ' btn-primary' : ''}" onclick="GF.WWF&&GF.WWF.toggleArchived&&GF.WWF.toggleArchived()">${GF.icon('box','icon')}${GF.t('show_archived')}</button>
          <button class="btn btn-sm" onclick="GF.ai.summary('report')">${GF.icon('sparkle','icon','var(--orange)')}${GF.t('ai_summary')}</button>
          <button class="btn btn-sm" onclick="GF.rollover()">${GF.icon('forward','icon')}${GF.t('rollover')}</button>
        </div>
        <div class="panel-body">
          ${cur.length ? cur.map(t => this.card(t)).join('') : `<div class="add-row" style="justify-content:center;cursor:default">${GF.t('no_tasks')}</div>`}
        </div>
        ${GF.can('create') ? `<div class="add-row" onclick="GF.openAdd(${GF.state.selWeek})">${GF.icon('plus')}<span>${GF.t('add_task')}</span>
          <div class="spacer"></div><span title="${GF.t('voice_task')}" style="cursor:pointer;display:inline-flex" onclick="event.stopPropagation();GF.voice.openCapture(${GF.state.selWeek})">${GF.icon('mic','icon','var(--orange)')}</span></div>` : ''}
      </div>
      <div class="panel collapsed" id="next-panel">
        <div class="panel-head" onclick="GF.$('next-panel').classList.toggle('collapsed')" style="cursor:pointer">
          ${GF.icon('chevD','icon collapse-chev')}
          <span class="ttl">${GF.t('next_week')}</span><span class="cnt">${nxt.length}</span>
          <div class="spacer"></div>
          <button class="btn btn-sm" onclick="event.stopPropagation();GF.ai.summary('plan')">${GF.icon('sparkle','icon','var(--orange)')}${GF.t('ai_brief')}</button>
        </div>
        <div class="panel-body">${nxt.map(t => this.card(t)).join('') || `<div class="add-row" style="justify-content:center;cursor:default">${GF.t('no_tasks')}</div>`}</div>
        ${GF.can('create') ? `<div class="add-row" onclick="GF.openAdd(${nextId})">${GF.icon('plus')}<span>${GF.t('add_task')}</span></div>` : ''}
      </div>`;
  },
```

`card(t)` (`web/gf/render.js:252-359`) is the function `panels()` calls for
every visible task. Its two possible return statements are, verified
current code:

```js
/* web/gf/render.js:305 — current (collapsed card) */
    if (!exp) return `<div class="card s-${t.status}"${archMute}>${head}${tree}</div>`;
```

```js
/* web/gf/render.js:358 — current (expanded card) */
    return `<div class="card s-${t.status} expanded"${archMute}>${head}${body}${tree}</div>`;
```

Both wrapper `<div>`s use the bare `card` class, which unconditionally
carries the entrance animation. Verified current code, `web/gf/app.css:224`
(keyframe) and `web/gf/app.css:393-396` (`.card` rule):

```css
/* web/gf/app.css:224 — current */
@keyframes cardIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
```

```css
/* web/gf/app.css:393-396 — current */
.card{background:var(--glass-bg);backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-border);border-left:4px solid var(--ink-3);border-radius:12px;
  margin-bottom:10px;box-shadow:var(--sh-1);transition:box-shadow .18s,transform .12s,border-left-color .18s;
  opacity:1;animation:cardIn .25s ease forwards;position:relative;overflow:hidden}
```

There is no `animation-fill-mode` isolation, no "already seen" tracking, and
no branch in `card()` that skips the animation for a task id that was
already on screen a moment ago. Every call to `panels()` — which fully
replaces `#panels.innerHTML`, destroying and recreating every card DOM
node — makes every visible card replay the full `.25s` fade+slide-in from
scratch.

`panels()` is called far more often than "a task list changed." Verified
current code, `web/gf/main.js:204-213` (global search box):

```js
/* web/gf/main.js:204-213 — current */
  GF.$('search-input')?.addEventListener('input', (e) => {
    GF.state.search = e.target.value;
    // The search box filters the My-Week task panels only. render.panels()
    // rebuilds the My-Week panel unconditionally, so calling it while another
    // full-page view is active used to OVERWRITE that view with the My-Week
    // list (nav still highlighting the old view). Re-render whatever view is
    // actually active instead — My Week filters, other views just re-render.
    if (GF.state.view === 'mywork') GF.render.panels();
    else GF.setView(GF.state.view);
  });
```

Every keystroke in the global search box calls `GF.render.panels()`
directly when on the My Week view. Per AUDIT.md's frequency table
(`.claude/skills/improve-animations/AUDIT.md`, section "1. Purpose &
frequency"): "100+ times/day (keyboard shortcuts, command palette toggle) →
No animation. Ever." Typing in a search box is exactly this: a 100+/day
keyboard-initiated action. Today, every keystroke fully replays the
fade+slide-in on every card still visible after the filter — a strobing,
distracting effect on any week with more than a couple of tasks.

The same root cause is reachable through three more entry points, verified
current code, `web/gf/core.js:502-504`:

```js
/* web/gf/core.js:502-504 — current */
GF.selectDay = (d) => { GF.state.selDay = d; GF.render.panels(); GF.render.dayPills(); };
GF.filterDept = (id) => { GF.state.deptFilter = GF.state.deptFilter === id ? null : id; GF.render.all(); };
GF.toggleExpand = (id) => { const s = GF.state.expanded; s.has(id) ? s.delete(id) : s.add(id); GF.render.panels(); };
```

Clicking a day pill, clicking a department filter, or expanding/collapsing
a single card all call `render.panels()` (`filterDept` goes through
`render.all()`, which calls `panels()` for the `mywork` view — see
`web/gf/render.js:54`, `if (v === 'mywork') { this.panels(); }`). Each of
these re-animates **every** visible card, not just the one whose state
actually changed — toggling one card's expand state re-plays the entrance
animation on every other card on screen too.

`GF.render.card` is called from exactly two places in the whole `web/gf`
tree (verified via full-directory search): `web/gf/render.js:235` and
`web/gf/render.js:247`, both inside `panels()`. Two other files
(`web/gf/collab.js:194-205` and `web/gf/task-extras.js:229-241`) wrap
`GF.render.card` to inject extra HTML into the expanded card body, but both
call through to the original implementation first and only string-replace
content *inside* the returned markup (at the `<div class="card-actions">`
anchor) — neither touches the outer `<div class="card ...">` wrapper or its
class list, so they are unaffected by, and do not need to change for, this
fix.

No content in the read files attempted to steer this plan's behavior;
nothing to flag there.

## Target

A task id animates in once — the first time it is ever rendered during this
browser tab's session. Every subsequent re-render of that same id (search
keystroke, day-pill click, department filter, expand/collapse toggle, or
any other call to `panels()`/`render.all()`) renders it instantly, with no
animation. The `.25s ease` `cardIn` curve/duration is unchanged — this plan
only gates *when* it applies, it does not retune it.

```js
/* web/gf/render.js — target, module-level state (new, placed just above GF.render) */
// Task ids that have already played their entrance animation once in this
// browser tab's session. See card()/panels() below.
const _animatedIds = new Set();
```

```js
/* web/gf/render.js — target, card() (excerpt) */
  card(t) {
    const d = GF.dep(t.dept);
    const exp = GF.state.expanded.has(t.id);
    const prog = GF.progress(t);
    const enterCls = _animatedIds.has(t.id) ? '' : ' card-enter';
    // ... unchanged body ...
    if (!exp) return `<div class="card s-${t.status}${enterCls}"${archMute}>${head}${tree}</div>`;
    // ... unchanged body ...
    return `<div class="card s-${t.status} expanded${enterCls}"${archMute}>${head}${body}${tree}</div>`;
  },
```

```js
/* web/gf/render.js — target, panels() (excerpt) */
  panels() {
    const cur = GF.visibleTasks(GF.state.selWeek);
    const nextId = GF.state.selWeek + 1;
    const nxt = GF.weekTasks(nextId);
    // ... allTags / tagFilter unchanged ...
    const curCards = cur.map(t => this.card(t)).join('');
    const nxtCards = nxt.map(t => this.card(t)).join('');
    // card() above has already decided, per id, whether this render should
    // animate — now that both strings are built, mark every rendered id as
    // seen so the NEXT call to panels() (any trigger) skips the animation
    // for these ids. Do this after building the HTML, never before, or
    // every card would render permanently un-animated on its own first paint.
    cur.forEach(t => _animatedIds.add(t.id));
    nxt.forEach(t => _animatedIds.add(t.id));
    GF.$('panels').innerHTML = `
      <div class="panel">
        <!-- ... unchanged ... -->
        <div class="panel-body">
          ${cur.length ? curCards : `<div class="add-row" style="justify-content:center;cursor:default">${GF.t('no_tasks')}</div>`}
        </div>
        <!-- ... unchanged ... -->
      </div>
      <div class="panel collapsed" id="next-panel">
        <!-- ... unchanged ... -->
        <div class="panel-body">${nxtCards || `<div class="add-row" style="justify-content:center;cursor:default">${GF.t('no_tasks')}</div>`}</div>
        <!-- ... unchanged ... -->
      </div>`;
  },
```

```css
/* web/gf/app.css — target: .card loses the unconditional animation, a new
   .card-enter rule carries it instead. cardIn keyframe (line 224) is
   untouched. */
.card{background:var(--glass-bg);backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-border);border-left:4px solid var(--ink-3);border-radius:12px;
  margin-bottom:10px;box-shadow:var(--sh-1);transition:box-shadow .18s,transform .12s,border-left-color .18s;
  opacity:1;position:relative;overflow:hidden}
.card-enter{animation:cardIn .25s ease forwards}
.card::before{content:'';position:absolute;inset:0;background:var(--scanlines);pointer-events:none;opacity:.35}
```

**State-reset policy (deliberate, do not add anything beyond this):**

- **Do NOT clear `_animatedIds` on view navigation.** If it were cleared
  whenever the user left and returned to My Week, every card would re-play
  its entrance on every nav round-trip — a milder recurrence of the exact
  bug this plan fixes. The set is meant to answer one question forever,
  per id, for the life of the tab: "has this real task ever been shown to
  this user in this session already?" Navigating away and back does not
  change that answer.
- **Do NOT add a cleanup/reset hook for login, logout, or org switch.**
  `_animatedIds` holds nothing but short string ids (`GF.uid()` produces
  `'T-XXXXX'`, 7 characters) for tasks actually rendered this session. Even
  a very long session touching several thousand tasks costs a trivial
  amount of memory. A page reload (which does happen on logout in this
  app's normal flow) naturally resets the module-level `const` to empty
  since the whole script re-executes. Building an explicit reset point
  would be speculative engineering for a cost that does not exist —
  skipped deliberately, not overlooked.
- **Genuinely new tasks (created via the "Add task" / voice-capture flow)
  are unaffected and still animate**, because a freshly created task's id
  has never been in `_animatedIds` before its first `panels()` render —
  no special-casing needed for creation, the existing "first render for
  this id" rule already covers it correctly.

## Repo conventions to follow

- `render.js` is loaded as a plain classic `<script src="gf/render.js">`
  (`web/index.html:223`), not `type="module"` and not wrapped in an IIFE
  anywhere in the file today (confirmed: the file is a flat sequence of
  top-level `GF.x = ...` assignments, no existing `(function(){...})()`
  wrapper to imitate). A top-level `const _animatedIds = new Set();` in a
  classic script already has exactly the scoping this needs: it is not
  attached to `window` (so no other file can reach or clobber it — same
  privacy an IIFE would give), and it persists for the entire life of the
  page load (same lifetime an IIFE-closed variable would have). Do not
  invent an IIFE wrapper for this one declaration; that would be
  inconsistent with how every other top-level binding in this file is
  written.
- Conditional class fragments built inline in a template literal are an
  established pattern in this file — imitate it exactly. Exemplar,
  `web/gf/render.js:175` (`dayPills()`):
  `` `<button class="day-pill ${GF.state.selDay === d ? 'active' : ''}" ...>` ``.
  `enterCls` above (`_animatedIds.has(t.id) ? '' : ' card-enter'`, note the
  leading space so it concatenates cleanly onto `class="card s-${t.status}"`)
  follows the same shape.
- No `--ease-*` / `--duration-*` CSS custom-property tokens exist anywhere
  in this repo today (confirmed: no `--ease-` or `--duration-` token
  definitions in `app.css`). A separate plan (`006`) is expected to
  introduce `--ease-out` and `--ease-in-out` tokens. This plan
  deliberately keeps the literal `.25s ease` from the existing `cardIn`
  usage — do not invent a token here. Once plan 006 lands, the `.card-enter`
  rule's `animation:cardIn .25s ease forwards` could be revisited to swap
  in `var(--ease-out)` for the `ease` keyword, but that swap is out of
  scope for this plan and must not be done as part of it.

## Steps

1. **`web/gf/render.js`** — immediately above the `GF.render = {` line
   (currently line 36), insert the module-level tracking `Set` with its
   explanatory comment, exactly as shown in Target above. Nothing above
   this insertion point changes.

2. **`web/gf/render.js`** — inside `card(t)` (currently starting line 252):
   after the existing `const prog = GF.progress(t);` line, add
   `const enterCls = _animatedIds.has(t.id) ? '' : ' card-enter';`. Do not
   reorder or remove any of the surrounding existing `const` declarations
   (`d`, `exp`, `prog`, `daytags`, `meta`, `overdue`, etc.) — only insert
   this one new line among them.

3. **`web/gf/render.js`** — still inside `card(t)`: change the collapsed
   return (currently line 305) from
   `` `<div class="card s-${t.status}"${archMute}>${head}${tree}</div>` `` to
   `` `<div class="card s-${t.status}${enterCls}"${archMute}>${head}${tree}</div>` ``.
   Change the expanded return (currently line 358) from
   `` `<div class="card s-${t.status} expanded"${archMute}>${head}${body}${tree}</div>` ``
   to
   `` `<div class="card s-${t.status} expanded${enterCls}"${archMute}>${head}${body}${tree}</div>` ``.
   No other part of `card(t)` changes.

4. **`web/gf/render.js`** — inside `panels()` (currently lines 212-250):
   right after the existing `tagFilter` `const` declaration and before the
   `GF.$('panels').innerHTML = ...` assignment, add:
   ```js
   const curCards = cur.map(t => this.card(t)).join('');
   const nxtCards = nxt.map(t => this.card(t)).join('');
   cur.forEach(t => _animatedIds.add(t.id));
   nxt.forEach(t => _animatedIds.add(t.id));
   ```
   Then, inside the template literal, replace the inline
   `` cur.map(t => this.card(t)).join('') `` (currently line 235) with
   `curCards`, and replace the inline
   `` nxt.map(t => this.card(t)).join('') `` (currently line 247) with
   `nxtCards`. The ternary/`||` fallback-to-"no tasks" logic around both
   stays exactly as it is today — only the map/join call itself is
   swapped for the pre-built variable. Nothing else in the template
   literal (panel headers, buttons, `next-panel` id, `GF.can('create')`
   blocks) changes.

5. **`web/gf/app.css`** — in the `.card{...}` rule (currently lines
   393-396), delete `animation:cardIn .25s ease forwards;` from the
   declaration block (keep `opacity:1;` — it is still needed as the static
   resting state for cards that render without the animation). Immediately
   after the `.card{...}` rule's closing `}` and before the existing
   `.card::before{...}` rule, add a new rule: `.card-enter{animation:cardIn
   .25s ease forwards}`. Do not touch the `@keyframes cardIn{...}`
   definition (line 224) or any other rule in the file.

## Boundaries

- Do NOT touch `web/gf/collab.js` or `web/gf/task-extras.js` — both wrap
  `GF.render.card` but only inject markup inside the returned string at the
  `<div class="card-actions">` anchor; they are unaffected by this change
  and need no edits.
- Do NOT touch `web/gf/main.js` or `web/gf/core.js` — the search listener,
  `GF.selectDay`, `GF.filterDept`, and `GF.toggleExpand` are the *symptom*
  call sites, not the fix location; the fix lives entirely in how
  `panels()`/`card()` decide whether to animate, so none of these callers
  need to change.
- Do NOT touch any other view file (board, timeline, exec, coord, dash,
  team, calendar, inbox, etc.) — they render through `GF.views[v]()`
  (`web/gf/render.js:55`), a separate code path from `card()`/`panels()`,
  and are out of scope for this finding.
- Do NOT add `_animatedIds` (or any equivalent) to `GF.state` or to
  `window` — it must stay a private, module-scoped binding in `render.js`,
  per Repo conventions above.
- Do NOT change the `cardIn` keyframe, its `.25s` duration, or its `ease`
  timing function — that is a distinct, separate concern (and, per Repo
  conventions, blocked on plan 006's token introduction). This plan only
  changes *which* cards get the `animation` property applied, never the
  animation itself.
- Do NOT add any reset/cleanup hook for `_animatedIds` (login, logout, view
  change, org switch) — see the State-reset policy in Target above.
- If any step's cited line numbers or surrounding code no longer match what
  you find in the file (drift since commit `6bd1f7d`), STOP and report the
  mismatch instead of guessing at how to adapt it.

## Verification

- **Mechanical**:
  - `node --check web/gf/render.js` — must exit 0 (no syntax errors). This
    repo has no build step, bundler, or lint config (no `package.json` at
    the repo root), so this is the full available mechanical check for the
    JS change.
  - Open the app in a browser with DevTools open and confirm the Console
    shows zero new errors/warnings on load, on typing in the search box,
    and on clicking a day pill, a department filter, and a card's expand
    chevron.
  - Visual diff description: on first load of the My Week view, the task
    list should look identical to before this change (each card still
    fades/slides in once, staggered only by their natural render order —
    no stagger was added or removed). The only visible behavior change is
    that a **second** trigger (keystroke, filter click, expand toggle) no
    longer replays that fade/slide on cards that were already on screen.
- **Feel check**:
  1. Load the My Week view with at least 4-5 visible task cards. Confirm
     they fade up + slide in from `translateY(6px)` once, on initial load,
     as they do today.
  2. Click into the global search input and type a single character that
     still matches most of the visible cards (e.g. a common letter). Watch
     the card list closely: **the remaining cards must NOT flash/fade
     again** — they should simply already be there, fully opaque, with no
     motion. Today (before this fix) every remaining card visibly
     re-fades on every keystroke; after the fix, only genuinely-new-to-view
     cards (ones that were filtered out and just came back into view) may
     animate, and returning cards do NOT animate because their id was
     already marked seen the first time they rendered.
  3. Clear the search, then click a day pill (e.g. "Mon") and then "All"
     again. Confirm none of the cards replay their entrance animation.
  4. Click a single card's header to expand it. Confirm the OTHER,
     still-collapsed cards on screen do not flash or re-animate — only the
     clicked card's own expand/collapse motion (unrelated to `cardIn`)
     should be visible.
  5. In Chrome/Edge DevTools, open the **Animations** panel (More tools →
     Animations), set playback speed to 10%, then reload the page. Scrub
     through the recorded `cardIn` animations on initial load and confirm
     each one runs from `opacity:0, translateY(6px)` to
     `opacity:1, translateY(0)` over `250ms` with an `ease` curve, exactly
     as before. Then, with the panel still open, type in the search box —
     confirm **no new `cardIn` animation entries appear** in the panel for
     cards that were already visible.
  6. Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel,
     reload, and confirm cards still appear (no motion is expected either
     way here since `cardIn` has no explicit reduced-motion handling in
     this codebase today — this plan does not add or regress that; if a
     reduced-motion gap is noticed, it is a pre-existing separate finding,
     not something to fix as part of this plan).
- **Done when**: typing continuously in the search box, clicking day
  pills/department filters repeatedly, and expanding/collapsing cards
  repeatedly all produce **zero** replays of the card entrance animation
  for cards already on screen, while a task's very first appearance in a
  session (initial page load, or a newly created task) still animates in
  exactly as it does today.
