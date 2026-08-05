# 008 — Gate transform-based `:hover` rules behind `@media (hover: hover) and (pointer: fine)`

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: MEDIUM
- **Category**: 6. Accessibility
- **Estimated scope**: 3 files (`web/gf/app.css`, `web/gf/mass-weed.css`, `web/gf/views.css`) — 9 `:hover` rules rewrapped in `@media (hover: hover) and (pointer: fine){ }` blocks (1 in `app.css`, 5 in `mass-weed.css`, 3 in `views.css`). No JS files touched, no markup/structure changes, no new custom properties, no new dependencies.

## Problem

Touchscreens fire a synthetic "hover" on tap with no corresponding hover-end
event — a real mouse pointer leaves the element and the browser clears
`:hover` automatically, but a finger has nothing to leave. On a touch or
tablet device, tapping any element with an ungated `:hover{transform:...}`
rule makes that transform activate and then **stay activated** (visually
"stuck") until the user happens to tap some other hoverable element — there
is no gesture that reliably clears it. AUDIT.md's category 6 names this
exact failure mode and gives the fix:

```css
/* .claude/skills/improve-animations/AUDIT.md:88-91 */
@media (hover: hover) and (pointer: fine) {
  .element:hover { transform: scale(1.05); } /* touch fires false hovers on tap */
}
```

This repo has zero instances of that media feature anywhere. Confirmed by
direct search against the live tree:

```
$ grep -rn "@media (hover: hover)" web/gf/*.css
(no output — zero matches across all 8 CSS files: app.css, brand.css,
 entry.css, leaf-fx.css, mass-weed.css, mobile.css, skins.css, views.css)
```

The only touch-aware media feature used anywhere in the app is the inverse
condition, and it only adjusts touch-target sizing — it does nothing to
neutralize any hover-transform rule:

```css
/* web/gf/mobile.css:7-11 — current, unrelated to this plan, cited for context only */
@media (hover: none) and (pointer: coarse) {
  .btn, .btn-sm, .icon-btn, .pill { min-height: 36px; }
  .nav-item { padding-top: 12px; padding-bottom: 12px; }
  input, select, textarea { font-size: 16px !important; /* iOS no-zoom */ }
}
```

`web/gf/mobile.css` exists and is non-trivial (173 lines, two real
breakpoints for tablet and phone plus a bottom nav bar), confirming this app
really is used on touch/tablet hardware — plausible for staff on a
cultivation-facility floor using a tablet rather than a mouse. Every rule
below will visibly "stick" (lifted card, glowing edge, scaled dot) after a
single tap on such a device, with no way for the user to clear it except
tapping elsewhere.

Nine confirmed ungated `:hover{transform:...}` rules, each read directly
from the live file and quoted verbatim:

```css
/* web/gf/app.css:398 — current */
.card:hover{box-shadow:var(--sh-2);transform:translateY(-1px)}
```

```css
/* web/gf/mass-weed.css:255-257 — current (base rule; note this is the
   selector the file's existing reduced-motion override at lines 305-307
   already targets — see "Repo conventions to follow" below for why that
   matters to how this edit must be placed) */
:root[data-theme^="mass-weed"] .card:hover{
  box-shadow:var(--sh-2), 0 0 18px rgba(var(--accent-rgb),.28);transform:translateY(-1px)
}
```

```css
/* web/gf/mass-weed.css:591-593 — current */
:root[data-theme^="mass-weed"] .kcard:hover,
:root[data-theme^="mass-weed"] .team-card:hover{
  box-shadow:var(--sh-2), 0 0 16px rgba(var(--accent-rgb),.22);transform:translateY(-1px)}
```

```css
/* web/gf/mass-weed.css:815-817 — current (a second, later, equal-specificity
   .kcard:hover rule that wins the cascade over the one above for .kcard
   elements specifically — see comment at mass-weed.css:807-811 in the file
   itself, which explains this is deliberate) */
:root[data-theme^="mass-weed"] .kcard:hover{
  box-shadow:var(--sh-2), 0 0 16px rgba(var(--accent-rgb),.22),
    inset 3px 0 0 var(--dept-acc, var(--primary));transform:translateY(-1px)}
```

```css
/* web/gf/mass-weed.css:1096 — current */
.mw-tcard:hover{ transform:translateX(2px); filter:brightness(1.12); }
```

```css
/* web/gf/mass-weed.css:1455 — current */
.mw-skins__dot:hover{ transform:scale(1.18); }
```

```css
/* web/gf/views.css:37 — current (base, non-theme-scoped .kcard:hover —
   distinct from the two mass-weed.css .kcard:hover rules above, which only
   apply when data-theme starts with "mass-weed"; both must be gated
   independently, they are not duplicates of each other) */
.kcard:hover{transform:translateY(-2px);box-shadow:var(--sh-2)}
```

```css
/* web/gf/views.css:62 — current */
.tlcard:hover{transform:translateY(-2px)}
```

```css
/* web/gf/views.css:232 — current */
.fac-room:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(0,0,0,.4);z-index:5}
```

For contrast, plain color/background hover changes elsewhere in the app —
e.g. `:root[data-theme^="mass-weed"] table tbody tr:hover{background:rgba(var(--accent-rgb),.08)}`
(`web/gf/mass-weed.css:400`) — are harmless on touch (a "stuck" background
tint reads as a normal tap-highlight, not a broken animation) and are
correctly **not** in this list; AUDIT.md's category 6 concern is
specifically transform-based motion feedback, and this plan only touches
rules that set `transform` (plus, per rule, any `box-shadow`/`filter`/
`z-index` that is part of the same hover-only motion affordance — judged
individually for each of the 9 rules in Steps below).

No oddities or embedded instructions were found in any file read for this
plan — all comments encountered (e.g. the mass-weed.css:807-811 cascade
explanation, the mass-weed.css:318-320 "ported from the mockup" section
header) are ordinary engineering comments and were treated as such.

## Target

Every one of the 9 rules above gets wrapped, in place, in a
`@media (hover: hover) and (pointer: fine){ }` block, exactly as AUDIT.md's
category 6 prescribes. No property value changes — the rule body inside the
media query is byte-for-byte identical to the current rule body quoted
above. Worked example (`app.css:398`):

```css
/* web/gf/app.css:398 — target */
@media (hover: hover) and (pointer: fine){
  .card:hover{box-shadow:var(--sh-2);transform:translateY(-1px)}
}
```

On a mouse-driven desktop (`hover: hover` and `pointer: fine` both true),
every one of these 9 rules behaves exactly as it does today — nothing
visibly changes. On a touchscreen or tablet (`hover: none`, `pointer:
coarse`), none of these 9 rules can match at all, so tapping the element
produces no lift/glow/scale/brightness change and nothing gets stuck.

## Repo conventions to follow

- The codebase already nests selector rules inside a conditional media
  at-rule using 2-space indentation for the nested selector, e.g.:
  ```css
  /* web/gf/mass-weed.css:795-799 — existing convention to mirror */
  @media (prefers-reduced-motion: reduce){
    :root[data-theme^="mass-weed"] .track>span::after,
    :root[data-theme^="mass-weed"] .ana-hb-f::after,
    :root[data-theme^="mass-weed"] .wl-fill::after{animation:none}
  }
  ```
  and the single-selector case at `web/gf/mass-weed.css:305-307`:
  ```css
  @media (prefers-reduced-motion: reduce){
    :root[data-theme^="mass-weed"] .card:hover{transform:none}
  }
  ```
  Use this exact same nesting shape (2-space indent, opening brace on the
  `@media` line, closing brace alone on its own line) for the new
  `@media (hover: hover) and (pointer: fine){ }` blocks — do not invent a
  different formatting convention.
- `web/gf/mobile.css:7` is the one exemplar in this repo of a touch-aware
  media feature already in use (`@media (hover: none) and (pointer:
  coarse)`), confirming this class of media query is a normal, expected
  pattern here — this plan adds its mirror-image condition
  (`hover: hover` and `pointer: fine`) rather than introducing an unfamiliar
  technique.
- Preserve each rule's exact existing declaration spacing when wrapping it —
  do not reformat. `web/gf/mass-weed.css:1096` and `:1455`
  (`.mw-tcard:hover`, `.mw-skins__dot:hover`) use a spaced style (space
  after `{`, space before `}`, trailing semicolons) inherited from the
  ported mockup component library (see the file's own section header
  comment at line 318-320); every other rule in this list uses the
  compact, no-inner-space style. Only add the new media-query wrapper
  around each rule — never touch the spacing inside it.
- **Cascade-order constraint on `mass-weed.css:255-257` specifically**: this
  is the one rule in this list that already has a same-specificity
  `@media (prefers-reduced-motion: reduce)` override sitting later in the
  file, at `mass-weed.css:305-307` (`:root[data-theme^="mass-weed"]
  .card:hover{transform:none}`). Wrapping `mass-weed.css:255-257` in a media
  query does not change its specificity, but it must stay **in place** at
  its current position in the file (still textually before line 305) — do
  not move it to the end of the file or anywhere after the
  `prefers-reduced-motion` block. Equal-specificity CSS rules resolve by
  source order, and the `prefers-reduced-motion` override must keep winning
  (for a user who has both a mouse and reduced-motion enabled) exactly as it
  does today. This plan only ever wraps rules in place; it never relocates
  them, for this reason.
- No `--ease-*`/`--duration-*` token system exists anywhere in this repo yet
  (confirmed — see plan `006-easing-duration-tokens.md`, which is what
  introduces `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` and
  `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)`). This plan does not add
  or change any `transition`/`animation` timing value itself — it only adds
  a wrapping media query around existing `:hover` declarations, so there is
  no cubic-bezier/duration literal in this plan's edits to swap for a
  token. The *base* selectors that pair with these 9 `:hover` rules do
  carry their own `transition:` declarations with hand-typed/bare easing
  (e.g. `web/gf/app.css:395` — `transition:box-shadow .18s,transform
  .12s,border-left-color .18s`; `web/gf/views.css:36,61,231`;
  `web/gf/mass-weed.css:1090,1454` — `transition:transform .12s ease,
  filter .12s ease` and `transition:transform .12s ease, box-shadow .12s
  ease`). Once plan 006 lands, those neighboring `transition:` lines become
  candidates for `var(--ease-out)`, but making that swap is not part of
  this plan and is not a required step here.

## Steps

### `web/gf/app.css` (1 edit)

1. Line 398 (`.card:hover`) — change:
   ```css
   /* current */
   .card:hover{box-shadow:var(--sh-2);transform:translateY(-1px)}
   ```
   to:
   ```css
   /* target */
   @media (hover: hover) and (pointer: fine){
     .card:hover{box-shadow:var(--sh-2);transform:translateY(-1px)}
   }
   ```
   `box-shadow` stays bundled with `transform` here — the shadow swap
   (`var(--sh-1)` → `var(--sh-2)`, set on the non-hover base rule at
   `app.css:393-396`) simulates the card lifting off the surface together
   with the `translateY`; they are one atomic "lift" affordance, not an
   independent color change, so both move inside the media query together.

### `web/gf/mass-weed.css` (5 edits)

2. Lines 255-257 (`:root[data-theme^="mass-weed"] .card:hover`) — change:
   ```css
   /* current */
   :root[data-theme^="mass-weed"] .card:hover{
     box-shadow:var(--sh-2), 0 0 18px rgba(var(--accent-rgb),.28);transform:translateY(-1px)
   }
   ```
   to:
   ```css
   /* target */
   @media (hover: hover) and (pointer: fine){
     :root[data-theme^="mass-weed"] .card:hover{
       box-shadow:var(--sh-2), 0 0 18px rgba(var(--accent-rgb),.28);transform:translateY(-1px)
     }
   }
   ```
   Same reasoning as step 1: the glow (`0 0 18px rgba(var(--accent-rgb),.28)`)
   and the lift (`translateY(-1px)`) are one hover-only affordance. Leave
   the existing `@media (prefers-reduced-motion: reduce){
   :root[data-theme^="mass-weed"] .card:hover{transform:none} }` block at
   lines 305-307 completely untouched and in its current position (after
   this edit's new closing `}`) — see the cascade-order note in "Repo
   conventions to follow" above.

3. Lines 591-593 (`:root[data-theme^="mass-weed"] .kcard:hover,
   :root[data-theme^="mass-weed"] .team-card:hover`) — change:
   ```css
   /* current */
   :root[data-theme^="mass-weed"] .kcard:hover,
   :root[data-theme^="mass-weed"] .team-card:hover{
     box-shadow:var(--sh-2), 0 0 16px rgba(var(--accent-rgb),.22);transform:translateY(-1px)}
   ```
   to:
   ```css
   /* target */
   @media (hover: hover) and (pointer: fine){
     :root[data-theme^="mass-weed"] .kcard:hover,
     :root[data-theme^="mass-weed"] .team-card:hover{
       box-shadow:var(--sh-2), 0 0 16px rgba(var(--accent-rgb),.22);transform:translateY(-1px)}
   }
   ```
   Keep the two-selector list intact inside the single wrapped rule — do
   not split it into two separate rules/media blocks.

4. Lines 815-817 (`:root[data-theme^="mass-weed"] .kcard:hover`, the later,
   dept-accent-aware override) — change:
   ```css
   /* current */
   :root[data-theme^="mass-weed"] .kcard:hover{
     box-shadow:var(--sh-2), 0 0 16px rgba(var(--accent-rgb),.22),
       inset 3px 0 0 var(--dept-acc, var(--primary));transform:translateY(-1px)}
   ```
   to:
   ```css
   /* target */
   @media (hover: hover) and (pointer: fine){
     :root[data-theme^="mass-weed"] .kcard:hover{
       box-shadow:var(--sh-2), 0 0 16px rgba(var(--accent-rgb),.22),
         inset 3px 0 0 var(--dept-acc, var(--primary));transform:translateY(-1px)}
   }
   ```
   `box-shadow` is a single CSS property — it cannot be half-gated — so the
   entire value (including the `inset 3px 0 0 var(--dept-acc, ...)` layer
   that also appears on the non-hover base rule at lines 812-814) moves
   inside the media query together with `transform`. This is correct: on a
   touch device with this edit applied, `.kcard:hover` simply never
   matches, so the element keeps whatever `box-shadow` its *non-hover* base
   rule (line 812-814, untouched by this plan) already sets — the dept
   accent edge stripe is still visible, it just doesn't gain the glow/lift
   on tap.

5. Line 1096 (`.mw-tcard:hover`) — change:
   ```css
   /* current */
   .mw-tcard:hover{ transform:translateX(2px); filter:brightness(1.12); }
   ```
   to:
   ```css
   /* target */
   @media (hover: hover) and (pointer: fine){
     .mw-tcard:hover{ transform:translateX(2px); filter:brightness(1.12); }
   }
   ```
   `filter:brightness(1.12)` is a hover-only highlight paired with the
   `translateX` nudge, not a state indicator used anywhere else on this
   element (compare `.mw-tcard--done`, which uses `color`/
   `text-decoration`, not `filter`) — it moves inside the media query too.

6. Line 1455 (`.mw-skins__dot:hover`) — change:
   ```css
   /* current */
   .mw-skins__dot:hover{ transform:scale(1.18); }
   ```
   to:
   ```css
   /* target */
   @media (hover: hover) and (pointer: fine){
     .mw-skins__dot:hover{ transform:scale(1.18); }
   }
   ```
   Leave `.mw-skins__dot.is-active{...transform:scale(1.12)...}` (line
   1456) untouched — it is a persistent selection state, not a hover
   effect, and is out of scope.

### `web/gf/views.css` (3 edits)

7. Line 37 (`.kcard:hover`, the base non-theme-scoped rule — distinct from
   the two mass-weed.css `.kcard:hover` rules edited in steps 3-4 above,
   which only apply under `data-theme^="mass-weed"`) — change:
   ```css
   /* current */
   .kcard:hover{transform:translateY(-2px);box-shadow:var(--sh-2)}
   ```
   to:
   ```css
   /* target */
   @media (hover: hover) and (pointer: fine){
     .kcard:hover{transform:translateY(-2px);box-shadow:var(--sh-2)}
   }
   ```

8. Line 62 (`.tlcard:hover`) — change:
   ```css
   /* current */
   .tlcard:hover{transform:translateY(-2px)}
   ```
   to:
   ```css
   /* target */
   @media (hover: hover) and (pointer: fine){
     .tlcard:hover{transform:translateY(-2px)}
   }
   ```

9. Line 232 (`.fac-room:hover`) — change:
   ```css
   /* current */
   .fac-room:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(0,0,0,.4);z-index:5}
   ```
   to:
   ```css
   /* target */
   @media (hover: hover) and (pointer: fine){
     .fac-room:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(0,0,0,.4);z-index:5}
   }
   ```
   `box-shadow` and `z-index:5` both travel with `transform` here: the drop
   shadow is the same "lift toward the viewer" affordance as the
   `translateY`, and the raised stacking order exists so the lifted room
   doesn't get visually clipped under its neighbors while it's elevated —
   it's not an independent "selected" indicator (that's the separate
   `.fac-room.sel{...z-index:6}` rule at line 233, untouched by this plan).
   All three properties are one hover-only affordance and move inside the
   media query together.

## Boundaries

- Do NOT touch `web/gf/mobile.css` — its one touch-aware query
  (`@media (hover: none) and (pointer: coarse)`, line 7) already correctly
  handles touch-target sizing; it is this plan's exemplar, not an edit
  target.
- Do NOT touch `:root[data-theme^="mass-weed"] table tbody tr:hover{background:rgba(var(--accent-rgb),.08)}`
  (`web/gf/mass-weed.css:400`) or any other plain color/background-only
  `:hover` rule anywhere in the app. AUDIT.md's category 6 concern is
  transform-based motion feedback; a "stuck" background tint on tap is a
  normal tap-highlight, not a bug, and gating it would be scope creep.
- Do NOT change any property *value* in any of the 9 rules — colors,
  `rgba()`/`color-mix()` percentages, pixel amounts, `scale()`/
  `translateX`/`translateY` amounts, `z-index` numbers, and every other
  declaration inside each rule body must remain byte-for-byte identical to
  what's quoted in Steps. The only change in this entire plan is adding the
  `@media (hover: hover) and (pointer: fine){ }` wrapper around each rule.
- Do NOT relocate any of the 9 rules to a new position in their file (e.g.
  grouping them all at the end of the file the way some
  `prefers-reduced-motion` blocks are grouped elsewhere in
  `mass-weed.css`). Wrap each one **in place**, at its current line. This
  matters most for `mass-weed.css:255-257` — see the cascade-order note in
  "Repo conventions to follow" and step 2 above; moving it after
  `mass-weed.css:305-307` would silently break the existing reduced-motion
  override for users who have both a mouse and reduced-motion enabled.
- Do NOT touch `.mw-skins__dot.is-active` (`mass-weed.css:1456`) or
  `.fac-room.sel` (`views.css:233`) — both are persistent selection-state
  rules, not hover effects, and are out of scope.
- Do NOT touch any `.js` file. Every one of the 9 rules is plain CSS
  `:hover`; none of them is driven by JS inline-style manipulation.
- Do NOT introduce any `--ease-*`/`--duration-*` custom property or
  reference `var(--ease-out)`/`var(--ease-in-out)` anywhere in this plan's
  edits — those tokens don't exist in this repo yet (plan 006 introduces
  them) and this plan doesn't touch any easing/duration value regardless.
- This plan's `@media (hover: hover) and (pointer: fine)` gate and the
  separate `@media (prefers-reduced-motion: reduce)` gate that a different
  plan (e.g. 007, if and when it exists) may add to some of these same 9
  selectors are **independent and complementary**, not duplicates of each
  other — one answers "can this device meaningfully hover at all", the
  other answers "has the user asked for less motion". Both should end up
  present, side by side, wrapping/targeting the same base declarations.
  Regardless of which plan lands first, never remove or merge the other
  plan's media block when adding this one's — see the worked example for
  `mass-weed.css:255-257` in step 2 above, which already has to coexist
  with an existing `prefers-reduced-motion` override today.
- If the current code found at any file:line above does not match what's
  quoted in Problem/Steps (drift since commit `6bd1f7d`), STOP and report
  the mismatch instead of guessing at how to adapt the edit.

## Verification

- **Mechanical**:
  - This plan touches CSS files only — no `.js` file is edited, so there is
    no `node --check` to run for this plan.
  - Run `grep -c "@media (hover: hover) and (pointer: fine)" web/gf/app.css web/gf/mass-weed.css web/gf/views.css`
    and confirm each file's count matches the number of edits made in it:
    `app.css`: 1, `mass-weed.css`: 5, `views.css`: 3 (9 total).
  - Run `grep -n ":hover{" web/gf/app.css web/gf/mass-weed.css web/gf/views.css`
    (and, separately, `grep -n ":hover{ " web/gf/mass-weed.css` for the two
    spaced-style rules) and manually confirm every occurrence containing a
    `transform` declaration is indented inside one of the new
    `@media (hover: hover) and (pointer: fine){ }` blocks added above — not
    left bare at the top level of the file.
  - Open the app in a browser with DevTools open, visit a page that
    exercises each touched file (the main task board for `.card`/`.kcard`,
    the timeline view for `.tlcard`, the facility board for `.fac-room`,
    and a mass-weed-skinned view for the `.mw-tcard`/`.mw-skins__dot`
    rules) and confirm the Console shows zero new CSS parse errors or
    warnings.
  - Visual diff description: on a mouse-driven desktop, nothing changes at
    all — every card/dot/room still lifts, glows, scales, or brightens on
    mouse-hover exactly as before, at the same values. The only observable
    difference is on a touchscreen/tablet: tapping any of these 9 elements
    no longer triggers any lift/glow/scale/brightness change, and nothing
    stays visually "stuck" after the tap.
  - **Feel check**:
    1. In Chrome/Edge DevTools, open the device toolbar (Ctrl+Shift+M /
       Cmd+Shift+M) and pick a touch device preset (e.g. "iPad"), which
       sets the emulated `hover`/`pointer` media features to `none`/
       `coarse`. Navigate to the main task board and click (DevTools maps
       a click to a tap in this mode) a `.card`. Confirm it does **not**
       lift or gain a shadow — the transform/box-shadow from step 1/2
       should not visibly apply at all.
    2. With device emulation still on, temporarily uncheck this plan's new
       `@media (hover: hover) and (pointer: fine)` rule in the Styles
       panel for that `.card` (or temporarily edit the media condition to
       `(pointer: coarse)` in DevTools) to reproduce the original bug:
       click the card, click elsewhere, and confirm the lifted/shadowed
       state now visibly persists with no user action able to clear it —
       this confirms you're looking at the real "stuck hover" failure mode
       before re-verifying the fix removes it. Re-enable the rule
       afterward.
    3. Turn device emulation off (back to a normal mouse/pointer-fine
       desktop context) and hover the mouse over the same `.card`, a
       `.kcard` on the board, a `.tlcard` on the timeline, and a
       `.fac-room` on the facility board. Confirm all four still lift and
       gain their shadow smoothly on mouse-hover, exactly as before this
       plan — this is the regression check that gating didn't silently
       break the desktop experience.
    4. In DevTools' Elements panel, select a `.card` element, open the
       Styles pane, and use the `:hov` force-element-state toggle to force
       `:hover` on. Confirm the Computed panel shows
       `transform: translateY(-1px)` and the lifted `box-shadow` while
       device emulation is off (`pointer: fine`), and confirm the same
       forced `:hover` state produces **no** transform/box-shadow change
       when device emulation is switched back on (`pointer: coarse`) —
       this directly proves the media query, not just the click behavior,
       is what's gating the effect.
    5. With device emulation off, open the Animations panel (More tools →
       Animations), set playback speed to 10%, then mouse-hover a `.card`
       again and watch the recorded animation. Confirm the `translateY`/
       `box-shadow` transition still plays at its original pace — the
       pairing `transition:box-shadow .18s,transform .12s,border-left-color .18s`
       on the non-hover base rule (`web/gf/app.css:395`) is untouched by
       this plan, so the motion itself should look and time identically to
       before; only its reachability from touch changed.
    6. Repeat a quick spot-check of step 3 on at least one mass-weed-themed
       element (switch the active theme to a `mass-weed*` skin, hover a
       `.kcard` and a `.mw-skins__dot`) to confirm the pattern held across
       theme-scoped selectors, not just the base app selectors.
  - **Done when**: all 9 `grep`-confirmed media-query wraps are in place
    exactly as specified in Steps, every rule body is byte-for-byte
    unchanged from its current form, the Console is clean, and the feel
    check above confirms desktop hover is unchanged while touch/coarse
    emulation can no longer trigger any of the 9 transforms.
