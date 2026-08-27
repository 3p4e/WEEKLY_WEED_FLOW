# Animation audit — implementation plans

15 plans, each self-contained per [`PLAN-TEMPLATE.md`](../.claude/skills/improve-animations/PLAN-TEMPLATE.md). Every plan was written to be executable standalone (with drift checks against the codebase), but a few interact with each other in ways worth knowing before you start. See "Dependencies & rationale" below the table.

| # | Title | Severity | Status |
|---|-------|----------|--------|
| 006 | Introduce `--ease-out`/`--ease-in-out` tokens and consolidate hand-typed motion curves | MEDIUM | TODO |
| 002 | Give the shared overlay/modal component (and card-body) a real exit animation | HIGH | TODO |
| 001 | Guard task-card entrance animation against re-render replay | HIGH | TODO |
| 013 | Give task completion a real, deliberate feedback flash | HIGH | TODO |
| 003 | Anchor the popup-chooser scale animation to its trigger, not viewport center | HIGH | TODO |
| 004 | Bound the infinite alert-pulse and progress-sheen loops to a finite, self-settling count | HIGH | TODO |
| 007 | Close the gaps in prefers-reduced-motion coverage across app.css, mass-weed.css, brand.css, leaf-fx.css/js, and views.css | HIGH | TODO |
| 010 | Replace `transition: all` (and bare, property-less `transition:`) with explicit property lists | MEDIUM | TODO |
| 009 | Give pressable elements tactile `:active` press feedback | MEDIUM | TODO |
| 008 | Gate transform-based `:hover` rules behind `@media (hover: hover) and (pointer: fine)` | MEDIUM | TODO |
| 005 | Remove 'storm' from the sidebar/header leaf's automatic idle-mode rotation; widen the wordmark bloom interval | MEDIUM | TODO |
| 014 | Sync the telemetry panel's reveal transition with its chevron rotation | MEDIUM | TODO |
| 011 | Convert layout-triggering `width`/`height` transitions to `transform` | LOW | TODO |
| 012 | Give the card-body reveal a translateY entrance instead of a pure fade | LOW | TODO |
| 015 | Give the Inbox/Activity tab switch a fade+rise entrance instead of an instant teleport | LOW | TODO |

## Dependencies & rationale

**006 goes first, but blocks nothing.** Every one of the other 14 plans explicitly documents that no `--ease-*`/`--duration-*` token exists yet and writes literal `cubic-bezier(...)` values on purpose — several of them (009, 012, 015) go further and state that even if 006 has *already landed* by the time they execute, they must still not swap in `var(--ease-out)`, because that swap is out of scope for them. So 006 doesn't gate anything mechanically. It's recommended early purely so that a later cleanup pass has the tokens available sooner rather than later — every plan that hand-types `cubic-bezier(0.23, 1, 0.32, 1)` or `cubic-bezier(0.77, 0, 0.175, 1)` is a candidate to revisit once the tokens exist. 006 also pre-emptively carves out `.tp-fill`/`.mw-stat__fill`/`.wl-fill` from its own scope ("reserved for plan 011... changing their easing now would be redundant with, and could conflict with, that rework"), so there's no clash with 011 regardless of order.

**001, 002, and 013 should be implemented by the same person in the same sitting.** All three edit `web/gf/render.js`'s `card(t)` function, and two of them land on the *exact same lines*: 001's Step 3 and 013's Step 1 both rewrite the collapsed return (`render.js:305`) and expanded return (`render.js:358`), and 002's Step 7 inserts a wrapper `<div>` immediately adjacent to that same expanded-return line (329–357). They're functionally independent — each plan's Boundaries section describes drift-detection language that lets it be applied alone — but applying them as three separate, uncoordinated diffs against the same few lines is exactly the kind of thing that produces avoidable merge conflicts. Do 002 → 001 → 013 in one pass. (002 first because 012 hard-depends on it — see below — and because doing it first gives 001/013 a stable base to layer onto.)

**012 hard-depends on 002.** 012's own Boundaries are explicit: "If plan 002 has not yet executed... **STOP**. This plan's Target is written against plan 002's post-landing `.card-body-inner` rule, which does not exist until plan 002 has been applied." This is a real blocker, not a soft preference — 012 has nothing to edit until 002's `.card-body-inner` wrapper exists.

**014 reuses 002's technique but does not depend on it.** 014's Boundaries state plainly: "this plan is independent of plan 002 and does not require it to have run first; it only reuses plan 002's *technique* as a pattern, on a different component." Worth sequencing after 002 anyway so the implementer has a finished, working `grid-template-rows: 0fr → 1fr` example to mirror, but nothing will break if 014 lands first.

**004 is independent of 001 despite the surface resemblance** (both concern animations that keep re-triggering). 004 addresses this directly: "does it matter today or only after plan 001 lands? It matters **today, independently of plan 001**." No ordering constraint between them.

**007 should follow 002 — not because 007 needs it, but because 002 changes the ground 007's `.modal` fix stands on.** 007's Step 1c adds a reduced-motion entry, `.modal{animation:expandIn .2s ease}`, written against `.modal`'s *current* mechanism (`animation:modalIn .2s ease`). Plan 002 deletes `@keyframes modalIn` entirely and rewrites `.modal` to use `transition`/`opacity`/`visibility` instead of `animation`. If 007 runs after 002, its own drift-detection boundary ("If the current code you find... does not match what's quoted... STOP and report") will correctly halt on that one step and force a deliberate re-derivation of `.modal`'s reduced-motion rule against the new mechanism — safer than the reverse order, where 007's rule would land cleanly, then go silently stale (referencing a swapped-out keyframe idiom) once 002 lands later, since 002's Boundaries explicitly decline to touch reduced-motion coverage ("that gap is pre-existing... a separate, adjacent audit finding. Do not add coverage for it here"). Either way, `.modal`'s reduced-motion rule needs a manual check after both plans have landed — flag it in review.

**010 should land before 009, and 009's `.mw-chip` step needs a manual patch when it does.** 009 adds `.mw-chip:active{transform:scale(.97)}` and explicitly states it "rides along on the existing (already in-budget, 130ms) transition" at `mass-weed.css:1149`, adding: "no plan in this repo currently addresses [`.mw-chip`'s `transition:all`]." That statement is incorrect against the final set of 15 — plan 010's Step 7 targets that exact line, narrowing `transition:all .13s ease` to `transition:color .13s ease, background .13s ease, box-shadow .13s ease`, which **drops `transform` from the transitioned properties**. Landed in either order, the combination silently breaks 009's press feedback (the `scale(.97)` would snap instantly instead of easing) unless someone adds `transform .13s ease` to 010's explicit list. Doing 010 first is the safer order: when 009's implementer reaches the `.mw-chip` step, the quoted "current" code (`transition:all`) will no longer match what's in the file, tripping 009's own drift-detection boundary and forcing a conscious fix rather than a silent regression. Flag this explicitly for whoever implements 009.

**005 and 007 touch the same file with no real conflict.** 007 calls this out itself as an "awareness note, not a conflict" — 005 edits `startAutoIdle`/`initMark` in `web/gf/leaf-fx.js`, 007 edits `tag()` in the same file, and the two don't overlap. No ordering requirement.

**015 deliberately does not adopt 001's or 013's patterns, on purpose.** 015 references both: it explicitly declines to add a replay-guard like 001's for `cardIn` ("this view's re-render frequency does not warrant one"), and separately reuses the "modifier class appended in JS, cleaned up via `animationend`" shape from 013's `.card--just-completed` flash as its structural precedent. Neither is a dependency — 015 works whether or not 001/013 have landed — but implementing it after that pair gives the author a concrete, working exemplar of the pattern it's borrowing from.

**003, 008, and 011 are fully self-contained.** 003 touches only `web/gf/chooser.js`; 008 only wraps existing `:hover` rules in a media query without changing any values; 011 explicitly reserves the one file (`entry.css`) it evaluated and declined to touch. None has an inbound or outbound dependency on any other plan in this set.

---

All 15 plans were written against commit `6bd1f7d`. Any plan whose cited file:line locations or quoted "current" code no longer match the tree (drift since that commit — including drift introduced by landing one of these other 14 plans) should be re-verified before execution; every plan's own Boundaries section says to stop and report rather than improvise when that happens.
