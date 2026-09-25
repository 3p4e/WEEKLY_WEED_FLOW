# Owner's Weekly Management Report — Requirements, Gap Analysis & Implementation Design

**Source:** email from the company owner (reply to the weekly management update).
**Purpose of this doc:** (1) structure the owner's requests into trackable
requirements, (2) assess how far the current app (`WWF` / GrowFlow) already meets
them, (3) design how to implement, source and render every request inside the app.

> **One-line conclusion.** The owner is asking for a **production-state report**
> (how many plants are where, at what flowering week, expected yield, equipment
> health, inventory, and a forward forecast). WWF today is a **weekly task
> tracker** — it reports on *work items* (status, hours, blockers), not on the
> *operational state of the facility*. The gap is **categorical, not cosmetic**:
> it cannot be closed by rearranging task data. It requires a small
> **operational-data layer** (genetics, rooms, plant groups, harvest batches,
> equipment, forecast) captured weekly, plus a new structured report that renders
> the owner's six sections. This document specifies that layer and a phased build.

---

## 1. What the app does today (baseline)

Grounded in the current code, not the marketing copy:

| Area | Reality |
|---|---|
| Domain | **Task tracking.** Create/assign/schedule/track tasks by department, person, week, status, priority. |
| Weekly report (`backend/app/api/reports.py`, `web/gf/report-view.js`) | Fri→Thu window. Renders **task** metrics only: totals by status, hours-by-person (regular/overtime/night/weekend), overdue tasks, department completion %, task-type chips, and an AI prose summary. |
| "Dashboard — production overview" (`web/gf/views.js` `dash()`) | Despite the label, it is **task counts** by status/department/person + a blocker list. No production quantities. |
| Coordination view | A **handoff pipeline** `clone→veg→flower→prod→qc→qa→whout` — mirrors the cultivation flow, but each node is a *task* in a handoff state, not a plant/batch quantity. |
| Task data model (`schema.tasks.sql`) | `title, description, status, priority, task_type(capa/sop/validation/document/lab/meeting/admin/other), department(_id), week, days[], tags[], due_date, estimated/actual_hours, outcome`. **No columns for plant counts, genetics, room state, yield, inventory, or equipment.** |
| Scope guard (`docs/SCOPE.md`) | WWF is explicitly a **non-GMP planning tool**, *not* a validated GxP/Part-11 system and *not* the QMS. Authoritative CAPA/SOP/validation/deviation records live in the QMS; WWF may only hold **pointers/planning status**. |

**Implication:** the department taxonomy and handoff pipeline already speak the
language of cultivation, and tasks *about* the owner's topics (e.g. "QA-release
Flower Room 3", "replace HVAC filters") can and do exist. But there is **no
quantitative production state** anywhere in the schema, so none of the owner's
numeric requests can be answered from current data.

---

## 2. The owner's requests, structured

Six sections, normalised into line items with stable IDs. Each carries a
**data-nature** tag that drives the design:

- **STATE** = a quantity/status describing the facility right now (needs a new data model).
- **WORK** = an activity/action (expressible as WWF tasks today).
- **QMS** = an authoritative GxP record that must stay in the QMS; WWF may show a *pointer/rollup* only.
- **DERIVED** = computed from STATE data (e.g. forecast, utilisation).

### A. Cultivation Status
| ID | Request | Nature |
|----|---------|--------|
| A1 | Number of mother plants **by genetics** | STATE |
| A2 | Number of clones **by genetics** | STATE |
| A3 | Plants in propagation | STATE |
| A4 | Plants in vegetative rooms | STATE |
| A5 | Plants in **each** flowering room | STATE |
| A6 | Flowering week per room (Week 1 → harvest) | STATE |
| A7 | Expected harvest **date** per flowering room | DERIVED (A6 + strain flower length) |
| A8 | Expected harvest **yield (kg)** per room | DERIVED / STATE (est.) |
| A9 | Room utilisation + overall facility utilisation | DERIVED (A3–A5 ÷ capacity) |

### B. Production Overview
| ID | Request | Nature |
|----|---------|--------|
| B1 | Weekly harvest completed (kg) | STATE |
| B2 | Product currently drying | STATE |
| B3 | Product currently curing | STATE |
| B4 | Product awaiting QC release | STATE (+ QMS pointer) |
| B5 | Product released for sale | STATE (+ QMS pointer) |
| B6 | Current inventory **by batch** | STATE |

### C. Transition Plan (new genetics)
| ID | Request | Nature |
|----|---------|--------|
| C1 | Progress against new-genetics implementation | WORK |
| C2 | Quarantine activities progress | WORK |
| C3 | Cleaning & sanitation status | WORK |
| C4 | QA-release status **per room** | WORK + QMS pointer |
| C5 | Outstanding actions + target completion dates | WORK |

### D. Technical Status (critical infrastructure)
| ID | Request | Nature |
|----|---------|--------|
| D1 | HVAC performance | STATE (equipment) |
| D2 | Compressors | STATE |
| D3 | Drying-room environmental controls | STATE |
| D4 | Dehumidifiers | STATE |
| D5 | Filter replacements | STATE + WORK |
| D6 | Valve installation | WORK |
| D7 | Any other equipment impacting production / GMP | STATE + WORK |
| D8 | Issues affecting capacity/GMP **highlighted + expected resolution date** | DERIVED (flag) |

### E. Quality & GMP
| ID | Request | Nature |
|----|---------|--------|
| E1 | Visual inspections | WORK (+ QMS pointer) |
| E2 | Laboratory testing | QMS pointer |
| E3 | Environmental monitoring | STATE + QMS pointer |
| E4 | Deviations & CAPAs | QMS pointer (rollup) |
| E5 | SOP revisions | QMS pointer / WORK |
| E6 | Validation activities | QMS pointer |
| E7 | Progress towards GMP readiness | DERIVED (rollup) |

### F. Production Forecast (rolling)
| ID | Request | Nature |
|----|---------|--------|
| F1 | Expected weekly harvests | DERIVED |
| F2 | Expected weekly production (kg) | DERIVED |
| F3 | Expected room availability | DERIVED |
| F4 | Anticipated capacity reduction | DERIVED |
| F5 | Recovery timeline back to full production | DERIVED |

**Cross-cutting asks (not a section but stated explicitly):**
- G1 — Present the weekly update in a **consistent structured format** every week.
- G2 — **Highlight** any technical/GMP issue with an **expected resolution date**.
- G3 — Frame everything around **protecting production capacity & cash flow** during the transition.
- G4 — Deliverable also includes a **revised production transition plan** document.

---

## 3. Adherence check — does the app meet these today?

Legend: ✅ present · 🟡 partial (only as free-text tasks, not structured/quantified) · ❌ absent.

| ID | Item | Status | What exists today |
|----|------|--------|-------------------|
| A1–A2 | Mothers / clones by genetics | ❌ | No genetics entity; no plant counts. |
| A3–A5 | Plants in prop / veg / flower rooms | ❌ | No room or plant-group entity. |
| A6 | Flowering week per room | ❌ | Not modelled. |
| A7 | Expected harvest date | 🟡 | A task can carry a `due_date`, but nothing derives it from flowering week. |
| A8 | Expected yield (kg) | ❌ | No yield field anywhere. |
| A9 | Utilisation | ❌ | No capacity reference to divide by. |
| B1 | Weekly harvest kg | ❌ | Not captured. |
| B2–B3 | Drying / curing | 🟡 | Only if someone opens a task "drying batch X"; no stage tracking. |
| B4–B5 | Awaiting QC / released | 🟡 | Handoff pipeline has `qc`/`qa`/`whout` *nodes*, but they track task handoff state, not product kg. |
| B6 | Inventory by batch | ❌ | No inventory/batch entity (only free-text `tags`/`reference_code` on tasks). |
| C1–C5 | Transition plan items | 🟡 | Fully expressible as **tasks** with owners, due dates, status — this is WWF's strength. Missing: a *structured* per-room transition board and target-date rollup. |
| D1–D7 | Equipment status | 🟡 | Maintenance-department tasks can reference equipment; no **asset register** with health/status. |
| D8 | Issue highlight + resolution date | 🟡 | `stuck` status + `blocker_reason` + `due_date` exist; not surfaced as an infra risk list. |
| E1 | Visual inspections | 🟡 | Trackable as tasks (there is even a `task_type` culture around inspections). |
| E2,E4,E5,E6 | Lab / deviations / CAPA / SOP / validation | 🟡 | `task_type` enum already has `capa/sop/validation/lab`. But per `docs/SCOPE.md` these are **pointers**, not records — WWF must roll them up, never claim authority. |
| E3 | Environmental monitoring | ❌ | No env-data capture. |
| E7 | GMP-readiness progress | ❌ | No rollup metric. |
| F1–F5 | Forecast | ❌ | No forward projection of any kind. |
| G1 | Consistent structured format | 🟡 | A weekly report exists and is consistent — but its **sections are task-centric**, not the owner's six sections. |
| G2 | Highlight + resolution date | 🟡 | Overdue list exists; no infra/GMP risk band. |

**Verdict:** roughly **60–70% of the line items (all STATE/DERIVED)** have **no
data home** in the app today. The **WORK-natured items (Section C, parts of D/E)**
are already achievable as tasks and need mostly *presentation*, not new plumbing.
The report the owner wants is therefore **~⅓ re-presentation of existing task
data** and **~⅔ new operational-data capture + rendering**.

---

## 4. Root cause: two different data domains

WWF answers *"what work is being done, by whom, in what state?"*
The owner is asking *"what is the physical state of the crop and the plant, and
what will it produce over the coming weeks?"*

Tasks are **verbs**; the owner wants **nouns with quantities** (plants, rooms,
batches, kilograms, machines) plus **time projection**. You cannot pivot a task
list into a plant census. The fix is to add a thin **operational-state layer**
that the weekly report reads from — while keeping WWF's non-GMP planning scope
intact (Section 6).

---

## 5. Proposed data model (the missing layer)

Small, additive tables in the existing tasks database. All org-scoped + RLS like
the current schema, all soft-delete + audit-trigger by reusing `app.fn_audit_row`.

```
genetics            (id, org_id, name, code, flower_days_est, yield_g_per_plant_est, notes)
rooms               (id, org_id, name, kind[prop|veg|flower|mother|dry|cure|store],
                     capacity_plants, capacity_note, active)
plant_groups        (id, org_id, genetics_id, room_id, stage[mother|clone|prop|veg|flower],
                     plant_count, flower_week, started_on, expected_harvest_on,
                     expected_yield_kg, snapshot_week, notes)      -- one row per genetics×room×week
harvest_batches     (id, org_id, code, genetics_id, room_id, harvest_date,
                     wet_kg, stage[drying|curing|awaiting_qc|released|rejected],
                     dry_kg, qms_ref, released_kg, notes)
equipment           (id, org_id, name, category[hvac|compressor|dehumidifier|
                     dry_ctrl|filter|valve|other], location, status[ok|degraded|down|planned],
                     issue_note, expected_fix_on, impacts_capacity bool, impacts_gmp bool)
env_readings        (id, org_id, room_id, taken_at, temp_c, rh_pct, co2_ppm, note)   -- optional / phase 2
forecast_snapshots  (id, org_id, week_start, payload jsonb)        -- materialised rolling forecast
gmp_rollup          (id, org_id, week_start, open_deviations, open_capa, overdue_capa,
                     sop_in_revision, validations_open, readiness_pct, qms_ref, note)
```

Notes:
- `plant_groups` is a **weekly snapshot** table (one set of rows per report week),
  so history is preserved and the report/forecast read a specific `snapshot_week`.
  A1–A6 are direct `GROUP BY genetics/room/stage` queries over it.
- A7 `expected_harvest_on` = `started_flower_date + genetics.flower_days_est`
  (auto-filled, editable). A8 defaults to `plant_count × genetics.yield_g_per_plant_est`
  (editable override). A9 utilisation = `Σ plant_count in room ÷ rooms.capacity_plants`.
- `harvest_batches.stage` drives B1–B6 directly; B4/B5 also carry a `qms_ref`.
- `equipment` covers D1–D8; `impacts_capacity/impacts_gmp` + `expected_fix_on`
  power the **highlight band** (G2).
- `gmp_rollup` is the **pointer/summary** for Section E — numbers + a QMS
  reference, explicitly *not* the authoritative records (Section 6).
- `forecast_snapshots.payload` caches the computed F1–F5 so the report is fast
  and the projection is reproducible week-to-week.

---

## 6. Scope boundary (must-read before building)

`docs/SCOPE.md` is binding: WWF is **not** the QMS and must not present itself as
holding validated GxP records. Map that onto the owner's asks:

- **Fits WWF (own system of record):** Cultivation Status (A), Production Overview
  quantities (B1–B3, B6), Technical Status (D), Production Forecast (F), Transition
  Plan work items (C). These are **management/operational planning** figures — the
  owner wants them for planning and cash-flow decisions, which is exactly WWF's
  remit.
- **Pointer/rollup only (authority stays in QMS):** QA-release status (B4/B5, C4),
  Deviations & CAPAs (E4), SOP revisions (E5), Validation (E6), Lab testing (E2),
  GMP-readiness (E7). WWF shows a **summarised count + a QMS reference + a "not an
  official record" label** (the same disclaimer pattern already used for AI pins in
  `report-view.js`). It never becomes the record.

This keeps the owner fully informed **and** keeps WWF on the right side of its own
scope decision. Call this out to the owner explicitly so the report's authority is
never misread.

---

## 7. Report design — the six sections

Rebuild the weekly report as the owner's structure. Keep the existing task
section (it is genuinely useful) but demote it below the new operational sections,
or make the report a **tabbed document**: `Overview · Cultivation · Production ·
Transition · Technical · Quality · Forecast`.

Each section, its source, and its rendering:

1. **Cultivation Status** — a genetics×room matrix table + per-room cards showing
   stage, flowering week (a Week 1→harvest progress pill), expected harvest date,
   expected yield, and a utilisation bar per room + a facility-total gauge.
   *Source:* `plant_groups` for the week, joined to `genetics`/`rooms`.
2. **Production Overview** — KPI tiles (harvest kg this week, kg drying, kg curing,
   kg awaiting QC, kg released) + an inventory-by-batch table.
   *Source:* `harvest_batches` grouped by `stage`.
3. **Transition Plan** — a per-room status board (new-genetics / quarantine /
   cleaning / QA-release) + an **outstanding-actions table with target dates**,
   fed from tagged WWF tasks (`tags` = `transition`, `quarantine`, `sanitation`).
   *Source:* existing tasks, filtered + grouped — **no new capture needed**.
4. **Technical Status** — an equipment table grouped by category with a status
   chip (ok/degraded/down), and a **red highlight band** at the top listing any
   `impacts_capacity || impacts_gmp` item with its `expected_fix_on` (satisfies G2).
   *Source:* `equipment` + linked maintenance tasks.
5. **Quality & GMP** — a **rollup card** (open deviations / open CAPA / overdue
   CAPA / SOPs in revision / validations open / GMP-readiness %) each with a QMS
   reference and the non-authoritative disclaimer; a visual-inspections mini-list
   from tasks.
   *Source:* `gmp_rollup` + `task_type in (capa,sop,validation,lab)` counts.
6. **Production Forecast** — a rolling table for the next N weeks: expected
   harvests, expected kg, room availability, a capacity-vs-baseline line, and the
   recovery-to-full-production week. Anticipated dips highlighted.
   *Source:* forecast engine (Section 9), cached in `forecast_snapshots`.

Reuse existing UI primitives: `GF.WWF._sc()` stat cards, the department bar
pattern, the report-scroll tables, and the AI-insights box. Keep bilingual EN/МК
(`AL()` helper) and the six themes.

---

## 8. How the data gets in (capture UX)

The make-or-break question is **data entry effort**. Design for < 15 min/week:

- **A weekly "Facility Snapshot" form** (new intake view) pre-filled from *last
  week's* snapshot, so the HOD only edits deltas: adjust plant counts, advance
  flowering weeks (one click = +1 week for all flower rooms), log harvests, update
  equipment status. "Roll forward" mirrors the existing task roll-over UX.
- **Role-gated:** cultivation HOD owns A/B capture; maintenance owns D; QA owns the
  E rollup; executive/owner is read-only. Reuse the existing 6-role RBAC + dept
  scoping (`dept_scope` in the backend).
- **Auto-derived fields** (harvest date, yield, utilisation, forecast) are computed
  and shown read-only with an edit-override, so nobody types a number a formula can
  produce.
- **Phase-2 integrations** (optional, if these systems exist): seed-to-sale /
  cultivation software for plant counts, BMS/sensors for D1–D4 + E3, LIMS/QMS for
  E2/E4–E7. Until then, manual weekly capture is the pragmatic MVP.

---

## 9. Forecast engine (F1–F5)

A deterministic projection over `plant_groups` + `genetics`:

- For each flower room: `harvest_week = snapshot_week + (flower_days_est/7 − current_flower_week)`.
  Bucket expected `yield_kg` into that week ⇒ **F1/F2** (harvest count + kg per week).
- Room becomes **available** the week after its harvest ⇒ **F3**.
- **Capacity baseline** = full-utilisation kg/week when all rooms cycle normally.
  Any week whose projected kg < baseline is an **anticipated reduction** ⇒ **F4**;
  annotate with the cause (room down for cleaning/quarantine, from Section C/D).
- **F5 recovery week** = first future week where projected kg ≥ baseline again.
- Cache to `forecast_snapshots`; render as a table + a simple capacity line chart
  (the `dataviz` guidance already in this repo's skill set applies).

This directly serves the owner's stated goal (G3): see capacity dips **early** and
protect cash flow.

---

## 10. Backend & frontend work

**Backend (`backend/app/`):**
- Migration adding the Section-5 tables (idempotent SQL, RLS policies, audit
  trigger) — mirror the existing `schema.tasks.sql` conventions.
- New routers: `api/cultivation.py`, `api/production.py`, `api/equipment.py`,
  `api/forecast.py`, `api/gmp_rollup.py` — CRUD + weekly aggregation, dept-scoped.
- Extend `api/reports.py` `/reports/weekly` to attach `cultivation`, `production`,
  `technical`, `quality`, `forecast` blocks (or a sibling `/reports/facility`).

**Frontend (`web/gf/`):**
- New `facility-snapshot-view.js` (capture form) + extend `report-view.js` with the
  six rendered sections (tabbed).
- Nav: keep the single **Report** entry; add in-report tabs.
- Export: extend `export.js` so the PDF/CSV/JSON include the new sections — this is
  what the owner actually forwards to management.

**AI:** the existing Letta `weekly_summary` function can be prompted with the new
structured blocks to auto-draft the narrative ("capacity dips in W34 due to Flower
Room 2 quarantine; recovery W37") — labelled informational per scope.

---

## 11. Phased delivery

| Phase | Scope | Owner value | Rough size |
|-------|-------|-------------|-----------|
| **0. Re-present (quick win)** | Restructure the report into the owner's six headings; fill Transition (C) + parts of Technical/Quality from **existing tasks** (tag conventions); ship the consistent format (G1). | Immediate: report *looks* right, transition plan is live. | Days |
| **1. Cultivation + Production** | `genetics`, `rooms`, `plant_groups`, `harvest_batches` + capture form + Sections 1–2. | A1–B6 answered with real numbers. | ~1–2 wk |
| **2. Technical + Forecast** | `equipment` + highlight band; forecast engine + Section 6. | D1–D8, F1–F5, G2, G3. | ~1–2 wk |
| **3. Quality rollup + integrations** | `gmp_rollup` pointers; optional BMS/LIMS/seed-to-sale feeds; env monitoring. | E-section, less manual entry. | ~1–2 wk + |

Each phase is independently shippable on the current stack (matches the existing
`docs/STATUS.md` philosophy).

---

## 12. Open decisions (for owner / product)

1. **Data sourcing:** manual weekly capture for MVP, or do cultivation/BMS/LIMS/QMS
   systems already exist to integrate? (Changes Phase 1–3 heavily.)
2. **Scope confirmation:** OK to render Quality/QA-release as **pointers with a QMS
   reference + non-authoritative label** (per `docs/SCOPE.md`), rather than as
   records? (Recommended — keeps WWF unregulated.)
3. **Yield estimation basis:** per-plant grams by genetics (simple) vs per-m²/room
   density? Affects `genetics`/`plant_groups` fields.
4. **Forecast horizon:** how many weeks rolling (8? 12? through end of transition)?
5. **Transition plan doc (G4):** generate it *from* WWF's transition tasks +
   forecast, or keep it as a separate authored document that WWF feeds?

---

## 13. Recommendation

Start with **Phase 0** now — it delivers the owner's requested *format* (G1) and a
live *Transition Plan* from data WWF already has, within days, and demonstrates the
structure to the owner before investing in the data model. In parallel, confirm the
Section-12 decisions (especially data sourcing and the scope/pointer boundary), then
execute Phases 1→3. Keep every GMP/QA element as a clearly-labelled pointer so WWF
stays a planning tool, not a regulated system.
