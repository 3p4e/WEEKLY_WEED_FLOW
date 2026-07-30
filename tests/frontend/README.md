# web/tests — frontend unit suite

```sh
cd web/tests
npm ci
npm test
```

Runs on `node --test` (node 22) with **jsdom as the only dependency**. No build
step, no test framework, no network, no real timers. CI runs exactly the two
commands above in the `web-unit` job of `.github/workflows/ci.yml`.

## What this suite is testing, and how

`web/index.html` is a no-build app: ~54 classic `<script src>` tags, ~60 files
in `web/gf/`, no `import`/`export` anywhere, everything hanging off a shared
`window.GF` global. There is nothing to `require()`.

So `helpers/gf-window.js` reproduces the actual loading model rather than
working around it: it appends a real `<script>` element per source file to a
jsdom document, in the same order `index.html` does, and lets jsdom execute it.

`<script>` elements specifically, not `window.eval(src)` — core.js declares two
**bare top-level consts** (`AL` and `_FULL`) and documents that later files call
`AL(...)` unqualified because classic scripts share one global lexical scope.
Indirect eval gives each call its own declarative environment, so `const AL`
would vanish and everything loaded after core.js would break in the harness but
not in a browser. Script elements share the realm's global lexical scope exactly
the way the browser does.

The consequence worth stating plainly: **these tests run the real
`web/gf/*.js` files.** No logic is copied into the tests. Delete a line from a
source file and the corresponding test goes red.

### Determinism

* **Frozen clock** — Thursday 2026-07-30 09:15 local, injected as a `Date`
  subclass into the jsdom realm before the sources load. core.js builds
  `GF.calendar.weeks` in a load-time IIFE off `new Date()`, so without a fixed
  clock the week table (and `GF.calendar.todayId`, and `GF.state.selWeek`)
  changes every week.
* **Pinned timezone** — `TZ=Europe/Skopje`, the facility timezone the backend
  hard-codes as `settings.snapshot_tz`. Several helpers are only *correct*
  because they read local date components instead of UTC ones; under `TZ=UTC`
  that distinction is invisible and a regression to `toISOString()` would pass.
  The harness asserts the zone actually resolved, so a runner without tzdata
  fails loudly instead of going green vacuously.
* **No `#toasts` container** in the harness DOM, which makes `GF.toast` (and so
  `GF.denyToast`) return early — the suite is free of real timers without
  stubbing anything.

### The only stub in the suite

`GF.export._download`, replaced by a recorder. It has to be: jsdom implements
`Blob` but not `URL.createObjectURL`, so that function cannot run here at all.
Everything that shapes the exported file — `_csv`, `_json`, and the escaping
inside them — is the real source.

## Coverage, and why these targets

Chosen by risk, not by ease.

| File | Under test | Why |
| --- | --- | --- |
| `export.js` | `_csv`, `_json` | The CSV formula-injection guard is a **security control** with zero coverage. Task titles are operator free text; the guard is what stops one becoming a formula in the recipient's spreadsheet. Pinned in both directions, plus quote doubling and the UTF-8 BOM. |
| `core.js` | `GF.esc`, `GF.kpiTile` | `GF.esc` is the app's **only** output encoder — every view builds markup by concatenation and assigns `.innerHTML`. |
| `core.js` | `GF.can`, `GF.perms`, `GF.ownsTask`, `GF.setStatus`, `GF.cycleStatus`, `GF.toggleDone` | Gate every write button. Hand-maintained 12-row role table whose failure mode is a new role silently dropping to `operator`; the matrix test iterates `Object.keys(GF.PERMS)` so a new role is covered as soon as it is added. |
| `core.js` | `GF.localDateStr`, `GF.todayISO`, `GF.todayDay`, the calendar generator | The local-vs-UTC off-by-one-day trap the source comments warn about in three separate places, all resting on one four-line function. |
| `core.js` | `GF.weekTasks`, `GF.visibleTasks`, `GF.scopedTasks`, `GF.execTasks` | Four selectors differing by one filter each; core.js records that views have already reached for the wrong one. |
| `core.js` | `GF.t`, `AL`, and the label helpers | `gf_lang` is user-writable localStorage and the helpers do not all handle an unknown value the same way. |
| `render.js` | `GF.progress`, `GF.avatar` | `progress` has a genuinely surprising precedence rule (a recorded 0% falls back to the status heuristic). |
| `dept-templates.js` | `collectDeptAttrs`, `attrChips`, `renderDeptFields` | A **data-loss** risk: the result is sent as a whole-object PATCH, so a key it fails to carry over is deleted server-side. |

### Deliberately not covered

* **The view files** (`views.js`, `render.js`'s renderers, and every
  `*-view.js`). They are `GF.WWF.*` functions that fetch through `GF.API` and
  write `.innerHTML` into specific ids from `index.html`, with module-private
  helpers closed over inside IIFEs. Testing them means shimming the whole
  index.html skeleton plus the API — at which point it is a worse version of the
  Playwright suite that already drives them (`web/e2e`).
* **`integrate.js`.** It runs at load, calls the API, and *replaces* several of
  the functions tested here. Its logic is inseparable from live HTTP.
* **`leaf3d.js` / `leaf-fx.js` / `voice.js`.** WebGL, canvas and the Web Speech
  API — none of which jsdom implements.

A small honest suite beats a broad fake one; the table above is the whole of it.

## Pinned-behaviour notes

Some assertions record what the code *does*, flagged as such in a comment
rather than presented as desirable:

* `weekNum` is `ceil((dayOfYear + 1) / 7)` against the week's own January 1 —
  **not** the ISO-8601 week number (Mon 2026-07-27 is ISO W31, labelled W30
  here). It reaches users, in the export filename.
* `GF.statusLabel` / `GF.prLabel` return `undefined` for any `gf_lang` outside
  `en`/`mk`, while `GF.t`, `GF.roleLabel`, `GF.depName` and `GF.dayLabel` all
  fall back to English by three different mechanisms.
* `export.js`'s own `esc()` is `String(s || '')`, so a literal `0` exports as an
  empty cell — the opposite choice from `GF.esc`, which uses `s == null`.
  Currently unreachable, so a latent trap rather than a live bug.
* `status`, `pr` and `archived` are interpolated into the CSV **unquoted and
  unescaped**, bypassing `esc()` entirely.
* Number-typed template fields carry `min="0" step="1"` in the markup, and
  nothing on the save path calls `checkValidity()` — a negative or fractional
  value is passed straight through.

## Adding a test

```js
const { loadGF } = require('./helpers/gf-window.js');

const h = loadGF({
  files: ['data.js', 'core.js', 'render.js'],  // index.html order
  storage: { gf_lang: 'mk' },   // seeded BEFORE load; core.js reads it at load time
  now: '2027-01-14T09:15:00+01:00',            // optional clock override
});
// h.GF     — window.GF after the sources ran
// h.window — the jsdom window (document, localStorage, window.Date)
// h.global('AL("en","mk")') — evaluate in the sources' own global scope
h.close();
```

If a source file throws while loading, the harness raises instead of handing
back a half-built `GF` — a file that cannot load is a red test, not a silent
skip.
