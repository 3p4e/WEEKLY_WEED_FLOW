# 004 — Bound the infinite alert-pulse and progress-sheen loops to a finite, self-settling count

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: HIGH
- **Category**: 1. Purpose & frequency (compounded by 5. Performance — animating `box-shadow` forces a repaint on every frame, not just a composite, so an unbounded loop on many simultaneously-visible badges/bars costs real CPU for as long as the underlying state holds, which for "overdue"/"critical"/"has subtasks" can be days or weeks)
- **Estimated scope**: 1 file (`web/gf/mass-weed.css`), 2 `@keyframes` rules rewritten, 4 rule blocks edited (2 alert-pulse selector groups + 2 sheen usages of the same shared keyframe). No JS files touched, no new files.

## Problem

`web/gf/mass-weed.css` (the "Mass Weed" HUD theme, active whenever
`:root[data-theme^="mass-weed"]`) has two `@keyframes … infinite` loops that
fire on ordinary, frequently-true dashboard states, not rare one-off alerts,
and never stop for as long as that state remains true.

### 1. The alert pulse (`mw-alert` / `mw-alert-amber`)

Verified current code, `web/gf/mass-weed.css:887-893`:

```css
/* web/gf/mass-weed.css:887-893 — current */
@keyframes mw-alert{0%,100%{box-shadow:0 0 0 0 rgba(239,77,77,0)}50%{box-shadow:0 0 10px 1px rgba(239,77,77,.55)}}
@keyframes mw-alert-amber{0%,100%{box-shadow:0 0 0 0 rgba(240,185,94,0)}50%{box-shadow:0 0 10px 1px rgba(240,185,94,.5)}}
:root[data-theme^="mass-weed"] .due-badge.overdue,
:root[data-theme^="mass-weed"] .attn-tag.overdue,
:root[data-theme^="mass-weed"] .ops-tag.overdue{animation:mw-alert-amber 2.4s ease-in-out infinite}
:root[data-theme^="mass-weed"] .attn-tag.stuck,
:root[data-theme^="mass-weed"] .prtag.critical{animation:mw-alert 2.4s ease-in-out infinite}
```

**Drift from the finding as filed**: the finding cited only
`.ops-tag.overdue` (line 891) and `.prtag.critical` (line 893). The live
file shows both of those selectors are the *last* member of a larger
comma-grouped selector list sharing the exact same declaration —
`.due-badge.overdue` and `.attn-tag.overdue` also get `mw-alert-amber`, and
`.attn-tag.stuck` also gets `mw-alert`. This is not a significant drift (the
fix pattern is identical for every selector in a group, since they share one
declaration), but it does mean the fix must cover all five classes, not just
the two the finding named — leaving `.due-badge.overdue`, `.attn-tag.overdue`,
and `.attn-tag.stuck` on `infinite` while only fixing the other two would be
an inconsistent half-fix.

Where these classes come from, confirmed by reading the render code:
`.prtag.critical` — `web/gf/render.js:298` (every task card's priority tag)
and `web/gf/views.js:50` (every board-view card); `.due-badge.overdue` —
`web/gf/render.js:261-262` (every card past its due date); `.attn-tag.stuck`
/`.attn-tag.overdue` — `web/gf/views.js:269-270,357` (the executive
dashboard's "Needs attention" list); `.ops-tag.overdue` — `web/gf/views.js:304`
(the executive dashboard's per-department rollup). None of these are rare —
a critical-priority task or an overdue rollup badge is a routine, commonly
seen ops-dashboard state, exactly the kind of "common state" AUDIT.md's frequency
table (section 1) says should not carry decorative infinite motion.

Only one of the five classes already has a **static** resting indicator in
the base (non-themed) stylesheet — verified current code,
`web/gf/app.css:439`: `.prtag.critical{background:var(--red);box-shadow:0 0
8px rgba(255,77,94,.35)}`. The other four (`.due-badge.overdue` —
`web/gf/app.css:617`, `.attn-tag.overdue`/`.attn-tag.stuck` —
`web/gf/app.css:749-750`, `.ops-tag.overdue` — `web/gf/app.css:784`) only
get a tinted `background`/`color`, no `box-shadow` — so today, once the
mass-weed theme's `infinite` keyframe is removed, those four would lose
their only permanent visual distinctiveness beyond the color tint unless
this plan adds one (see Target).

**Does bounding the iteration count actually change anything visible today,
or only after plan `001` lands?** It matters **today, independently of plan
001**. Plan `001` (`plans/001-card-render-replay.md`) only gates whether the
*outer* `.card` wrapper replays its `cardIn` entrance fade on re-render; it
does not touch, and does not need to touch, `card(t)`'s inner `head`/`tree`
markup — the `.prtag`, `.due-badge`, `.attn-tag`, `.ops-tag` elements are
part of that inner markup and are destroyed and recreated by
`GF.render.card()`/`GF.render.panels()` on **every** call, both before and
after plan 001 (plan 001 does not change this). So yes: every time
`panels()` re-renders (a search keystroke, a day-pill click, a
department-filter click, an expand/collapse toggle — see
`plans/001-card-render-replay.md`'s Problem section for the exact call
sites), the alert-pulse DOM node is fresh and its bounded animation starts
over from iteration 1. But `panels()`/the exec dashboard's `GF.views[v]()`
are **not** called on a timer — they only fire on those specific user
actions. Between actions, while the user is simply looking at the board (the
majority of the time any given task stays "critical" or "overdue" — hours to
days), the existing DOM node is untouched and `infinite` genuinely loops
forever today. Bounding the count to a small number is therefore a real,
today-effective fix for that idle-viewing majority case. The residual
behavior — a burst of active re-renders (e.g. continuously typing in the
search box) restarting the bounded pulse on each keystroke for whichever
cards remain visible — is a real but minor and strictly out-of-scope
limitation of this plan (a *bounded* pulse restarting a few times during a
few seconds of active typing is still categorically better than an
unbounded one looping the entire time the tab is open); it is not something
this plan or plan 001 needs to additionally solve.

### 2. The progress-bar sheen (`mw-sheen`)

Verified current code, `web/gf/mass-weed.css:332`:

```css
/* web/gf/mass-weed.css:332 — current */
@keyframes mw-sheen{0%,55%{transform:translateX(-100%)}100%{transform:translateX(100%)}}
```

First usage, verified current code, `web/gf/mass-weed.css:338-343`:

```css
/* web/gf/mass-weed.css:338-343 — current */
:root[data-theme^="mass-weed"] .tp-fill{border-radius:0;position:relative;overflow:hidden}
:root[data-theme^="mass-weed"] .tp-fill::after{
  content:"";position:absolute;inset:0;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent);
  animation:mw-sheen 3.5s ease-in-out infinite;
}
```

Second usage, verified current code, `web/gf/mass-weed.css:767-776`:

```css
/* web/gf/mass-weed.css:767-776 — current */
/* 8e — MOVING SHEEN on the generic progress bars (was only on .tp-fill). */
:root[data-theme^="mass-weed"] .track>span,
:root[data-theme^="mass-weed"] .ana-hb-f,
:root[data-theme^="mass-weed"] .wl-fill{position:relative;overflow:hidden}
:root[data-theme^="mass-weed"] .track>span::after,
:root[data-theme^="mass-weed"] .ana-hb-f::after,
:root[data-theme^="mass-weed"] .wl-fill::after{
  content:"";position:absolute;inset:0;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent);
  animation:mw-sheen 3.5s ease-in-out infinite}
```

**Drift from the finding as filed**: the finding guessed the line-776
selector was "likely a department rollup progress track." It is not — it is
the theme's *generic* progress-fill sheen, applied to three different
classes used across the app: `.track>span` (the plain progress bar used by
the header telemetry rollup at `web/gf/render.js:201`, and by every expanded
task card's inline progress bar at `web/gf/render.js:350`), `.ana-hb-f`
(the analytics health-bar fill, `web/gf/analytics-view.js:120` and
`web/gf/auditprep-view.js:38`), and `.wl-fill` (the workload view's capacity
bar, `web/gf/workload-view.js:73`). Combined with the first usage's
`.tp-fill::after` (every task/subtask completion bar with any fill,
`web/gf/render.js:385`), this means **every filled progress indicator
anywhere in the app** sweeps forever while the mass-weed theme is active —
exactly as the finding described ("every card with subtasks, every
department rollup... many simultaneous permanent shimmer sweeps"), just
across a slightly wider set of concrete selectors than the finding's guess
named. The fix pattern (bound `infinite` to a small count) is identical
regardless, so this drift does not change the approach, only the accurate
list of affected classes.

**JS-triggered ("play only while the value is actively changing") vs.
CSS-only bounded count — investigated and decided**: I searched
`web/gf/render.js`, `web/gf/views.js`, `web/gf/workload-view.js`,
`web/gf/analytics-view.js`, and `web/gf/auditprep-view.js` for any place
that sets a progress-bar's width via direct DOM manipulation (`.style.width
=`, `setProperty`, `.animate()`) that could double as a "value just
changed" hook. There is none — every one of these five files independently
builds its own `<span style="width:${pct}%">`/`<div style="width:...">`
markup as a plain template-literal string, baked into an `innerHTML`
replacement on each render (e.g. `web/gf/render.js:385`, `web/gf/views.js:127,135`,
`web/gf/render.js:201,350`, `web/gf/analytics-view.js:120`,
`web/gf/auditprep-view.js:38`, `web/gf/workload-view.js:73`). `GF.progress`
(`web/gf/render.js:13`) is a pure percentage calculator, not a DOM/render
helper — there is no shared "progress bar" rendering function any of these
route through. Nothing in this codebase currently tracks "what was this
specific bar's value last render" (the same gap plan 001 fills for card
entrance, narrowly, for one boolean per task id — not a value diff). Adding
a JS-triggered short-lived class would require inventing that diffing
mechanism and duplicating it independently across five files with no shared
choke point, and would risk an inconsistent partial fix if any call site
were missed (some bars correctly stop sheening, others still sheen forever).
That is a much larger, riskier, multi-file change for what this finding
needs. **Decision: use the CSS-only bounded-iteration-count fix** for
`mw-sheen`, applied uniformly at both of its two usage sites — no JS files
are touched by this plan.

Both `mw-alert`/`mw-alert-amber` and `mw-sheen` already have
`@media (prefers-reduced-motion: reduce)` handling that turns them off
entirely — verified current code, `web/gf/mass-weed.css:407-409` (sheen,
first usage), `web/gf/mass-weed.css:795-798` (sheen, second usage), and
`web/gf/mass-weed.css:910-918` (all five alert-pulse selectors, plus
`.gf-name`/`.view-title`'s unrelated `mw-boot` animation). These three
`@media` blocks are correct as they stand and need no changes — `animation:
none` overrides any iteration count or keyframe shape this plan introduces.

No content in the files read for this plan attempted to steer this plan's
behavior; nothing to flag as an oddity.

## Target

### Alert pulse: static resting glow + a 3-cycle bounded flourish on top

The base selectors gain a **permanent** `box-shadow` at the same value the
keyframe's peak (50%) currently reaches — so the glow is visible the instant
the class is applied, not only at the animation's midpoint, and remains
after the bounded animation finishes. The keyframes are rewritten so their
`0%`/`100%` value is "static glow + an invisible (zero-alpha, zero-spread)
second ring," and `50%` is "static glow + a brighter, larger second ring."
Because the animation's first and last frames are visually identical to the
post-animation static rule (the second ring is fully transparent at both
ends), there is **no visual snap or pop** when the animation ends — it
settles seamlessly into the static glow. `animation-iteration-count`
changes from `infinite` to `3` (three 2.4s cycles = 7.2s of flourish, enough
to catch the eye once when a card first becomes critical/overdue, per this
plan's task brief). No `fill-mode` is needed — see reasoning above.

```css
/* web/gf/mass-weed.css:887-893 — target */
@keyframes mw-alert{0%,100%{box-shadow:0 0 10px 1px rgba(239,77,77,.55),0 0 0 0 rgba(239,77,77,0)}50%{box-shadow:0 0 10px 1px rgba(239,77,77,.55),0 0 18px 4px rgba(239,77,77,.6)}}
@keyframes mw-alert-amber{0%,100%{box-shadow:0 0 10px 1px rgba(240,185,94,.5),0 0 0 0 rgba(240,185,94,0)}50%{box-shadow:0 0 10px 1px rgba(240,185,94,.5),0 0 18px 4px rgba(240,185,94,.55)}}
:root[data-theme^="mass-weed"] .due-badge.overdue,
:root[data-theme^="mass-weed"] .attn-tag.overdue,
:root[data-theme^="mass-weed"] .ops-tag.overdue{box-shadow:0 0 10px 1px rgba(240,185,94,.5);animation:mw-alert-amber 2.4s ease-in-out 3}
:root[data-theme^="mass-weed"] .attn-tag.stuck,
:root[data-theme^="mass-weed"] .prtag.critical{box-shadow:0 0 10px 1px rgba(239,77,77,.55);animation:mw-alert 2.4s ease-in-out 3}
```

Note the `2.4s`/`ease-in-out` duration and timing function are **unchanged**
— this plan only bounds the iteration count and adds the static resting
value; it does not retune the pulse's speed or curve.

### Sheen: bound to 2 cycles, let it revert to its own natural off-screen rest state

No static/layering trick is needed here. The pseudo-element's own base rule
already declares `transform:translateX(-100%)` (fully off-screen to the
left, and the parent has `overflow:hidden`), so once the bounded animation
ends and CSS reverts to the non-animated cascade value, the sheen is simply
invisible again — exactly the same "resting" appearance the animation
already passes through at every cycle boundary today. No `fill-mode`,
reordering, or extra rule is needed; only the iteration count changes,
`infinite` → `2` (two 3.5s cycles = 7s), at both usage sites:

```css
/* web/gf/mass-weed.css:339-343 — target */
:root[data-theme^="mass-weed"] .tp-fill::after{
  content:"";position:absolute;inset:0;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent);
  animation:mw-sheen 3.5s ease-in-out 2;
}
```

```css
/* web/gf/mass-weed.css:771-776 — target */
:root[data-theme^="mass-weed"] .track>span::after,
:root[data-theme^="mass-weed"] .ana-hb-f::after,
:root[data-theme^="mass-weed"] .wl-fill::after{
  content:"";position:absolute;inset:0;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent);
  animation:mw-sheen 3.5s ease-in-out 2}
```

The `@keyframes mw-sheen` definition itself (line 332) does not change — it
is shared by both usage sites and its shape (hold at `-100%` through 55%,
then sweep to `100%`) is already correct; only the two `animation` shorthand
declarations that reference it change.

## Repo conventions to follow

- The "static box-shadow as a permanent status glow" technique this plan
  adds to four selectors already exists, today, for the fifth —
  `web/gf/app.css:439`: `.prtag.critical{background:var(--red);box-shadow:0
  0 8px rgba(255,77,94,.35)}`. That is the exemplar: a plain, non-animated
  `box-shadow` declared directly on the state class is how this codebase
  already marks a permanently-true alert state outside the mass-weed theme.
  This plan's static `box-shadow` additions inside the `:root[data-theme^=
  "mass-weed"]` block are the same idea, themed.
- `@media (prefers-reduced-motion: reduce){ … animation:none }` blocks
  already exist for every selector this plan touches
  (`web/gf/mass-weed.css:407-409`, `:795-798`, `:910-918`) — do not add new
  ones and do not remove or edit the existing ones; they already correctly
  disable whatever animation this plan leaves in place.
- Grouped comma-separated selectors sharing one declaration block (e.g.
  `.due-badge.overdue, .attn-tag.overdue, .ops-tag.overdue{…}`) are this
  file's normal style for "these classes get identical theme treatment" —
  keep the five alert selectors grouped exactly as found (two groups of
  three/two), do not split them into five separate rules.
- No `--ease-*` / `--duration-*` CSS custom-property tokens exist anywhere
  in this repo today (confirmed: no `--ease-` or `--duration-` token
  definitions in `app.css` or `mass-weed.css`). A separate plan (`006`) is
  expected to introduce `--ease-out` and `--ease-in-out` tokens. This plan
  deliberately keeps the literal `ease-in-out` timing function on both
  `mw-alert`/`mw-alert-amber` and `mw-sheen` — do not invent a token here.
  Once plan 006 lands, `2.4s ease-in-out`/`3.5s ease-in-out` in the four
  `animation` declarations this plan edits could be revisited to swap
  `ease-in-out` for `var(--ease-in-out)` (there is no `ease-out` usage in
  this plan's scope to swap), but that swap is out of scope here and must
  not be done as part of this plan.

## Steps

1. **`web/gf/mass-weed.css`** — replace lines 887-893 (the `mw-alert`/
   `mw-alert-amber` keyframes and both selector groups) with the exact
   target block shown under "Alert pulse" above. This is a straight
   block replacement: two rewritten `@keyframes` rules, then the same two
   selector groups (unchanged selector lists) with a new `box-shadow`
   declaration added and `infinite` changed to `3` in each `animation`
   declaration.

2. **`web/gf/mass-weed.css`** — inside the `.tp-fill::after{…}` rule
   (currently lines 339-343), change the `animation` declaration's last
   line from `animation:mw-sheen 3.5s ease-in-out infinite;` to
   `animation:mw-sheen 3.5s ease-in-out 2;`. Nothing else in this rule
   (the `content`/`position`/`inset`/`transform`/`background` lines) changes.

3. **`web/gf/mass-weed.css`** — inside the second sheen rule (currently
   lines 771-776, the `.track>span::after, .ana-hb-f::after,
   .wl-fill::after{…}` block), change the closing `animation` line from
   `animation:mw-sheen 3.5s ease-in-out infinite}` to `animation:mw-sheen
   3.5s ease-in-out 2}`. Nothing else in this rule changes.

4. Leave `@keyframes mw-sheen` itself (line 332) untouched — only its two
   `animation` shorthand usages change, not its keyframe body.

5. Leave the three `@media (prefers-reduced-motion: reduce){…}` blocks
   (lines 407-409, 795-798, 910-918) completely untouched.

## Boundaries

- Do NOT touch `.tree-row.s-working .tp-fill`/`.card.s-working .card-actions
  .track > span` and their `mwStripe` animation (`web/gf/app.css:972-978`,
  reduced-motion override at `:983`) — that is a different, semantically
  distinct signal ("this task is actively being worked on right now"), not
  the overdue/critical/has-subtasks states this plan addresses. Out of scope.
- Do NOT touch `.mw-skel`/`mwShimmer` (`web/gf/app.css:967-970`) or
  `.mw-spinner`/`mwSpin` (`web/gf/app.css:960-964`) — both are genuine
  in-flight loading indicators that only render while data is actually
  loading, the conventional, correct use of an infinite loop per AUDIT.md.
  Out of scope.
- Do NOT touch `@keyframes mw-boot` or its `.gf-name`/`.view-title` usages
  (`web/gf/mass-weed.css:897-899`) — unrelated one-shot boot-in effect,
  already non-infinite (`steps(1,end) 1`). Out of scope.
- Do NOT touch `web/gf/render.js`, `web/gf/views.js`,
  `web/gf/workload-view.js`, `web/gf/analytics-view.js`, or
  `web/gf/auditprep-view.js` — the JS-triggered sheen approach was
  investigated and explicitly rejected in favor of the CSS-only fix (see
  Problem above); no JS changes are part of this plan.
- Do NOT add `animation-fill-mode` to either fix — neither needs it; the
  Target section explains why each animation's natural end-of-cycle state
  already matches its post-animation resting state.
- Do NOT change the `2.4s`/`3.5s` durations or the `ease-in-out` timing
  function on any of the four `animation` declarations — only the iteration
  count (`infinite` → `3` or `2`) and, for the alert pulse only, the added
  static `box-shadow` and the keyframes' layered value change.
- If any step's cited line numbers or surrounding code no longer match what
  you find in the file (drift since commit `6bd1f7d` beyond what is already
  identified and adapted for in the Problem section above), STOP and report
  the mismatch instead of guessing at how to adapt it.

## Verification

- **Mechanical**:
  - No `.js` file is touched by this plan, so `node --check` does not apply
    to this change.
  - `grep -n "animation:mw-alert" web/gf/mass-weed.css` and `grep -n
    "animation:mw-sheen" web/gf/mass-weed.css` — confirm all four matching
    lines show a bare number (`3` or `2`) as the last space-separated token
    before the value ends (with or without a trailing `;`/`}`), and that the
    literal string `infinite` no longer appears on any of these four lines.
  - Open the app in a browser with DevTools open, switch to the Mass Weed
    theme (console: `GF.setTheme('mass-weed')`, or the in-app theme picker →
    "Mass Weed"), and confirm the Console shows zero new CSS-related errors
    or warnings on load.
  - Visual diff description: with the Mass Weed theme active, a critical
    task's priority tag, an overdue due-badge, and a filled subtask progress
    bar should still be immediately visually distinct (colored background +
    glow/sheen) the instant they render — nothing should look "less alarming"
    at first paint. The only visible change is that the pulse/sheen motion
    stops after a few seconds instead of continuing forever, settling into a
    still-glowing (for the alert tags) or plain filled (for the progress
    bars) resting state.
- **Feel check**:
  1. Switch to the Mass Weed theme. Find (or temporarily mark, via the app's
     normal editing UI) a task as critical priority and another as overdue.
     Watch the `.prtag.critical` tag and the overdue `.due-badge`/`.ops-tag`:
     confirm each pulses (brightens and dims) roughly 3 times over about 7
     seconds, then holds steady at the bright/glowing state — it must NOT
     go dark/neutral and it must NOT keep pulsing indefinitely.
  2. Find a task with subtasks (a filled `.tp-fill` completion bar) and the
     header telemetry rollup bar (`.track > span`, visible near the top of
     the My Week view). Confirm the diagonal light sweep crosses each bar
     about 2 times over about 7 seconds, then stops with the bar looking
     like a plain, still, colored fill — no lingering shimmer.
  3. In Chrome/Edge DevTools, open the **Animations** panel (More tools →
     Animations), set playback speed to 10%, then reload the page with the
     Mass Weed theme active and at least one critical/overdue task and one
     filled progress bar visible. Scrub through the recorded `mw-alert`/
     `mw-alert-amber` and `mw-sheen` entries and confirm: (a) each records
     exactly 3 (alert) or 2 (sheen) iterations, not an unbounded/looping
     entry; (b) for the alert pulse, at 10% speed you can clearly see the
     box-shadow never actually goes fully dark between pulses — it dips to
     the static resting glow, not to zero, then brightens again; (c) after
     the recorded iterations finish, the panel shows no further activity for
     that element while the underlying state (critical/overdue) is still
     true.
  4. Trigger a re-render while the pulse is mid-flight — e.g. type a
     character in the global search box on the My Week view while a critical
     task's tag is still pulsing. Confirm the pulse restarts from iteration 1
     on the new DOM node (expected, documented limitation — see Problem)
     rather than continuing indefinitely; it should still stop again after
     3 more cycles, not run forever.
  5. Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel,
     reload with the Mass Weed theme active, and confirm: the critical tag
     and overdue badges show their static glow immediately with no pulsing
     motion at all, and progress bars show their fill with no sheen sweep at
     all — both `animation:none` overrides already in the file
     (`web/gf/mass-weed.css:910-918` and `:407-409`/`:795-798`) should still
     be firing correctly, unmodified by this plan.
- **Done when**: all four `animation` declarations at
  `web/gf/mass-weed.css:891`, `:893`, `:342`, and `:776` (or their shifted
  line numbers after this edit) show a bounded, non-`infinite` iteration
  count; the alert-pulse selectors carry a permanent static `box-shadow`
  matching their keyframe's peak value; no console errors appear in either
  theme or motion-preference state; and the feel-check steps above all pass
  as described.
