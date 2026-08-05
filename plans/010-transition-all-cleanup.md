# 010 — Replace `transition: all` (and bare, property-less `transition:`) with explicit property lists

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: MEDIUM
- **Category**: 5. Performance
- **Estimated scope**: 3 files (`web/gf/app.css`, `web/gf/mass-weed.css`, `web/gf/views.css`) — 10 `transition` edits (6 in `app.css`, 1 in `mass-weed.css`, 3 in `views.css`). No JS files touched, no markup/structure changes, no new custom properties, no new dependencies.

## Problem

AUDIT.md's category 5 ("Performance") is explicit and non-negotiable about this pattern:

```
/* .claude/skills/improve-animations/AUDIT.md:71-80 */
## 5. Performance

- **Animate `transform` and `opacity` only.** `width`/`height`/`margin`/`padding`/`top`/`left` trigger layout + paint + composite.
- **`transition: all`** animates unintended properties off-GPU — always a finding.
...
Hunt for: `transition: all`, animated layout properties, ...
```

`transition: all` (or a bare `transition: <duration>` with no property at all — CSS's
`transition-property` initial value is `all`, so this is functionally identical) tells
the browser to watch *every* CSS property on the element for changes and animate any
that differ between states. Today, for 9 of these 10 selectors, the only properties
that actually change between states are colors/shadows/transform, so the practical
damage is currently latent rather than visibly janky. But the footgun is real and
already live in one case (see selector 6 below, `.td-wrap .pl-stat button`, where
`.on` also flips `font-weight`, so `transition: all` is — right now, today — animating
a property nobody intended to animate) and it silently re-arms on every future edit:
the moment anyone adds a `:hover`/`.on`/`:checked` rule that also happens to touch
`width`, `padding`, `top`, or any other layout property, `transition: all` will start
animating layout on that element with zero visual indication in the diff that a
performance regression just shipped. Removing `all` in favor of an explicit property
list closes that door permanently, for free, with no behavior change on 9 of the 10
selectors and only a one-property behavior change (removing font-weight from the
animated set) on the 10th.

Confirmed, read directly from the live tree at commit `6bd1f7d`. Ten locations,
grouped by file. Each block below shows the full current rule **plus every related
`:hover`/`.active`/`.on`/`.done`/`:disabled`/`:checked` rule for the same element**,
because those state rules are what determine which properties legitimately need to be
in the replacement list.

### `web/gf/app.css` (6 locations)

```css
/* web/gf/app.css:356-360 — current (.day-pill and its state rules) */
.day-pill{display:flex;align-items:center;gap:6px;padding:7px 13px;border-radius:999px;
  border:1px solid var(--glass-border);background:rgba(var(--accent-rgb),.05);color:var(--ink-2);
  font-size:12.5px;font-weight:700;cursor:pointer;transition:all .15s}
.day-pill:hover{background:rgba(var(--accent-rgb),.09);color:var(--ink)}
.day-pill.active{background:rgba(var(--accent-rgb),.18);color:var(--primary);border-color:rgba(var(--accent-rgb),.3)}
```

```css
/* web/gf/app.css:509-512 — current (.add-row and its state rule) */
.add-row{display:flex;gap:10px;align-items:center;background:rgba(var(--accent-rgb),.04);
  border:1px dashed rgba(var(--accent-rgb),.2);border-radius:11px;padding:11px 14px;
  cursor:pointer;color:var(--ink-3);font-weight:600;font-size:13.5px;transition:all .15s}
.add-row:hover{border-color:rgba(var(--accent-rgb),.4);color:var(--primary);background:rgba(var(--accent-rgb),.07)}
```

```css
/* web/gf/app.css:551-555 — current (.chip-opt and its state rules) */
.chip-opt{padding:7px 12px;border-radius:8px;border:1px solid var(--glass-border);
  background:rgba(var(--accent-rgb),.05);font-size:12.5px;font-weight:700;color:var(--ink-2);
  cursor:pointer;user-select:none;transition:all .15s}
.chip-opt:hover{background:rgba(var(--accent-rgb),.09);color:var(--ink)}
.chip-opt.on{background:rgba(var(--accent-rgb),.15);border-color:rgba(var(--accent-rgb),.35);color:var(--primary)}
```

```css
/* web/gf/app.css:946-950 — current (.mw-pager button and its state rules) */
.mw-pager button{min-width:32px;height:32px;padding:0 14px;font:600 13px var(--font);
  color:var(--ink-2);background:var(--surface-2);border:1px solid var(--line);cursor:pointer;
  border-radius:var(--r-sm,4px);transition:all .14s ease}
.mw-pager button:hover{color:var(--primary);border-color:var(--border-strong)}
.mw-pager button:disabled{opacity:.35;cursor:not-allowed}
```

```css
/* web/gf/app.css:1141-1144 — current (.td-wrap .thead .chk and its state rules;
   this block is in the "spaced" formatting dialect — see Repo conventions below) */
.td-wrap .thead .chk { width: 24px; height: 24px; flex: none; margin-top: 4px; border: 1.5px solid var(--mw-cyan-dim); border-radius: 4px; cursor: pointer; position: relative; transition: all .12s ease; }
.td-wrap .thead .chk:hover { border-color: var(--mw-cyan); }
.td-wrap .thead .chk.done { background: var(--mw-acc, var(--mw-cyan)); border-color: var(--mw-acc, var(--mw-cyan)); }
.td-wrap .thead .chk.done::after { content: ""; position: absolute; left: 8px; top: 2px; width: 6px; height: 13px; border: solid var(--mw-void); border-width: 0 2.5px 2.5px 0; transform: rotate(45deg); }
```

Note: `.chk.done::after` is a *separate generated box* (the checkmark tick) that
only exists at all once `.done` is present — it has no `transition` of its own
today and isn't affected by `.chk`'s own `transition` property (a `transition`
declared on `.chk` does not apply to `.chk::after`'s pseudo-element, which needs
its own `transition` to animate). It's out of scope for this plan; see Boundaries.

```css
/* web/gf/app.css:1194-1196 — current (.td-wrap .pl-stat button / .pl-stat2 button
   and their state rules; also "spaced" dialect) */
.td-wrap .pl-stat button, .td-wrap .pl-stat2 button { font-family: var(--mw-font-cond), sans-serif; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; padding: 8px 3px; background: rgba(6,20,40,.5); color: var(--mw-text-faint); border: none; box-shadow: inset 0 0 0 1px rgba(94,200,240,.15); cursor: pointer; clip-path: polygon(4px 0, 100% 0, 100% 100%, 0 100%, 0 4px); transition: all .12s; }
.td-wrap .pl-stat button:hover, .td-wrap .pl-stat2 button:hover { color: var(--mw-text); box-shadow: inset 0 0 0 1px rgba(94,200,240,.4); }
.td-wrap .pl-stat button.on, .td-wrap .pl-stat2 button.on { color: var(--mw-void); font-weight: 700; background: var(--st, var(--mw-cyan)); box-shadow: 0 0 12px -2px var(--st, var(--mw-cyan)); }
```

Note: this is the one selector where `transition: all` is doing something *today*,
not just latently. `.on` also sets `font-weight: 700` (the base rule never sets
`font-weight` explicitly, so it computes from the inherited/default value). Under
`transition: all`, `font-weight` is included in the animated set — whether that is
visually perceptible depends on whether the active font stack (`var(--mw-font-cond)`,
falling back to `sans-serif`) is a variable font capable of interpolating weight; most
system/webfont stacks are not, and simply snap to the nearest available weight file,
so in practice this is likely invisible today — but it is still real, unintended
animated-property tracking that costs a style recalculation on every hover/press for
no visual benefit, exactly what AUDIT.md category 5 is warning about.

### `web/gf/mass-weed.css` (1 location)

```css
/* web/gf/mass-weed.css:1144-1154 — current (.mw-chip and its state rules) */
.mw-chips{ display:flex; flex-wrap:wrap; gap:8px; }
.mw-chip{ --cc: var(--mw-cyan); display:inline-flex; align-items:center; gap:7px; padding:8px 13px;
  background:var(--mw-panel-in); box-shadow:inset 0 0 0 1px rgba(94,200,240,.18);
  clip-path:polygon(6px 0,100% 0,100% calc(100% - 6px),calc(100% - 6px) 100%,0 100%,0 6px);
  font-family:var(--mw-font); font-size:12.5px; font-weight:600; letter-spacing:.03em; color:var(--mw-text-dim);
  border:none; cursor:pointer; user-select:none; transition:all .13s ease; }
.mw-chip:hover{ color:var(--mw-text); box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--cc) 45%, transparent); }
.mw-chip.on{ color:var(--cc); background:color-mix(in srgb, var(--cc) 16%, var(--mw-panel-in));
  box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--cc) 55%, transparent), 0 0 14px -4px var(--cc); }
.mw-chip .d{ width:7px; height:7px; border-radius:50%; background:currentColor; box-shadow:0 0 6px currentColor; opacity:.5; flex:none; }
.mw-chip.on .d{ opacity:1; }
```

Note: `.mw-chip .d` (the little status dot inside the chip) changes `opacity` on
`.on`, but it is a *different element* (a child of `.mw-chip`) with **no `transition`
declared on itself at all** — `.mw-chip`'s `transition: all` only ever applied to
`.mw-chip` itself, never cascaded to animate `.d`, so `.d`'s opacity already snaps
instantly today. This plan does not change that; see Boundaries.

### `web/gf/views.css` (3 locations)

```css
/* web/gf/views.css:219-222 — current (.fac-chip and its state rules) */
.fac-chip{display:inline-flex;align-items:center;gap:7px;font:700 12px/1 'Saira',system-ui,sans-serif;
  color:var(--ink-2);background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:7px 12px;cursor:pointer;transition:all .15s}
.fac-chip.on{border-color:var(--zc);background:rgba(0,0,0,0);outline:1px solid var(--zc)}
.fac-chip:not(.on){opacity:.5}
```

Note: `.on` also adds `outline: 1px solid var(--zc)` where no outline existed
before. `outline-style` (the `solid` keyword) is not an interpolable value — like
`border-style`, a transition can't animate "between" `none` and `solid`, it can only
ever snap — so including `outline` in the replacement list would cost a tracked
property for zero visual effect. It's excluded below for that reason (see Steps).

```css
/* web/gf/views.css:303-308 — current (.sp-switch, its two children with bare
   "transition:.2s", and the :checked state rules that drive them) */
.sp-switch{position:relative;display:inline-block;width:34px;height:20px;cursor:pointer}
.sp-switch input{opacity:0;width:0;height:0}
.sp-switch span{position:absolute;inset:0;background:var(--surface-3);border:1px solid var(--line);border-radius:999px;transition:.2s}
.sp-switch span:before{content:"";position:absolute;width:16px;height:16px;left:2px;top:2px;background:var(--ink-3);border-radius:50%;transition:.2s}
.sp-switch input:checked+span{background:var(--primary);border-color:var(--primary)}
.sp-switch input:checked+span:before{transform:translateX(14px);background:var(--text-on-primary)}
```

Note: this is the **bare-`transition:.2s`, implicit-`all`** case from the finding —
`transition-property`'s CSS initial value is `all`, so `transition:.2s` with no
property named is exactly as unbounded as `transition:all .2s` and gets the same
fix. This is the toggle-switch component (`.sp-switch`): the track (`span`) swaps
`background`/`border-color` on `:checked`, and the knob (`span:before`) both moves
(`transform:translateX(14px)`) and recolors (`background`) on `:checked`.

No steering or instructional content was found embedded in any of the CSS comments
read for this plan (e.g. the mass-weed.css:1140-1143 "pass 4" header and the
app.css:1123-1129 `#td-modal` header are both plain descriptive documentation) — noted
here only to confirm the check was made, per this plan's own ground rules.

## Target

Every rule below keeps its **exact original duration and easing** — `.15s`, `.14s
ease`, `.12s ease`, `.12s`, `.13s ease`, `.2s`, all unchanged — and only replaces
`all` (or the omitted, implicitly-`all` property) with an explicit, comma-separated
property list. No color, shadow, radius, spacing, or other declaration value changes
anywhere in this plan.

```css
/* web/gf/app.css:358 — target */
.day-pill{display:flex;align-items:center;gap:6px;padding:7px 13px;border-radius:999px;
  border:1px solid var(--glass-border);background:rgba(var(--accent-rgb),.05);color:var(--ink-2);
  font-size:12.5px;font-weight:700;cursor:pointer;transition:background .15s,color .15s,border-color .15s}
```

```css
/* web/gf/app.css:511 — target */
.add-row{display:flex;gap:10px;align-items:center;background:rgba(var(--accent-rgb),.04);
  border:1px dashed rgba(var(--accent-rgb),.2);border-radius:11px;padding:11px 14px;
  cursor:pointer;color:var(--ink-3);font-weight:600;font-size:13.5px;transition:border-color .15s,color .15s,background .15s}
```

```css
/* web/gf/app.css:553 — target */
.chip-opt{padding:7px 12px;border-radius:8px;border:1px solid var(--glass-border);
  background:rgba(var(--accent-rgb),.05);font-size:12.5px;font-weight:700;color:var(--ink-2);
  cursor:pointer;user-select:none;transition:background .15s,color .15s,border-color .15s}
```

```css
/* web/gf/app.css:948 — target */
.mw-pager button{min-width:32px;height:32px;padding:0 14px;font:600 13px var(--font);
  color:var(--ink-2);background:var(--surface-2);border:1px solid var(--line);cursor:pointer;
  border-radius:var(--r-sm,4px);transition:color .14s ease,border-color .14s ease,opacity .14s ease}
```

```css
/* web/gf/app.css:1141 — target */
.td-wrap .thead .chk { width: 24px; height: 24px; flex: none; margin-top: 4px; border: 1.5px solid var(--mw-cyan-dim); border-radius: 4px; cursor: pointer; position: relative; transition: border-color .12s ease, background .12s ease; }
```

```css
/* web/gf/app.css:1194 — target */
.td-wrap .pl-stat button, .td-wrap .pl-stat2 button { font-family: var(--mw-font-cond), sans-serif; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; padding: 8px 3px; background: rgba(6,20,40,.5); color: var(--mw-text-faint); border: none; box-shadow: inset 0 0 0 1px rgba(94,200,240,.15); cursor: pointer; clip-path: polygon(4px 0, 100% 0, 100% 100%, 0 100%, 0 4px); transition: color .12s, background .12s, box-shadow .12s; }
```

```css
/* web/gf/mass-weed.css:1149 — target */
.mw-chip{ --cc: var(--mw-cyan); display:inline-flex; align-items:center; gap:7px; padding:8px 13px;
  background:var(--mw-panel-in); box-shadow:inset 0 0 0 1px rgba(94,200,240,.18);
  clip-path:polygon(6px 0,100% 0,100% calc(100% - 6px),calc(100% - 6px) 100%,0 100%,0 6px);
  font-family:var(--mw-font); font-size:12.5px; font-weight:600; letter-spacing:.03em; color:var(--mw-text-dim);
  border:none; cursor:pointer; user-select:none; transition:color .13s ease, background .13s ease, box-shadow .13s ease; }
```

```css
/* web/gf/views.css:220 — target */
.fac-chip{display:inline-flex;align-items:center;gap:7px;font:700 12px/1 'Saira',system-ui,sans-serif;
  color:var(--ink-2);background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:7px 12px;cursor:pointer;transition:border-color .15s,background .15s,opacity .15s}
```

```css
/* web/gf/views.css:305-306 — target */
.sp-switch span{position:absolute;inset:0;background:var(--surface-3);border:1px solid var(--line);border-radius:999px;transition:background .2s,border-color .2s}
.sp-switch span:before{content:"";position:absolute;width:16px;height:16px;left:2px;top:2px;background:var(--ink-3);border-radius:50%;transition:transform .2s,background .2s}
```

## Repo conventions to follow

- **This codebase already has the correct pattern in plenty of places** — an
  explicit, comma-separated `transition` property list is the norm, not something
  new being introduced. The clearest exemplar is right there in the same file as
  four of these edits:
  ```css
  /* web/gf/app.css:395 — exemplar, already correct, do not touch */
  transition:box-shadow .18s,transform .12s,border-left-color .18s;
  ```
  and several more in the same section of `app.css` (lines 258, 282, 290, 319, 336,
  372, 389 — e.g. `transition:background .15s,color .15s`). Match this exact
  style for every "compact-dialect" edit in this plan (see next bullet): no space
  after the property name's comma, no space after the `:` before the duration,
  properties comma-joined with **no** space after the comma.
- **Use `background`, not `background-color`, for background transitions.** Every
  base rule in this plan declares its background with the `background:` shorthand
  (e.g. `background:rgba(var(--accent-rgb),.05)`), never `background-color:`. The
  existing exemplars above (`app.css:258,282,290,319,336`) all transition
  `background`, not `background-color`. Follow that: this plan's property lists use
  `background`, matching both the property this codebase already declares and the
  property it already transitions elsewhere.
- **Two formatting dialects coexist in this codebase — preserve each rule's own
  dialect, do not cross-pollinate.** Most of `app.css`/`mass-weed.css`/`views.css`
  uses a compact style (no spaces around `:`, no space after `,`, no space inside
  `{ }`, no trailing `;` before `}`) — that's the dialect for 7 of these 10 edits
  (`app.css:358,511,553,948`; `views.css:220,305,306`). A second, "spaced" dialect
  (space after `:` and `,`, space inside `{ }`, trailing `;` before `}`) is used for
  code ported verbatim from the standalone Mass Weed mockup HTML files. Two comment
  headers in this codebase explain why and confirm it's deliberate, not drift:
  ```css
  /* web/gf/app.css:1123-1129 */
  /* ── Task Detail SCREEN (#td-modal / .td-wrap) — the Mass Weed design's
     full-page task view (design/mass-weed-mockup/task-detail{,-qc}.html). ...
     Rendered by web/gf/task-detail-view.js (GF.WWF.openTaskDetail). ── */
  ```
  ```css
  /* web/gf/mass-weed.css:1140-1143 */
  /* ═══ Component fill, pass 4 — the 2026-07-30 design revision's atoms:
     chip groups, reveal wells, subtask tree, dependency + acknowledgment
     pills (verbatim from design/mass-weed-mockup/mass-weed.css; consumed by
     task-detail / task-create / depthome surfaces) ═══ */
  ```
  `app.css:1141` and `app.css:1194` (both inside the `#td-modal`/`.td-wrap` block)
  and `mass-weed.css:1149` (`.mw-chip`, inside the "pass 4" block) are all in this
  spaced dialect — their target `transition:` values above use `, ` (comma-space)
  between properties, matching the spacing already used for multi-value
  `box-shadow`/`background` lists inside those same blocks (e.g.
  `mass-weed.css:1151-1152`'s `box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--cc)
  55%, transparent), 0 0 14px -4px var(--cc)`). Do not "clean up" a spaced-dialect
  rule into the compact dialect, or vice versa — only the `transition` value itself
  changes in every edit in this plan.
- **No `--ease-*`/`--duration-*` token system exists anywhere in this repo yet**
  (confirmed — this is the same fact plan `006-easing-duration-tokens.md` starts
  from, which is what introduces `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` and
  `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)`). This plan is a narrowly-scoped
  mechanical safety fix — it never changes a duration or easing value, only the
  `transition-property` list — so there is no token to reach for here regardless.
  Once plan 006 lands, the literal durations/easings preserved in this plan's target
  rules (`.15s`, `.14s ease`, `.12s ease`, `.12s`, `.13s ease`, `.2s`) could in
  principle be swapped for `var(--ease-out)`/`var(--ease-in-out)` where the curve
  matches, but making that swap is **not** part of this plan and is not a required
  step here.
- Property order within each comma-separated list is not functionally significant
  (CSS doesn't care what order `transition-property` entries appear in). This plan
  picked an order per selector — documented per-step below — that follows the order
  each property first appears across that selector's own `:hover`/`.on`/`:checked`
  state rules, purely so the list reads traceably against the Problem-section state
  rules above. Keep the order given; don't invent a different one.

## Steps

### `web/gf/app.css` (6 edits)

1. **Line 358** (`.day-pill`) — related state rules are `.day-pill:hover` (changes
   `background`, `color`) and `.day-pill.active` (changes `background`, `color`,
   `border-color`). Union of properties that ever change: `background`, `color`,
   `border-color`. Change:
   ```css
   /* current */
   transition:all .15s}
   ```
   to:
   ```css
   /* target */
   transition:background .15s,color .15s,border-color .15s}
   ```
   (full rule shown in Target above). No other declaration in the rule changes.

2. **Line 511** (`.add-row`) — related state rule is `.add-row:hover`, which
   changes `border-color`, `color`, `background` (in that order in the rule).
   Change:
   ```css
   /* current */
   font-weight:600;font-size:13.5px;transition:all .15s}
   ```
   to:
   ```css
   /* target */
   font-weight:600;font-size:13.5px;transition:border-color .15s,color .15s,background .15s}
   ```

3. **Line 553** (`.chip-opt`) — related state rules are `.chip-opt:hover`
   (`background`, `color`) and `.chip-opt.on` (`background`, `border-color`,
   `color`). Union: `background`, `color`, `border-color`. Change:
   ```css
   /* current */
   cursor:pointer;user-select:none;transition:all .15s}
   ```
   to:
   ```css
   /* target */
   cursor:pointer;user-select:none;transition:background .15s,color .15s,border-color .15s}
   ```

4. **Line 948** (`.mw-pager button`) — related state rules are
   `.mw-pager button:hover` (`color`, `border-color`) and
   `.mw-pager button:disabled` (`opacity`). `opacity` is a genuinely
   state-changing property here (`.35` on `:disabled` vs. the implicit `1`
   otherwise) and opacity is one of the two properties AUDIT.md category 5
   explicitly calls out as safe/cheap to animate (`transform`/`opacity`), so it is
   included. `cursor` also differs on `:disabled` but `cursor` is not a visually
   animatable property (it has no in-between state — the pointer glyph just swaps),
   so it's excluded. Change:
   ```css
   /* current */
   border-radius:var(--r-sm,4px);transition:all .14s ease}
   ```
   to:
   ```css
   /* target */
   border-radius:var(--r-sm,4px);transition:color .14s ease,border-color .14s ease,opacity .14s ease}
   ```

5. **Line 1141** (`.td-wrap .thead .chk`, spaced dialect) — related state rules
   are `.chk:hover` (`border-color`) and `.chk.done` (`background`,
   `border-color`). Union: `border-color`, `background`. (`.chk.done::after`'s
   properties belong to a different box entirely — see the Problem-section note —
   and are out of scope.) Change:
   ```css
   /* current */
   .td-wrap .thead .chk { width: 24px; height: 24px; flex: none; margin-top: 4px; border: 1.5px solid var(--mw-cyan-dim); border-radius: 4px; cursor: pointer; position: relative; transition: all .12s ease; }
   ```
   to:
   ```css
   /* target */
   .td-wrap .thead .chk { width: 24px; height: 24px; flex: none; margin-top: 4px; border: 1.5px solid var(--mw-cyan-dim); border-radius: 4px; cursor: pointer; position: relative; transition: border-color .12s ease, background .12s ease; }
   ```

6. **Line 1194** (`.td-wrap .pl-stat button, .td-wrap .pl-stat2 button`, spaced
   dialect) — related state rules are the `:hover` rule (`color`, `box-shadow`)
   and the `.on` rule (`color`, `font-weight`, `background`, `box-shadow`). Union
   of colors/shadow/background: `color`, `background`, `box-shadow`. `font-weight`
   is deliberately **excluded** — see the Problem-section note above: it's the one
   place in this plan where `transition: all` is animating something today
   (subtly, font-stack-dependent), and dropping it from the explicit list is the
   actual fix this selector needs. Change:
   ```css
   /* current */
   .td-wrap .pl-stat button, .td-wrap .pl-stat2 button { font-family: var(--mw-font-cond), sans-serif; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; padding: 8px 3px; background: rgba(6,20,40,.5); color: var(--mw-text-faint); border: none; box-shadow: inset 0 0 0 1px rgba(94,200,240,.15); cursor: pointer; clip-path: polygon(4px 0, 100% 0, 100% 100%, 0 100%, 0 4px); transition: all .12s; }
   ```
   to:
   ```css
   /* target */
   .td-wrap .pl-stat button, .td-wrap .pl-stat2 button { font-family: var(--mw-font-cond), sans-serif; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; padding: 8px 3px; background: rgba(6,20,40,.5); color: var(--mw-text-faint); border: none; box-shadow: inset 0 0 0 1px rgba(94,200,240,.15); cursor: pointer; clip-path: polygon(4px 0, 100% 0, 100% 100%, 0 100%, 0 4px); transition: color .12s, background .12s, box-shadow .12s; }
   ```

### `web/gf/mass-weed.css` (1 edit)

7. **Line 1149** (`.mw-chip`, spaced dialect) — related state rules are
   `.mw-chip:hover` (`color`, `box-shadow`) and `.mw-chip.on` (`color`,
   `background`, `box-shadow`). Union: `color`, `background`, `box-shadow`.
   (`.mw-chip .d`'s `opacity` belongs to a child element with no `transition` of
   its own — out of scope, see the Problem-section note.) Change:
   ```css
   /* current */
   border:none; cursor:pointer; user-select:none; transition:all .13s ease; }
   ```
   to:
   ```css
   /* target */
   border:none; cursor:pointer; user-select:none; transition:color .13s ease, background .13s ease, box-shadow .13s ease; }
   ```

### `web/gf/views.css` (3 edits)

8. **Line 220** (`.fac-chip`) — related state rules are `.fac-chip.on`
   (`border-color`, `background`, plus a non-animatable `outline` — see below) and
   `.fac-chip:not(.on)` (`opacity`). Union of animatable properties:
   `border-color`, `background`, `opacity`. `outline` is deliberately excluded —
   see the Problem-section note: `.on` introduces `outline: 1px solid var(--zc)`
   where no outline existed before, but `outline-style` going from unset to
   `solid` is a discrete, non-interpolable value change (like `border-style`), so
   including `outline` in the transition list would track a property that can
   never actually animate. Change:
   ```css
   /* current */
   padding:7px 12px;cursor:pointer;transition:all .15s}
   ```
   to:
   ```css
   /* target */
   padding:7px 12px;cursor:pointer;transition:border-color .15s,background .15s,opacity .15s}
   ```

9. **Line 305** (`.sp-switch span`) — bare `transition:.2s`, implicitly `all`
   (see the finding's framing in the Problem section). The only related state
   rule is `.sp-switch input:checked+span`, which changes `background` and
   `border-color`. Change:
   ```css
   /* current */
   .sp-switch span{position:absolute;inset:0;background:var(--surface-3);border:1px solid var(--line);border-radius:999px;transition:.2s}
   ```
   to:
   ```css
   /* target */
   .sp-switch span{position:absolute;inset:0;background:var(--surface-3);border:1px solid var(--line);border-radius:999px;transition:background .2s,border-color .2s}
   ```

10. **Line 306** (`.sp-switch span:before`) — bare `transition:.2s`, implicitly
    `all`. The only related state rule is
    `.sp-switch input:checked+span:before`, which changes `transform`
    (`translateX(14px)`) and `background`. Change:
    ```css
    /* current */
    .sp-switch span:before{content:"";position:absolute;width:16px;height:16px;left:2px;top:2px;background:var(--ink-3);border-radius:50%;transition:.2s}
    ```
    to:
    ```css
    /* target */
    .sp-switch span:before{content:"";position:absolute;width:16px;height:16px;left:2px;top:2px;background:var(--ink-3);border-radius:50%;transition:transform .2s,background .2s}
    ```

## Boundaries

- Do NOT touch any `transition:` declaration not listed in the 10 locations above.
  In particular, leave the already-correct explicit-list exemplars alone —
  `app.css:395` (`transition:box-shadow .18s,transform .12s,border-left-color
  .18s`), `app.css:258,282,290,319,336,372,389`, and every other multi- or
  single-property `transition` elsewhere in the app — none of those are `all` and
  none are in scope.
- Do NOT change any duration or easing value. Every target rule above keeps its
  original number exactly: `.15s`, `.14s ease`, `.12s ease`, `.12s`, `.13s ease`,
  `.2s`. This plan only changes the `transition-property` portion.
- Do NOT change any other declaration's value in any of the 10 rules — colors,
  `rgba()`/`color-mix()` values, radii, padding, shadow layers, `clip-path`
  polygons, font stacks, everything else stays byte-for-byte identical to what's
  quoted in Problem/Target. Also do not remove or add `!important`, do not add
  vendor prefixes.
- Do NOT reformat a rule's spacing dialect. Keep the compact-dialect rules compact
  and the spaced-dialect rules spaced, exactly as flagged in each Step. Only the
  `transition` value's content changes; brace/comma/colon spacing around it stays
  whatever that rule already used.
- Do NOT add a `transition` to `.td-wrap .thead .chk.done::after` or to
  `.mw-chip .d` — both are separate child/pseudo-elements with no `transition`
  declared today; giving them one is a different, additive finding (AUDIT.md
  category 8, "missed opportunities"), not this mechanical safety fix.
- Do NOT introduce any `--ease-*`/`--duration-*` custom property or reference
  `var(--ease-out)`/`var(--ease-in-out)` anywhere in this plan's edits — see "Repo
  conventions to follow" above; that's plan 006's territory, and this plan changes
  no easing/duration value regardless.
- Do NOT touch any `.js` file. All 10 locations are plain CSS `:hover`/`.on`/
  `.active`/`.done`/`:disabled`/`:checked`-driven transitions; none of them is
  produced by hand-rolled JS inline-style manipulation.
- Do NOT touch `web/gf/entry.css`, `web/gf/leaf-fx.css`, `web/gf/brand.css`, or
  `web/gf/skins.css` — none of the 10 confirmed locations are in those files.
- If the current code found at any file:line above does not match what's quoted in
  Problem/Target (drift since commit `6bd1f7d`), STOP and report the mismatch
  instead of guessing at how to adapt the edit.

## Verification

- **Mechanical**:
  - This plan touches CSS files only — no `.js` file is edited, so there is no
    `node --check` to run for this plan.
  - Run `grep -n "transition:[[:space:]]*all\b" web/gf/app.css web/gf/mass-weed.css web/gf/views.css`
    and confirm **zero** matches remain anywhere in these three files (before this
    plan, that command matches the 8 `transition: all`/`transition:all` locations
    listed in Problem).
  - Run `grep -n "transition:\.2s\|transition: \.2s" web/gf/views.css` and confirm
    zero matches remain (before this plan, it matches lines 305 and 306).
  - Run `grep -c "^\.day-pill{" web/gf/app.css` (and similarly spot-check a couple
    of the other 9 selectors) to confirm no duplicate rule was accidentally
    introduced instead of editing in place.
  - Open the app in a browser with DevTools Console open, navigate to a view that
    exercises each touched selector — the weekly board (`.day-pill`, `.add-row`,
    `.chip-opt`), a Mass Weed dashboard page with pagination (`.mw-pager button`),
    a task detail screen (`.chk`, `.pl-stat button`, `.mw-chip`), the facility map
    (`.fac-chip`), and any species-lock toggle (`.sp-switch`) — and confirm zero
    new CSS parse errors or warnings appear.
  - Visual diff description: on every one of the 10 elements, hover/press/toggle
    interactions look **identical** to before this plan — same colors, same
    shadows, same knob slide, same timing. The only non-visual difference is that
    `.td-wrap .pl-stat button`/`.pl-stat2 button`'s `font-weight` jump to `700` on
    `.on` now happens instantly instead of being nominally "tracked" for
    animation by `transition: all` (see the feel check below for how to actually
    observe this one).
- **Feel check**:
  1. Open DevTools → More tools → **Animations** panel. Navigate to the weekly
     board and hover a `.day-pill`. Trigger the hover, then immediately open the
     Animations panel's recording — confirm the transition entry's property
     breakdown lists only `background-color`/`color`/`border-color` (Chrome's
     panel reports the longhand `background-color` even though the source says
     `background`) — never `padding`, `border-radius`, `gap`, or anything
     layout-related. Repeat for `.add-row` and `.chip-opt` (click one to toggle
     `.on`) — confirm the same: only color/background/border-color entries, never
     anything else.
  2. Set the Animations panel's playback speed to **10%**. Click a Mass Weed
     pagination button's disabled/enabled boundary (or hover a `.mw-pager
     button`) and watch the slowed-down transition: confirm `color` and
     `border-color` visibly ease over ~1.4s (14s at 10% speed) and, on the
     disabled boundary, `opacity` visibly fades over the same slowed window —
     nothing snaps abruptly and nothing unrelated animates alongside it.
  3. Open a task detail screen, still at 10% playback, and click a `.chk`
     checkbox to toggle `.done`. Confirm the border and fill color ease smoothly
     over the slowed duration, and confirm the checkmark tick (the `::after`
     pseudo-element) still just appears instantly with no animation at all —
     that part of the behavior is unchanged by this plan, since `::after` never
     had its own `transition`.
  4. Still on the task detail screen, at 10% playback, click a `.pl-stat`/
     `.pl-stat2` progress button to toggle `.on`. Confirm `color`, `background`,
     and `box-shadow` all ease smoothly over the slowed duration. Then, in the
     Elements panel, select the button, open the Computed tab, and toggle `.on`
     on/off a few times while watching the `font-weight` value: confirm it flips
     between `400` (or whatever the inherited value is) and `700` **without** an
     entry for `font-weight` appearing in the Animations panel's recorded
     transition — this is the one concrete behavior change in this plan: before
     the fix, `font-weight` was part of the tracked/animated set (even if
     visually subtle); after the fix, it's provably not tracked at all.
  5. Open a Mass Weed themed view with `.mw-chip` elements (e.g. a chip-group
     filter). At 10% playback, click a chip to toggle `.on`: confirm `color`,
     `background`, and `box-shadow` (including the outer glow) all ease
     smoothly, and confirm the small status dot inside the chip (`.mw-chip .d`)
     still just snaps its opacity instantly with no easing — unchanged from
     before this plan, since `.d` never had its own `transition`.
  6. Open the facility floor-plan map and click a `.fac-chip` to toggle `.on`.
     Confirm `border-color`/`background` ease smoothly and the dimmed
     (`opacity: .5`) look of the non-selected chips fades in/out smoothly too.
     Confirm the `outline` that appears on the selected chip pops in **instantly**
     with no easing, both before and after this plan (it never could animate,
     `outline-style` isn't interpolable) — this confirms excluding `outline` from
     the property list changed nothing observable, as expected.
  7. Find a species-lock `.sp-switch` toggle and, at 10% playback, click it.
     Confirm the track recolors (`background`/`border-color`) and the knob both
     slides (`transform: translateX(14px)`) and recolors (`background`) smoothly
     over the slowed duration, exactly as before this plan — this is the
     regression check that turning the bare, implicit-`all` `transition:.2s`
     into an explicit two-property list didn't drop the knob's slide or either
     rule's recolor.
  8. As a broader regression pass, turn on DevTools' Rendering tab → **Paint
     flashing**, then rapidly hover/click through all 10 elements in quick
     succession (spam-click a `.chip-opt`, a `.mw-chip`, and the `.sp-switch`).
     Confirm the flashed paint regions stay confined to each element's own box
     with no unexpected flashing outside it — nothing in this plan should ever
     have caused a broader repaint, so this is purely a sanity check that the
     edits didn't introduce one.
- **Done when**: the two `grep` commands above return zero matches for
  `transition:\s*all` and bare `transition:\.2s` in `app.css`, `mass-weed.css`,
  and `views.css`; all 10 target rules in this plan match what's quoted in the
  Target section above, byte-for-byte on every value except the
  `transition-property` list; and every item in the feel check above passes.
