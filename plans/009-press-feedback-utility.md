# 009 — Give pressable elements tactile `:active` press feedback

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: MEDIUM
- **Category**: 3. Physicality & origin
- **Estimated scope**: 3 files (`web/gf/app.css`, `web/gf/views.css`, `web/gf/mass-weed.css`), 10 small CSS additions total (6 in `app.css` including one new utility-class block, 1 in `views.css`, 3 in `mass-weed.css`). No JS files touched, no markup changes, no new dependencies.

## Problem

Across all 8 CSS files in `web/gf/` (`app.css`, `brand.css`, `entry.css`,
`leaf-fx.css`, `mass-weed.css`, `mobile.css`, `skins.css`, `views.css`),
only 4 `:active` rules exist in the entire codebase (confirmed:
`grep -rn ":active{" web/gf/*.css` plus the two spaced-style ones in
`entry.css` → exactly 4 matches), against 100+ elements carrying
`cursor:pointer`. Almost nothing in the app gives the user tactile
confirmation that a press registered — AUDIT.md category 3 calls this out
explicitly: "Press feedback: `transform: scale(0.97)` on `:active` with
`transition: transform 160ms ease-out`. Keep it subtle (0.95–0.98)." and
lists "pressable elements with no press feedback" as a hunt-for item.

### The 4 existing `:active` rules (full inventory, all verified against the live files)

```css
/* web/gf/app.css:321 — current — CORRECT, the exemplar to replicate */
.btn:active{transform:scale(.97)}
```
This is the one rule in the whole app that already matches the AUDIT target
exactly (scale within the 0.95–0.98 range, driven by the base `.btn` rule's
own `transition:background .15s,box-shadow .15s,transform .1s` at
`app.css:319`). Nothing about this rule changes in this plan — it is cited
here only as the pattern every other fix below replicates.

```css
/* web/gf/entry.css:266 — current — NOT touched by this plan */
.gf-btn:active { transform: translateY(1px); }
```
```css
/* web/gf/entry.css:325 — current — NOT touched by this plan */
.gf-demo-float:active { transform: translateY(1px); }
```
Both are a push-down style rather than scale, both scoped to the login/entry
screen's own buttons, and both are an acceptable alternate physically-real
press style (a 1px push-down still reads as "the button gave way under your
finger"). They are left exactly as they are — see Boundaries.

```css
/* web/gf/mass-weed.css:1543 — current */
.mw-btn:active { filter: brightness(0.9); }
```
This is the Mass Weed theme's own primary button. It dims on press but has
**zero transform** — no scale, no translate, nothing physical happens. This
one gets fixed (brightness kept, scale added) — see Steps.

### Representative high-traffic pressables with zero `:active` rule anywhere

The following 6 elements were checked (current code verified against the
live files, not just the summary that named them) and confirmed to have no
`:active` rule anywhere in any of the 8 CSS files, and no `transition`
covering `transform` in most cases either:

```css
/* web/gf/app.css:405 — current (.card-head — the task card header, the
   single highest-frequency clickable surface in the app: tapped constantly
   to expand/collapse every task card) */
.card-head{display:flex;align-items:center;gap:12px;padding:13px 15px;cursor:pointer}
```

```css
/* web/gf/app.css:426-428 — current (.pill — status pill, opens the chooser) */
.pill{display:inline-flex;align-items:center;gap:6px;font-weight:700;font-size:12px;
  padding:5px 11px;border-radius:999px;line-height:1;white-space:nowrap;cursor:pointer;
  user-select:none;border:none;backdrop-filter:blur(8px)}
```

```css
/* web/gf/app.css:815-819 — current (.sel-btn — the popup chooser's own
   trigger button; only has :focus/:disabled today) */
.sel-btn{width:100%;display:flex;align-items:center;justify-content:space-between;gap:8px;
  border:1px solid var(--glass-border);border-radius:9px;padding:10px 12px;font-size:14px;
  background:var(--surface-2);color:var(--ink);cursor:pointer;text-align:left;font-family:inherit}
.sel-btn:focus{outline:none;border-color:rgba(var(--accent-rgb),.4);box-shadow:0 0 0 3px var(--primary-soft)}
.sel-btn:disabled{opacity:.55;cursor:not-allowed}
```

```css
/* web/gf/app.css:827-831 — current (.sel-row — chooser option row; only
   :hover/.on today) */
.sel-row{display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;border:none;
  border-radius:8px;background:none;color:var(--ink);font-size:14px;font-family:inherit;
  cursor:pointer;text-align:left;min-height:42px}
.sel-row:hover,.sel-row.hover{background:var(--primary-soft)}
.sel-row.on{background:var(--primary-soft);font-weight:600}
```

```css
/* web/gf/views.css:35-37 — current (.kcard — kanban board card) */
.kcard{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:12px;cursor:pointer;
  box-shadow:var(--sh-1);transition:transform .12s,box-shadow .12s}
.kcard:hover{transform:translateY(-2px);box-shadow:var(--sh-2)}
```

```css
/* web/gf/mass-weed.css:1144-1155 — current (.mw-chip — a chip/toggle
   button; no :active) */
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
.mw-chip--sm{ padding:6px 10px; font-size:11.5px; }
```

### Drift note: `.dept-row` is in `app.css`, not `views.css`

The finding this plan was written from cited `.dept-row` as
`web/gf/views.css:281`. `web/gf/views.css` lines 275-285 are in fact the
sample-prep formula/container section (`.sp-formula-calc`, `.sp-cont`,
`.sp-stat`, …) — there is no `.dept-row` anywhere in `views.css`
(confirmed: `grep -n "dept-row" web/gf/views.css` → no matches). The real,
live `.dept-row` rule is in `web/gf/app.css:281-284`:

```css
/* web/gf/app.css:281-284 — current (the real location — a citation error
   in the finding, not code drift; the selector/body itself matches what
   was described) */
.dept-row{display:flex;align-items:center;gap:10px;padding:6px 12px;border-radius:7px;cursor:pointer;
  font-size:12.5px;font-weight:600;color:var(--ink-2);transition:background .15s}
.dept-row:hover{background:rgba(var(--accent-rgb),.07);color:var(--ink)}
.dept-row.active{background:rgba(var(--accent-rgb),.11);color:var(--ink)}
```

Note the trap here for whoever implements this: `.dept-row.active` (a
**class** called `active`, dot-syntax, marking the currently-selected
department in a sidebar list) already exists two lines below where the new
rule goes. The new rule this plan adds is `.dept-row:active` (a **pseudo-class**,
colon-syntax, the transient "finger is down right now" state) — a
completely different, unrelated selector that happens to share the word
"active". Do not merge them, do not confuse one for the other.

### A real compose conflict: `.kcard`'s hover lift, especially under the Mass Weed theme

`.kcard` already animates `transform` on hover (`views.css:37`, quoted
above: `translateY(-2px)`). If a bare `.kcard:active{transform:scale(.97)}`
is added naively, then on a mouse-driven desktop — where `:hover` and
`:active` are both true at once while a button is held down — the `transform`
property does not blend between the two rules; only one rule's value wins.
`.kcard:hover` and a plain `.kcard:active` have equal specificity
(0,0,2,0 each: one class + one pseudo-class), so it comes down to source
order — whichever rule is later in the file fully replaces the other rule's
`transform` value. The press would either keep showing the stale
`translateY(-2px)` with no scale at all, or the lift would vanish and jump
straight to `scale(.97)` with no lift — a visible snap between two unrelated
transform values, which is the exact failure mode to avoid.

It gets worse under the Mass Weed theme. `web/gf/mass-weed.css` has its own,
higher-specificity `.kcard:hover` overrides:

```css
/* web/gf/mass-weed.css:591-593 — current */
:root[data-theme^="mass-weed"] .kcard:hover,
:root[data-theme^="mass-weed"] .team-card:hover{
  box-shadow:var(--sh-2), 0 0 16px rgba(var(--accent-rgb),.22);transform:translateY(-1px)}
```
```css
/* web/gf/mass-weed.css:812-817 — current (the later, dept-accent-aware
   rule that wins the cascade for .kcard specifically over the one above —
   per the file's own comment at :807-811, this is deliberate) */
:root[data-theme^="mass-weed"] .kcard{
  box-shadow:var(--sh-1), 0 0 0 1px rgba(var(--accent-rgb),.06),
    inset 3px 0 0 var(--dept-acc, var(--primary))}
:root[data-theme^="mass-weed"] .kcard:hover{
  box-shadow:var(--sh-2), 0 0 16px rgba(var(--accent-rgb),.22),
    inset 3px 0 0 var(--dept-acc, var(--primary));transform:translateY(-1px)}
```

Each of these selectors is `:root` (pseudo-class) + `[data-theme^="mass-weed"]`
(attribute) + `.kcard` (class) + `:hover` (pseudo-class) = specificity
(0,0,4,0) — strictly higher than a plain `.kcard:active`'s (0,0,2,0). That
means under the Mass Weed theme, a plain `.kcard:active{transform:scale(.97)}`
in `views.css` would **never win** while the card is hovered — the themed
`:hover` rule's `translateY(-1px)` would keep beating it on specificity
alone, regardless of which file loads last or which rule is written later.
Press feedback would silently be swallowed on what is, based on the amount
of CSS dedicated to it in this codebase, the app's primary visual theme.
This plan fixes both problems: it composes the base-theme `:active` rule so
it carries the same lift the hover state already has (rather than fighting
it), and adds a matching-specificity themed `:active` rule for Mass Weed so
the fix isn't silently defeated there. See Target/Steps.

No mass-weed-theme transform overrides exist for `.card-head`, `.pill`,
`.sel-btn`, `.sel-row`, or `.dept-row` (confirmed: `web/gf/mass-weed.css`
only touches `.pill`'s `letter-spacing`/`text-transform` at line 303 and
`.sel-btn`'s `clip-path`/`border-radius` at lines 310-311 — neither sets
`transform`), so none of those five need an extra themed rule the way
`.kcard` does.

`.card-head` itself has no hover rule of its own anywhere. The only nearby
hover-transform rule is on its *parent*, `.card` (`app.css:398`,
`.card:hover{box-shadow:var(--sh-2);transform:translateY(-1px)}`) — a
different element. A child's `transform` and its ancestor's `transform` are
independent (each element's `transform` only affects that element's own box
and its descendants' rendering, not the ancestor's computed style), so
`.card-head:active{transform:scale(.97)}` composes safely underneath
`.card:hover`'s lift with no fight.

### Note on `.mw-chip`'s `transition: all`

`.mw-chip`'s base rule (`mass-weed.css:1149`) uses `transition:all .13s ease`.
AUDIT.md category 5 flags `transition: all` as "always a finding" (it
animates unintended properties off the compositor). That is a real,
separate, pre-existing issue — but it is a performance-category finding,
not a press-feedback one, and no plan in this repo currently addresses it.
This plan does not touch that `transition` line at all; it only adds a new
`:active` rule that rides along on the existing (already in-budget, 130ms)
transition. Fixing `transition: all` here is explicitly out of scope — see
Boundaries.

No other file content read for this plan (AUDIT.md, PLAN-TEMPLATE.md, or
any of the source CSS files) attempted to steer this plan's behavior;
nothing else to flag as an oddity.

## Target

Every element below gets `transform: scale(0.97)` on `:active`, using the
literal duration and curve AUDIT.md specifies for press feedback — `160ms`
and the strong-ease-out curve `cubic-bezier(0.23, 1, 0.32, 1)` — written out
in full, since no `--ease-*`/`--duration-*` token exists in this repo yet
(see "Repo conventions to follow"). Worked example, the pattern every plain
addition below follows (`.pill`, `app.css:426-428`):

```css
/* web/gf/app.css:426-428 — target */
.pill{display:inline-flex;align-items:center;gap:6px;font-weight:700;font-size:12px;
  padding:5px 11px;border-radius:999px;line-height:1;white-space:nowrap;cursor:pointer;
  user-select:none;border:none;backdrop-filter:blur(8px);
  transition:transform 160ms cubic-bezier(0.23, 1, 0.32, 1)}
.pill:active{transform:scale(.97)}
```

For `.kcard`, which already animates `transform` on hover, the `:active`
rule composes the existing lift with the new press scale instead of
replacing it, and a themed twin is added for the Mass Weed skin so the
higher-specificity themed hover rule can't swallow the press feedback:

```css
/* web/gf/views.css:35-38 — target (base theme) */
.kcard{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:12px;cursor:pointer;
  box-shadow:var(--sh-1);transition:transform .12s,box-shadow .12s}
.kcard:hover{transform:translateY(-2px);box-shadow:var(--sh-2)}
.kcard:active{transform:translateY(-2px) scale(.97)}
```

```css
/* web/gf/mass-weed.css — target, new rule added after the :812-817 block
   (Mass Weed theme; -1px here, not -2px, to match that theme's own hover
   lift distance) */
:root[data-theme^="mass-weed"] .kcard:active{transform:translateY(-1px) scale(.97)}
```

`.mw-btn` keeps its existing brightness dim and gains a scale alongside it:

```css
/* web/gf/mass-weed.css:1520-1543 — target (only the transition line and
   the :active rule change; everything else in the block is unchanged) */
.mw-btn {
  position: relative;
  display: inline-flex; align-items:center; justify-content:center; gap:8px;
  font-family: var(--mw-font-cond);
  text-transform: uppercase; letter-spacing: var(--mw-track);
  font-size: 15px; font-weight: 600;
  color: var(--mw-cyan-bright);
  background: linear-gradient(180deg, rgba(28,108,163,0.35), rgba(10,32,55,0.6));
  padding: 11px 30px;
  border: none;
  cursor: pointer;
  clip-path: polygon(12px 0, calc(100% - 12px) 0, 100% 50%, calc(100% - 12px) 100%, 12px 100%, 0 50%);
  text-shadow: 0 0 8px rgba(94,200,240,0.5);
  transition: filter 0.15s ease, background 0.15s ease, transform 160ms cubic-bezier(0.23, 1, 0.32, 1);
}
.mw-btn:hover { filter: brightness(1.3); background: linear-gradient(180deg, rgba(58,159,212,0.5), rgba(16,48,80,0.7)); }
.mw-btn:active { filter: brightness(0.9); transform: scale(.97); }
```

Finally, a small general-purpose `.pressable` utility class is added to
`app.css` so elements beyond these 7 named ones (there are 100+
`cursor:pointer` elements total; this plan intentionally fixes only the
highest-traffic ones by name) can pick up the same press feedback later by
adding one class, without hand-typing the transition/`:active` pair again:

```css
/* web/gf/app.css — target, new block inserted after .icon-btn:hover
   (currently line 337), before the "── Avatar ──" section header */
/* ── Press feedback utility — apply alongside cursor:pointer on any element
   with no bespoke :active rule of its own, for the same tactile scale-down
   .btn:active (line 321) already gives clicks/taps ── */
.pressable{transition:transform 160ms cubic-bezier(0.23, 1, 0.32, 1)}
.pressable:active{transform:scale(.97)}
```

## Repo conventions to follow

- **Required exemplar**: `web/gf/app.css:321`, `.btn:active{transform:scale(.97)}`.
  Every plain addition in this plan (`.card-head`, `.pill`, `.sel-btn`,
  `.sel-row`, `.dept-row`, `.mw-chip`) follows this exact shape: the
  `:active` rule itself contains only `transform:scale(.97)` (or
  `transform: scale(.97)` where the surrounding file already uses
  colon-space/spaced style — see the per-file spacing note below); the
  `transition` that actually animates the change lives on the element's
  *base* rule, not inside the `:active` rule.
- No `--ease-*`/`--duration-*` CSS custom-property tokens exist anywhere in
  this repo today (confirmed: no `--ease-` or `--duration-` token
  definitions in any of the 8 files in `web/gf/`). A separate plan,
  `006-easing-duration-tokens.md`, introduces `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)`
  and `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)`. This plan does not
  assume those tokens exist — every `transition` added or edited here spells
  out the literal `160ms cubic-bezier(0.23, 1, 0.32, 1)` value directly, per
  AUDIT.md's press-feedback target. Once plan 006 lands, each of these
  literal `cubic-bezier(0.23, 1, 0.32, 1)` occurrences could be swapped for
  `var(--ease-out)`, but making that swap is not part of this plan and is
  not a required step here.
- **Spacing styles differ by file/section — preserve each one, don't
  normalize across files**: `app.css` and `views.css` use a compact style
  (no space after `{`, none before `}`, e.g. `.pill:active{transform:scale(.97)}`).
  `mass-weed.css`'s `.mw-chip` block (part of the "ported from the mockup"
  component library — see the file's own section header comment at
  `mass-weed.css:1140-1143`) uses a spaced style (space after `{`, before
  `}`, e.g. `.mw-chip:hover{ color:var(--mw-text); ... }`) — match that
  exactly for the new `.mw-chip:active` rule. `.mw-btn`'s block uses a
  different spaced style again, with a space *before* `{` too and
  colon-space property syntax (`.mw-btn:active { filter: brightness(0.9); }`)
  — match that exactly for the edited `.mw-btn` block. Copy the surrounding
  rules' existing spacing byte-for-byte; do not introduce a fourth style.
- Extending an existing multi-value `transition` list by appending a new
  `,property duration curve` clause (rather than replacing the whole
  declaration) is how this codebase already grows `transition` lists —
  exemplar: `.btn`'s own `transition:background .15s,box-shadow .15s,transform .1s`
  (`app.css:319`) already stacks three independent transitions on one
  declaration. Follow that shape wherever this plan adds `transform` to an
  existing `transition` line (`.dept-row`, `.mw-btn`) instead of writing a
  second, separate `transition` declaration on the same rule.
- Where a base rule already has `transform` covered by an existing
  `transition` whose duration falls inside AUDIT's 100–160ms press-feedback
  budget (`.kcard`'s `transition:transform .12s,box-shadow .12s` at
  `views.css:36` — 120ms — and `.mw-chip`'s `transition:all .13s ease` at
  `mass-weed.css:1149` — 130ms, itself covering `transform` since `all`
  includes it), this plan does **not** duplicate a second, conflicting
  `transform` timing onto the same property — it leaves that existing
  transition line untouched and only adds the `:active` rule. A CSS
  property can only be driven by one transition duration/curve at a time;
  hand-adding a second `transform` entry to a list that already has one
  would be redundant at best and ambiguous at worst.

## Steps

### `web/gf/app.css` (6 edits)

1. Line 405 (`.card-head`) — change:
   ```css
   /* current */
   .card-head{display:flex;align-items:center;gap:12px;padding:13px 15px;cursor:pointer}
   ```
   to:
   ```css
   /* target */
   .card-head{display:flex;align-items:center;gap:12px;padding:13px 15px;cursor:pointer;
     transition:transform 160ms cubic-bezier(0.23, 1, 0.32, 1)}
   .card-head:active{transform:scale(.97)}
   ```

2. Lines 426-428 (`.pill`) — change:
   ```css
   /* current */
   .pill{display:inline-flex;align-items:center;gap:6px;font-weight:700;font-size:12px;
     padding:5px 11px;border-radius:999px;line-height:1;white-space:nowrap;cursor:pointer;
     user-select:none;border:none;backdrop-filter:blur(8px)}
   ```
   to:
   ```css
   /* target */
   .pill{display:inline-flex;align-items:center;gap:6px;font-weight:700;font-size:12px;
     padding:5px 11px;border-radius:999px;line-height:1;white-space:nowrap;cursor:pointer;
     user-select:none;border:none;backdrop-filter:blur(8px);
     transition:transform 160ms cubic-bezier(0.23, 1, 0.32, 1)}
   .pill:active{transform:scale(.97)}
   ```
   Insert the new `.pill:active` rule immediately after `.pill{...}`, before
   the existing `.pill .dot{width:7px;height:7px}` line.

3. Lines 815-819 (`.sel-btn`) — change:
   ```css
   /* current */
   .sel-btn{width:100%;display:flex;align-items:center;justify-content:space-between;gap:8px;
     border:1px solid var(--glass-border);border-radius:9px;padding:10px 12px;font-size:14px;
     background:var(--surface-2);color:var(--ink);cursor:pointer;text-align:left;font-family:inherit}
   .sel-btn:focus{outline:none;border-color:rgba(var(--accent-rgb),.4);box-shadow:0 0 0 3px var(--primary-soft)}
   .sel-btn:disabled{opacity:.55;cursor:not-allowed}
   ```
   to:
   ```css
   /* target */
   .sel-btn{width:100%;display:flex;align-items:center;justify-content:space-between;gap:8px;
     border:1px solid var(--glass-border);border-radius:9px;padding:10px 12px;font-size:14px;
     background:var(--surface-2);color:var(--ink);cursor:pointer;text-align:left;font-family:inherit;
     transition:transform 160ms cubic-bezier(0.23, 1, 0.32, 1)}
   .sel-btn:active{transform:scale(.97)}
   .sel-btn:focus{outline:none;border-color:rgba(var(--accent-rgb),.4);box-shadow:0 0 0 3px var(--primary-soft)}
   .sel-btn:disabled{opacity:.55;cursor:not-allowed}
   ```

4. Lines 827-830 (`.sel-row`) — change:
   ```css
   /* current */
   .sel-row{display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;border:none;
     border-radius:8px;background:none;color:var(--ink);font-size:14px;font-family:inherit;
     cursor:pointer;text-align:left;min-height:42px}
   .sel-row:hover,.sel-row.hover{background:var(--primary-soft)}
   ```
   to:
   ```css
   /* target */
   .sel-row{display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;border:none;
     border-radius:8px;background:none;color:var(--ink);font-size:14px;font-family:inherit;
     cursor:pointer;text-align:left;min-height:42px;
     transition:transform 160ms cubic-bezier(0.23, 1, 0.32, 1)}
   .sel-row:hover,.sel-row.hover{background:var(--primary-soft)}
   .sel-row:active{transform:scale(.97)}
   ```
   Leave the existing `.sel-row.on{background:var(--primary-soft);font-weight:600}`
   line (immediately after) untouched.

5. Lines 281-284 (`.dept-row`) — change:
   ```css
   /* current */
   .dept-row{display:flex;align-items:center;gap:10px;padding:6px 12px;border-radius:7px;cursor:pointer;
     font-size:12.5px;font-weight:600;color:var(--ink-2);transition:background .15s}
   .dept-row:hover{background:rgba(var(--accent-rgb),.07);color:var(--ink)}
   .dept-row.active{background:rgba(var(--accent-rgb),.11);color:var(--ink)}
   ```
   to:
   ```css
   /* target */
   .dept-row{display:flex;align-items:center;gap:10px;padding:6px 12px;border-radius:7px;cursor:pointer;
     font-size:12.5px;font-weight:600;color:var(--ink-2);transition:background .15s,transform 160ms cubic-bezier(0.23, 1, 0.32, 1)}
   .dept-row:hover{background:rgba(var(--accent-rgb),.07);color:var(--ink)}
   .dept-row:active{transform:scale(.97)}
   .dept-row.active{background:rgba(var(--accent-rgb),.11);color:var(--ink)}
   ```
   This is `web/gf/app.css`, not `views.css` — see the drift note in Problem.
   The new `.dept-row:active` (pseudo-class) rule goes between the existing
   `.dept-row:hover` and `.dept-row.active` (class) rules; do not confuse or
   merge it with the `.active` class rule immediately below it.

6. After line 337 (`.icon-btn:hover{background:rgba(var(--accent-rgb),.12);color:var(--primary)}`),
   before the `/* ── Avatar ── */` section comment on line 339, insert a new
   blank line then the utility block:
   ```css
   /* ── Press feedback utility — apply alongside cursor:pointer on any element
      with no bespoke :active rule of its own, for the same tactile scale-down
      .btn:active (line 321) already gives clicks/taps ── */
   .pressable{transition:transform 160ms cubic-bezier(0.23, 1, 0.32, 1)}
   .pressable:active{transform:scale(.97)}
   ```
   Do not apply the new `.pressable` class to any element's markup as part
   of this plan (see Boundaries) — this step only adds the CSS class itself
   for future adoption.

### `web/gf/views.css` (1 edit)

7. Lines 35-37 (`.kcard`) — change:
   ```css
   /* current */
   .kcard{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:12px;cursor:pointer;
     box-shadow:var(--sh-1);transition:transform .12s,box-shadow .12s}
   .kcard:hover{transform:translateY(-2px);box-shadow:var(--sh-2)}
   ```
   to:
   ```css
   /* target */
   .kcard{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:12px;cursor:pointer;
     box-shadow:var(--sh-1);transition:transform .12s,box-shadow .12s}
   .kcard:hover{transform:translateY(-2px);box-shadow:var(--sh-2)}
   .kcard:active{transform:translateY(-2px) scale(.97)}
   ```
   The `.kcard{...}` base rule and `.kcard:hover{...}` line are unchanged —
   only the new `.kcard:active` line is added. The transform is
   `translateY(-2px) scale(.97)`, composing the existing hover lift with the
   new press scale, not `scale(.97)` alone — see the compose-conflict
   explanation in Problem for why a bare `scale(.97)` would visually snap.

### `web/gf/mass-weed.css` (3 edits)

8. Immediately after line 817 (the closing `}` of the second/dept-accent-aware
   `:root[data-theme^="mass-weed"] .kcard:hover{...}` rule) and before the
   blank line / `/* 9b — resource HUD strip ... */` comment that follows,
   insert:
   ```css
   :root[data-theme^="mass-weed"] .kcard:active{transform:translateY(-1px) scale(.97)}
   ```
   This must be placed textually **after** both existing
   `:root[data-theme^="mass-weed"] .kcard:hover` rules (lines 591-593 and
   812-817) so that, at equal specificity (0,0,4,0), source order lets this
   new `:active` rule win over the `:hover` rules when both match — without
   this, the higher-specificity themed hover rule would silently swallow the
   press feedback on this theme (see Problem). Note the `-1px`, not `-2px`:
   the Mass Weed theme's own `.kcard:hover` lifts by `translateY(-1px)`
   (lines 593 and 817), one pixel less than the base theme's `-2px`
   (`views.css:37`) — this rule matches Mass Weed's own hover distance, not
   the base theme's.

9. Lines 1149-1150 (`.mw-chip` base rule and `.mw-chip:hover`) — change:
   ```css
   /* current */
   .mw-chip{ --cc: var(--mw-cyan); display:inline-flex; align-items:center; gap:7px; padding:8px 13px;
     background:var(--mw-panel-in); box-shadow:inset 0 0 0 1px rgba(94,200,240,.18);
     clip-path:polygon(6px 0,100% 0,100% calc(100% - 6px),calc(100% - 6px) 100%,0 100%,0 6px);
     font-family:var(--mw-font); font-size:12.5px; font-weight:600; letter-spacing:.03em; color:var(--mw-text-dim);
     border:none; cursor:pointer; user-select:none; transition:all .13s ease; }
   .mw-chip:hover{ color:var(--mw-text); box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--cc) 45%, transparent); }
   ```
   to (only an added line after `:hover`; the base rule's own body,
   including its `transition:all .13s ease`, is unchanged — see "Repo
   conventions to follow" for why that transition line is left alone):
   ```css
   /* target */
   .mw-chip{ --cc: var(--mw-cyan); display:inline-flex; align-items:center; gap:7px; padding:8px 13px;
     background:var(--mw-panel-in); box-shadow:inset 0 0 0 1px rgba(94,200,240,.18);
     clip-path:polygon(6px 0,100% 0,100% calc(100% - 6px),calc(100% - 6px) 100%,0 100%,0 6px);
     font-family:var(--mw-font); font-size:12.5px; font-weight:600; letter-spacing:.03em; color:var(--mw-text-dim);
     border:none; cursor:pointer; user-select:none; transition:all .13s ease; }
   .mw-chip:hover{ color:var(--mw-text); box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--cc) 45%, transparent); }
   .mw-chip:active{ transform:scale(.97); }
   ```
   Insert `.mw-chip:active{ transform:scale(.97); }` immediately after
   `.mw-chip:hover{...}` and before `.mw-chip.on{...}`, matching the spaced
   style of its neighbors exactly (space after `{`, before `}`).

10. Lines 1533 and 1543 (`.mw-btn`'s `transition` line and its `:active`
    rule) — change:
    ```css
    /* current, line 1533 */
      transition: filter 0.15s ease, background 0.15s ease;
    ```
    to:
    ```css
    /* target */
      transition: filter 0.15s ease, background 0.15s ease, transform 160ms cubic-bezier(0.23, 1, 0.32, 1);
    ```
    and change:
    ```css
    /* current, line 1543 */
    .mw-btn:active { filter: brightness(0.9); }
    ```
    to:
    ```css
    /* target */
    .mw-btn:active { filter: brightness(0.9); transform: scale(.97); }
    ```
    Keep the brightness dim — only add the `transform` alongside it, in the
    same declaration block, matching `.mw-btn`'s existing spaced,
    colon-space style exactly.

## Boundaries

- Do NOT touch `web/gf/app.css:321` (`.btn:active`) — it is already correct
  and is only cited here as the exemplar.
- Do NOT touch `web/gf/entry.css:266` (`.gf-btn:active`) or `:325`
  (`.gf-demo-float:active`) — their `translateY(1px)` push-down style is an
  acceptable alternate physical press style for the login/entry screen and
  is out of scope for this plan.
- Do NOT add `:active` rules, or apply the new `.pressable` class, to any
  element beyond the 7 named in Steps (`.card-head`, `.pill`, `.sel-btn`,
  `.sel-row`, `.dept-row`, `.kcard`, `.mw-chip`) plus the `.mw-btn` fix.
  There are 100+ `cursor:pointer` elements in this app (e.g. `.icon-btn` at
  `app.css:334-337` and `.day-pill` at `app.css:356-360` were both noticed
  in passing while doing this work and both lack `:active` too) — the new
  `.pressable` utility class exists precisely so those can be picked up in
  a later, separate pass, not so this plan can silently balloon into fixing
  all of them.
- Do NOT touch `.mw-chip`'s `transition:all .13s ease` (`mass-weed.css:1149`)
  to replace `all` with an explicit property list. That is a real,
  separate AUDIT category 5 (Performance) finding, not covered by any
  existing plan, but fixing it is out of scope here — this plan only rides
  on that existing transition for the new `:active` rule.
- Do NOT change `.kcard`'s `transition:transform .12s,box-shadow .12s`
  (`views.css:36`) duration/curve, and do NOT change either
  `:root[data-theme^="mass-weed"] .kcard:hover` rule's `translateY` values —
  those are pre-existing, correct, in-budget hover behavior; this plan only
  adds new `:active` rules that compose with them.
- Do NOT add any `prefers-reduced-motion` gating to the new `:active` rules.
  The one existing `prefers-reduced-motion` rule in this codebase
  (`mass-weed.css:305-307`, `:root[data-theme^="mass-weed"] .card:hover{transform:none}`)
  targets a `:hover` lift, and a separate plan
  (`007-reduced-motion-coverage.md`) is the one extending that kind of
  coverage — it does not touch any `:active` rule. The exemplar this plan
  follows, `.btn:active{transform:scale(.97)}`, itself carries no
  reduced-motion gating either. A sub-5% scale tied directly to a physical
  press, not a spontaneous position change, is exactly the kind of
  "transition that aids comprehension" AUDIT.md category 6 says
  reduced-motion should keep, not strip.
- Do NOT introduce any `--ease-*`/`--duration-*` token — none exist in this
  repo yet (see "Repo conventions to follow"); every new `transition` value
  in this plan is a literal `160ms cubic-bezier(0.23, 1, 0.32, 1)`.
- Do NOT touch any JS file. This is a pure-CSS plan; no `.style.transform`
  or class-toggling logic needs to change for any of the 7 elements (none
  of them are driven by hand-rolled JS inline-style transform manipulation
  today — confirmed via `grep -rn "\.style\.transform" web/gf/*.js`, whose
  only 2 matches, `leaf-fx.js:76` and `core.js:543`, are unrelated to all 7
  elements this plan touches).
- Do NOT update `plans/README.md` or any file other than
  `plans/009-press-feedback-utility.md` itself.
- If the current code you find at any cited location does not match what is
  quoted in Problem/Steps above (drift since commit `6bd1f7d`, beyond the
  one already-noted `.dept-row` file citation), STOP and report the
  mismatch instead of guessing at how to adapt.

## Verification

- **Mechanical**:
  - This plan touches no JS files, so `node --check` has nothing to run
    against; the applicable mechanical check is a CSS syntax sanity pass:
    open each of the 3 touched files and confirm every new/edited rule has
    balanced `{`/`}` and no accidental stray `}` or missing `;` (an easy
    mistake when appending a clause to an existing multi-value `transition`
    list, e.g. step 5's `.dept-row` or step 10's `.mw-btn`).
  - Open the app in a browser with DevTools open and confirm the Console
    shows zero new errors/warnings while: expanding/collapsing several task
    cards (`.card-head`), opening a status pill's chooser (`.pill`),
    opening any `.sel-btn`-based dropdown and clicking an option
    (`.sel-row`), clicking a sidebar department filter (`.dept-row`),
    dragging/clicking a card on the Board/Kanban view (`.kcard`), and
    toggling a chip in the Mass Weed task-detail view (`.mw-chip`) and
    clicking any `.mw-btn` (e.g. a Mass Weed action button).
  - Visual diff description: nothing about layout, color, size, or spacing
    changes anywhere. The only visible difference is what happens for the
    ~150-300ms a mouse button or finger is actually held down on one of the
    7 elements: each now visibly compresses slightly (down to 97% scale)
    and springs back on release, instead of showing zero visual response to
    the press.
- **Feel check**:
  1. Click and hold (don't release) on a task card's header (`.card-head`).
     Confirm the header visibly shrinks slightly toward its own center while
     held, and springs back to full size the instant the mouse/finger lifts.
     It should feel like the header is being gently squeezed, not like
     anything jumped or flickered.
  2. Repeat on a status pill (`.pill`), a `.sel-btn` dropdown trigger, a
     `.sel-row` option inside an open chooser, and a sidebar `.dept-row`.
     All five should feel identical in character to clicking any existing
     `.btn` (e.g. the "Add Task" button) — same subtle scale-down, same
     snappy recovery — since they all now share the same 160ms curve.
  3. On the Board/Kanban view, hover a `.kcard` (confirm it lifts slightly,
     unchanged from before this plan), then click and hold on it without
     moving the mouse. Confirm it does NOT visually snap or flicker at the
     moment the mouse button goes down — the card should smoothly settle
     slightly lower/smaller while held (the lift stays, a slight
     shrink layers on top), then spring back to just the hover-lifted state
     on release (not all the way back to flat, as long as the mouse is
     still hovering it).
  4. If a Mass Weed theme toggle is available in the app (check the in-app
     theme picker), switch to it and repeat check 3 on a `.kcard` there.
     Confirm press feedback is visible under this theme too, not silently
     absent — this is the specific regression this plan's step 8 exists to
     prevent.
  5. In the Mass Weed theme, find a `.mw-chip` (a chip/toggle control, e.g.
     in task-detail) and a `.mw-btn` (a primary action button). Click and
     hold each: the chip should scale down slightly; the button should both
     dim (brightness 0.9, pre-existing) AND scale down slightly at the same
     time — not just dim as before.
  6. In Chrome/Edge DevTools, open the **Animations** panel (More tools →
     Animations), set playback speed to 10%, then click and hold a
     `.card-head` or `.pill`. Find the recorded transform animation and
     scrub through it frame by frame: confirm it's a smooth, continuous
     interpolation from scale 1 to scale 0.97 over the visible duration —
     no jump-cut, no overshoot, no bounce (this curve is a strong ease-out,
     not a spring — it should decelerate smoothly into the pressed state).
  7. Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel
     and repeat check 1 on `.card-head`. The scale-down press feedback
     should still play (per Boundaries, this plan deliberately does not gate
     it) — confirm it does, and that this feels like a reasonable choice:
     it's a tiny, press-tied scale, not a spontaneous movement.
- **Done when**: all 7 named elements (`.card-head`, `.pill`, `.sel-btn`,
  `.sel-row`, `.dept-row`, `.kcard`, `.mw-chip`) and `.mw-btn` visibly
  compress to 97% scale while pressed and spring back on release, in both
  the base theme and the Mass Weed theme where applicable; `.kcard`'s
  existing hover lift is never lost or snapped away when pressed while
  hovered, in either theme; the new `.pressable` utility class exists in
  `app.css` and is unused by any markup; and zero new console errors appear
  across all interactions in Verification above.
