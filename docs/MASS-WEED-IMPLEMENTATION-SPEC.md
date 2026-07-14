# Mass Weed Redesign — Implementation Spec (plan of record)

Derived from the owner's actual mockup (vendored at `design/mass-weed-mockup/`,
45 screens + the full 76 KB `mass-weed.css` component library) compared against
the live app (`web/gf/`). Supersedes the assumption that "Mass Weed = a skin."

## The core finding
The **shipped** `web/gf/mass-weed.css` (~206 lines) is a token map + a thin
re-skin of the app's existing classes. The **mockup** `mass-weed.css` (1382
lines) is a full component library on `.mw-*` classes with its own DOM, and the
screens add `.af-*` / `.ntf` / `.pl-*` components on top. The prior work ported
the palette but **none of the components** (the add-form well, a popup chooser,
the notification list, the log-progress panel). This spec targets the
components. CSS alone will not move the needle — each component needs its CSS
ported **and** the `GF.*` JS that emits the markup changed.

## Scope
- **CORE (in scope):** the only missing core *screen* is **Notifications**;
  everything else maps to an existing `GF` view/modal and needs component/
  behavior upgrades. Core = new-task popup, popup choosers, notifications,
  subtask status control, board/task-detail, and filling out the design-system
  CSS component-by-component.
- **Domain screens (deferred):** harvest, genetics, batch, cure, environment,
  nutrients, packaging, orders, compliance, facility, automations, rule-builder
  — the mockup's OWN `nav.js` keeps these off-rail ("QMS/LIMS territory, future
  reuse"). They imply whole new backend features and are a separate project.

## Build sequence (each ships test → live like every other change)

**1. `GF.chooser` — reusable popup chooser (replaces dropdowns) — effort M**
Files: new `web/gf/chooser.js` (+ `GF.selectField` trigger helper); port
`.mw-menu`/`.mw-menu__item`/`.mw-select` CSS into `mass-weed.css`; `index.html`
script tag. Reuses the existing `GF.openThemePicker` overlay pattern
(`core.js:384`) + `cmdk.js` list/keyboard. Single-select, optional search for
long lists, color swatches (dept), sub-labels (person role), icons (type).
This is the owner's most-repeated request ("every dropdown → a popup").

**2. Redesigned new-task popup (`af-modal.html`) — effort M**
Files: `main.js` (`GF.openAdd`) + `dept-templates.js` (`renderDeptFields`) +
`mass-weed.css` + `index.html`. Wrap the dept fields in the `.af-block`
dept-tinted well with header; set the modal accent (`--mw-acc`) from the chosen
department's color; add a **live task-card preview** that shows how dept-field
values become filled `.mw-attr` chips and tags become outline `.mw-htag` chips;
convert the modal's dept/priority/type/recurrence selects to `GF.chooser` (#1).
Keep the app's superior extras the mockup lacks (responsible-people chips,
recurrence, est-hours, day chips, dictation, dept-scope lock, edit mode).

**3. Notifications — effort M (needs a small backend addition)**
Files: new `web/gf/notifications-view.js` + `notifications` backend table +
`GET /notifications` (unread count + mark-read), events written at
assign/comment/ack/status-change; port `.ntf*` / `.daylabel` / `.mw-badge2`
CSS. Nav item gets an unread badge. This is the "COO/owner sees what happened"
surface — pairs with a shared, append-only, **bilingual** activity feed
(structured events rendered per-language, never pre-composed strings).

**4. Subtask status control — effort S–M (checkbox already shipped in Phase 0)**
Files: `render.js` (`treeRows`), `worklog.js`, `mass-weed.css`. The Phase-0 fix
already added a checkbox + clickable pill and session→working auto-advance.
Remaining: swap the cycle-only pill for an explicit status picker (reuse #1),
add the completion-% control to the worklog modal, adopt `.mw-st--{status}` /
`.mw-stat__fill` styling.

**5. Fill out the design-system CSS — effort L, ongoing, behind 1–4**
Grow `mass-weed.css` with the missing `.mw-*` families as views adopt them
(rail collapse/groups/accent, `.mw-btn` variants, badges/pills, and the utility
set: toast, alert, empty, avatar, accordion, stepper, pager, crumbs, table,
progress, ring, gauge, feed, stat-card). Do it component-by-component — a
big-bang CSS dump is what failed the first time. Keep the app's `GF.t()`/`AL()`
JS i18n; do NOT port the mockup's `html[data-lang]` CSS toggle.

## Already done (Phase 0, live in v52)
Subtask rows got a real completion checkbox + clickable status pill; logging a
work session auto-advances a "Not started" task to "Working on it."

## Reference
Full component-level spec (selectors, field schemas, data shapes) was produced
from the vendored mockup; `design/mass-weed-mockup/` is the source of truth for
every screen and the `.mw-*` CSS.
