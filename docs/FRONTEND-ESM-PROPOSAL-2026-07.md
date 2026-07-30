# Frontend module migration — scoped proposal (2026-07-30)

**Status: proposal, not accepted.** Nothing here has been done. Written so the
decision can be made against real numbers instead of an impression, after the
review paired "migrate the frontend to ESM" with "add a unit suite" and only the
suite was built.

## Why this is not a formality

The review's framing was that ESM is tidier. That is the weakest argument for it.
The real argument is that the current loading model produces **silent** bugs, and
this session produced three concrete instances rather than hypotheses.

### The current shape

`web/index.html` loads **54** classic `<script src>` tags. `web/gf/` holds ~60
files sharing one `window.GF` global, with **zero** `import`/`export`. There is
no dependency graph: the only statement of what depends on what is the order of
the tags, and nothing verifies it.

### Evidence, all from this session

1. **A dead duplicate that was also wrong.** `web/gf/export.js` used to define
   `GF.rollover`, and `integrate.js` — loaded later — replaced it at startup
   every time. The dead copy mutated `t.weekId` in memory and called the
   abandoned client-side store, so it persisted *nothing*. Reordering two script
   tags would have silently restored a rollover that appears to work and saves
   no data. That is recorded in a comment in `export.js` because someone already
   hit it.

2. **Load-time side effects make units untestable in isolation.**
   `integrate.js` ends with a bare `GF.WWF.install()`, so *merely loading the
   file executes it*, and `install()` assigns onto `GF.voice`, which `voice.js`
   owns. Unit-testing one pure function in that file requires either loading the
   other ~50 scripts or declaring the globals it happens to touch on the way up
   (`tests/frontend/dates-calendar.test.js` does the latter, via `PRE_INTEGRATE`,
   and says so). With modules this is an `import`, not a shim.

3. **The same bug in two files at once.** The Sunday week-selection defect fixed
   in `9afda0f` existed independently in `core.js` *and* `integrate.js`, because
   the week-boundary rule is expressed twice with no shared owner. Three further
   call sites compared `d <= w.end` against the same broken boundary. A module
   with one exported helper cannot drift from itself.

## Why not a big-bang conversion

Converting all 54 tags at once is the wrong shape of risk for this app:

- A missed global is a **runtime** failure in production, not a build error.
  There is no compiler and no type checker to catch it.
- The only end-to-end net is the Playwright suite, which covers primary flows,
  not all 115 `GF.*` entry points.
- It is a GxP-adjacent production app. A frontend that half-loads can show a
  stale or empty week to someone recording a batch operation.
- It cannot be verified except by deploying, and it would land as one
  undiffable change across ~60 files.

## Proposed path — strangler, not rewrite

Each step is independently deployable and independently revertible. Stop at any
point and the app is in a consistent state.

**Step 0 — cover the seams first (partly done).**
`tests/frontend/` now has 104 tests over the real sources. Before converting a
file, its exported behaviour must be pinned there, both directions (neutralise
the guard → red; restore → green), which is already this repo's standing rule.

**Step 1 — extract pure helpers into real modules.**
Date/week logic, formatters, permission predicates, escaping. These have no DOM
or load-order dependencies. Ship as `web/gf/lib/*.mjs`, imported by a single
`<script type="module">`, while the existing files keep their `GF.*` names as
thin re-exports so no caller changes yet. **The Sunday bug lives exactly here** —
this step is what makes it unrepeatable.

**Step 2 — remove the assignment-order hazards.**
Audit for any `GF.x` assigned in more than one file (the `export.js` /
`integrate.js` class). Each one is either a real duplicate to delete or a real
override to make explicit. This step is worth doing **even if the migration
stops here** — it is pure risk reduction and needs no module system.

**Step 3 — split load-time side effects from definitions.**
`install()`-style calls move out of file scope into one explicit bootstrap. This
is what makes the remaining files testable without shims, and it is the step
that pays for the suite.

**Step 4 — views last, one at a time.**
Each view is one tag removed and one `import` added, deployable on its own.

## Cost and risk

- Steps 1–3 are the majority of the benefit and a minority of the risk; they
  touch shared logic, not rendering.
- Step 4 is most of the work and most of the residual risk, and it is the part
  that can be deferred indefinitely without leaving the codebase inconsistent.
- No build step is introduced at any point. Native ESM in the browser keeps the
  no-build property, which is worth preserving — it is why a frontend deploy here
  is a `COPY` and a container restart.
- Every step needs a `sw.js` VERSION bump or clients serve the cached shell back.
  See the 2026-07-30 entry in `DEPLOY.md`.

## Recommendation

Do **Step 2 now**, on its own: it removes a class of silent bug, requires no
module system, and is cheap. Treat Steps 1 and 3 as the actual proposal, worth
scheduling. Treat Step 4 as optional and not currently justified.

Do not do Step 4 first, and do not do all four as one change.
