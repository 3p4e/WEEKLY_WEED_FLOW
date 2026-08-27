# 005 — Remove 'storm' from the sidebar/header leaf's automatic idle-mode rotation; widen the wordmark bloom interval

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: MEDIUM
- **Category**: 1. Purpose & frequency (compounded by 7. Cohesion & tokens — a festive/party-register animation firing unattended, forever, on persistent chrome clashes with a cannabis-cultivation-facility task-management dashboard's crisp, functional personality)
- **Estimated scope**: 1 file (`web/gf/leaf-fx.js`), 2 single-value edits plus one explanatory comment, ~10 lines touched total. No CSS changes, no HTML changes, no other JS file touched.

## Problem

`web/gf/leaf-fx.js` drives the animated leaf logo (sidebar `#brand-leaf` and
header `#header-leaf`) and the "GrowFlow" wordmark that both appear in the
persistent app chrome — rendered on every view, for the entire time a user
has the app open. This app is a cannabis-cultivation-facility task-management
dashboard, not a marketing site; its own file comments describe the leaf as
an "interactive leaf" logo with click-to-cycle FX, not a page that should be
performing unattended attention-grabbing motion on its own.

**Note on a path correction in the original finding**: the finding this plan
is based on cited the wordmark markup as `web/gf/index.html:64` and `:90`.
No `web/gf/index.html` exists in this repo (confirmed:
`find web/gf -name index.html` → no results). The actual host page is
`web/index.html`, and the line numbers are otherwise exactly right — verified
current code, `web/index.html:64` (sidebar) and `:90` (header):

```html
<!-- web/index.html:64 — current -->
        <div class="gf-name" style="font-size:21px"><span class="gf-grow-word">Grow</span><b>Flow</b></div>
```

```html
<!-- web/index.html:90 — current -->
        <span class="gf-name" style="font-size:21px"><span class="gf-grow-word">Grow</span><b>Flow</b></span>
```

### 1. The permanent `gf-flow` wordmark gradient — confirmed, but explicitly OUT of scope

Verified current code, `web/gf/leaf-fx.css:153-163`:

```css
/* web/gf/leaf-fx.css:153-163 — current */
.gf-name b{
  background:linear-gradient(90deg,#2BE8A0 0%,#2BE8A0 33%,#2FD9D9 66%,#2BE8A0 100%);
  background-size:300% 100%;
  -webkit-background-clip:text;background-clip:text;color:transparent;
  animation:gf-flow 4s ease-in-out infinite;
  display:inline-block;
}
@keyframes gf-flow{
  0%,100%{background-position:0% 50%}
  50%{background-position:100% 50%}
}
```

This is a slow (4s), low-amplitude color wave across the "Flow" half of the
wordmark — gentle, no shape/position change, no particles. Along with the
base leaf idle motion (`web/gf/leaf-fx.css:16-23`, `lf-float` and
`pp-leaf-breathe` — a subtle float/bob and a slow breathing scale, both
`ease-in-out`, both running unconditionally at `data-mode="calm"`), this is
plausibly an intentional brand-identity choice, not a mechanical animation
defect. **This plan does not touch `gf-flow`, `lf-float`, `pp-leaf-breathe`,
or any aura/shimmer idle effect on the logo itself.** Whether to remove them
entirely is a product/design call, not something a motion-advisor plan
should unilaterally make.

### 2. The bloom loop's repeat interval — confirmed, IN scope

`web/gf/leaf-fx.js`'s `initMark()` re-triggers a scale-pop ("bloom") on the
"Grow" half of the wordmark on a recurring timer, forever, unconditionally,
on every page. Verified current code, `web/gf/leaf-fx.js:202-211`:

```js
/* web/gf/leaf-fx.js:202-211 — current */
  initMark() {
    if (this._markInit) return; this._markInit = true;
    const bloom = () => {
      document.querySelectorAll('.gf-grow-word').forEach(w => {
        w.classList.remove('blooming'); void w.offsetWidth; w.classList.add('blooming');
      });
      setTimeout(bloom, 8000 + Math.random() * 8000);
    };
    setTimeout(bloom, 2000 + Math.random() * 3000);
  },
```

Line 208 (`setTimeout(bloom, 8000 + Math.random() * 8000)`) is the recurring
interval: after every bloom, the next one is scheduled 8-16 seconds later,
forever, for as long as the tab stays open. The pop itself is the
`gf-bloom` keyframe — verified current code, `web/gf/leaf-fx.css:167-172`:

```css
/* web/gf/leaf-fx.css:167-172 — current */
.gf-grow-word.blooming{animation:gf-bloom .65s cubic-bezier(.22,1,.36,1) both}
@keyframes gf-bloom{
  0%{transform:scale(.84) translateY(4px);opacity:.6}
  58%{transform:scale(1.08) translateY(-2px)}
  100%{transform:scale(1) translateY(0);opacity:1}
}
```

(Minor citation note: the original finding cited this keyframe as
"167-171" — the verified block actually closes at line 172, one line past
that. Citation-truncation artifact, not code drift; the block above is
complete and confirmed against the file on disk.)

A 0.65s pop with a strong `cubic-bezier(.22,1,.36,1)` ease-out is a
reasonable "flourish" shape on its own — the problem per AUDIT.md's
frequency table (section 1) is purely cadence: at 8-16s, it recurs roughly
every dozen seconds for as long as the app is open, which reads as a
background tic rather than an occasional flourish. This plan widens only
that recurring interval (line 208); the pop's own shape, duration, and
easing (`gf-bloom`, `.65s`, `cubic-bezier(.22,1,.36,1)`) are unchanged, and
the one-time initial delay before the very first bloom (line 210,
`2000 + Math.random() * 3000`) is also left untouched — it only ever fires
once per page load and isn't the repeating tic being addressed here.

### 3. The auto-idle system's escalation into 'storm' — confirmed, IN scope, with an important correction to the original finding

Verified current code, `web/gf/leaf-fx.js:17-35` (`init()`), showing the
auto-idle system is wired up **only** on the non-WebGL CSS-fallback
rendering path:

```js
/* web/gf/leaf-fx.js:17-35 — current */
  init() {
    this.initMark();
    // Use the real 3D WebGL leaf (leaf3d.js) for EVERY leaf logo in the app —
    // sidebar, header, assistant, and any future ones — so the whole app matches
    // the splash's animated leaf. The flat CSS/PNG leaf + its click-FX below is
    // kept only as the graceful fallback when three.js/WebGL isn't available.
    if (window.GF && GF.leaf3d && GF.leaf3d.supported()) {
      this.mount3dAll();
      return;
    }
    document.querySelectorAll('.leaf-stage').forEach(st => this.bind(st));
    // Auto-idle for sidebar + header leaves (start after page warm-up)
    setTimeout(() => {
      const sidebar = document.getElementById('brand-leaf');
      if (sidebar) this.startAutoIdle(sidebar, {restMin:4500, restMax:11000, holdMin:900, holdMax:2000});
      const header  = document.getElementById('header-leaf');
      if (header)  this.startAutoIdle(header,  {restMin:7000, restMax:16000, holdMin:700, holdMax:1500});
    }, 3500);
  },
```

The auto-idle loop itself — verified current code, `web/gf/leaf-fx.js:154-197`:

```js
/* web/gf/leaf-fx.js:154-197 — current */
  startAutoIdle(stage, opts) {
    if (stage._autoIdle) return;
    stage._autoIdle = true;
    opts = opts || {};
    const active   = ['pulse','shake','spin','bounce','storm','drift'];
    const restMin  = opts.restMin  || 2000;
    const restMax  = opts.restMax  || 5000;
    const holdMin  = opts.holdMin  || 900;
    const holdMax  = opts.holdMax  || 2000;
    let   lastMode = '';

    const tick = () => {
      if (!document.contains(stage)) return;
      const rest = restMin + Math.random() * (restMax - restMin);
      setTimeout(() => {
        if (!document.contains(stage)) return;
        // pick a mode different from last one
        const pool = active.filter(m => m !== lastMode);
        const mode = pool[Math.floor(Math.random() * pool.length)];
        lastMode = mode;
        stage.dataset.mode = mode;
        this.burst(stage, mode);
        const hold = holdMin + Math.random() * (holdMax - holdMin);

        setTimeout(() => {
          if (!document.contains(stage)) return;
          // 30% chance: chain a second rapid hit before resting
          if (Math.random() < 0.3) {
            const pool2 = active.filter(m => m !== mode);
            const mode2 = pool2[Math.floor(Math.random() * pool2.length)];
            stage.dataset.mode = mode2;
            this.burst(stage, mode2);
            setTimeout(() => {
              if (document.contains(stage)) { stage.dataset.mode = 'calm'; tick(); }
            }, 700 + Math.random() * 400);
          } else {
            stage.dataset.mode = 'calm';
            tick();
          }
        }, hold);
      }, rest);
    };
    tick();
  },
```

So: with `restMin`/`restMax` of 4500-11000ms (sidebar) and 7000-16000ms
(header), the idle logo picks a random mode from `active` roughly every
4.5-16 seconds, forever, unattended, only when WebGL isn't available
(`GF.leaf3d.supported()` is falsy) — confirming the finding's description of
frequency and gating.

**Correction to the original finding**: the finding described "storm/rave"
together as both being in this automatic rotation and both applying
rainbow hue-rotation. The verified code does not match that pairing exactly:

- `active` (line 158) is `['pulse','shake','spin','bounce','storm','drift']`
  — **`'rave'` is already absent.** Only `'storm'` is in the automatic pool.
- The rainbow hue-rotate filter belongs only to `'rave'`. Verified current
  code, `web/gf/leaf-fx.css:101-108`:

  ```css
  /* web/gf/leaf-fx.css:101-108 — current */
  .leaf-stage[data-mode="rave"] .pp-leaf-anim{animation:lf-spin .95s linear infinite,lf-rave 1.8s linear infinite}
  .leaf-stage[data-mode="rave"] .leaf-float{animation:lf-bounce .48s ease-in-out infinite}
  .leaf-stage[data-mode="rave"] .pp-leaf-anim::before{animation:pp-aura-pulse .75s ease-in-out infinite}
  @keyframes lf-rave{
    0%{filter:hue-rotate(0deg) saturate(2) brightness(1.2) drop-shadow(0 0 26px rgba(43,232,160,.95))}
    100%{filter:hue-rotate(360deg) saturate(2) brightness(1.2) drop-shadow(0 0 26px rgba(43,232,160,.95))}
  }
  ```

  `'storm'` instead does a wild multi-axis 3D tumble with no color/filter
  change — verified current code, `web/gf/leaf-fx.css:91-99`:

  ```css
  /* web/gf/leaf-fx.css:91-99 — current */
  .leaf-stage[data-mode="storm"] .pp-leaf-anim{animation:lf-storm 4s ease-in-out infinite}
  @keyframes lf-storm{
    0%,55%,100%{transform:rotateX(0deg) rotateY(0deg) rotateZ(0deg)}
    12%{transform:rotateX(42deg) rotateY(138deg) rotateZ(-18deg)}
    25%{transform:rotateX(-26deg) rotateY(268deg) rotateZ(14deg)}
    38%{transform:rotateX(18deg) rotateY(360deg) rotateZ(-8deg)}
    50%{transform:rotateX(0deg) rotateY(360deg) rotateZ(0deg)}
  }
  ```

This changes the concrete fix from what the finding assumed: **only
`'storm'` needs to be removed from the automatic `active` pool.** `'rave'`
requires no change — it's already excluded from automatic rotation.
`'storm'` is still squarely in scope: it's a "wild tumble" mode, 18 particles
per burst (see `burst()` below), firing unattended on brand chrome every
4.5-16 seconds — a clear frequency/personality mismatch on its own, distinct
from `'rave'`'s rainbow filter, but the same category of problem: high-energy,
attention-grabbing motion that should not run automatically and indefinitely.

The particle-burst sizing that confirms `'storm'`'s energy level — verified
current code, `web/gf/leaf-fx.js:109-139` (`burst()`):

```js
/* web/gf/leaf-fx.js:109-139 — current */
  burst(stage, mode) {
    if (window.matchMedia && matchMedia('(prefers-reduced-motion:reduce)').matches) return;
    const rip = document.createElement('span');
    rip.className = 'leaf-ripple';
    stage.appendChild(rip);
    setTimeout(() => rip.remove(), 700);

    const n = mode === 'rave' ? 26 : (mode === 'storm' || mode === 'shake') ? 18 : 14;
    for (let k = 0; k < n; k++) {
      const s   = document.createElement('span');
      s.className = 'leaf-spark';
      const ang = (Math.PI * 2 * k / n) + Math.random() * 0.65;
      const dist = 30 + Math.random() * 44;
      s.style.setProperty('--dx', (Math.cos(ang) * dist).toFixed(1) + 'px');
      s.style.setProperty('--dy', (Math.sin(ang) * dist).toFixed(1) + 'px');
      const sz = 5 + Math.random() * 6;
      s.style.width = s.style.height = sz.toFixed(1) + 'px';
      if (mode === 'rave') {
        const h = Math.floor(Math.random() * 360);
        s.style.background = `radial-gradient(circle,hsl(${h},92%,74%),hsl(${h},92%,52%))`;
      } else if (mode === 'storm') {
        s.style.background = 'radial-gradient(circle,#b3fff0,#2FD9D9)';
      } else if (mode === 'pulse') {
        s.style.background = 'radial-gradient(circle,#d4f7bc,#5BBA47)';
      } else if (mode === 'shake') {
        s.style.background = 'radial-gradient(circle,#ffe9b3,#FF9A1A)';
      }
      stage.appendChild(s);
      setTimeout(() => s.remove(), 790);
    }
  },
```

### `'storm'`/`'rave'` reachability outside `startAutoIdle` — verified, confirms the fix is complete

`grep -rn "storm\|rave" web/` (excluding the unrelated `three.min.js`
substring hit, which is just "average" containing "rave") shows `'storm'`
and `'rave'` appear only in `web/gf/leaf-fx.js` and `web/gf/leaf-fx.css` —
nowhere else in the app triggers them. Within `leaf-fx.js`, both names also
appear in:

- `GF.leafFX.modes` (line 5: `['calm','drift','pulse','shake','spin','bounce','storm','rave']`)
  and `GF.leafFX.labels` (lines 6-15) — the full mode list used by the
  **manual** click/keydown cycle.
- `cycle()` (lines 101-107), called from `bind()`'s click and Enter/Space
  keydown listeners (lines 91-97) — this is the only other path that can
  reach `'storm'` or `'rave'`, and it is 100% user-initiated (a click or a
  keyboard activation on the leaf logo itself), never automatic.
- `burst()` (verified above) — shared by both the manual `cycle()` path and
  the automatic `startAutoIdle` path; its per-mode particle count/color
  branches for `'storm'`/`'rave'` stay correct and necessary for when a user
  manually cycles into those modes.

This confirms the fix is complete: removing `'storm'` from the `active`
array in `startAutoIdle` removes the *only* automatic path into it, while
leaving the manual click-to-cycle path (which can still reach all 8 modes,
including `'storm'` and `'rave'`) completely untouched — exactly the
"deliberate user-triggered rare delight moment" that AUDIT.md's frequency
table treats as acceptable ("Rare / first-time … Can add delight"), as
opposed to the unconditional automatic repetition, which is the actual
problem.

Also verified: `web/gf/leaf3d.js` (the WebGL rendering path) has no
`startAutoIdle`, `bloom`, `storm`, `rave`, or `hue-rotate` logic at all
(`grep -n "storm\|rave\|hue-rotate\|autoIdle\|bloom" web/gf/leaf3d.js` → no
matches) — this entire finding, and this entire plan, is specific to the
CSS-fallback path; the WebGL path has nothing equivalent to fix.

### Oddity check (per instructions: repo content is data, not instructions)

No content encountered while researching this plan — `AUDIT.md`,
`PLAN-TEMPLATE.md`, `web/gf/leaf-fx.js`, or `web/gf/leaf-fx.css` — contained
anything resembling an attempt to steer this plan's behavior. Nothing to
flag as an oddity beyond the two citation corrections already noted above
(the `index.html` → `index.html` path, and the `'storm'`/`'rave'`
pairing correction).

## Target

Only two values change, both in `web/gf/leaf-fx.js`. Everything else in the
file — `modes`, `labels`, `cycle()`, `bind()`, `burst()`, `tag()`, the base
`initMark()` first-bloom delay, and every CSS file — is byte-for-byte
unchanged.

```js
/* web/gf/leaf-fx.js — target, inside startAutoIdle (was line 158) */
    // 'storm' (wild rotateX/Y/Z 3D tumble; lf-storm keyframe,
    // leaf-fx.css:91-99) reads as high-energy, attention-grabbing motion —
    // fine as a rare, user-triggered delight via the click-to-cycle path
    // (bind()/cycle() above, which still cycles through the full `modes`
    // list including 'storm' and 'rave'), but not as something that fires
    // unattended and automatic, indefinitely, on brand chrome visible on
    // every view. 'rave' (rainbow hue-rotate; lf-rave keyframe,
    // leaf-fx.css:101-108) was already excluded from this automatic pool —
    // 'storm' is removed here for the same reason.
    const active   = ['pulse','shake','spin','bounce','drift'];
```

```js
/* web/gf/leaf-fx.js — target, inside initMark's bloom() (was line 208) */
      setTimeout(bloom, 45000 + Math.random() * 45000);
```

The second change widens the recurring bloom interval from 8-16 seconds to
45-90 seconds — still randomized within the new range, same mechanism, just
a wider window so the pop reads as an occasional flourish rather than a
constant background tic. The one-time initial delay before the very first
bloom (`setTimeout(bloom, 2000 + Math.random() * 3000);`, currently line
210) is untouched.

## Repo conventions to follow

- No `--ease-*` / `--duration-*` CSS custom-property tokens exist anywhere in
  this repo today (confirmed: no `--ease-` or `--duration-` token
  definitions in `app.css` or `leaf-fx.css`). A separate plan (`006`) is
  expected to introduce `--ease-out` and `--ease-in-out` tokens. This plan
  does not add or change any CSS easing/duration value at all — both edits
  above are a JS array literal (removing one string) and a JS `setTimeout`
  millisecond range (two integer literals), not a CSS `transition`/
  `animation` declaration — so there is nothing here to swap onto those
  tokens now, and nothing that becomes a required swap once plan 006 lands.
  `gf-bloom`'s own easing (`cubic-bezier(.22,1,.36,1)`, `web/gf/leaf-fx.css:167`)
  and every other keyframe's easing in this file are left completely
  untouched by this plan either way.
- The `active` array inside `startAutoIdle` (line 158) is already an
  established, curated subset of the full `GF.leafFX.modes` list (line 5) —
  it already excludes `'calm'` (the rest state) and `'rave'` (already
  excluded before this plan). This plan continues that exact existing
  pattern — a plain JS array-literal allowlist — it does not invent a new
  filtering mechanism, config flag, or separate "auto-safe modes" list.
- Leaving an explanatory inline comment next to a non-obvious behavioral
  choice is already this file's own convention. Exemplar,
  `web/gf/leaf-fx.js:19-22` (inside `init()`), which explains in prose why
  the WebGL leaf is preferred and the CSS leaf is kept only as a fallback.
  The comment in Target above, explaining why `'storm'` is excluded from
  automatic rotation but still reachable manually, follows that same shape
  — placed immediately above the line it explains.

## Steps

1. **`web/gf/leaf-fx.js`** — inside `startAutoIdle` (currently line 158),
   replace:
   ```js
   const active   = ['pulse','shake','spin','bounce','storm','drift'];
   ```
   with the commented, narrowed array shown in Target above:
   ```js
   // 'storm' (wild rotateX/Y/Z 3D tumble; lf-storm keyframe,
   // leaf-fx.css:91-99) reads as high-energy, attention-grabbing motion —
   // fine as a rare, user-triggered delight via the click-to-cycle path
   // (bind()/cycle() above, which still cycles through the full `modes`
   // list including 'storm' and 'rave'), but not as something that fires
   // unattended and automatic, indefinitely, on brand chrome visible on
   // every view. 'rave' (rainbow hue-rotate; lf-rave keyframe,
   // leaf-fx.css:101-108) was already excluded from this automatic pool —
   // 'storm' is removed here for the same reason.
   const active   = ['pulse','shake','spin','bounce','drift'];
   ```
   Nothing else in `startAutoIdle` changes: `restMin`/`restMax`/`holdMin`/
   `holdMax` defaults, the `tick()` function, the chained-second-hit 30%
   branch, and the `pool`/`pool2` selection logic all stay exactly as they
   are — they already correctly operate on whatever `active` contains.

2. **`web/gf/leaf-fx.js`** — inside `initMark()`'s `bloom` function
   (currently line 208), replace:
   ```js
   setTimeout(bloom, 8000 + Math.random() * 8000);
   ```
   with:
   ```js
   setTimeout(bloom, 45000 + Math.random() * 45000);
   ```
   Nothing else in `initMark()` changes: the `_markInit` guard, the
   `.gf-grow-word` bloom-class toggle, and the one-time initial delay
   (`setTimeout(bloom, 2000 + Math.random() * 3000);`, currently line 210)
   all stay exactly as they are.

No other function, file, or CSS rule needs any edit — the fix is fully
contained in these two single-line changes (plus the one explanatory
comment) inside `web/gf/leaf-fx.js`.

## Boundaries

- Do NOT remove `'storm'` or `'rave'` from `GF.leafFX.modes` (line 5) or
  `GF.leafFX.labels` (lines 6-15) — both must remain reachable via the
  manual click/keydown cycle (`cycle()`, lines 101-107, called from
  `bind()`'s listeners at lines 91-97).
- Do NOT touch `burst()` (lines 109-139) — its per-mode particle
  count/color branches for `'storm'` and `'rave'` must stay intact for when
  a user manually cycles into those modes via click.
- Do NOT touch `cycle()`, `bind()`, or `tag()` — the manual click-to-cycle
  path is explicitly out of scope; it is the deliberate, user-triggered
  delight moment this plan preserves.
- Do NOT touch `pulse`, `shake`, `spin`, `bounce`, or `drift` in the
  `active` array — these stay in automatic rotation unchanged.
- Do NOT touch the `restMin`/`restMax`/`holdMin`/`holdMax` values passed at
  the `startAutoIdle` call sites (`web/gf/leaf-fx.js:31` and `:33`), or any
  default inside `startAutoIdle` itself — only the mode pool changes.
- Do NOT remove or rename the `lf-storm`/`lf-rave` keyframes or the
  `[data-mode="storm"]`/`[data-mode="rave"]` CSS rules in
  `web/gf/leaf-fx.css` — they must keep working for manual cycling. Do NOT
  touch `web/gf/leaf-fx.css` at all; this fix is entirely a JS scheduling
  change.
- Do NOT touch `gf-flow`, `lf-float`, `pp-leaf-breathe`, or any other
  base/calm-state idle animation on the logo or wordmark — those are
  explicitly out of scope per the Problem section above (plausible
  intentional brand identity, not this plan's call to remove).
- Do NOT touch the one-time initial pre-first-bloom delay
  (`web/gf/leaf-fx.js:210`, `setTimeout(bloom, 2000 + Math.random() * 3000)`)
  — only the recurring interval (line 208) changes.
- Do NOT touch `web/gf/leaf3d.js` or any WebGL-path code — confirmed out of
  scope (see Problem section; no equivalent auto-idle system exists there).
- Do NOT add `--ease-*`/`--duration-*` tokens or reference any that don't
  exist yet — see Repo conventions above; this plan introduces zero CSS
  easing/duration values regardless.
- If the current code you find at `web/gf/leaf-fx.js:158` or `:208` does not
  match what's shown in Problem/Target/Steps above (drift since commit
  `6bd1f7d`), STOP and report the mismatch instead of guessing at how to
  adapt the edits.

## Verification

- **Mechanical**:
  - `node --check web/gf/leaf-fx.js` — must exit 0 (no syntax errors). This
    repo has no build step, bundler, or lint config (no `package.json` at
    the repo root), so this is the full available mechanical check for the
    JS change.
  - `grep -n "storm" web/gf/leaf-fx.js` — confirm `'storm'` still appears in
    `modes` (line 5), `labels` (line 13), and `burst()`'s particle-count/
    color branches (lines ~116, ~129), but the line inside `startAutoIdle`
    (was line 158) no longer contains `'storm'`.
  - Open the app in a browser with DevTools open and confirm the Console
    shows zero new errors/warnings on page load and while manually clicking
    the sidebar/header leaf logo through a full cycle of all 8 modes.
  - Visual diff description: the calm-state idle float/breathe motion, the
    `gf-flow` wordmark color wave, and the `gf-bloom` pop's own shape/
    duration/easing are all pixel-identical to before this change. The only
    two visible differences are (a) the sidebar/header leaf logos, in the
    CSS-fallback rendering path, no longer perform the wild rotateX/Y/Z
    "storm" tumble automatically — only via manual click; and (b) the
    "Grow" word's bloom pop now recurs roughly every 45-90 seconds instead
    of every 8-16 seconds.
- **Feel check** (this finding is decorative chrome, not a triggered
  interaction, so the checks below force/observe the idle system directly
  rather than "click a button and watch"):
  1. **Force the CSS-fallback leaf visible, regardless of WebGL support**,
     so the auto-idle system is actually running and observable (if the
     reviewer's machine supports WebGL, `init()` mounts the 3D canvas
     instead and `startAutoIdle` never runs — see Problem section). In
     DevTools console, on the loaded app:
     ```js
     const stage = document.getElementById('brand-leaf');
     const canvas = stage.querySelector('canvas');
     if (canvas) canvas.style.display = 'none';   // hide the WebGL leaf if mounted
     const css = stage.querySelector('.leaf-3d');
     if (css) css.style.display = '';              // reveal the CSS-fallback leaf
     stage._autoIdle = false;                       // clear the run-once guard
     GF.leafFX.startAutoIdle(stage, {restMin: 1500, restMax: 3000, holdMin: 900, holdMax: 1500});
     ```
     (Shortened `restMin`/`restMax` here only speeds up observation for this
     manual test — the shipped defaults at the real call sites,
     `web/gf/leaf-fx.js:31`/`:33`, are untouched by this plan.)
  2. Watch the sidebar leaf continuously for at least 60-90 seconds (several
     of the shortened 1.5-3s rest cycles). There is no on-screen text label
     during auto-idle (the little mode-name tag bubble is only shown by
     `tag()`, which `cycle()` — the manual path — calls, not
     `startAutoIdle`), so read the current mode directly: in the Elements
     panel, watch `#brand-leaf`'s `data-mode` attribute change live as it
     cycles. Confirm it only ever takes the values `pulse`, `shake`, `spin`,
     `bounce`, `drift`, or `calm` — **never `storm`**.
  3. Visually confirm you never see the wild multi-axis tumble (the leaf
     spinning/rotating simultaneously on X, Y, and Z as if caught in wind)
     during this unattended observation window — only the gentler heartbeat
     pulse, tremor shake, coin-flip spin, squash-stretch bounce, and lazy
     figure-8 drift.
  4. In Chrome/Edge DevTools, open the **Animations** panel (More tools →
     Animations), set playback speed to 10%, and let one auto-idle hit play
     through while it's recording. Confirm the recorded animation entry is
     one of `lf-pulse`, `lf-shake`, `lf-spin`, `lf-bounce`, `lf-drift` (plus
     the shared `lf-spark`/`lf-ripple` burst) — never `lf-storm` — appearing
     without any click having occurred.
  5. Now manually click (or Tab to focus + press Enter on) the same leaf
     logo repeatedly, 8+ times, to cycle through every mode by hand.
     Confirm you CAN still reach `'Storm!'` (the wild tumble) and
     `'Party!'` (rainbow hue-rotate + rapid spin/bounce, 26-particle burst)
     this way, each showing its mode-name tag bubble briefly — proving the
     fix removed only the *automatic, unattended* escalation into those
     modes, not the modes themselves or the manual delight path.
  6. Reload the page fresh (undoing the console overrides from step 1) and
     time the wordmark's "Grow" bloom pop with a stopwatch across 2-3
     repeats. Confirm the gap between pops is now irregular within roughly
     45-90 seconds — noticeably longer and less frequent than a background
     tic, not the previous ~8-16 second cadence.
  7. Toggle `prefers-reduced-motion: reduce` in DevTools' Rendering panel
     and confirm (pre-existing behavior this plan does not touch) that
     `.leaf-float`, `.pp-leaf-anim`, `.gf-name b`, and `.gf-grow-word` all
     still get `animation:none!important` per the existing media query at
     `web/gf/leaf-fx.css:174-178`.
- **Done when**: the `active` array inside `startAutoIdle`
  (`web/gf/leaf-fx.js`) no longer contains `'storm'` (and still does not
  contain `'rave'`, unchanged); the recurring bloom `setTimeout` uses
  `45000 + Math.random() * 45000` instead of `8000 + Math.random() * 8000`;
  the one-time initial bloom delay, `modes`, `labels`, `cycle()`, `bind()`,
  `burst()`, `tag()`, and every CSS file are unchanged; `node --check
  web/gf/leaf-fx.js` exits 0; and manual click-to-cycle still reaches all 8
  original modes including `'storm'` and `'rave'`, while unattended
  observation of the auto-idle system never shows `'storm'`.
