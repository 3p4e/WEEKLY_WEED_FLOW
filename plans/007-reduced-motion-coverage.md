# 007 — Close the gaps in prefers-reduced-motion coverage across app.css, mass-weed.css, brand.css, leaf-fx.css/js, and views.css

- **Status**: TODO
- **Commit**: 6bd1f7d
- **Severity**: HIGH
- **Category**: 6. Accessibility
- **Estimated scope**: 6 files (`web/gf/app.css`, `web/gf/mass-weed.css`, `web/gf/brand.css`, `web/gf/leaf-fx.css`, `web/gf/leaf-fx.js`, `web/gf/views.css`) — 4 existing `@media (prefers-reduced-motion: reduce)` blocks extended, 1 brand-new block added (`views.css`, which currently has none), ~15 CSS declarations added/changed total, plus a 1-line JS guard added inside `leaf-fx.js`'s `tag()` function. No new `@keyframes` defined, no markup changes, no new dependencies.

## Problem

`prefers-reduced-motion` coverage in this codebase is a token gesture, not a
real policy: it is inconsistent file-to-file, and — inside `app.css` itself —
inconsistent even between two selectors that share the *identical* keyframe.
Five files verified against the live tree below.

### 1. `web/gf/app.css` — the one reduced-motion block covers 3 rules; 6 real movement animations are ungated

Verified current code, `web/gf/app.css:975-984` (the file's only
`prefers-reduced-motion` block):

```css
/* web/gf/app.css:975-984 — current */
.tree-row.s-working .tp-fill,
.card.s-working .card-actions .track > span{
  background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.16) 0,rgba(255,255,255,.16) 6px,transparent 6px,transparent 12px);
  animation:mwStripe 1s linear infinite}

@media (prefers-reduced-motion: reduce){
  .mw-spinner{animation-duration:1.6s}
  .mw-skel{animation:none}
  .tree-row.s-working .tp-fill,.card.s-working .card-actions .track > span{animation:none}
}
```

Verified current code, `web/gf/app.css:223-233` (the keyframes block):

```css
/* web/gf/app.css:223-233 — current */
/* ── Keyframes ── */
@keyframes cardIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes expandIn{from{opacity:0}to{opacity:1}}
@keyframes modalIn{from{opacity:0;transform:scale(.96) translateY(8px)}to{opacity:1;transform:none}}
@keyframes toastIn{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:none}}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulseRec{0%,100%{box-shadow:0 0 0 0 rgba(224,167,62,.45)}50%{box-shadow:0 0 0 7px rgba(224,167,62,0)}}
@keyframes micLive{0%,100%{box-shadow:0 10px 30px rgba(224,167,62,.5)}50%{box-shadow:0 10px 30px rgba(224,167,62,.5),0 0 0 16px rgba(224,167,62,.12)}}
@keyframes asst-bounce{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-4px);opacity:1}}
@keyframes gf-plasma-pulse{0%,100%{opacity:.35}50%{opacity:1}}
@keyframes gf-energy-sweep{0%{left:-30%;opacity:0}15%{opacity:1}85%{opacity:1}100%{left:130%;opacity:0}}
```

Consumers of these keyframes, verified current code:

```css
/* web/gf/app.css:393-398 — current (.card / .card:hover) */
.card{background:var(--glass-bg);backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-border);border-left:4px solid var(--ink-3);border-radius:12px;
  margin-bottom:10px;box-shadow:var(--sh-1);transition:box-shadow .18s,transform .12s,border-left-color .18s;
  opacity:1;animation:cardIn .25s ease forwards;position:relative;overflow:hidden}
.card::before{content:'';position:absolute;inset:0;background:var(--scanlines);pointer-events:none;opacity:.35}
.card:hover{box-shadow:var(--sh-2);transform:translateY(-1px)}
```

```css
/* web/gf/app.css:527 — current (.modal) */
  width:100%;max-width:480px;max-height:90vh;animation:modalIn .2s ease;
```

```css
/* web/gf/app.css:590 — current (.toast) */
  display:flex;align-items:center;gap:10px;animation:toastIn .3s ease;min-width:220px;color:var(--ink)}
```

```css
/* web/gf/app.css:583-584 — current (.spinner) */
.spinner{width:20px;height:20px;border:2.5px solid var(--line);border-top-color:var(--primary);
  border-radius:999px;animation:spin .6s linear infinite}
```

`cardIn` (fires on **every** task-card render — the single highest-frequency
animation in the app), `modalIn` (`scale(.96) translateY(8px)`), `toastIn`
(`translateX(30px)`), and `.card:hover`'s own `translateY(-1px)` all carry
real transform movement and are completely ungated. `spin` is ungated too,
while its near-identical sibling `.mw-spinner` (same file, `mwSpin`
keyframe, `@keyframes mwSpin{to{transform:rotate(360deg)}}` at
`web/gf/app.css:961`, `.mw-spinner{...animation:mwSpin .8s linear
infinite}` at `:963`) gets `animation-duration:1.6s` in the existing block —
an identical rotating-spinner pattern treated two different ways in the same
file.

**Two drifts from the finding as filed, confirmed by repo-wide `grep`, that
change which selectors this plan actually needs to touch:**

- **`asst-bounce` (app.css:231) is dead code inside `app.css` itself.**
  `grep -rn "asst-bounce" web/gf` returns exactly three lines: the keyframe
  definition here at `app.css:231`, an *identical duplicate* keyframe
  definition at `web/gf/views.css:174`, and the only actual consumer,
  `web/gf/views.css:172` (`.asst-typing span{...animation:asst-bounce 1.2s
  infinite}`). No selector anywhere in `app.css` applies `animation:
  asst-bounce`. Adding an `.asst-typing` entry to `app.css`'s block would be
  an inert no-op (nothing in this file selects it) — the real fix belongs in
  `views.css` (Step 6 below), where the keyframe is actually consumed.
- **`gf-energy-sweep` (app.css:233) is dead code everywhere.**
  `grep -rn "gf-energy-sweep" /home/user/WEEKLY_WEED_FLOW` returns exactly
  one line: the keyframe definition itself. No selector in any CSS or JS
  file in the repo references it via `animation:`, and it is never set via
  inline style either. There is nothing to gate — see Boundaries.

### 2. `web/gf/mass-weed.css` — its own reduced-motion block covers 1 of 5 hover-transform rules, and the fix needs `!important` to actually take effect

Verified current code, `web/gf/mass-weed.css:305-307` (the file's only
`prefers-reduced-motion` block):

```css
/* web/gf/mass-weed.css:305-307 — current */
@media (prefers-reduced-motion: reduce){
  :root[data-theme^="mass-weed"] .card:hover{transform:none}
}
```

Four more hover-transform rules in this same file are ungated:

```css
/* web/gf/mass-weed.css:585-593 — current */
:root[data-theme^="mass-weed"] .kcol,
:root[data-theme^="mass-weed"] .kcard,
:root[data-theme^="mass-weed"] .tlcard,
:root[data-theme^="mass-weed"] .wl-row{
  border-radius:0;clip-path:var(--clip-notch);
  box-shadow:var(--sh-1), 0 0 0 1px rgba(var(--accent-rgb),.06)}
:root[data-theme^="mass-weed"] .kcard:hover,
:root[data-theme^="mass-weed"] .team-card:hover{
  box-shadow:var(--sh-2), 0 0 16px rgba(var(--accent-rgb),.22);transform:translateY(-1px)}
```

```css
/* web/gf/mass-weed.css:812-817 — current (second, independent .kcard:hover
   rule — the file's own comment two lines above this, at :810-811, explains
   it "wins by source order at equal specificity without disturbing sibling
   selectors") */
:root[data-theme^="mass-weed"] .kcard{
  box-shadow:var(--sh-1), 0 0 0 1px rgba(var(--accent-rgb),.06),
    inset 3px 0 0 var(--dept-acc, var(--primary))}
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

**Cascade-order finding not in the original brief, discovered while
verifying against the live file — this changes how the fix must be written,
not just what it targets.** The existing reduced-motion block sits at
`mass-weed.css:305-307`, *before* every one of these four rules in the same
file (`:591-593`, `:815-817`, `:1096`, `:1455`). CSS resolves ties between
rules of equal specificity by source order — later wins — regardless of
whether either rule sits inside a `@media` block. `:root[data-theme^=
"mass-weed"] .kcard:hover` and `:root[data-theme^="mass-weed"]
.team-card:hover` have the *exact same selector text*, hence the exact same
specificity, in both the (proposed) reduced-motion entry and the real rules
at `:591-593`/`:815-817`. If the new entries are simply appended inside the
existing early block with no `!important`, the later, unreduced declarations
at `:591`, `:815`, `:1096`, and `:1455` would win the cascade even while
`prefers-reduced-motion: reduce` is active — a fix that silently does
nothing. (The file's own comment at `:810-811` shows its authors are already
relying on exactly this same-specificity/source-order mechanic elsewhere, so
this is a real, load-bearing detail of this file's cascade, not a
theoretical edge case.) The existing single entry at `:306` avoids this problem
by accident: its target, `.card:hover{transform:translateY(-1px)}`, lives in
a *different file* (`app.css:398`) with *lower* specificity (no
`:root[data-theme^="mass-weed"]` prefix), so `:306` wins on specificity
alone, independent of file order. The four new entries this plan adds do not
have that luck — see Steps for the `!important` fix.

### 3. `web/gf/brand.css` — the reduced-motion block gates one selector using a keyframe that's applied by a second, ungated selector too, plus one more fully ungated animation — and the same cascade-order problem applies

Verified current code, `web/gf/brand.css:85-105`:

```css
/* web/gf/brand.css:85-105 — current */
@keyframes pp-leaf-float {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50%      { transform: translateY(-8px) rotate(-1.4deg); }
}
@keyframes pp-leaf-breathe {
  0%, 100% { filter: drop-shadow(0 0 36px rgba(43,232,160,0.42)) drop-shadow(0 0 12px rgba(47,217,217,0.28)) saturate(1.1) brightness(1.03); }
  50%      { filter: drop-shadow(0 0 60px rgba(43,232,160,0.68)) drop-shadow(0 0 20px rgba(47,217,217,0.44)) saturate(1.2) brightness(1.10); }
}
@keyframes pp-aura-pulse {
  0%, 100% { transform: scale(1);    opacity: 0.65; }
  50%      { transform: scale(1.14); opacity: 1; }
}
@keyframes pp-leaf-shimmer {
  0%       { background-position: 220% 0;  opacity: 0; }
  18%      { opacity: 1; }
  46%      { background-position: -120% 0; opacity: 0; }
  100%     { background-position: -120% 0; opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .pp-leaf-anim, .pp-leaf-anim::before, .pp-leaf-anim::after { animation: none; }
}
```

Two more consumers, both ungated:

```css
/* web/gf/brand.css:140-154 — current (.pp-brand-text) */
.pp-brand-text {
  font-family: 'Poppins', 'Comfortaa', system-ui, sans-serif;
  font-weight: 800;
  letter-spacing: -0.015em;
  background: linear-gradient(135deg,
    #2BE8A0 0%,
    #2FD9D9 50%,
    #E0A73E 100%);
  background-size: 200% 200%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: pp-title-shift 8s ease-in-out infinite;
  display: inline-block;
}
```

```css
/* web/gf/brand.css:166-171 — current (.pp-brand-hero .pp-leaf) */
.pp-brand-hero .pp-leaf {
  width: 90px; height: 104px;
  filter: drop-shadow(0 4px 18px rgba(43,232,160,0.40));
  animation: pp-leaf-float 6s ease-in-out infinite;
  margin-bottom: 0.4rem;
}
```

`.pp-brand-hero .pp-leaf` uses the *exact same* `pp-leaf-float` keyframe
(real `translateY(-8px) rotate(-1.4deg)` movement) that `.pp-leaf-anim`
already correctly gets `animation: none` for — it's a second, unrelated
selector (the splash/login hero lockup's leaf, not the multi-layer animated
leaf effect) that the existing gate's selector list simply doesn't reach.
`.pp-brand-text` (`pp-title-shift`, an infinite 8s `background-position`
sweep across the gradient wordmark text) is ungated entirely.

Same cascade-order issue as `mass-weed.css` applies here: the reduced-motion
block sits at `brand.css:103-105`, *before* `.pp-brand-text` (`:140`) and
`.pp-brand-hero .pp-leaf` (`:166`) later in the same file, at equal
specificity to each. (The *existing* entry, `.pp-leaf-anim`, doesn't have
this problem — its own unreduced rule is at `:42-57`, which is *before*
`:103-105`, so plain source order already resolves correctly with no
`!important` needed.) The two new entries need `!important` for the same
reason as `mass-weed.css`'s four — see Steps.

### 4. `web/gf/leaf-fx.css` / `web/gf/leaf-fx.js` — the mode-name tag bubble has neither the CSS gate nor the JS guard its sibling `burst()` effect has

Verified current code, `web/gf/leaf-fx.css:130-178`:

```css
/* web/gf/leaf-fx.css:130-144 — current */
/* ── Mode tag — plasma dark style ── */
.leaf-mode-tag{
  position:absolute;left:50%;bottom:calc(100% + 5px);transform:translateX(-50%);
  font:700 10px/1 'Saira',system-ui,sans-serif;letter-spacing:.02em;color:var(--primary,#2BE8A0);
  background:rgba(11,25,19,.92);border:1px solid rgba(43,232,160,.35);border-radius:999px;
  padding:3px 8px;white-space:nowrap;pointer-events:none;opacity:0;z-index:200;
  box-shadow:0 4px 14px rgba(43,232,160,.18);cursor:default;
}
.leaf-mode-tag.show{animation:lf-tag 1.5s ease forwards}
@keyframes lf-tag{
  0%{opacity:0;transform:translateX(-50%) translateY(4px)}
  16%{opacity:1;transform:translateX(-50%) translateY(0)}
  72%{opacity:1;transform:translateX(-50%) translateY(0)}
  100%{opacity:0;transform:translateX(-50%) translateY(-3px)}
}
```

```css
/* web/gf/leaf-fx.css:174-178 — current */
@media (prefers-reduced-motion:reduce){
  .leaf-float,.leaf-stage .pp-leaf-anim,
  .gf-name b,.gf-grow-word{animation:none!important}
  .leaf-3d{transition:none}
}
```

`.leaf-mode-tag.show` (real `translateY` movement in the `lf-tag` keyframe)
is not in this list. (`.leaf-mode-tag`'s base rule sets `opacity:0`
directly, so `animation:none!important` alone is the correct fix here —
unlike `.modal`/`.toast` in `app.css`, there is no separate opacity-driving
declaration to preserve; the element's only path to `opacity:1` is through
this keyframe.)

Verified current code, `web/gf/leaf-fx.js:101-151` (`cycle()`, `burst()`,
`tag()`):

```js
/* web/gf/leaf-fx.js:101-151 — current */
  cycle(stage) {
    const i    = this.modes.indexOf(stage.dataset.mode || 'calm');
    const next = this.modes[(i + 1) % this.modes.length];
    stage.dataset.mode = next;
    this.burst(stage, next);
    this.tag(stage, next);
  },

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

  tag(stage, mode) {
    let el = stage.querySelector('.leaf-mode-tag');
    if (!el) {
      el = document.createElement('span');
      el.className = 'leaf-mode-tag';
      stage.appendChild(el);
    }
    const lang = (window.GF && GF.state && GF.state.lang) || 'en';
    el.textContent = (this.labels[mode] || {})[lang] || this.labels[mode].en;
    el.classList.remove('show'); void el.offsetWidth; el.classList.add('show');
  },
```

`burst()` (line 110) correctly bails out under reduced motion before
creating any spark/ripple DOM nodes. `tag()`, called immediately after it in
`cycle()` (line 106), has no equivalent guard.

**Design decision — why this plan mirrors `burst()`'s guard exactly, rather
than keeping `tag()`'s text visible under reduced motion:** `leaf-fx.js` is
the click-to-cycle Easter-egg on the sidebar/header leaf logo (see
`plans/005-tame-ambient-brand-motion.md` for confirmation this is decorative
chrome, not a task-completion affordance) — AUDIT.md's category 1 frequency
table files this as "Rare / first-time... Can add delight," and neither the
mode-name bubble nor the spark burst carries information needed to complete
any task. Both are the same category of decorative flourish. Mirroring
`burst()`'s full early-return keeps that treatment consistent — under
reduced motion, clicking the leaf still changes `data-mode` and still cycles
modes, it just no longer creates the spark burst *or* the mode-name bubble.
This makes the CSS-level fix in Step 4 below (`.leaf-mode-tag.show` added to
the existing `animation:none!important` group) a defensive backstop rather
than the primary mechanism — with the JS guard in place, `.show` is never
added under reduced motion in the first place, so the CSS rule never
actually needs to fire; it's included anyway so the element is inert even if
some future code path calls `tag()` without going through this guard.

**Awareness note, not a conflict:** `plans/005-tame-ambient-brand-motion.md`
also edits `web/gf/leaf-fx.js`, at `startAutoIdle` (line 158) and
`initMark()`'s `bloom` function (line 208) — both different functions,
different line ranges, from `tag()` (lines 141-151) edited here. No overlap.

### 5. `web/gf/views.css` — zero `prefers-reduced-motion` blocks exist in this file at all

Verified current code:

```css
/* web/gf/views.css:35-37 — current (.kcard:hover) */
.kcard{background:var(--surface);border:1px solid var(--line);border-radius:11px;padding:12px;cursor:pointer;
  box-shadow:var(--sh-1);transition:transform .12s,box-shadow .12s}
.kcard:hover{transform:translateY(-2px);box-shadow:var(--sh-2)}
```

```css
/* web/gf/views.css:60-62 — current (.tlcard:hover) */
.tlcard{background:var(--surface);border:1px solid var(--line);border-left:3px solid var(--ink-3);border-radius:10px;
  padding:10px;cursor:pointer;box-shadow:var(--sh-1);transition:transform .12s}
.tlcard:hover{transform:translateY(-2px)}
```

```css
/* web/gf/views.css:171-174 — current (.asst-typing, the AI "typing"
   indicator, and its own duplicate copy of the asst-bounce keyframe) */
.asst-typing{display:inline-flex;gap:4px;padding:2px 0}
.asst-typing span{width:6px;height:6px;border-radius:999px;background:var(--ink-3);animation:asst-bounce 1.2s infinite}
.asst-typing span:nth-child(2){animation-delay:.15s}.asst-typing span:nth-child(3){animation-delay:.3s}
@keyframes asst-bounce{0%,60%,100%{transform:translateY(0);opacity:.4}30%{transform:translateY(-4px);opacity:1}}
```

```css
/* web/gf/views.css:230-232 — current (.fac-room:hover) */
.fac-room{position:absolute;border:1.5px solid;border-radius:8px;padding:7px 9px;cursor:pointer;overflow:hidden;
  transition:transform .12s,box-shadow .12s,opacity .2s;display:flex;flex-direction:column;gap:3px}
.fac-room:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(0,0,0,.4);z-index:5}
```

`.asst-typing span`'s `asst-bounce` is the *only place this keyframe is
actually consumed* in the whole app (see drift note in section 1 above) — an
AI-response "typing" indicator that can loop for the entire duration of a
response, potentially many seconds. `.kcard:hover`/`.tlcard:hover`/
`.fac-room:hover` are the base (non-mass-weed-skin) versions of hover lifts
whose mass-weed-skin equivalents this plan is also fixing in Step 2/3.

**Confirmed complete, no additional fix needed:** `.fac-room:hover` has two
more, non-conflicting declarations layered on top by other files —
`web/gf/app.css:991` (`.fac-room:hover{border-color:var(--border-strong);
box-shadow:var(--sh-1)}`) and `web/gf/mass-weed.css:482`
(`:root[data-theme^="mass-weed"] .fac-room:hover{box-shadow:0 0 18px
rgba(var(--accent-rgb),.2)}`) — neither sets `transform`, so this plan's
`views.css` fix (which only touches `transform`) is sufficient across every
skin without needing a matching entry in either of those two files.
Likewise `.team-card` has no `:hover` rule at all in the base skin
(`web/gf/views.css:115-116` sets no hover state) — only `mass-weed.css`
animates it on hover, and that is already covered by Step 2 below.

### Oddities and drift, summarized

No content in `AUDIT.md`, `PLAN-TEMPLATE.md`, or any of the six source files
read while preparing this plan attempted to steer this plan's behavior in
any way — nothing to flag as a prompt-injection-style oddity. The genuine
code-level oddities found (summarized from above, all confirmed by direct
`grep` against the live tree, all accounted for in Steps/Boundaries below):

1. `asst-bounce` is defined identically in two files (`app.css:231` and
   `views.css:174`) but consumed only via `views.css:172`. The `app.css`
   copy is unused dead code; this plan does not remove it (out of scope —
   dead-code cleanup, not a motion finding) and does not add a matching
   entry to `app.css`'s reduced-motion block (would be an inert no-op).
2. `gf-energy-sweep` (`app.css:233`) is unused dead code with zero consumers
   anywhere in the repo. Not gated by this plan — see Boundaries.
3. Two files (`mass-weed.css`, `brand.css`) have an existing
   `prefers-reduced-motion` block positioned *before*, in source order, the
   very rules this plan needs it to override, at equal CSS specificity. The
   four/two new entries in those two files' Steps below use `!important` to
   guarantee they win regardless of position — this is a correctness
   requirement, not a style preference, and is explained per-file above.

## Target

The `AUDIT.md` accessibility category is explicit that reduced motion means
*fewer and gentler* animations, not zero:

```css
@media (prefers-reduced-motion: reduce) {
  .element { animation: fade 0.2s ease; } /* keep opacity/color feedback, drop movement */
}
```

Applied consistently across all five files, this plan's end state is:

- **`app.css`**: `cardIn` reduced to effectively instant (its highest
  frequency, per-render entrance, justifies the most aggressive reduction);
  `modalIn`/`toastIn` keep their opacity fade via the existing `expandIn`
  keyframe but drop their scale/slide; `.card:hover`'s lift is dropped,
  its `box-shadow` feedback kept; `.spinner` is slowed 2x (matching the
  `.mw-spinner` exemplar already in this same block), not stopped, because
  a spinner's motion *is* its "work in progress" signal.
- **`mass-weed.css`**: the four missing hover-lift rules join the existing
  block, transform dropped, `box-shadow`/`filter` feedback kept, all with
  `!important` for the cascade-order reason established in Problem.
- **`brand.css`**: the hero leaf and gradient title text join the existing
  block with full `animation: none` (matching the treatment their sibling
  `.pp-leaf-anim` already gets), `!important` for the same cascade reason.
- **`leaf-fx.css`/`leaf-fx.js`**: the mode-name tag bubble is suppressed the
  same way its sibling spark/ripple burst already is — a CSS gate plus a
  matching JS-level early return in `tag()`.
- **`views.css`**: a brand-new block gates the three base-skin hover lifts
  (transform dropped, feedback kept where present) and slows the assistant
  "typing" indicator 2x, matching the same spinner-slowdown idiom used in
  `app.css`.

## Repo conventions to follow

- Every reduced-motion override lives in a `@media (prefers-reduced-motion:
  reduce){...}` block placed in the *same file* as the rule(s) it overrides.
  Four such blocks already exist, one per file (`app.css:980-984`,
  `mass-weed.css:305-307`, `brand.css:103-105`, `leaf-fx.css:174-178`) — this
  plan extends all four and adds a fifth, brand-new one, to `views.css`
  (which currently has none).
- "Drop the transform, keep the rest" is the established idiom for hover
  feedback — exemplar, the one entry that already exists,
  `mass-weed.css:306`: `:root[data-theme^="mass-weed"]
  .card:hover{transform:none}` overrides *only* `transform`, leaving that
  same rule's `box-shadow:var(--sh-2)` (from the base `app.css:398` rule it
  layers on top of) fully intact as hover feedback. Every hover-transform
  fix in this plan (Steps 1b, 2, 6) follows that exact idiom: override
  `transform` alone, never the sibling `box-shadow`/`filter` declaration in
  the same original rule.
- "Slow the loop 2x, don't stop it" is the established idiom for continuous
  in-progress indicators — exemplar, `app.css:981`:
  `.mw-spinner{animation-duration:1.6s}`, exactly double `.mw-spinner`'s
  unreduced `.8s` duration (`app.css:963`). This is deliberately different
  from the "stop entirely" idiom one line below it, `app.css:982`:
  `.mw-skel{animation:none}` — a shimmer placeholder's mere static presence
  already communicates "loading," so it needs no motion at all, while a
  spinner's rotation *is* the only signal that work is still happening.
  This plan's `.spinner` fix (Step 1e) and `.asst-typing span` fix (Step 6)
  both follow the "slow 2x" idiom, matching `.mw-spinner`, because both are
  continuous "something is happening" indicators, not decorative loops.
- Reuse an existing opacity-only keyframe rather than hand-typing a new
  near-duplicate one — exemplar, `expandIn` already exists at
  `app.css:225` (`@keyframes expandIn{from{opacity:0}to{opacity:1}}`) and is
  already used once, at `app.css:449`. This plan reuses it again for
  `.modal`/`.toast`'s reduced-motion entrance (Step 1c/1d) instead of
  inventing `modalInReduced`/`toastInReduced` keyframes.
- No custom easing/duration CSS token system exists yet in this repo
  (confirmed: no `--ease-*`/`--duration-*` custom property anywhere in
  `web/gf/*.css`). A separate plan (`006`) is expected to introduce
  `--ease-out`/`--ease-in-out` tokens. Every duration/easing value this plan
  writes is a literal, matching what's already on the surrounding rule (e.g.
  `.modal{animation:expandIn .2s ease}` keeps the original `.2s ease` from
  `modalIn`). Once plan 006 lands, the literal `ease` in this plan's
  `.modal`/`.toast` reduced-motion entries (Step 1c/1d) could be swapped for
  `var(--ease-out)` (both are entrances, per AUDIT.md category 2's decision
  order) — but that swap is explicitly not part of this plan and must not be
  made here.

## Steps

### `web/gf/app.css` (1 block extended, 5 new declarations)

1. In the existing block at `app.css:980-984`, insert five new lines after
   the existing `.tree-row.s-working .tp-fill,.card.s-working .card-actions
   .track > span{animation:none}` line and before the block's closing `}`:

   ```css
   /* web/gf/app.css:980-984 — target (full block) */
   @media (prefers-reduced-motion: reduce){
     .mw-spinner{animation-duration:1.6s}
     .mw-skel{animation:none}
     .tree-row.s-working .tp-fill,.card.s-working .card-actions .track > span{animation:none}
     .card{animation-duration:.01ms!important;animation-iteration-count:1!important}
     .card:hover{transform:none}
     .modal{animation:expandIn .2s ease}
     .toast{animation:expandIn .3s ease}
     .spinner{animation-duration:1.2s}
   }
   ```

   a. `.card{animation-duration:.01ms!important;animation-iteration-count:1!important}`
      — `cardIn` reduced to effectively instant. `.card`'s existing
      `animation:cardIn .25s ease forwards` (`:396`) keeps its
      `animation-name`/`animation-timing-function`/`fill-mode`; only the
      duration and iteration-count sub-properties are overridden, so the
      card still lands correctly at `opacity:1;transform:none` — just too
      fast (0.01ms) to perceive any slide, and unable to restart into a
      second loop.
   b. `.card:hover{transform:none}` — drops the `translateY(-1px)` hover
      lift from `app.css:398`, keeps that rule's `box-shadow:var(--sh-2)`.
   c. `.modal{animation:expandIn .2s ease}` — swaps `modalIn`
      (`opacity` + `scale(.96) translateY(8px)`) for the existing
      `expandIn` keyframe (opacity-only), same `.2s ease` from the original
      rule at `:527`.
   d. `.toast{animation:expandIn .3s ease}` — same swap, same idiom, using
      `toastIn`'s original `.3s ease` from `:590`.
   e. `.spinner{animation-duration:1.2s}` — exactly 2x `.spinner`'s
      unreduced `.6s` (`:584`), matching the `.mw-spinner` "slow 2x"
      exemplar one line above in this same block.

   **Do not add an `asst-bounce` or `gf-energy-sweep` entry to this block —
   see the drift notes in Problem section 1 and Boundaries below.**

### `web/gf/mass-weed.css` (1 block extended, 3 new rule entries, `!important` required)

2. In the existing block at `mass-weed.css:305-307`, insert three new rules
   after the existing `:root[data-theme^="mass-weed"]
   .card:hover{transform:none}` line and before the block's closing `}`:

   ```css
   /* web/gf/mass-weed.css:305-307 — target (full block) */
   @media (prefers-reduced-motion: reduce){
     :root[data-theme^="mass-weed"] .card:hover{transform:none}
     :root[data-theme^="mass-weed"] .kcard:hover,
     :root[data-theme^="mass-weed"] .team-card:hover{transform:none!important}
     :root[data-theme^="mass-weed"] .mw-tcard:hover{transform:none!important}
     .mw-skins__dot:hover{transform:none!important}
   }
   ```

   The `:root[data-theme^="mass-weed"] .kcard:hover,
   :root[data-theme^="mass-weed"] .team-card:hover` entry overrides
   `transform` for *both* of the file's separate `.kcard:hover` rule blocks
   (`:591-593` and `:815-817`, per the file's own "wins by source order"
   comment at `:810-811`) with one declaration — `!important` makes source
   order irrelevant here, so it does not matter which of the two later
   blocks would otherwise win. `box-shadow`/`filter` on all four targets are
   left untouched as hover feedback. **`!important` is required on all
   three new entries** — see the cascade-order finding in Problem section 2;
   without it, the later, unreduced declarations at `:591`, `:815`, `:1096`,
   and `:1455` would silently win even while reduced motion is active.

### `web/gf/brand.css` (1 block extended, 2 new declarations, `!important` required)

3. In the existing block at `brand.css:103-105`, insert two new declarations
   after the existing `.pp-leaf-anim, .pp-leaf-anim::before,
   .pp-leaf-anim::after { animation: none; }` line and before the block's
   closing `}`:

   ```css
   /* web/gf/brand.css:103-105 — target (full block) */
   @media (prefers-reduced-motion: reduce) {
     .pp-leaf-anim, .pp-leaf-anim::before, .pp-leaf-anim::after { animation: none; }
     .pp-brand-hero .pp-leaf { animation: none !important; }
     .pp-brand-text { animation: none !important; }
   }
   ```

   `.pp-brand-hero .pp-leaf` gets the same full `animation: none` treatment
   its sibling `.pp-leaf-anim` already gets for the identical `pp-leaf-float`
   keyframe — there is no separate opacity-bearing declaration on this
   selector to preserve, only the float. `.pp-brand-text`'s `pp-title-shift`
   is a purely decorative infinite gradient sweep with no state/comprehension
   value; fully removing it is consistent with `.pp-leaf-anim`'s existing
   treatment. **`!important` is required on both new entries** — see the
   cascade-order finding in Problem section 3; `.pp-brand-text` (`:140`) and
   `.pp-brand-hero .pp-leaf` (`:166`) both appear later in the file, at equal
   specificity, than this block (`:103-105`).

### `web/gf/leaf-fx.css` (1 selector added to an existing group, no `!important` needed)

4. In the existing block at `leaf-fx.css:174-178`, add `.leaf-mode-tag.show`
   to the existing comma-separated selector group:

   ```css
   /* web/gf/leaf-fx.css:174-178 — target (full block) */
   @media (prefers-reduced-motion:reduce){
     .leaf-float,.leaf-stage .pp-leaf-anim,
     .gf-name b,.gf-grow-word,.leaf-mode-tag.show{animation:none!important}
     .leaf-3d{transition:none}
   }
   ```

   No `!important`-cascade concern here: `.leaf-mode-tag.show`'s unreduced
   rule is at `leaf-fx.css:138`, *before* this block at `:174`, so plain
   source order already resolves correctly (and the group already carries
   `!important` regardless). With the JS guard in Step 5 also in place, this
   rule becomes a defensive backstop rather than the primary mechanism (see
   Problem section 4).

### `web/gf/leaf-fx.js` (1 function edited — this is the plan's only JS change)

5. In `tag()` (currently `leaf-fx.js:141-151`), add the same
   `prefers-reduced-motion` guard `burst()` already has (line 110), as the
   very first line of the function body:

   ```js
   /* web/gf/leaf-fx.js:141-151 — target */
   tag(stage, mode) {
     if (window.matchMedia && matchMedia('(prefers-reduced-motion:reduce)').matches) return;
     let el = stage.querySelector('.leaf-mode-tag');
     if (!el) {
       el = document.createElement('span');
       el.className = 'leaf-mode-tag';
       stage.appendChild(el);
     }
     const lang = (window.GF && GF.state && GF.state.lang) || 'en';
     el.textContent = (this.labels[mode] || {})[lang] || this.labels[mode].en;
     el.classList.remove('show'); void el.offsetWidth; el.classList.add('show');
   },
   ```

   Every other line in `tag()` — element creation/reuse, `textContent`
   assignment, the `remove('show'); void el.offsetWidth; add('show')`
   retrigger — is unchanged. Do not touch `burst()`, `cycle()`, `bind()`,
   `startAutoIdle()`, or `initMark()` in this same file.

### `web/gf/views.css` (1 brand-new block, appended at end of file)

6. Append a new block at the very end of `views.css` (currently 503 lines;
   add after the last existing line). Appending at the end guarantees this
   block comes after `.kcard:hover` (`:37`), `.tlcard:hover` (`:62`),
   `.asst-typing span` (`:172`), and `.fac-room:hover` (`:232`) in source
   order, so no `!important` is needed:

   ```css
   /* web/gf/views.css — target, new content appended at end of file */

   /* ── Reduced motion ── */
   @media (prefers-reduced-motion: reduce){
     .kcard:hover{transform:none}
     .tlcard:hover{transform:none}
     .fac-room:hover{transform:none}
     .asst-typing span{animation-duration:2.4s}
   }
   ```

   `.kcard:hover`/`.tlcard:hover`/`.fac-room:hover` drop their
   `translateY` lift, keeping `box-shadow`/`z-index` where present.
   `.asst-typing span{animation-duration:2.4s}` is exactly 2x the unreduced
   `1.2s` (`:172`), matching the same "slow the loop 2x" idiom as
   `.spinner` in `app.css` Step 1e — the typing indicator communicates
   "still generating a response," so it is slowed, not stopped.

## Boundaries

- Do NOT touch `web/gf/mobile.css` or `web/gf/skins.css` — both contain zero
  `animation`/`transform`/`transition` declarations (confirmed clean; verify
  with `grep -n "animation\|transform\|transition" web/gf/mobile.css
  web/gf/skins.css` before assuming otherwise if in doubt).
- Do NOT touch `web/gf/entry.css` — no reduced-motion finding for this file
  is part of this plan's scope.
- Do NOT add an `asst-bounce` entry to `app.css`'s reduced-motion block —
  the keyframe is defined there but consumed by no selector in that file
  (see Problem section 1's drift note). The real fix is the `.asst-typing
  span` entry in `views.css` Step 6.
- Do NOT add a `gf-energy-sweep` entry anywhere — confirmed dead code with
  zero consumers anywhere in the repo (see Problem section 1's drift note).
  There is nothing to verify, so there is nothing to gate.
- Do NOT remove the duplicate `asst-bounce` keyframe definition from either
  `app.css:231` or `views.css:174` — dead-code/duplication cleanup is a
  separate concern from this plan's reduced-motion scope.
- Do NOT touch `.mw-skins__dot.is-active` (`mass-weed.css:1456`) — only
  `:hover` is in scope; the active-state scale is a persistent selection
  indicator, not transient hover motion, and is not part of this plan.
- Do NOT touch `burst()`, `cycle()`, `bind()`, `startAutoIdle()`, or
  `initMark()` in `web/gf/leaf-fx.js` — only `tag()` is edited. (Note:
  `plans/005-tame-ambient-brand-motion.md` separately edits
  `startAutoIdle`/`initMark` in this same file at different line ranges —
  no overlap with this plan's edit to `tag()`.)
- Do NOT add or remove any `@keyframes` body anywhere in this plan — every
  fix either overrides a longhand sub-property (`animation-duration`,
  `animation-iteration-count`, `transform`), swaps to the pre-existing
  `expandIn` keyframe, or sets `animation:none`. No new `@keyframes` is
  introduced.
- Do NOT introduce `var(--ease-out)`/`var(--ease-in-out)` or any other
  `--ease-*`/`--duration-*` token — see Repo conventions above; no such
  token system exists yet in this repo (plan `006` introduces it
  separately), and this plan writes only literal values.
- Do NOT change any declaration in any touched rule other than what Steps
  1-6 specify — `box-shadow`, `filter`, `border-color`, `z-index`, and every
  other sibling declaration on these selectors' *unreduced* rules stay
  byte-for-byte unchanged; only the reduced-motion block additions are new.
- If the current code you find at any file:line cited above does not match
  what's quoted in Problem/Steps (drift since commit `6bd1f7d` beyond what
  is already identified and adapted for in the Problem section), STOP and
  report the mismatch instead of guessing at how to adapt the edit.

## Verification

- **Mechanical**:
  - `node --check web/gf/leaf-fx.js` — must exit 0 (no syntax errors). This
    is the only `.js` file touched by this plan; no other file has a
    mechanical check available (no build step, bundler, or lint config in
    this repo).
  - `grep -n "prefers-reduced-motion" web/gf/app.css web/gf/mass-weed.css
    web/gf/brand.css web/gf/leaf-fx.css web/gf/views.css` — confirm exactly
    one match per file (still one block per file; `views.css` now has one
    where it previously had zero).
  - `grep -n "asst-bounce\|gf-energy-sweep" web/gf/app.css` — confirm both
    keyframe definitions are still present, byte-for-byte unchanged, and
    that neither appears inside the reduced-motion block.
  - `grep -c "matchMedia('(prefers-reduced-motion:reduce)').matches)
    return" web/gf/leaf-fx.js` — confirm the count is 2 (one in `burst()`,
    one newly added in `tag()`).
  - Open the app in a browser with DevTools open, with
    `prefers-reduced-motion: reduce` OFF (default), and confirm the Console
    shows zero new errors/warnings while: loading the board (cards render),
    opening/closing the "Add Task" modal, triggering a toast, hovering a
    kanban card / timeline card / facility room, switching to the Mass Weed
    theme and repeating the hovers there, and clicking the sidebar/header
    leaf logo through a full mode cycle.
  - Visual diff description (motion OFF, i.e. `prefers-reduced-motion` at
    its default `no-preference`): nothing changes. Every declaration this
    plan adds lives inside a `@media (prefers-reduced-motion: reduce)`
    block, so with that media feature not matching, every animation in the
    app looks and behaves exactly as it did before this plan.
- **Feel check** — repeat with `prefers-reduced-motion: reduce` ON. In
  Chrome/Edge DevTools: Cmd/Ctrl+Shift+P → "Show Rendering" → set "Emulate
  CSS media feature prefers-reduced-motion" to "reduce". Reload the app
  after enabling it.
  1. Add a new task (or trigger any board re-render). The new card should
     appear essentially instantly — no visible upward slide, no fade you can
     actually perceive as gradual. In the DevTools **Animations** panel
     (More tools → Animations), set playback speed to 10%, re-trigger a card
     render, and confirm the recorded `.card` animation entry's duration
     reads as a sliver at the very start of the timeline (0.01ms), not a
     quarter-second bar.
  2. Open the "Add Task" modal. It should fade into view with **no**
     scale-up and **no** upward drift — it should look like it simply
     "appears," not "pops" or "grows into place." At 10% playback speed in
     the Animations panel, scrub the recorded `.modal` entry and confirm its
     `transform` track is flat (no keyframe segment moves it) while its
     `opacity` track still ramps from 0 to 1.
  3. Trigger a toast (e.g. save something). It should fade in with **no**
     rightward slide — no sense of it "flying in" from off-screen.
  4. Hover a kanban card (`.kcard`), a timeline card (`.tlcard`), a task
     card (`.card`), and (on the facility board) a room cell (`.fac-room`).
     None should lift/translate on hover. Where the unreduced version also
     changes `box-shadow` (all four do), confirm that shadow change is
     **still visible** on hover — hover feedback is not fully gone, only the
     movement is.
  5. Watch the loading spinner (`.spinner`, e.g. while the AI summary is
     generating) and, separately, send a chat message to trigger the
     assistant's "typing" indicator (`.asst-typing`). Both should still
     visibly move (this is not a "stop everything" fix) but noticeably
     slower than normal — roughly half speed. Confirm in the Animations
     panel that the recorded duration is `1.2s` for `.spinner` (not `.6s`)
     and `2.4s` for `.asst-typing span` (not `1.2s`).
  6. Switch to the Mass Weed theme (console: `GF.setTheme('mass-weed')`, or
     the in-app theme picker). Repeat the hover check on `.kcard`,
     `.team-card`, and the skin-chooser's own kanban-style cards
     (`.mw-tcard`), plus the small color-swatch scheme-picker dots
     (`.mw-skins__dot`, in the app's theme/skin picker). None should
     lift/translate/scale on hover.
  7. Visit the splash/sign-in screen (where `.pp-brand-hero .pp-leaf`
     renders) and any screen where the gradient "GrowFlow"-style title text
     using `.pp-brand-text` appears. The hero leaf should sit still (no
     float/rotate bob) and the gradient title should show a static color
     gradient with no visible sweep/shimmer across it.
  8. Click the sidebar or header leaf logo to cycle through modes. Confirm
     you do **not** see the spark/ripple burst (already correct,
     pre-existing behavior) **and** do **not** see the small mode-name tag
     bubble pop up near the leaf (new behavior from this plan). The leaf
     itself should still visibly change mode (inspect `data-mode` in the
     Elements panel to confirm the click is still registering) — only the
     two decorative flourishes are suppressed.
  9. Turn `prefers-reduced-motion` back OFF and spot-check steps 1-4 again:
     confirm every animation is back to its original full-motion behavior
     (card slides in over ~250ms, modal pops with a scale, toast slides in
     from the right, hovers lift) — proving the fix is purely additive
     inside the media query and does not touch the default experience.
- **Done when**: all six files match their target blocks above exactly;
  `node --check web/gf/leaf-fx.js` exits 0; all four `grep` checks above
  return the expected counts; zero new console errors appear across every
  interaction listed in Mechanical; and all nine feel-check steps pass as
  described, both with `prefers-reduced-motion: reduce` ON (steps 1-8) and
  confirmed unchanged with it OFF (step 9).
