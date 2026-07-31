# WWF — Department Task Workflow Handoff (continue-from-here)

**Prepared:** 2026-07-23 · **Project:** WWF (WEEKLY_WEED_FLOW · app brand GrowFlow) · **Active thread:** MASS WEED sci-fi HUD skin, `mass-weed/` folder.

> **Read `PROJECT-HANDOFF.md` first** for product/brand/token/environment context — this document does **not** repeat it. This file covers only the **department task-detail + task-creation workflow** built across the last several turns, so another agent can continue without re-deriving it.

---

## 0. TL;DR

Built a **config-driven task-detail + task-creation system across all 7 departments** in `mass-weed/`, plus a **whole-app review hub** (`review.html`). QC has **deeper, SOP-aligned** pages; the other 6 share one template each, differing only by a `DEPT` config block. Two SOP adherence audits were written to `docs/`. Everything is **informational-only** — no GMP/QMS records are reproduced (hard scope rule). The plan in `docs/QC-012-adherence-and-plan.md` is **fully implemented (Phases 1–5)**.

---

## 1. The hard scope rule (never break)

WWF is an **informational planning/tracking tool**. It must **never reproduce controlled GMP/QMS records**: no Certificate of Analysis/Quality documents, no Register of Issued Certificates, no monotonic certificate numbering, no electronic signatures, no batch-release records, no ALCOA+ record-correction. The app **references** these (a code, a link, a status label) and **tracks the work** around them — it is not the system of record. Every SOP feature added this session was built as label/link/status only. Keep it that way.

---

## 2. What was built this session

### 2.1 Per-department task screens (all 7 departments)
For each department: `task-detail-<dept>.html` + `task-create-<dept>.html` in `mass-weed/`.

| dept code | file suffix | accent | handoff target |
|---|---|---|---|
| cultivation | `-cultivation` | `#2BE8A0` | → PR Production |
| production | `-production` | `#2FD9D9` | → QC |
| **qc** | `-qc` | `#9B7BE8` | → QA (→ QP on CoQ) |
| quality_assurance | `-quality_assurance` | `#E0743A` | → WH |
| logistics (Warehouse) | `-logistics` | `#22B8D8` | → Dispatch |
| security | `-security` | `#7C90AE` | standalone |
| tooling (Maintenance) | `-tooling` | `#8496B2` | standalone |

### 2.2 Two shared templates (the source of the 6 non-QC files)
- **`task-detail-cultivation.html`** and **`task-create-cultivation.html`** are the **canonical shared shells**. Cultivation was hand-authored; the other 5 non-QC departments were **generated** from these by swapping only the `DEPT` config object.
- **QC is NOT generated** — `task-detail-qc.html` / `task-create-qc.html` are bespoke and carry the SOP logic (§3). Do not overwrite them with the generic generator.

### 2.3 Generic + board surfaces retrofitted
- **`task-detail.html`** (generic) rebuilt on the shared shell, kept its CoA/Compliance sample content (now references real form **QCT 012**), crumb points to `board.html`.
- **`my-day.html`** agenda rows now show task type + subtask progress and route to the correct `task-detail-<dept>.html`.
- **Department home task cards** (`depthome*.html`) are click-wired to open their dept detail page.
- **`board.html`** was **left as a grow-cycle batch board** (strain/room/stage → `batch.html`) — it is intentionally *not* a task board. If a task kanban is wanted, that's a new build.

### 2.4 Whole-app review hub
- **`review.html`** — the walkthrough entry point. A departments band (7 depts × Home/New/Detail, QC row tagged SOP-aligned) + grouped links to every screen (Entry, Operations, Task surfaces, Manager, System, Design reference) + links to the two SOP docs. **Start here when reviewing.**

---

## 3. The config-driven pattern (how to extend)

Both shared templates carry a single config block delimited by comment markers:

```js
/* @DEPT-CONFIG-START */
const DEPT = { code, en, mk, ab, col, sopRef, /* + task/refs/presets/handoff/deps/fields/tags */ };
/* @DEPT-CONFIG-END */
```

Everything below the block is department-agnostic and reads from `DEPT`. To **regenerate** the 5 non-QC departments (or add a new one), splice a new config between those markers — do **not** hand-edit the body. The generator that produced them:
1. reads `task-detail-cultivation.html` / `task-create-cultivation.html` as templates,
2. replaces the slice between `@DEPT-CONFIG-START`/`END` with `const DEPT = <json>;`,
3. saves as `task-{detail,create}-<code>.html`.

**Config shape differs slightly between the two files:**
- **detail** `DEPT`: `task{id,en,mk,type_en,type_mk,prio_en,prio_mk,desc_en,desc_mk}`, `refs[[label,val]]`, `presets[[en,mk]]`, `handoff{ab,col,en,mk}`, `depOn{en,mk,met}`, `blocks{en,mk,met}`.
- **create** `DEPT`: `icon` (inline SVG path), `title{en,mk}`, `desc{en,mk}`, `fields[{k,en,mk,type:'text'|'select',options?,val,unit?}]`, `presets`, `handoff[ {ab,col,en?,mk?} … ]` (pipeline array), `depBefore[[en,mk]]`, `depAfter[[en,mk]]`, `tags[]`.

### Shared shell features (both files, every dept)
Task type pill · reference-code chips · nested **unlimited-depth** subtask tree (expand/collapse, inline "↳ add sub-item", ✕ delete) · dependencies (blocks / blocked-by, met/unmet pills) · reviewer **accept/decline ack** pill · recurrence · SOP-ref field (code+link only) · **blocker field revealed on "Stuck"** · **multi-entry work-session log** (date/hours/note, not just a counter) · dept-specific default **handoff target**. Detail page also has: description, attachments, comments, activity feed, Log-Progress panel (status chips + completion slider + sessions).

**No native `<select>` anywhere** (locked decision). Every choice is a `.mw-chip` button group with a small vanilla delegator. `af-modal.html`'s old real `<select>`s were converted to chip groups earlier in the thread.

---

## 4. QC SOP-aligned pages (the deep ones)

`task-detail-qc.html` + `task-create-qc.html` encode three approved SOPs. **Authority:** where an SOP's text and a NotebookLM infographic disagree, the SOP text wins.

### 4.1 QCSOP 001 v2 — Laboratory Testing Lifecycle (governing)
- 5-phase stepper **RQS → SFR → STR → ARI → Closure** (clicking a phase on detail, or the phase chip on create, drives state).
- Request control-number format `PP-QC-F-001.A01/YYYY-NNN`; sample code `NNN/YY_SFR-…`; method ref `STP/AM`.
- Priorities Routine (10 working days) / Urgent (3).
- Roles: QC Analyst, **QC Reviewer** (four-eyes verification), QC Lab Manager.
- Request-submission form surfaced as **QCT 002**.
- **⚠️ There are two QCSOP 001 files in the client folder.** The **v2 "Laboratory Testing Lifecycle"** one is authoritative (user-confirmed); the older "Activities in QC Department" one is superseded. Don't re-audit against the old one.

### 4.2 QCSOP 019 v2 — OOx investigation
- Deviation flag = **four result types: OOS / OOT / OOE / OOC** (an umbrella called OOx — NOT a two-tier OOE→OOS system; that was an infographic simplification).
- Investigation: **Phase I** (IA analyst immediate review → IB supervisor 7-step) → **Phase II** (root-cause / impact / cross-functional). Analyst reports to QC Supervisor **within 1 hour**.
- Roles escalate: QC Analyst → QC Supervisor → Head of QC → Head of QA → **QP** (HIGH-risk + batch disposition).
- Setting an OOx flag reveals the investigation context and (on Closure/CoQ) flips the CoQ "no open OOS" prerequisite to **"✕ Open OOS — CoQ blocked"**.

### 4.3 QCSOP 012 v3 — CoA / CoQ (Closure phase) — **reference-only**
Certificate sub-panel appears at the **Closure** phase:
- **Type** chips: **iCoA** (own lab, same working day) · **eCoA** (contract lab, review ≤ **5 working days** vs Annex A03) · **CoQ** (batch aggregate for QP release).
- **Certificate ref** field with per-type format hint (`iCoA/eCoA/CoQ-PP-YYYY-NNNN`).
- **Register status** chips: Draft / Issued / Accepted / Revised / Superseded / Voided — labelled "held in the Register, not here".
- **SLA** line updates per type; "*Analysed by → Reviewed & approved by (QC Manager)*" caption.
- **CoQ** selection → sets **hands-off-to = QP** (not QA) + shows the **CoQ prerequisite gate** (all params tested · all iCoA approved · all eCoA accepted · no open OOS).
- Detail sidebar shows **Requested by** (origin sector, e.g. Production) — reflects requests coming from other sectors and results returning outward.
- **`task-create-qc.html` extra subtask templates:** "eCoA intake" (receive → register → Annex A03 review → resolve → accept) and "Revise / void certificate" (identify original → new number + reason → set Superseded/Voided → retain original).

---

## 5. Documents produced

- **`docs/QC-adherence-audit.md`** — audit vs QCSOP 001 v2 / 011 / 019. Verdict: QC screens are adherent (earlier "gaps" were from weighting the superseded SOP 001). Optional enrichments listed.
- **`docs/QC-012-adherence-and-plan.md`** — QCSOP 012 v3 analysis + 5-phase plan, with a dated **"implemented"** status block at the bottom (Phases 1–5 done). This is the record of what the certificate/Closure work does and — importantly — the **"explicitly NOT to build"** scope-guard list.

Extracted SOP text (working copies) live in `scraps/sops/*.txt` (+ `.docx`). The client's originals are in the mounted folder **`DB3_PP_CURRENT/`** (all paths must start with that prefix). SOP source `.docx` filenames are Macedonian Cyrillic; the extractor script (a manual zip/deflate-raw reader in `run_script`) is reusable — the DOCX has `word/document.xml`, paragraphs split on `<w:p>`, table cells on `</w:tc>`.

---

## 6. CSS atoms added to `mass-weed/mass-weed.css`

The shared shells rely on `.mw-*` atoms added to the kit stylesheet — reuse these, don't reinvent:
`.mw-chip` / `.mw-chip--sm` (chip button, `--cc` accent), `.mw-chips` (group), `.mw-subnode` / `.mw-subbranch` (nested subtask tree with dept-colored rails), `.mw-dep` (`.met`/`.unmet` dependency pill), `.mw-ack` (`.mw-ack--accepted`/`--pending` acceptance pill), `.mw-step` (`.done`/`.current` phase stepper node), `.mw-reveal` (`.show`, `--warn`/`--info` variants) for blocker/cert panels, `.mw-attr` (attribute chip), `.mw-htag` (hashtag), `.mw-input`/`.mw-textarea`/`.mw-field`, `.mw-btn` (`--primary`/`--ghost`/`--accent`). Bilingual is via `.en`/`.mk` spans toggled by `mw-i18n.js`; theme/lang control bar is `.mw-ctlbar` + `.mw-seg`.

---

## 7. State & open items

**Complete:** all 7 depts (detail+create), QC SOP pages (001/012/019), generic detail, my-day routing, dept-card wiring, review hub, both audit docs, QCSOP 012 Phases 1–5.

**Not done / possible next steps:**
1. **`board.html` as a task kanban** — currently a batch board by design; build only if asked.
2. **Other Manager/System screens** (`workload`, `approvals`, `reports`, `execreport`, `analytics`, `notifications`, `search`, `settings`, `team`, `automations`, `rule-builder`) do **not** yet surface the new task fields — retrofit if desired.
3. **Persistence** — all state is in-memory; nothing survives reload. No localStorage wired for tasks.
4. **Other departments' SOPs** — only QC has been analyzed. Cultivation/Production/QA/Warehouse have SOPs in `DB3_PP_CURRENT/` that could deepen their (currently generic) pages the way QC's were.
5. **nav.js** still links "Dept Home" → the generic `depthome.html` hub, not a specific dept.
6. **MASS WEED vs green-hero canonical decision** is still open (see PROJECT-HANDOFF §7) — this session worked entirely in the standalone `mass-weed/` kit, which is a **reference artifact, not the compiled DS**. None of this session's files are compiled into `_ds_bundle.js`.

**Environment reminder:** this is a design-system project. Don't hand-edit `_ds_bundle.js` / `_ds_manifest.json` / `_adherence.oxlintrc.json`; run `check_design_system` after DS-level changes. The `mass-weed/` kit is plain HTML/CSS/JS and is not swept into the bundle, so editing it there is safe.

---

## 8. Fast file map (this session's additions, all under `mass-weed/`)

```
review.html                     ★ whole-app walkthrough hub — START HERE
task-detail-cultivation.html    ★ canonical shared DETAIL template (config-driven)
task-create-cultivation.html    ★ canonical shared CREATE template (config-driven)
task-detail-<dept>.html         production · quality_assurance · logistics · security · tooling  (generated)
task-create-<dept>.html         (same 5, generated)
task-detail-qc.html             ★ bespoke QC — QCSOP 001v2 / 012v3 / 019v2 (reference-only)
task-create-qc.html             ★ bespoke QC — cert types, eCoA/revise templates, CoQ gate
task-detail.html                generic, rebuilt on shared shell (CoA/QCT 012 sample content)
my-day.html                     agenda rows route to dept detail pages
depthome-<dept>.html            task cards wired to open dept detail
mass-weed.css                   .mw-* atoms extended (chips, subtree, deps, stepper, reveal)

docs/QC-adherence-audit.md          audit vs QCSOP 001v2/011/019
docs/QC-012-adherence-and-plan.md   QCSOP 012v3 analysis + plan (Phases 1–5 = done)
scraps/sops/*.txt|.docx             extracted SOP working copies
```
