# 012 — Give the card-body reveal a translateY entrance instead of a pure fade

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: LOW
- **Category**: 3. Physicality & origin
- **Estimated scope**: 1 file (`web/gf/app.css`), ~3 lines changed inside one existing rule block. Depends on plan `002` (`plans/002-overlay-modal-exit-animation.md`) having landed first — see Boundaries.

## Problem

### `expandIn` is the one entrance keyframe in this app with zero initial transform

Verified current code, `web/gf/app.css:224-227` (the full keyframes block containing every entrance animation in the app):

```css
/* web/gf/app.css:224-227 — current */
@keyframes cardIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes expandIn{from{opacity:0}to{opacity:1}}
@keyframes modalIn{from{opacity:0;transform:scale(.96) translateY(8px)}to{opacity:1;transform:none}}
@keyframes toastIn{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:none}}
```

Verified current code, `web/gf/app.css:447-449` (where `expandIn` is used):

```css
/* web/gf/app.css:447-449 — current */
.card-body{display:none;padding:0 15px 15px;border-top:1px solid var(--line-2);
  margin:0 0 0 0;padding-top:14px}
.card.expanded .card-body{display:block;animation:expandIn .15s ease}
```

Every other entrance animation in the app pairs `opacity` with a real spatial move:
`cardIn` (line 224) pairs it with `translateY(6px)→none`; `modalIn` (line 226) with
`scale(.96) translateY(8px)→none`; `toastIn` (line 227) with `translateX(30px)→none`.
`expandIn` (line 225) is the outlier — pure `opacity:0→1`, no transform at all — which
is exactly the "pure-fade entrances with no initial transform" pattern
`.claude/skills/improve-animations/AUDIT.md`'s section "3. Physicality & origin" calls
out to hunt for: "Hunt for: `scale(0)`, pure-fade entrances with no initial transform,
`transform-origin: center` (or none) on trigger-anchored elements, pressable elements
with no press feedback." A card's expand/collapse body is one of the more frequently
triggered reveals in the app (used every time a task is triaged/expanded to read notes
or take action), so this flatness is felt often, not just once.

### This exact code is also plan 002's target — read plan 002 before editing anything

`plans/002-overlay-modal-exit-animation.md` (Status: TODO as of this writing) already
targets this same `.card-body` / `.card.expanded .card-body` rule and this same
`@keyframes expandIn`, as part of fixing `.card-body`'s missing *exit* animation (the
`display:none`/`block` toggle is a discontinuous property that cannot be transitioned in
either direction, and `@keyframes` cannot play in reverse). Plan 002's Target section 3
replaces `web/gf/app.css:447-449` and deletes `@keyframes expandIn` (line 225) entirely,
introducing a `grid-template-rows: 0fr → 1fr` mechanism with a new wrapper element.
Quoted verbatim from `plans/002-overlay-modal-exit-animation.md`'s Target section 3:

```css
/* plans/002-overlay-modal-exit-animation.md's Target — replaces app.css:447-449 */
.card-body{display:grid;grid-template-rows:0fr;
  transition:grid-template-rows 150ms cubic-bezier(0.23, 1, 0.32, 1)}
.card.expanded .card-body{grid-template-rows:1fr}
.card-body-inner{overflow:hidden;padding:0 15px 15px;border-top:1px solid var(--line-2);
  margin:0 0 0 0;padding-top:14px;
  opacity:0;transition:opacity 150ms cubic-bezier(0.23, 1, 0.32, 1)}
.card.expanded .card-body-inner{opacity:1}
```

Plan 002 also adds a `<div class="card-body-inner">` wrapper inside `card()`'s body
template in `web/gf/render.js` (its Step 7), so the new `.card-body-inner` selector has
something to attach to, and deletes `@keyframes expandIn` (its Step 6).

**This changes the shape of this finding, not the finding itself.** Plan 002's
`.card-body-inner` rule fixes the exit-animation defect (category 4/8) but reproduces
the exact same physicality defect this plan is about: it is still a pure `opacity:0→1`
fade with no initial transform — the flatness just moved from the `@keyframes expandIn`
keyframe onto the new `.card-body-inner` transition. This plan (012) is therefore a
small, targeted addendum on top of plan 002's technique: once plan 002's
`.card-body-inner` rule exists, add a `translateY` pair to it, matching the vocabulary
`cardIn`/`modalIn`/`toastIn` already establish elsewhere in this file.

No content in the read files (`AUDIT.md`, `PLAN-TEMPLATE.md`, `app.css`, plan 002)
attempted to steer this plan's behavior; nothing to flag as an oddity.

## Target

AUDIT.md's section "3. Physicality & origin" gives two possible shapes for physicality:
scale (`"Never scale(0) — nothing in the real world appears from nothing. Target:
scale(0.9–0.97) + opacity: 0."`) and, separately, translate (demonstrated by this app's
own `cardIn`/`modalIn`/`toastIn`). The `scale(0.9–0.97)` guidance in AUDIT.md is aimed at
trigger-anchored popovers/dropdowns scaling from a point of origin (see AUDIT.md section
3's popover/dropdown guidance) — `.card-body` is not that shape. It is not appearing
"from a point," it is a block of already-positioned, natural-flow content (notes,
buttons, a description) unfurling below an already-visible, already-full-width card
header. A small `translateY`, not a scale, is the correct match here — the same
reasoning that makes `cardIn` (a card joining a list) use `translateY(6px)` instead of a
scale.

**Direction matters, and it is not simply "copy cardIn's sign."** `cardIn`'s
`translateY(6px)→none` is *positive*: a card is a new item settling into a vertical
list, and items in a list conventionally arrive from slightly below, drifting up into
place. `.card-body-inner` is a different physical situation: nothing is joining a list.
The card header stays exactly where it is, and the body unfurls *underneath* it as the
`.card-body` grid row opens from `0fr` to `1fr` (per plan 002's mechanism). The content
should read as **dropping down into the newly-opened space**, settling from slightly
*above* its resting position — not as rising up out of the collapsed sliver beneath the
fold to meet its final position, which is what a *positive* `translateY` would suggest,
and which would visually fight the downward-opening direction of the grid-row expansion
itself. That means the correct sign here is **negative**: `translateY(-4px) → none`.
The magnitude is also deliberately smaller than `cardIn`'s `6px` — `4px` — because this
is a frequent, in-place, already-occasional-per-AUDIT.md-frequency-table reveal (not a
first-appearance list entrance), so it should read as a subtle settle, not a noticeable
slide.

Duration and easing are not new decisions for this plan — they are inherited unchanged
from plan 002's own `.card-body-inner` rule (`150ms`, matching AUDIT.md's duration table
"Dropdowns, selects | 150–250ms" band as the closest listed analogue to an in-place
content reveal, and `cubic-bezier(0.23, 1, 0.32, 1)`, AUDIT.md's `--ease-out` curve for
"Entering or exiting"). This plan only adds `transform` to the same `transition:`
declaration plan 002 already writes, so opacity and the new translateY move in lockstep,
not on a second, differently-timed transition.

```css
/* web/gf/app.css — target: the ONLY rule this plan touches, once plan 002 has
   landed. This is plan 002's `.card-body-inner` block (quoted above) with a
   translateY pair added; `.card-body` / `.card.expanded .card-body` (the
   grid-template-rows rules) are UNCHANGED and not touched by this plan. */
.card-body-inner{overflow:hidden;padding:0 15px 15px;border-top:1px solid var(--line-2);
  margin:0 0 0 0;padding-top:14px;
  opacity:0;transform:translateY(-4px);
  transition:opacity 150ms cubic-bezier(0.23, 1, 0.32, 1),transform 150ms cubic-bezier(0.23, 1, 0.32, 1)}
.card.expanded .card-body-inner{opacity:1;transform:none}
```

Three changes relative to plan 002's version of this rule, all inside `.card-body-inner`
and its `.expanded` pair: (1) `transform:translateY(-4px)` added next to `opacity:0`,
(2) the `transition:` list extended with `,transform 150ms cubic-bezier(0.23, 1, 0.32, 1)`,
(3) `transform:none` added next to `opacity:1` in `.card.expanded .card-body-inner`.

## Repo conventions to follow

- **`cardIn`/`modalIn`/`toastIn`'s own vocabulary is the exemplar**: every real entrance
  in this app pairs `opacity` with a matching `transform` (`web/gf/app.css:224,226,227`).
  This plan brings `.card-body-inner` in line with that existing convention instead of
  leaving it a pure-opacity outlier.
- No `--ease-*` / `--duration-*` CSS custom-property tokens exist anywhere in this repo
  today (confirmed: no `--ease-` or `--duration-` token definitions in `app.css`). Plan
  `006` (`plans/006-easing-duration-tokens.md`) is expected to introduce `--ease-out` and
  `--ease-in-out` tokens. This plan uses the literal `cubic-bezier(0.23, 1, 0.32, 1)`
  value directly, matching the exact literal plan 002 already writes for this same
  element, so the two edits stay textually consistent. Once plan 006 lands, both could be
  revisited to swap in `var(--ease-out)`, but that swap is out of scope here and must not
  be done as part of this plan.
- Plan 002's choice of a plain CSS `transition:` (not a `@keyframes` animation) for
  `.card-body-inner` is deliberate, per AUDIT.md section 4 ("Interruptibility"):
  transitions retarget smoothly from the current state on rapid re-triggering,
  `@keyframes` restarts from zero. This plan must preserve that — the new `transform` is
  added to the same `transition:` property list, never a new `@keyframes` block.

## Steps

1. Open `web/gf/app.css` and locate the `.card-body-inner{...}` rule and its sibling
   `.card.expanded .card-body-inner{...}` rule (introduced by plan 002 — exact current
   line numbers depend on where plan 002 landed them; they replace what was
   `web/gf/app.css:447-449` before plan 002's edit). Confirm they read exactly as quoted
   under "Verified current code" in the Problem section's plan-002 quote above (i.e.
   `opacity:0;transition:opacity 150ms cubic-bezier(0.23, 1, 0.32, 1)}` and
   `.card.expanded .card-body-inner{opacity:1}`). If you cannot find this rule at all —
   i.e. `web/gf/app.css` still shows the pre-002 `.card-body{display:none;...}` /
   `.card.expanded .card-body{display:block;animation:expandIn .15s ease}` mechanism with
   `@keyframes expandIn{from{opacity:0}to{opacity:1}}` still present — STOP. See
   Boundaries; this plan is not yet actionable.
2. In `.card-body-inner{...}`, add `transform:translateY(-4px)` immediately after
   `opacity:0;`.
3. In the same rule's `transition:` declaration, extend it from
   `transition:opacity 150ms cubic-bezier(0.23, 1, 0.32, 1)` to
   `transition:opacity 150ms cubic-bezier(0.23, 1, 0.32, 1),transform 150ms cubic-bezier(0.23, 1, 0.32, 1)`.
4. In `.card.expanded .card-body-inner{opacity:1}`, add `transform:none` so the rule
   reads `.card.expanded .card-body-inner{opacity:1;transform:none}`.
5. Leave every other declaration in both rules (`overflow`, `padding`, `border-top`,
   `margin`, `padding-top`) and every other rule in the file completely untouched.

## Boundaries

- Do NOT touch `web/gf/render.js` — plan 002's Step 7 already adds the
  `.card-body-inner` wrapper `<div>`; this plan requires that wrapper to already exist
  in the markup and only edits its CSS rule. No JS changes are needed or in scope here.
- Do NOT touch `.card-body{...}` / `.card.expanded .card-body{...}` (the
  `grid-template-rows` rules plan 002 introduces) — those are plan 002's concern and are
  already correct as written; this plan only touches `.card-body-inner` and
  `.card.expanded .card-body-inner`.
- Do NOT re-add, restore, or reference `@keyframes expandIn` — it is intentionally
  deleted by plan 002's Step 6. This plan does not need it and must not resurrect it in
  any form.
- Do NOT change the `150ms` duration or the `cubic-bezier(0.23, 1, 0.32, 1)` curve
  already established by plan 002 for this element — reuse them exactly (as shown in
  Target above) so the new `transform` moves in lockstep with the existing `opacity`
  transition, not on a separately-timed one.
- Do NOT add new dependencies or a build step.
- **If plan 002 has not yet executed** — i.e. `web/gf/app.css` still shows the old
  `.card-body{display:none;...}` / `.card.expanded .card-body{display:block;
  animation:expandIn .15s ease}` mechanism with `@keyframes expandIn` still present —
  **STOP**. This plan's Target is written against plan 002's post-landing
  `.card-body-inner` rule, which does not exist until plan 002 has been applied; there is
  nothing here for this plan to edit yet. Do not improvise a transform onto the old
  `expandIn` keyframe or the `display:none` mechanism as a substitute — that mechanism is
  being deleted, not fixed, by plan 002. Land plan 002 first, then return to this plan.
- **If plan 002 has landed but produced a structurally different mechanism** than what is
  quoted in this plan's Problem/Target sections (a different wrapper class name, a
  different CSS property driving the reveal, a different duration) — STOP and adapt:
  apply the same underlying principle (a small `translateY(-4px)→none` paired with
  whatever opacity transition is actually present on the content wrapper, using
  whatever duration/easing that actual rule already uses) rather than blindly pasting the
  exact CSS block from this plan's Target section.
- If any other cited line number or surrounding code no longer matches what you find in
  the file (drift since commit `6bd1f7d`, beyond the plan-002-landing question above),
  STOP and report the mismatch instead of guessing at how to adapt it.

## Verification

- **Mechanical**:
  - This plan touches no `.js` file, so there is no `node --check` target for this
    specific change (plan 002's own `render.js` edit is verified by plan 002, not here).
  - `web/gf/app.css` has no syntax checker available in this repo (no build step, no
    `package.json` at the repo root). Visually confirm the edited rule has balanced
    `{`/`}` and every declaration ends in `;` or is the last one in its block.
  - Open the app in a browser with DevTools' Console open. Expand and collapse a task
    card a few times. Confirm zero new Console errors or warnings.
  - Visual diff description: before this change, the card body (once plan 002 has
    landed) crossfades in flatly — only `opacity` moves, the content is static in place.
    After this change, the same crossfade is accompanied by the content easing down
    ~4px into its resting position as it fades in (and lifting back up ~4px as it fades
    out on collapse), in the same 150ms window as the opacity change.
  - **Note on exercising this through the real UI**: per plan 002's Problem section,
    `web/gf/render.js`'s `card()` function currently rebuilds `.card-body`/
    `.card-body-inner` fresh on every `GF.render.panels()` call and omits it entirely
    when collapsed (`GF.toggleExpand`, `web/gf/core.js:504`, calls `render.panels()`,
    which replaces `#panels`'s entire `innerHTML`). This means a freshly-inserted node
    has no "before" state to transition from, so clicking a card's expand toggle in the
    live app will **not** visibly show this transition regardless of the CSS — this is a
    pre-existing architectural gap that plan 002 documents and explicitly leaves
    unfixed, and this plan does not fix it either. Use the DevTools-based check below to
    verify the CSS mechanism directly.
- **Feel check**:
  1. Expand any task card so `.card-body`/`.card-body-inner` exist in the DOM (via the
     app's normal expand click — the DOM nodes will exist afterward even though the
     transition itself didn't play, per the note above).
  2. In DevTools' Elements panel, select the `.card` element and, using the class-list
     editor (the small "+"/checkbox UI, not clicking in the app), toggle the `expanded`
     class off, then back on.
  3. With playback at normal speed first: confirm collapsing visibly lifts the content
     up slightly while it fades out, and expanding visibly drops the content down
     slightly into place while it fades in — it should read as the content settling into
     the newly-opened space from just above, not as a flat crossfade and not as the
     content rising up from below.
  4. Open Chrome/Edge DevTools' **Animations** panel (More tools → Animations), set
     playback speed to **10%**, then repeat the class toggle from step 2. Confirm you see
     a `transform` entry and an `opacity` entry on `.card-body-inner`, both starting and
     ending at the same time (perfect lockstep, no stagger between them), and that
     scrubbing through the `transform` shows a smooth `translateY(-4px) → none` motion
     with a fast-start/slow-finish curve (matching `cubic-bezier(0.23, 1, 0.32, 1)` — no
     linear motion, no bounce, no overshoot past `translateY(0)`).
  5. Toggle the class off and on a few times in quick succession (as fast as the class
     editor allows). Confirm the transform never freezes, snaps, or jumps to a
     half-finished state — because this is a `transition` (not `@keyframes`), each
     re-trigger should smoothly retarget from wherever `.card-body-inner` currently sits.
  6. Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel (More tools →
     Rendering → Emulate CSS media feature `prefers-reduced-motion`) and repeat step 2.
     Confirm the translateY/opacity transition still plays exactly as before — this repo
     has no `prefers-reduced-motion` handling for `.card-body`/`.card-body-inner` either
     before or after this plan (a pre-existing gap noted in plan 002's Boundaries too);
     adding that coverage is out of scope for this plan.
- **Done when**: `.card-body-inner`'s rule (wherever plan 002 landed it) includes
  `transform:translateY(-4px)` paired with `opacity:0` in its base state and
  `transform:none` paired with `opacity:1` in `.card.expanded .card-body-inner`, both
  riding the same `150ms cubic-bezier(0.23, 1, 0.32, 1)` transition; manual DevTools
  class-toggling (per feel check above) shows the transform and opacity animating in
  perfect lockstep with a fast-start/slow-finish curve and no overshoot; rapid toggling
  never snaps or freezes; `@keyframes expandIn` remains deleted (not resurrected); and no
  new Console errors appear on expand/collapse.
