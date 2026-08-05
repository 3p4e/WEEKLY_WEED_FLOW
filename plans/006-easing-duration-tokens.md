# 006 — Introduce `--ease-out`/`--ease-in-out` tokens and consolidate hand-typed motion curves

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: MEDIUM
- **Category**: 7. Cohesion & tokens (compounded by 2. Easing & duration — several of the consolidated call sites are bare `ease` on entering/exiting elements, which the audit always flags, and three `entry.css` durations exceed the 200–500ms modal/drawer budget)
- **Estimated scope**: 4 files (`web/gf/app.css`, `web/gf/entry.css`, `web/gf/leaf-fx.css`, `web/gf/views.css`) — 1 new `:root` token block (2 custom properties) plus 18 individual `transition`/`animation` edits (5 in `app.css`, 7 in `entry.css`, 5 in `leaf-fx.css`, 1 in `views.css`). No JS files touched, no markup changes, no new dependencies.

## Problem

### No easing/duration token system exists anywhere in this codebase

Confirmed by direct search, run against the live tree:

```
$ grep -rn -- "--ease-\|--duration-" web/gf/*.css
(no output — zero matches across all 8 CSS files: app.css, brand.css, entry.css,
 leaf-fx.css, mass-weed.css, mobile.css, skins.css, views.css)
```

Every `transition`/`animation` in the app hand-types its own curve and duration
inline. That has produced a cluster of near-duplicate hand-typed cubic-beziers
that are all trying to be the same "strong ease-out" shape, plus a long tail of
bare `ease` on elements that are entering or exiting the screen — a case
AUDIT.md's category 2 calls out explicitly: "Built-in CSS easings are too weak
for deliberate motion; plans should introduce strong custom curves (as
tokens, matching repo conventions)."

### Near-duplicate hand-typed cubic-beziers (all "strong ease-out" shape, x1 .2–.28, y1 .7–1, x2 .2–.42, y2 1)

Verified current code, one file:line per bullet:

```css
/* web/gf/entry.css:96 — current */
  transition: transform .7s cubic-bezier(.2, .8, .2, 1), margin .7s cubic-bezier(.2, .8, .2, 1);
```

```css
/* web/gf/entry.css:220 — current */
  transition: transform .55s cubic-bezier(.2, .8, .2, 1);
```

```css
/* web/gf/app.css:940 — current (.mw-gauge__needle, the dashboard gauge needle) */
  transform-origin:bottom center;transition:transform .5s cubic-bezier(.2,.8,.3,1);z-index:2}
```

```css
/* web/gf/leaf-fx.css:83 — current (.leaf-stage[data-mode="bounce"] .leaf-float) */
.leaf-stage[data-mode="bounce"] .leaf-float{animation:lf-bounce .9s cubic-bezier(.28,.84,.42,1) infinite}
```

```css
/* web/gf/leaf-fx.css:114 — current (.leaf-spark) */
  animation:lf-spark .72s cubic-bezier(.22,.7,.3,1) forwards;
```

```css
/* web/gf/leaf-fx.css:13 — current (.leaf-3d) */
  transition:transform .15s cubic-bezier(.22,1,.36,1);
```

```css
/* web/gf/leaf-fx.css:167 — current (.gf-grow-word.blooming) */
.gf-grow-word.blooming{animation:gf-bloom .65s cubic-bezier(.22,1,.36,1) both}
```

The last pair (`leaf-fx.css:13` and `leaf-fx.css:167`) both use
`cubic-bezier(.22,1,.36,1)`, which is nearly identical to the target
`--ease-out` value this plan introduces (`cubic-bezier(0.23, 1, 0.32, 1)`) —
these are effectively the same curve, hand-typed independently in two places.

**Not in scope, noted for awareness only:** `app.css:884` (`.tp-fill`,
`transition:width .4s cubic-bezier(.2,.7,.3,1)`) is *also* a member of this
same near-duplicate cluster, but it is deliberately excluded from this plan's
edits — see "Three progress-bar-fill components" below for why.

### Bare `ease` on entering/exiting elements

AUDIT.md category 2's decision order: "Entering or exiting → `ease-out`
(starts fast, feels responsive)." Every rule below animates an element
appearing or disappearing, and every one uses the bare built-in `ease`
keyword instead:

```css
/* web/gf/app.css:224-227 — current (keyframes themselves; unchanged by this
   plan — only the animation-shorthand call sites below, which reference
   these keyframe names, currently pin the easing to bare `ease`) */
@keyframes cardIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes expandIn{from{opacity:0}to{opacity:1}}
@keyframes modalIn{from{opacity:0;transform:scale(.96) translateY(8px)}to{opacity:1;transform:none}}
@keyframes toastIn{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:none}}
```

```css
/* web/gf/app.css:396 — current (.card, entrance) */
  opacity:1;animation:cardIn .25s ease forwards;position:relative;overflow:hidden}
```

```css
/* web/gf/app.css:449 — current (.card.expanded .card-body, entrance) */
.card.expanded .card-body{display:block;animation:expandIn .15s ease}
```

```css
/* web/gf/app.css:527 — current (.modal, entrance) */
  width:100%;max-width:480px;max-height:90vh;animation:modalIn .2s ease;
```

```css
/* web/gf/app.css:590 — current (.toast, entrance) */
  display:flex;align-items:center;gap:10px;animation:toastIn .3s ease;min-width:220px;color:var(--ink)}
```

```css
/* web/gf/entry.css:123 — current (.gf-shadow, exiting — collapses to
   height:0/opacity:0 when .gf-entry.entered) */
  transition: opacity .5s ease;
```

```css
/* web/gf/entry.css:135 — current (.gf-lockup, exiting — the file's own
   comment at line 127 reads "Brand lockup — fades out on enter", and this
   transition carries a transform too, which the audit specifically flags:
   "should be ease-out") */
  transition: opacity .4s ease, max-height .5s ease, margin .5s ease, transform .5s ease;
```

```css
/* web/gf/entry.css:201 — current (.gf-lw, entering via .gf-lw.show) */
  transition: opacity .5s ease, max-height .55s ease;
```

```css
/* web/gf/entry.css:286 — current (.gf-back, entering via .gf-entry.entered .gf-back) */
  transition: opacity .4s ease, max-height .4s ease;
```

```css
/* web/gf/entry.css:387 — current (.mw-secacc__boot > div.in, boot-log lines
   entering one at a time) */
.mw-secacc__boot > div.in { opacity: 1; transform: none; transition: opacity .3s ease, transform .3s ease; }
```

```css
/* web/gf/leaf-fx.css:138 — current (.leaf-mode-tag.show, entrance+exit
   keyframe — the lf-tag keyframe both fades in and back out within one run) */
.leaf-mode-tag.show{animation:lf-tag 1.5s ease forwards}
```

### `entry.css` durations exceed the 200–500ms modal/drawer budget

AUDIT.md category 2's duration table caps "Modals, drawers" at 200–500ms, with
an explicit carve-out only for "Marketing / explanatory" content ("Can be
longer"). `entry.css` is the app's login/boot screen (its own header comment,
`entry.css:1-5`: "splash + sign-in for the 3D-leaf entry flow… tapping it
shrinks + lifts the leaf and slides a glass sign-in card in beneath it") —
this is routine, repeated shift-worker sign-in chrome, not a one-time
marketing moment, so the standard 500ms ceiling applies. Three durations on
this screen exceed it:

- `entry.css:96` — `.gf-stage` transform: **700ms** (already quoted above)
- `entry.css:201` — `.gf-lw` max-height: **550ms** (already quoted above)
- `entry.css:220` — `.gf-card` transform: **550ms** (already quoted above)

### Mismatched curve on the assistant drawer

```css
/* web/gf/views.css:137-141 — current, full rule (assistant chat drawer) */
.assistant-drawer{position:fixed;top:0;right:0;height:100vh;width:400px;max-width:92vw;
  background:var(--glass-bg);backdrop-filter:var(--glass-blur);-webkit-backdrop-filter:var(--glass-blur);
  border-left:1px solid var(--glass-border);box-shadow:-12px 0 40px rgba(0,0,0,.5);z-index:130;
  transform:translateX(100%);transition:transform .28s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column}
.assistant-drawer.open{transform:translateX(0)}
```

`cubic-bezier(.4,0,.2,1)` is Material Design's "standard" curve. Its first
control point (`x1=.4, y1=0`) sits on the time axis, giving it a near-zero
initial slope — the curve starts slow, exactly the functional problem
AUDIT.md calls out for bare `ease`/`ease-in` on entering UI, just expressed as
a hand-typed cubic-bezier instead of a keyword. The drawer slides in
(`.assistant-drawer.open{transform:translateX(0)}`) and this is the only
occurrence of this specific curve in the codebase (confirmed:
`grep -rn "cubic-bezier(.4,0,.2,1)" web/gf/*.css` → this one match only).

### Three progress-bar-fill components independently reinvented the same role (not edited by this plan)

Three separate components animate a fill bar to a new `width` on data change —
the identical semantic role, three different hand-typed timings:

```css
/* web/gf/app.css:884 — current, NOT edited by this plan */
.tp-fill{display:block;height:100%;border-radius:3px;transition:width .4s cubic-bezier(.2,.7,.3,1)}
```

```css
/* web/gf/mass-weed.css:1204 — current, NOT edited by this plan */
.mw-stat__fill{ height:100%; border-radius:3px; position:relative; transition:width .4s ease; }
```

```css
/* web/gf/views.css:447 — current, NOT edited by this plan */
.wl-fill{height:100%;border-radius:9px;transition:width .3s ease}
```

These are noted here for awareness only — **this plan does not touch their
duration, easing, or the `width` property they animate.** A separate plan
(011, "layout-property-to-transform") is expected to rework all three
selectors' underlying technique (animating `width`, a layout property, is
itself the finding that plan addresses — see AUDIT.md category 5). Changing
their easing now would be redundant with that rework and risks conflicting
edits. Once plan 011 lands and reworks these three onto a non-layout
technique, they become good candidates to also consolidate onto
`var(--ease-out)` (or a dedicated fill-specific token) — but that is a future
step, not part of this plan.

### Other near-duplicate curves found but out of scope for this plan

Two more spots independently hand-type curves this plan's token system would
naturally absorb, but neither is part of this plan's itemized scope (the
finding this plan was written from lists exactly the 18 edits below across
`app.css`/`entry.css`/`leaf-fx.css`/`views.css`, and these two fall outside
that list):

- `web/gf/tweaks-vanilla.js:177` — a JS-injected `<style>` block (`#gf-tweaks-panel`, a dev-tools tweaks panel) hand-types `transition:transform .22s cubic-bezier(.22,1,.36,1),opacity .18s;`. Same near-duplicate `--ease-out`-shaped curve as `leaf-fx.css:13`/`:167` above, but it lives inside a JS template string, not a CSS file, and touching JS files is outside this plan's boundaries (see Boundaries below).
- `web/gf/brand.css:54,55,66,77,152,169` — six `animation: … ease-in-out infinite` declarations (ambient leaf float/breathe/shimmer/title-shift effects). These use the plain `ease-in-out` *keyword* for continuous looping decoration, which is a different, already-correct case per AUDIT.md's decision order ("Constant motion (marquee, progress) → `linear`"; these are gentle infinite breathing loops, not one-shot entrances) — not a bare-`ease`-on-entrance finding and not a hand-typed cubic-bezier needing consolidation. Confirmed present, left untouched, not a finding.

Neither of these requires action from this plan; both are recorded here only
so a future pass doesn't need to re-discover them from scratch.

### Oddities check

No content in `AUDIT.md`, `PLAN-TEMPLATE.md`, or any of the 8 source CSS
files read while preparing this plan attempted to steer this plan's behavior
in any way outside normal code/doc content — nothing to flag.

## Target

### 1. New tokens in `web/gf/app.css`'s `:root` block

```css
/* web/gf/app.css — target, end of the existing :root block (currently lines
   108-111) */
  /* ── Type scale ── */
  --fs-xs: 10px; --fs-sm: 12px; --fs-base: 14px; --fs-md: 15px;
  --fs-lg: 17px; --fs-xl: 20px; --fs-2xl: 24px;  --fs-3xl: 32px;

  /* ── Motion ── */
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);        /* strong ease-out for UI entrances/exits */
  --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);    /* strong ease-in-out for on-screen movement */
}
```

Both cubic-bezier values are copied verbatim from AUDIT.md's category-2 token
block (`.claude/skills/improve-animations/AUDIT.md:31-32`). `--ease-in-out` is
not consumed by any edit in this plan (every finding below is an
entrance/exit or a "same curve family" consolidation, both of which map to
`--ease-out` per AUDIT.md's decision order) — it is added now as the second
half of the token pair this plan is responsible for introducing, so future
plans that touch on-screen movement/morphing have it available without
re-opening `app.css`'s token block. Do not delete it as "unused."

### 2. Every other edit: swap the value, don't restructure the rule

For all 18 edits below, the *only* change is inside the existing
`transition`/`animation` declaration — the property list, selector, and
every other declaration in the rule stay byte-for-byte identical. Full
before/after for every one of the 18 is given in Steps below, grouped by
file. As a representative sample of each of the three edit shapes:

```css
/* bare `ease` on an entrance/exit → var(--ease-out), duration unchanged
   web/gf/app.css:590 — target */
  display:flex;align-items:center;gap:10px;animation:toastIn .3s var(--ease-out);min-width:220px;color:var(--ink)}
```

```css
/* near-duplicate hand-typed cubic-bezier → var(--ease-out), duration unchanged
   web/gf/leaf-fx.css:13 — target */
  transition:transform .15s var(--ease-out);
```

```css
/* over-budget duration capped to 500ms AND curve consolidated in the same edit
   web/gf/entry.css:220 — target */
  transition: transform .5s var(--ease-out);
```

```css
/* mismatched Material curve → var(--ease-out), duration unchanged
   web/gf/views.css:140 — target */
  transform:translateX(100%);transition:transform .28s var(--ease-out);display:flex;flex-direction:column}
```

## Repo conventions to follow

- Design tokens live in `web/gf/app.css`'s single `:root` block (lines
  16-111), grouped into sections under a `/* ── Section Name ── */` header
  comment — exemplars already in the file: `/* ── Borders (a touch stronger
  so edges show on the lighter surfaces) ── */` (line 31), `/* ── Primary:
  plasma green ── */` (line 36), `/* ── Typography ── */` (line 94), `/* ──
  Layout ── */` (line 100), `/* ── Type scale ── */` (line 108). The new
  motion tokens must follow this exact convention: a `/* ── Motion ── */`
  header, then the two `--ease-*` declarations, placed as the new last
  section before the block's closing `}`.
- `web/gf/app.css` is the only file in the app with a `:root` token block —
  confirmed by inspecting `brand.css`, `mass-weed.css`, `mobile.css`,
  `skins.css`, `views.css`; `mass-weed.css` only defines *theme-scoped*
  overrides (`:root[data-theme="mass-weed"]{...}`, line 17), never the base
  `:root`. `app.css` is the correct and only sensible place for tokens that
  apply across every theme.
- `web/index.html` links `gf/app.css` first (line 45), well before
  `gf/views.css`, `gf/leaf-fx.css`, `gf/entry.css`, and `gf/mass-weed.css`
  (lines 49-52). Custom properties declared on `:root` are inherited by every
  element in the document regardless of which stylesheet's rule references
  `var(--ease-out)`, but this load order means there is no ambiguity either
  way — every other touched file is parsed after the token declaration
  lands.
- This plan is what introduces `--ease-out`/`--ease-in-out` — confirmed zero
  `--ease-*`/`--duration-*` declarations exist anywhere in the repo before
  it (see Problem above). Because Step 1 below (the token declaration) is
  itself part of this same plan, every other step in this plan can safely
  reference `var(--ease-out)` directly rather than duplicating the literal
  `cubic-bezier(0.23, 1, 0.32, 1)` value at each call site — there is no
  ordering problem within a single plan's execution. Once this plan has
  landed, any other hand-typed near-duplicate curve discovered later in this
  codebase (for example `web/gf/tweaks-vanilla.js:177` or the three
  progress-bar-fill components noted in Problem above, once plan 011 reworks
  them) could similarly be swapped onto `var(--ease-out)` — but making those
  swaps is explicitly not a required step of this plan; they are out of its
  itemized scope.
- Compact, no-space CSS (`transition:width .4s ease`, no space after the
  colon) and spaced CSS (`transition: opacity .5s ease;`) both already
  coexist in this codebase file-by-file (`leaf-fx.css`/`views.css` favor
  compact; `entry.css` favors spaced). Preserve each file's existing
  spacing style around the edited declaration — do not reformat whitespace
  beyond what's needed to swap the value.

## Steps

### `web/gf/app.css` (6 edits: 1 token block + 5 value swaps)

1. In the `:root` block, immediately after the existing `--fs-lg: 17px;
   --fs-xl: 20px; --fs-2xl: 24px;  --fs-3xl: 32px;` line and before the
   block's closing `}` (currently line 111), insert a new section:
   ```css
   /* ── Motion ── */
   --ease-out: cubic-bezier(0.23, 1, 0.32, 1);        /* strong ease-out for UI entrances/exits */
   --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);    /* strong ease-in-out for on-screen movement */
   ```

2. Line 396 (`.card`, `cardIn` entrance) — change:
   ```css
   /* current */
   opacity:1;animation:cardIn .25s ease forwards;position:relative;overflow:hidden}
   ```
   to:
   ```css
   /* target */
   opacity:1;animation:cardIn .25s var(--ease-out) forwards;position:relative;overflow:hidden}
   ```

3. Line 449 (`.card.expanded .card-body`, `expandIn` entrance) — change:
   ```css
   /* current */
   .card.expanded .card-body{display:block;animation:expandIn .15s ease}
   ```
   to:
   ```css
   /* target */
   .card.expanded .card-body{display:block;animation:expandIn .15s var(--ease-out)}
   ```

4. Line 527 (`.modal`, `modalIn` entrance) — change:
   ```css
   /* current */
   width:100%;max-width:480px;max-height:90vh;animation:modalIn .2s ease;
   ```
   to:
   ```css
   /* target */
   width:100%;max-width:480px;max-height:90vh;animation:modalIn .2s var(--ease-out);
   ```

5. Line 590 (`.toast`, `toastIn` entrance) — change:
   ```css
   /* current */
   display:flex;align-items:center;gap:10px;animation:toastIn .3s ease;min-width:220px;color:var(--ink)}
   ```
   to:
   ```css
   /* target */
   display:flex;align-items:center;gap:10px;animation:toastIn .3s var(--ease-out);min-width:220px;color:var(--ink)}
   ```

6. Line 940 (`.mw-gauge__needle`) — change:
   ```css
   /* current */
   transform-origin:bottom center;transition:transform .5s cubic-bezier(.2,.8,.3,1);z-index:2}
   ```
   to:
   ```css
   /* target */
   transform-origin:bottom center;transition:transform .5s var(--ease-out);z-index:2}
   ```
   Do NOT touch line 884 (`.tp-fill`) in this same file — see Boundaries.

### `web/gf/entry.css` (7 edits — do these after `app.css`'s token block exists)

7. Line 96 (`.gf-stage`) — change:
   ```css
   /* current */
   transition: transform .7s cubic-bezier(.2, .8, .2, 1), margin .7s cubic-bezier(.2, .8, .2, 1);
   ```
   to:
   ```css
   /* target */
   transition: transform .5s var(--ease-out), margin .5s var(--ease-out);
   ```
   (curve consolidated AND duration capped 700ms → 500ms, both properties on this one line)

8. Line 123 (`.gf-shadow`) — change:
   ```css
   /* current */
   transition: opacity .5s ease;
   ```
   to:
   ```css
   /* target */
   transition: opacity .5s var(--ease-out);
   ```

9. Line 135 (`.gf-lockup`) — change:
   ```css
   /* current */
   transition: opacity .4s ease, max-height .5s ease, margin .5s ease, transform .5s ease;
   ```
   to:
   ```css
   /* target */
   transition: opacity .4s var(--ease-out), max-height .5s var(--ease-out), margin .5s var(--ease-out), transform .5s var(--ease-out);
   ```
   (all four properties on this line swap; no duration changes here — none of the four exceed 500ms)

10. Line 201 (`.gf-lw`) — change:
    ```css
    /* current */
    transition: opacity .5s ease, max-height .55s ease;
    ```
    to:
    ```css
    /* target */
    transition: opacity .5s var(--ease-out), max-height .5s var(--ease-out);
    ```
    (curve swapped on both properties; only `max-height` needed its duration capped, 550ms → 500ms — `opacity` was already exactly at the 500ms budget ceiling, so its duration is unchanged)

11. Line 220 (`.gf-card`) — change:
    ```css
    /* current */
    transition: transform .55s cubic-bezier(.2, .8, .2, 1);
    ```
    to:
    ```css
    /* target */
    transition: transform .5s var(--ease-out);
    ```
    (curve consolidated AND duration capped 550ms → 500ms)

12. Line 286 (`.gf-back`) — change:
    ```css
    /* current */
    transition: opacity .4s ease, max-height .4s ease;
    ```
    to:
    ```css
    /* target */
    transition: opacity .4s var(--ease-out), max-height .4s var(--ease-out);
    ```

13. Line 387 (`.mw-secacc__boot > div.in`) — change:
    ```css
    /* current */
    .mw-secacc__boot > div.in { opacity: 1; transform: none; transition: opacity .3s ease, transform .3s ease; }
    ```
    to:
    ```css
    /* target */
    .mw-secacc__boot > div.in { opacity: 1; transform: none; transition: opacity .3s var(--ease-out), transform .3s var(--ease-out); }
    ```

### `web/gf/leaf-fx.css` (5 edits)

14. Line 13 (`.leaf-3d`) — change:
    ```css
    /* current */
    transition:transform .15s cubic-bezier(.22,1,.36,1);
    ```
    to:
    ```css
    /* target */
    transition:transform .15s var(--ease-out);
    ```

15. Line 83 (`.leaf-stage[data-mode="bounce"] .leaf-float`) — change:
    ```css
    /* current */
    .leaf-stage[data-mode="bounce"] .leaf-float{animation:lf-bounce .9s cubic-bezier(.28,.84,.42,1) infinite}
    ```
    to:
    ```css
    /* target */
    .leaf-stage[data-mode="bounce"] .leaf-float{animation:lf-bounce .9s var(--ease-out) infinite}
    ```

16. Line 114 (`.leaf-spark`) — change:
    ```css
    /* current */
    animation:lf-spark .72s cubic-bezier(.22,.7,.3,1) forwards;
    ```
    to:
    ```css
    /* target */
    animation:lf-spark .72s var(--ease-out) forwards;
    ```

17. Line 138 (`.leaf-mode-tag.show`) — change:
    ```css
    /* current */
    .leaf-mode-tag.show{animation:lf-tag 1.5s ease forwards}
    ```
    to:
    ```css
    /* target */
    .leaf-mode-tag.show{animation:lf-tag 1.5s var(--ease-out) forwards}
    ```

18. Line 167 (`.gf-grow-word.blooming`) — change:
    ```css
    /* current */
    .gf-grow-word.blooming{animation:gf-bloom .65s cubic-bezier(.22,1,.36,1) both}
    ```
    to:
    ```css
    /* target */
    .gf-grow-word.blooming{animation:gf-bloom .65s var(--ease-out) both}
    ```

### `web/gf/views.css` (1 edit)

19. Line 140 (`.assistant-drawer`) — change:
    ```css
    /* current */
    transform:translateX(100%);transition:transform .28s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column}
    ```
    to:
    ```css
    /* target */
    transform:translateX(100%);transition:transform .28s var(--ease-out);display:flex;flex-direction:column}
    ```
    Do NOT touch line 447 (`.wl-fill`) in this same file — see Boundaries.

## Boundaries

- Do NOT touch `web/gf/app.css:884` (`.tp-fill`), `web/gf/mass-weed.css:1204`
  (`.mw-stat__fill`), or `web/gf/views.css:447` (`.wl-fill`) — all three are
  reserved for plan 011 (`layout-property-to-transform`), which reworks their
  underlying `width`-based technique; changing their easing now would be
  redundant with, and could conflict with, that rework.
- Do NOT touch `web/gf/tweaks-vanilla.js` — its `#gf-tweaks-panel` inline
  `<style>` string (line 177) hand-types the same `--ease-out`-shaped curve,
  but it is a JS file outside this plan's itemized CSS-only scope. This plan
  touches CSS files only; no JS file is edited anywhere in this plan.
- Do NOT touch `web/gf/brand.css`'s six `ease-in-out`-keyword ambient-loop
  animations (lines 54, 55, 66, 77, 152, 169) — those are continuous,
  already-correct loops per AUDIT.md's decision order, not a finding.
- Do NOT introduce a `--ease-drawer` token. AUDIT.md's category-2 example
  block (`.claude/skills/improve-animations/AUDIT.md:33`) shows a third
  token, `--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1)`, but no finding in
  this plan calls for it — the one drawer this plan touches
  (`.assistant-drawer`) is fixed by moving it onto `--ease-out`, not by
  giving it a bespoke curve. Adding an unused token invites drift; a future
  plan can introduce `--ease-drawer` if a genuine drawer-specific need
  arises.
- Do NOT change any `transition`/`animation` *property list*, *selector*, or
  any other declaration in any touched rule — every edit above changes only
  the easing keyword/cubic-bezier (and, for `entry.css:96`, `:201`, `:220`
  only, the duration number immediately next to it) inside an existing
  declaration. Nothing about which properties animate, what they animate to,
  or any other CSS declaration in these rules changes.
- Do NOT touch the four `@keyframes` bodies at `web/gf/app.css:224-227`
  (`cardIn`, `expandIn`, `modalIn`, `toastIn`) themselves — only the
  `animation:` shorthand call sites that reference them (lines 396, 449,
  527, 590) change.
- Do NOT change `entry.css:135`'s four duration values (`.4s`/`.5s`/`.5s`/
  `.5s`) — none of them exceed the 500ms budget, so only the easing on that
  line changes, not the durations.
- Do NOT change `entry.css:201`'s `opacity .5s` duration — it is already
  exactly at the 500ms budget ceiling; only its `max-height .55s` needs
  capping to `.5s`.
- Do NOT touch `web/gf/mobile.css` or `web/gf/skins.css` — grepped for
  `cubic-bezier`/bare `ease`/`ease-in`/`ease-out`/`ease-in-out`, zero matches
  in either file.
- If the current code you find at any file:line above does not match what's
  quoted in Problem/Steps (drift since commit `6bd1f7d`), STOP and report the
  mismatch instead of guessing at how to adapt the edit.

## Verification

- **Mechanical**:
  - This plan touches CSS files only — no `.js` file is edited, so there is
    no `node --check` to run for this plan.
  - Run `grep -c "var(--ease-out)" web/gf/app.css web/gf/entry.css
    web/gf/leaf-fx.css web/gf/views.css` and confirm each file's count
    matches the number of edits made in it above (`app.css`: 5,
    `entry.css`: 7, `leaf-fx.css`: 5, `views.css`: 1).
  - Run `grep -n -- "--ease-out\|--ease-in-out" web/gf/app.css` and confirm
    both new custom-property declarations appear once each, inside the
    `:root` block, above the block's closing `}`.
  - Open the app in a browser with DevTools open, load a page that exercises
    each touched file (the entry/sign-in screen, the main dashboard with
    task cards, an "Add Task" modal, a toast, the leaf toy, and the
    assistant drawer) and confirm the Console shows zero new CSS parse
    errors or warnings.
  - In DevTools' Elements → Styles panel, select the `<html>` (or `<body>`)
    element and confirm the Computed panel lists `--ease-out:
    cubic-bezier(0.23, 1, 0.32, 1)` and `--ease-in-out: cubic-bezier(0.77,
    0, 0.175, 1)`. Then select `.modal`, `.toast`, `.assistant-drawer`, and
    one edited `entry.css` element (e.g. `.gf-card`) in turn and confirm
    their Computed `animation-timing-function`/`transition-timing-function`
    resolves to `cubic-bezier(0.23, 1, 0.32, 1)` — not the browser's default
    `ease` (`cubic-bezier(0.25, 0.1, 0.25, 1)`), which is what you'd see if
    a `var(--ease-out)` reference were mistyped and silently fell back to
    initial.
  - Visual diff description: nothing changes in layout, color, size, or
    position anywhere. The only visible difference is motion quality —
    entrances/exits that used to ease weakly now start with a snappier,
    more decisive first frame at the same (or, for the three capped
    `entry.css` rules, a slightly shorter) duration.
- **Feel check**:
  1. Reload the app to see the entry/sign-in screen fresh, then tap the 3D
     leaf. Watch the whole reveal sequence: the leaf (`.gf-stage`) shrinking
     and lifting, the ambient shadow (`.gf-shadow`) and brand lockup
     (`.gf-lockup`) collapsing away, the sign-in card (`.gf-card`) sliding
     up into place, and the "back" link (`.gf-back`) fading in. Confirm the
     whole sequence reads as snappier and more decisive than a soft linear
     drift — motion should visibly *start* fast and settle, not ease
     gently in from a standing start. In Chrome/Edge DevTools, open the
     **Animations** panel (More tools → Animations), set playback speed to
     10%, and re-trigger the reveal (reload + tap again): scrub through the
     `.gf-card` transform and confirm it covers most of its distance in the
     first third of its 500ms run, not a roughly even pace throughout.
  2. If the app has a secondary sign-in path that shows the
     `.mw-secacc__boot` boot-log lines (`entry.css:387`), trigger it and
     confirm each line still steps in cleanly, now with a slightly crisper
     pop rather than a soft fade — no line should look like it's
     overshooting, jittering, or arriving out of sync with its siblings.
  3. Add a new task (triggers `cardIn`), expand an existing task card
     (triggers `expandIn`), open the "Add Task" modal (triggers `modalIn`),
     and trigger a toast (e.g. save something) (triggers `toastIn`).
     Confirm all four still read as a fast, confident pop-in — this is a
     same-duration curve swap, so nothing should look slower, and nothing
     should look broken (no snapping to a wrong end state, no visible pause
     mid-animation).
  4. Open the assistant drawer (the chat panel that slides in from the
     right, `.assistant-drawer`). This is the most important check in this
     plan: the OLD curve (`cubic-bezier(.4,0,.2,1)`) starts nearly flat and
     ramps up, so the drawer used to feel like it eases gently into view.
     With the fix, it should now feel like it snaps out immediately and
     settles — a visibly quicker, more responsive first frame. In the
     DevTools Animations panel at 10% playback speed, scrub the recorded
     transform and confirm most of the drawer's horizontal travel happens
     early, not spread evenly across the full 280ms.
  5. Switch the leaf toy to "bounce" mode (`data-mode="bounce"`) and click
     it to trigger the spark/ripple effect. Confirm the squash-and-stretch
     bounce and the spark burst both still look smooth and continuous — no
     visible stutter, snap, or discontinuity at the curve boundary. This is
     a same-curve-family consolidation (the old and new curves are close),
     so the visual difference here should be subtle to imperceptible, not a
     behavior change.
  6. Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel
     and repeat steps 1 and 4. Note (do not fix) that none of the rules
     touched by this plan have reduced-motion handling today either way —
     that is a pre-existing gap this plan does not introduce or resolve.
- **Done when**: `web/gf/app.css`'s `:root` block declares both
  `--ease-out` and `--ease-in-out` with the exact values above; all 18 edits
  listed in Steps are applied with no other declaration in any touched rule
  changed; `grep -rn -- "cubic-bezier(.2, .8, .2, 1)\|cubic-bezier(.2,.8,.3,1)\|cubic-bezier(.2,.7,.3,1)\|cubic-bezier(.28,.84,.42,1)\|cubic-bezier(.22,.7,.3,1)\|cubic-bezier(.22,1,.36,1)\|cubic-bezier(.4,0,.2,1)" web/gf/app.css web/gf/entry.css web/gf/leaf-fx.css web/gf/views.css`
  returns exactly one remaining match — `web/gf/app.css:884` (`.tp-fill`,
  `cubic-bezier(.2,.7,.3,1)`), intentionally untouched per Boundaries — and
  no others; `entry.css` no longer contains `.7s`, `.55s` on the three
  specific rules listed in Steps 7/10/11; the Computed-style check and all
  six feel-check steps above pass; and zero new Console errors/warnings
  appear across the entry screen, task cards, modal, toast, assistant
  drawer, and leaf toy.
