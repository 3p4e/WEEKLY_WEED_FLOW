# 011 — Convert layout-triggering `width`/`height` transitions to `transform`

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: LOW
- **Category**: 5. Performance
- **Estimated scope**: 4 paired CSS+JS fixes across 7 files — `web/gf/views.css` + `web/gf/workload-view.js` (`.wl-fill`), `web/gf/mass-weed.css` + `web/gf/task-detail-view.js` (`.mw-stat__fill`), `web/gf/app.css` + `web/gf/render.js` (`.tp-fill`), and a second, unrelated pair inside `web/gf/app.css` + `web/gf/voice.js` (`.wave span`). 9 edits total across those 7 files (2 separate edits land in `app.css` — `.tp-fill` and `.wave span` are unrelated rules; 2 separate edits land in `voice.js` — inserting the `waveMax` constant and rewriting the template string). `web/gf/entry.css` (4 locations: `.gf-stage`, `.gf-lockup`, `.gf-lw`, `.gf-back`) was read and evaluated but is **deliberately left unconverted** — see the last part of Problem and the first Boundaries bullet for why.

## Problem

AUDIT.md's category 5 ("Performance") is explicit about this pattern:

```
/* .claude/skills/improve-animations/AUDIT.md:71-80 */
## 5. Performance

- **Animate `transform` and `opacity` only.** `width`/`height`/`margin`/`padding`/`top`/`left` trigger layout + paint + composite.
- **`transition: all`** animates unintended properties off-GPU — always a finding.
...
Hunt for: `transition: all`, animated layout properties, ...
```

Eight CSS rules in this codebase transition a layout-triggering property
(`width`, `height`, `margin`, or `max-height`) instead of `transform`. Real-world impact is low for most
of them — they sit on occasional-use surfaces (the login screen, the voice
capture modal) that render rarely, not on every frame of a busy view. The
exception is the three progress-bar-fill selectors below (`.wl-fill`,
`.mw-stat__fill`, `.tp-fill`): these render on every workload page, every
dept-home KPI meter, and every task-tree row with sub-tasks — i.e. on every
normal task-list view — so their `width` transitions cost a real
Layout+Paint+Composite pass on a surface users see constantly. This plan fixes
those three, plus a fourth genuinely-convertible case (the voice waveform),
and explains in detail why the remaining four `entry.css` locations are
**not** converted.

### 1. `.wl-fill` — workload progress bar (converted)

```css
/* web/gf/views.css:447 — current */
.wl-fill{height:100%;border-radius:9px;transition:width .3s ease}
```

Its track wrapper clips overflow, which matters for the fix below:

```css
/* web/gf/views.css:446 — current, for context (unchanged) */
.wl-bar{position:relative;height:18px;background:var(--surface-2);border:1px solid var(--line);border-radius:9px;overflow:hidden}
```

The width is set inline, per row, from a template string in
`web/gf/workload-view.js`:

```js
/* web/gf/workload-view.js:73 — current */
<div class="wl-bar"><div class="wl-fill wl-${tier}" style="width:${pct}%"></div>
```

(`pct` is computed at `workload-view.js:59` as
`Math.min(100, Math.round((d.pts / CAP) * 100))` — already clamped to
`0..100` and already an integer.)

### 2. `.mw-stat__fill` — dept-home KPI meter / subtask completion bar (converted)

```css
/* web/gf/mass-weed.css:1204 — current */
.mw-stat__fill{ height:100%; border-radius:3px; position:relative; transition:width .4s ease; }
```

Its track wrapper also clips:

```css
/* web/gf/mass-weed.css:1203 — current, for context (unchanged) */
.mw-stat__track{ height:6px; background:var(--mw-stat-track); border-radius:3px; overflow:hidden; }
```

One of its call sites (there may be others; only the one in scope for this
plan's confirmed findings is shown) is a template string in
`web/gf/task-detail-view.js`:

```js
/* web/gf/task-detail-view.js:119 — current */
<div class="mw-stat__track subbar"><div class="mw-stat__fill mw-stat__fill--mid" style="width:${pct}%"></div></div>
```

(`pct` is computed at `task-detail-view.js:111` as
`kids.length ? Math.round(done / kids.length * 100) : 0` — an integer,
`0..100`.)

### 3. `.tp-fill` — task-tree progress fill (converted)

```css
/* web/gf/app.css:884 — current */
.tp-fill{display:block;height:100%;border-radius:3px;transition:width .4s cubic-bezier(.2,.7,.3,1)}
```

Its track wrapper clips too:

```css
/* web/gf/app.css:882-883 — current, for context (unchanged) */
.tp-track{width:52px;height:6px;border-radius:3px;background:var(--surface-3);overflow:hidden;
  box-shadow:inset 0 0 0 1px var(--line-2)}
```

Its call site is in `web/gf/render.js`, not `web/gf/views.js` (see the drift
note below):

```js
/* web/gf/render.js:385 — current */
<span class="tp-track"><span class="tp-fill ${p >= 75 ? 'hi' : p >= 34 ? 'mid' : 'lo'}" style="width:${p}%"></span></span>
```

(`p` comes from `GF.progress(c)` at `render.js:13-17`, which returns an
integer `0..100`.)

`.tp-fill` also has a mass-weed-theme "sheen" overlay pseudo-element that must
keep working after the fix:

```css
/* web/gf/mass-weed.css:338-343 — current, for context (unchanged) */
:root[data-theme^="mass-weed"] .tp-fill{border-radius:0;position:relative;overflow:hidden}
:root[data-theme^="mass-weed"] .tp-fill::after{
  content:"";position:absolute;inset:0;transform:translateX(-100%);
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent);
  animation:mw-sheen 3.5s ease-in-out infinite;
}
```

This `::after` is `inset:0` relative to `.tp-fill`'s own (post-transform)
rendered box, and a `transform` on a parent scales its whole rendered content,
pseudo-elements included. So once `.tp-fill` grows via `transform:scaleX()`
instead of `width`, the sheen still exactly covers the visible fill — no
change needed to this block. (`.wl-fill` has the equivalent sheen rule at
`mass-weed.css:767-776`, same reasoning, also needs no change.)

**Drift note**: this plan's source finding said to search
`web/gf/render.js` and `web/gf/views.js` for the JS/template call sites.
`web/gf/render.js` was correct for `.tp-fill` (line 385). `web/gf/views.js`
exists (30656 bytes, unrelated view code) but contains **no** reference to
`.tp-fill`, `.wl-fill`, or `.mw-stat__fill` — grepping the whole `web/gf/`
directory shows the real call sites are `web/gf/workload-view.js:73` and
`web/gf/task-detail-view.js:119` instead. Steps below use the confirmed
real locations, not the originally-guessed file.

### 4. `.wave span` — voice-capture waveform, 25 simultaneous bars (converted)

```css
/* web/gf/app.css:569 — current */
.wave span{width:4px;border-radius:4px;background:var(--primary);transition:height .12s}
```

Container, for context:

```css
/* web/gf/app.css:568 — current, for context (unchanged) */
.wave{display:flex;align-items:center;gap:3px;height:54px}
```

Rendered in `web/gf/voice.js`, one `<span>` per array entry, 25 entries,
height set inline on every one:

```js
/* web/gf/voice.js:52 — current, the hardcoded amplitude array */
const wave = [10, 22, 38, 26, 48, 64, 40, 72, 30, 54, 84, 46, 68, 34, 58, 24, 44, 30, 18, 40, 60, 36, 50, 26, 14];
```

```js
/* web/gf/voice.js:81 — current */
<div class="wave">${wave.map((h, i) => `<span style="height:${live ? h : 8}px;${!live ? 'opacity:.3' : i > 16 ? 'opacity:.35' : ''}"></span>`).join('')}</div>
```

`.wave` has a fixed `height:54px` that does **not** grow to fit its
children (its own box height is a static declared value, not
content-driven), and `align-items:center` vertically centers each bar
within that fixed-height row — so bars taller than 54px (the array's max
value is 84) already visually overflow the row's box today, symmetrically
above and below, without ever changing `.wave`'s own rendered size or
pushing any sibling around. This means the 25 simultaneous `height`
transitions never cause document-level reflow of anything outside `.wave`
today — but each one still forces the browser to lay out and repaint that
span every time the modal opens/closes or the mic toggles, 25 times at
once, for zero layout benefit since nothing outside the box moves. That's
exactly the "off-compositor cost with no compensating layout need" pattern
category 5 flags, and it converts cleanly to `transform: scaleY()` because
the vertical centering behavior is trivially replicated by `transform-origin:
center` (the default) on a fixed-height box.

### Why the four `entry.css` locations are read, documented, but NOT converted

```css
/* web/gf/entry.css:92-105 — current, .gf-stage (login screen leaf shrink) */
.gf-stage {
  position: relative;
  z-index: 2;
  transform-origin: center top;
  transition: transform .7s cubic-bezier(.2, .8, .2, 1), margin .7s cubic-bezier(.2, .8, .2, 1);
  will-change: transform;
}
.gf-entry.entered .gf-stage {
  transform: scale(.5);
  margin: 2px -70px -150px;
}
```

The codebase's own comments explain exactly what this negative margin is
for, and it is not cosmetic positioning — it is a deliberate layout hack:

```css
/* web/gf/entry.css:47-53 — current, comment directly above .gf-entry.gf-overflow .gf-stage */
/* The normal reveal shrinks the leaf with transform: scale() + a -150px bottom
   margin — a visual trick whose layout box stays full-size, so the flex
   container's scrollHeight never grows and the overflow can't be scrolled to.
   When the group genuinely overflows a short viewport we instead reformat the
   leaf into a REAL compact box (layout == paint): the whole leaf is fitted into
   a small square and the card flows directly beneath it, so scrollHeight is
   honest and the demo button is always reachable. */
```

`transform` never affects document flow or the layout of sibling elements —
that is precisely why it's the recommended property for animation. But this
rule's negative margin is doing the opposite job on purpose: it shrinks
`.gf-stage`'s contribution to the flex column's flow so `.gf-lockup` and the
sign-in card visually close the gap the `scale(.5)` leaves behind (`scale`
only shrinks what's painted; it never shrinks the space reserved in layout).
`web/gf/entry.js`'s `ensureCardInView()` (lines 188-203) then measures
`card.getBoundingClientRect().bottom` against `window.innerHeight` to decide
whether to add the `.gf-overflow` class, and is called on a timer
(`setTimeout(ensureCardInView, 620)`, roughly matching this rule's `.7s`
duration) specifically so it reads the settled post-margin layout. Swapping
this `margin` for a `transform: translate()` would leave `.gf-stage`'s full
pre-shrink box still reserved in the flex flow: the sign-in card would stay
where it was, a visible gap would open up where the leaf used to be, and
`ensureCardInView()`'s geometry read would no longer reflect what the "trick"
comment above is counting on. This is a functional coupling, not just a
performance tradeoff — converting it would risk breaking the login card's
layout and the overflow-detection fallback, for a rule that only runs once
per login-screen visit. **Not converted** in this plan; see Boundaries.

```css
/* web/gf/entry.css:128-136 — current, .gf-lockup */
.gf-lockup {
  position: relative;
  z-index: 2;
  margin-top: 14px;
  text-align: center;
  max-height: 260px;
  overflow: hidden;
  transition: opacity .4s ease, max-height .5s ease, margin .5s ease, transform .5s ease;
}
.gf-entry.entered .gf-lockup {
  opacity: 0;
  max-height: 0;
  margin: 0;
  transform: translateY(-12px);
  pointer-events: none;
}
```

```css
/* web/gf/entry.css:195-207 — current, .gf-lw */
.gf-lw {
  ...
  flex-direction: column;
  align-items: center;
  opacity: 0;
  max-height: 0;
  overflow: hidden;
  pointer-events: none;
  transition: opacity .5s ease, max-height .55s ease;
}
.gf-lw.show {
  opacity: 1;
  max-height: 660px;   /* room for the card + demo button; container scrolls if taller */
  pointer-events: auto;
}
```

```css
/* web/gf/entry.css:275-293 — current, .gf-back */
.gf-back {
  position: relative;
  z-index: 4;
  margin-top: 14px;
  font-size: 12.5px;
  color: var(--ink-2, #8FB6A6);
  cursor: pointer;
  opacity: 0;
  max-height: 0;
  overflow: hidden;
  pointer-events: none;
  transition: opacity .4s ease, max-height .4s ease;
}
.gf-back:hover { color: var(--ink, #DDF3E9); }
.gf-entry.entered .gf-back {
  opacity: .75;
  max-height: 36px;
  pointer-events: auto;
}
```

All three of these animate `max-height` specifically to fake "animate to
auto height": the true content height isn't known ahead of time (or, for
`.gf-lockup`/`.gf-back`, is being animated down to a collapsed `0`), so a
large fixed `max-height` stands in for `height: auto`. `max-height` is a
layout property — like `height`, animating it forces
Layout+Paint+Composite every frame, and it also genuinely changes each
element's contribution to the flex column's flow (which is the whole point:
`.gf-lockup`/`.gf-back` need to stop taking up vertical space when
collapsed). The standard trick for animating "to auto height" without
`max-height` is the `grid-template-rows: 0fr` → `1fr` technique (wrap the
content in a `display:grid` cell and transition `grid-template-rows`
instead of `max-height`). That trick is worth knowing, but it does **not**
solve this plan's performance problem: `grid-template-rows` is exactly as
layout-triggering as `max-height` — both force the browser to recompute the
size of a track and reflow surrounding content every frame, so swapping one
for the other changes zero performance characteristics; it would only be
worth doing to fix a *correctness* problem (an unknown/dynamic content
height), which none of these three rules has (each already declares an
explicit `max-height` value: `260px`, `660px`, `36px`). Since there is no
transform-based (compositor-only) way to fake "animate to/from a
content-dependent height while also making surrounding content genuinely
reflow to match," and the only real alternative has the identical
performance profile, these three `max-height` transitions are a known,
accepted tradeoff — **not converted** in this plan.

No steering or instructional content was found embedded in any comment read
for this plan — the `entry.css:47-53` comment quoted above, `entry.css:1-5`'s
file-header comment, and every other comment read across `views.css`,
`mass-weed.css`, `app.css`, `voice.js`, `render.js`, `workload-view.js`, and
`task-detail-view.js` are all plain descriptive engineering notes, consistent
with the rest of the codebase's documentation style — noted here only to
confirm the check was made, per this plan's own ground rules.

## Target

Every rule below keeps its **exact original duration and easing** — only the
animated property changes from a layout property to `transform`, plus the
static base size (`width:100%` for the three fill bars, `height:84px` for the
wave bars) and `transform-origin` each needs to render identically to today.

```css
/* web/gf/views.css:447 — target */
.wl-fill{width:100%;height:100%;border-radius:9px;transform-origin:left center;transition:transform .3s ease}
```

```css
/* web/gf/mass-weed.css:1204 — target */
.mw-stat__fill{ width:100%; height:100%; border-radius:3px; position:relative; transform-origin:left center; transition:transform .4s ease; }
```

```css
/* web/gf/app.css:884 — target */
.tp-fill{display:block;width:100%;height:100%;border-radius:3px;transform-origin:left center;transition:transform .4s cubic-bezier(.2,.7,.3,1)}
```

```css
/* web/gf/app.css:569 — target */
.wave span{width:4px;height:84px;border-radius:4px;background:var(--primary);transform-origin:center;transition:transform .12s}
```

```js
/* web/gf/workload-view.js:73 — target */
<div class="wl-bar"><div class="wl-fill wl-${tier}" style="transform:scaleX(${pct / 100})"></div>
```

```js
/* web/gf/task-detail-view.js:119 — target */
<div class="mw-stat__track subbar"><div class="mw-stat__fill mw-stat__fill--mid" style="transform:scaleX(${pct / 100})"></div></div>
```

```js
/* web/gf/render.js:385 — target */
<span class="tp-track"><span class="tp-fill ${p >= 75 ? 'hi' : p >= 34 ? 'mid' : 'lo'}" style="transform:scaleX(${p / 100})"></span></span>
```

```js
/* web/gf/voice.js:52-53 — target (new line 53 inserted) */
const wave = [10, 22, 38, 26, 48, 64, 40, 72, 30, 54, 84, 46, 68, 34, 58, 24, 44, 30, 18, 40, 60, 36, 50, 26, 14];
const waveMax = 84; // must equal the array's max value so the tallest bar renders at scaleY(1)
```

```js
/* web/gf/voice.js:81 (now 82 after the insert above) — target */
<div class="wave">${wave.map((h, i) => `<span style="transform:scaleY(${((live ? h : 8) / waveMax).toFixed(3)});${!live ? 'opacity:.3' : i > 16 ? 'opacity:.35' : ''}"></span>`).join('')}</div>
```

## Repo conventions to follow

- **Two formatting dialects coexist in this codebase — preserve each rule's
  own dialect.** `views.css:447`, `app.css:884`, and `app.css:569` are all
  compact style (no spaces around `:`, no space after `,`, no space inside
  `{ }`). `mass-weed.css:1204` is the "spaced" dialect (space after `:` and
  `,`, space inside `{ }`, trailing `;` before `}`) used throughout that
  block (see the header comment at `mass-weed.css:1200-1202`, "Verbatim from
  design/mass-weed-mockup/mass-weed.css"). Match each target block above
  exactly — do not reformat one dialect into the other.
- **Every one of these three fill bars already sits inside a track wrapper
  with `overflow:hidden` and a fixed pixel width/height** —
  `.wl-bar` (`views.css:446`), `.mw-stat__track` (`mass-weed.css:1203`), and
  `.tp-track` (`app.css:882-883`). This is exactly what makes
  `width:100%;transform-origin:left center;transform:scaleX(pct/100)` safe:
  the fill's static `width:100%` fills the track at full scale, the parent's
  `overflow:hidden` clips it exactly like the old `width:${pct}%` did, and
  `transform-origin:left center` makes it shrink/grow from the track's left
  edge — the only visually-correct origin for a left-to-right fill bar (the
  default `center` origin would grow from both sides at once, which reads as
  wrong for a progress meter). Use this same three-part pattern
  (`width:100%` + `transform-origin:left center` + `transform:scaleX()`) for
  all three; do not invent a different technique for any one of them.
- **No `--ease-*`/`--duration-*` token system exists anywhere in this repo
  yet** (confirmed — this is the same fact plan `006-easing-duration-tokens.md`
  starts from, which is what introduces `--ease-out:
  cubic-bezier(0.23, 1, 0.32, 1)` and `--ease-in-out: cubic-bezier(0.77, 0,
  0.175, 1)`). This plan never changes a duration or easing value — `.3s
  ease`, `.4s ease`, `.4s cubic-bezier(.2,.7,.3,1)`, and `.12s` are all kept
  byte-for-byte — so there is no token to reach for here. Once plan 006
  lands, these literal easing values could in principle be swapped for
  `var(--ease-out)`/`var(--ease-in-out)` where the curve matches, but making
  that swap is **not** part of this plan and is not a required step.
- `pct`/`p` are already integers clamped or naturally bounded to `0..100` at
  every one of the three call sites (see the Problem section citations for
  each) — `pct / 100` / `p / 100` in the target template strings needs no
  additional rounding or clamping logic added.

## Steps

1. **`web/gf/views.css:447`** (`.wl-fill`) — change:
   ```css
   /* current */
   .wl-fill{height:100%;border-radius:9px;transition:width .3s ease}
   ```
   to:
   ```css
   /* target */
   .wl-fill{width:100%;height:100%;border-radius:9px;transform-origin:left center;transition:transform .3s ease}
   ```

2. **`web/gf/workload-view.js:73`** — change:
   ```js
   /* current */
   <div class="wl-bar"><div class="wl-fill wl-${tier}" style="width:${pct}%"></div>
   ```
   to:
   ```js
   /* target */
   <div class="wl-bar"><div class="wl-fill wl-${tier}" style="transform:scaleX(${pct / 100})"></div>
   ```

3. **`web/gf/mass-weed.css:1204`** (`.mw-stat__fill`) — change:
   ```css
   /* current */
   .mw-stat__fill{ height:100%; border-radius:3px; position:relative; transition:width .4s ease; }
   ```
   to:
   ```css
   /* target */
   .mw-stat__fill{ width:100%; height:100%; border-radius:3px; position:relative; transform-origin:left center; transition:transform .4s ease; }
   ```

4. **`web/gf/task-detail-view.js:119`** — change:
   ```js
   /* current */
   <div class="mw-stat__track subbar"><div class="mw-stat__fill mw-stat__fill--mid" style="width:${pct}%"></div></div>
   ```
   to:
   ```js
   /* target */
   <div class="mw-stat__track subbar"><div class="mw-stat__fill mw-stat__fill--mid" style="transform:scaleX(${pct / 100})"></div></div>
   ```

5. **`web/gf/app.css:884`** (`.tp-fill`) — change:
   ```css
   /* current */
   .tp-fill{display:block;height:100%;border-radius:3px;transition:width .4s cubic-bezier(.2,.7,.3,1)}
   ```
   to:
   ```css
   /* target */
   .tp-fill{display:block;width:100%;height:100%;border-radius:3px;transform-origin:left center;transition:transform .4s cubic-bezier(.2,.7,.3,1)}
   ```
   Do not touch `.tp-fill.hi`/`.tp-fill.mid`/`.tp-fill.lo` (`app.css:885-887`,
   color-only) or the mass-weed `.tp-fill::after` sheen block
   (`mass-weed.css:338-352`) — both already work unmodified against a
   `transform`-scaled parent, see Problem section 3 above.

6. **`web/gf/render.js:385`** — change:
   ```js
   /* current */
   <span class="tp-track"><span class="tp-fill ${p >= 75 ? 'hi' : p >= 34 ? 'mid' : 'lo'}" style="width:${p}%"></span></span>
   ```
   to:
   ```js
   /* target */
   <span class="tp-track"><span class="tp-fill ${p >= 75 ? 'hi' : p >= 34 ? 'mid' : 'lo'}" style="transform:scaleX(${p / 100})"></span></span>
   ```

7. **`web/gf/app.css:569`** (`.wave span`) — change:
   ```css
   /* current */
   .wave span{width:4px;border-radius:4px;background:var(--primary);transition:height .12s}
   ```
   to:
   ```css
   /* target */
   .wave span{width:4px;height:84px;border-radius:4px;background:var(--primary);transform-origin:center;transition:transform .12s}
   ```
   `84` is the highest value in the `wave` array (`voice.js:52`) — it is the
   tallest a bar can ever be, so it's the correct static base for every bar
   to scale down from.

8. **`web/gf/voice.js:52-53`** — insert a new line directly after the `wave`
   array declaration, matching the array's max value:
   ```js
   /* current, line 52 only */
   const wave = [10, 22, 38, 26, 48, 64, 40, 72, 30, 54, 84, 46, 68, 34, 58, 24, 44, 30, 18, 40, 60, 36, 50, 26, 14];
   ```
   to:
   ```js
   /* target, two lines */
   const wave = [10, 22, 38, 26, 48, 64, 40, 72, 30, 54, 84, 46, 68, 34, 58, 24, 44, 30, 18, 40, 60, 36, 50, 26, 14];
   const waveMax = 84; // must equal the array's max value so the tallest bar renders at scaleY(1)
   ```

9. **`web/gf/voice.js:81`** (now line 82 after step 8's insert) — change:
   ```js
   /* current */
   <div class="wave">${wave.map((h, i) => `<span style="height:${live ? h : 8}px;${!live ? 'opacity:.3' : i > 16 ? 'opacity:.35' : ''}"></span>`).join('')}</div>
   ```
   to:
   ```js
   /* target */
   <div class="wave">${wave.map((h, i) => `<span style="transform:scaleY(${((live ? h : 8) / waveMax).toFixed(3)});${!live ? 'opacity:.3' : i > 16 ? 'opacity:.35' : ''}"></span>`).join('')}</div>
   ```

## Boundaries

- **Do NOT touch `web/gf/entry.css`.** All four locations there
  (`.gf-stage:96`, `.gf-lockup:135`, `.gf-lw:201`, `.gf-back:286`) were read
  and deliberately left unconverted — the margin on `.gf-stage` is a
  documented, JS-depended-on layout mechanism (not a cosmetic offset a
  `transform` can substitute for), and the three `max-height` transitions
  have no transform-based fix that wouldn't cost the exact same
  Layout+Paint+Composite performance profile (the `grid-template-rows`
  alternative is equally layout-triggering). See the Problem section for the
  full reasoning on each. If a future plan wants to revisit this, it needs
  to solve the layout-coupling problem, not just swap the animated property.
- Do NOT touch `web/gf/entry.js` — `ensureCardInView()` is cited in the
  Problem section only as evidence for why `.gf-stage`'s margin can't be
  safely converted; this plan makes no change to it.
- Do NOT change any transition duration or easing value anywhere in this
  plan. `.3s ease`, `.4s ease`, `.4s cubic-bezier(.2,.7,.3,1)`, and `.12s`
  are preserved exactly.
- Do NOT add `prefers-reduced-motion` handling to `.wave span` or to any of
  the three fill-bar selectors. None of the four have it today; adding it is
  a different finding (AUDIT category 6), out of scope here.
- Do NOT touch the mass-weed "sheen" pseudo-element rules
  (`mass-weed.css:338-352` for `.tp-fill::after`, `mass-weed.css:767-776`
  for `.wl-fill::after`/`.track>span::after`/`.ana-hb-f::after`) — they are
  `inset:0` relative to their parent's rendered box and already work
  correctly once the parent scales via `transform` instead of `width`, per
  the reasoning in Problem section 3.
- Do NOT touch `.tree-row.s-working .tp-fill`/`.card.s-working .card-actions
  .track > span` (`app.css:975-978`, the striped "actively working" overlay)
  — it only changes `background-image` and runs its own `mwStripe`
  `background-position` keyframe animation, unrelated to this plan's
  `width`/`transform` swap.
- `transform: scaleX(0)` at `pct`/`p === 0` (an honest zero-progress state)
  is correct and is **not** a violation of AUDIT category 3's "never
  `scale(0)`" rule — that rule is about entrances that shouldn't visually
  appear from nothing (popovers, modals); a progress fill legitimately
  showing zero completion is data, not an entrance animation.
- If the current code found at any file:line above does not match what's
  quoted in Problem/Target (drift since commit `6bd1f7d`), STOP and report
  the mismatch instead of guessing at how to adapt the edit.

## Verification

- **Mechanical**:
  - Run `node --check web/gf/render.js`, `node --check web/gf/workload-view.js`,
    `node --check web/gf/task-detail-view.js`, and `node --check web/gf/voice.js`
    — all four must exit with no output/error.
  - Run `grep -n "transition:width\|transition: width" web/gf/views.css web/gf/mass-weed.css web/gf/app.css`
    and confirm **zero** matches remain (before this plan it matches
    `views.css:447`, `mass-weed.css:1204`, `app.css:884` — exactly the 3
    locations this plan fixes).
  - Run `grep -n "transition:height\|transition: height" web/gf/app.css` and
    confirm zero matches remain (before this plan it matches `app.css:569`).
  - Run `grep -n "style=\"width:\${" web/gf/workload-view.js web/gf/task-detail-view.js web/gf/render.js`
    and confirm zero matches remain, and
    `grep -n "style=\"transform:scaleX(" web/gf/workload-view.js web/gf/task-detail-view.js web/gf/render.js`
    finds exactly one match in each file.
  - Run `grep -n "style=\"height:\${live" web/gf/voice.js` and confirm zero
    matches; `grep -n "waveMax" web/gf/voice.js` finds exactly 2 matches
    (the declaration and its one use).
  - Visual diff description: on every touched surface, the fill bars and
    waveform look **pixel-identical** to before this plan at rest (0%, 100%,
    and mid-value states) — same colors, same track clipping, same
    left-anchored growth direction for the three progress bars, same
    vertically-centered growth for the waveform bars. The only allowed
    visual difference is a very slightly different corner rounding on
    partially-filled progress bars: `border-radius` doesn't scale with
    `transform: scaleX()`, so a fill's right-edge corner radius stays a
    constant `9px`/`3px`/`3px` (whichever selector) at every fill level
    instead of `border-radius` implicitly shrinking with a smaller `width` —
    this is expected, standard behavior for this technique and not a bug.
- **Feel check**:
  1. Open the Workload view (any week with assigned people/points). Open
     DevTools → More tools → **Animations** panel. Change one person's
     points so their bar's percentage changes (or reload with different
     data), triggering `.wl-fill`'s transition. Confirm the recorded
     transition's property is `transform`, never `width`. Set the
     Animations panel's playback speed to **10%** and re-trigger: watch the
     bar visibly grow from the **left edge** of the track outward — not
     from the center, not from the right — confirming
     `transform-origin:left center` is doing its job.
  2. Open a task-detail screen for a task with subtasks, at 10% playback,
     and check/uncheck a subtask so the completion percentage changes.
     Confirm `.mw-stat__fill`'s bar grows/shrinks from the left edge only,
     smoothly over the slowed `.4s`, and that the Animations panel again
     shows `transform`, not `width`.
  3. Open a task-tree view with a parent task that has scored subtasks (a
     `.tp-fill` bar visible), at 10% playback, and change a subtask's
     progress. Confirm the same left-anchored growth over the slowed `.4s`
     with the `cubic-bezier(.2,.7,.3,1)` curve still visibly easing (not
     linear, not snapping). If viewing under the mass-weed theme, also
     confirm the diagonal "sheen" sweep across the fill still plays and
     stays confined to the fill's actual (scaled) width — it should never
     spill out past the visible fill edge onto the empty track.
  4. Open the voice capture modal (mic icon on a task-creation flow), at
     10% playback, and toggle the mic on. Confirm all 25 waveform bars grow
     from **8px up to their target height, symmetrically from the vertical
     center** of the `.wave` row (some pixels appear above the row's
     original center, some below) — not just downward or upward only —
     confirming the default `transform-origin:center` reproduces the old
     `align-items:center` growth behavior. Confirm the Animations panel
     shows `transform`, never `height`, for these spans. Toggle the mic off
     and confirm the bars shrink back to 8px the same way.
  5. Toggle `prefers-reduced-motion` (DevTools Rendering panel → "Emulate
     CSS media feature prefers-reduced-motion: reduce") and repeat any one
     of the checks above: behavior is unchanged from before this plan
     (none of the four touched selectors had reduced-motion handling before
     this plan, and this plan doesn't add any — see Boundaries).
  6. As a sanity check that the transitions are still properly
     interruptible (CSS `transition`, not `@keyframes`, so this should hold
     regardless of the property swap): rapidly change a progress value
     twice in quick succession (e.g. check then immediately uncheck a
     subtask) and confirm the bar smoothly retargets to the new value
     mid-animation instead of snapping or restarting from `scaleX(0)`.
- **Done when**: all four `node --check` calls pass; both `grep` "zero
  matches" checks pass; both `grep` "exactly N matches" checks pass; every
  target rule/template in this plan matches what's quoted in the Target
  section above, byte-for-byte on every value except what's noted; and
  every item in the feel check above passes.
