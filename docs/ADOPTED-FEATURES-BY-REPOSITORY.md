# Adopted Features by Source Repository

**What was taken from every repository / version you shared, and where it lives now
in the one unified GrowFlow platform.**

- **Owner:** Purely Plant GmbH — engineering
- **Date:** 2026‑07‑23
- **Companion docs:** `docs/PLATFORM-ROADMAP-2026-07.md` (§3 asset inventory — the
  analytical basis for this list), `docs/UNIFICATION-ANALYSIS-2026-07.md` (the
  strangler‑fig method), `docs/DOCENGINE-CANON-2026-07.md` (the per‑component
  document‑engine canon), `docs/PROVENANCE.md` (the original isolation note).

---

## 0. The one‑paragraph story

You shared, over many attempts and versions, roughly a dozen separate apps and codebases
that each tried to build a piece of the Purely Plant operation — a task manager, an
SOP/QMS document generator, and several QC‑LIMS / certificate systems. Rather than run
them as separate products, everything was **absorbed into the single live GrowFlow
platform by the strangler‑fig pattern** — one login, one URL, one database spine, one
bilingual PWA. The central analytical finding was that **nine assets reduce to four
capability layers, not nine products**: a shared spine, cross‑cutting services (DocEngine
+ Notifications), and three domain modules (Task Management, QC LIMS, Certificates). Every
repository below was mined for its *unique* value; duplicated ideas were consolidated, and
superseded instruction‑texts were dropped in favor of the newest dated canon. Nothing was
run as a second app or a forked stack.

**The three systems you named, and where they landed:**

| Your framing | In the unified app | Zone |
|---|---|---|
| **Task‑management system** | The operations core + the next‑gen TMS (T1–T5) | Zone A — Operations (non‑GMP) |
| **QMS *creation* system** | "Document Studio" — the DocEngine authoring wizard | Zone B — QMS Studio |
| **QMS / QC‑LIMS *lifecycle* application** | The QC LIMS module + the Certificate pipeline | Zone C — GMP records |

---

## 1. The source assets at a glance

| # | Asset (as you shared it) | What it was | Domain | Verdict |
|---|---|---|---|---|
| 1 | **WWF / GrowFlow** (this repo) | Live ops + weekly‑reporting PWA | Foundation / Operations | **The spine — base of everything** |
| 2 | **pp‑document‑suite v1.7.0** | House‑style bilingual `.docx` engine | Document generation | **Adopted completely** into `docengine/` |
| 3 | **Cannabis‑EU‑GMP‑QMS‑Creator** (`qms-creator/`) | Questionnaire‑driven SOP/annex authoring + 13 Letta agent personas | QMS authoring | **Workflow shape kept**, instruction texts superseded |
| 4 | **ACME_SOP** | Engine lineage + `build_from_md.py` / `[[FORM:grid]]` layout brain | Document generation | **Folded into the DocEngine canon** |
| 5 | **QC_LIMS_Ao** (`qc-lims-ao/`) | React+FastAPI QC‑LIMS prototype (deep domain) | QC LIMS | **Primary source** for the QC LIMS module |
| 6 | **QC_LIMS_APP** | RSA sampling form + GMP‑QC HTML + roadmap | QC LIMS (sampling) | **Merged** — sampling sub‑domain |
| 7 | **QC_APP** | LIMS README stub | QC LIMS | Placeholder — folded in |
| 8 | **cannabis‑sample‑tracker‑89871** | Lovable React sample‑tracker SPA | QC LIMS (samples) | **UI/UX ideas** for sample views |
| 9 | **CoA_TRACK** (v3.0.0) | CoA management: ingestion, AI PDF extraction, Annex‑11 | Certificates | **Merged into the one certificate pipeline** |
| 10 | **COQ_GEN** | eCOA → Certificate‑of‑Quality generation engine | Certificates | **Merged into the same pipeline** |
| 11 | **Kade** (CoA Tracker) | Ingest · Track · RAG · Discover Placeholders | Certificates | **Confirmed** the pipeline; contributed the placeholder‑discovery idea |
| 12 | **SUMA / ISO17025 corpus** (3 variants) | `WEEKLY_SUMA_ISO17_v2` · `suma-platform` · `01_TASKMASTA_ISO17025` | Ancestor | **Ancestor of WWF** — one genuine delta adopted |
| 13 | **QCSOP 001–024** (approved SOPs, Drive) | The facility's controlled SOPs | Regulatory authority | **The source of truth** the domain was built to |

Also assimilated as *regulatory canon* (not code): **EU‑GMP Annex 11** (computerized
systems / e‑signatures), **EU‑GMP Annex 16** (QP certification), **WHO TRS 1010** (CoQ
mandatory‑field manifest), **ALCOA+** data‑integrity principles, and a **URS gap
analysis** (`docs/URS-COQ-GAP-ANALYSIS-2026-07.md`) that drove 10 QC increments.

---

## 2. Adoption detail, repository by repository

### 2.1 WWF / GrowFlow — the spine (base of everything)

Everything else was built *on top of* what this repo already provided. Adopted forward as
the permanent foundation:

- **Two‑DB architecture** — a users DB and a tasks DB kept physically separate, merged in
  the app layer (never SQL‑joined).
- **Organization isolation via row‑level security (RLS)** + per‑request identity GUCs — a
  true multi‑tenant boundary the whole platform relies on.
- **Hash‑chained, tamper‑evident audit trigger** — the ALCOA+ audit log every GMP record
  now hangs off of.
- **13‑role model** (ADMIN, OWNER/CEO/COO, the seven managers + QP, USER) — replaced every
  prototype's ad‑hoc RBAC.
- **Bilingual EN/МК vanilla‑JS PWA** — the single shell, service worker, offline cache,
  and the token‑driven design system that all modules render into.
- **Weekly task rhythm** — departments, weeks, board/timeline/calendar, weekly plan/report
  documents, executive overview, analytics — the operational heart.
- **Notifications v1**, **AI binding** (per‑org Letta) plumbing, deploy discipline
  (test→prod, path‑scoped CI, schema‑drift gate).

### 2.2 pp‑document‑suite v1.7.0 — **adopted completely** (QMS creation core)

The production house‑style `.docx` engine — taken wholesale into the new `docengine/`
service (this was an explicit "adopt completely" directive):

- The **canonical formatting core**: navy **#2B547E** house style, Calibri, the **6 pt
  minimum font floor**, bilingual **MK | EN** layout, auto annex/table layout, `kv_block`
  / `cell08` / `value_span` / `sop_nested_table` primitives, parameterized approval‑role
  blocks (no hardcoded personnel — a GxP win).
- **`pp_verify`** — the hard **`RESULT: PASS/FAIL`** verification gate. A FAIL never leaves
  the engine; no controlled document ships without PASS.
- **`PP_BASE_TEMPLATE.docx`** house template + the reference guides.
- Rendered to PDF via **Gotenberg**.

### 2.3 ACME_SOP — the newest layout brain (QMS creation core)

The document‑engine lineage that was *newer* than the zip on two specific components — the
canon analysis (`docs/DOCENGINE-CANON-2026-07.md`) picked these deliberately:

- The **July‑14 `fixed()` layout algorithm** — data‑driven overflow compression + word‑
  boundary entry matching (grafted into `pp_format.py`).
- **`build_from_md.py`** with **`[[FORM:grid]]`** content‑aware per‑field packing — the
  most advanced realization of the §6D form‑layout rules.
- Union of reference guides (bilingual‑markdown + unified‑docx guides).

### 2.4 Cannabis‑EU‑GMP‑QMS‑Creator (`qms-creator/`) — the workflow *shape* (QMS creation)

The questionnaire‑driven SOP authoring app. Its **workflow shape was kept; its instruction
texts were superseded** by the newer pp‑suite/ACME canon:

- **Adopted:** the Mode‑A pipeline shape — *questionnaire → section‑author agents →
  per‑section regulatory‑database check → assemble → format → register*. This is exactly
  the shape of "Document Studio" (the `qmsstudio` wizard).
- **Adopted:** the idea of a **Letta agent fleet** with role personas (orchestrator,
  section authors, MK⇄EN translator, regulatory checker, RACI/annex specialists, QA
  auditor) — rebuilt as the namespaced **`gf_*` fleet** (additive; existing agents never
  blind‑flipped).
- **Superseded / dropped:** the qms‑creator's own agent instruction texts, the section
  checklist YAMLs, and the standalone `qms-api` registry service (later **formally
  retired** — the registry/knowledge tabs now point at Document Studio).

### 2.5 QC_LIMS_Ao (`qc-lims-ao/`) — **the primary QC‑LIMS source** (lifecycle app)

The richest QC domain prototype (React + FastAPI + a `qc_lims` Postgres). It was
**assimilated natively** (rebuilt on the WWF spine — two‑DB RLS, hash‑chained audit,
bilingual PWA — *not* run as a second app). What the QC LIMS module took from it:

- **Specifications** master data + parameters/acceptance limits (QC‑U1).
- **Sample lifecycle** state machine (COLLECTED → IN_TRANSIT → RECEIVED → IN_TEST → TESTED
  → REVIEWED → APPROVED → RELEASED, + REJECTED, + QUARANTINE) and **batch genealogy**
  (parent/child ancestry) (QC‑U2).
- **CoA + test results** with server‑side `complies` evaluation and the **out‑of‑spec →
  auto‑quarantine** hook (QC‑U3).
- **OOS** two‑phase investigation + append‑only register + **CAPA** (QC‑U4).
- **Custody cluster** — sampling requests (RQS, with a 24 h registration window), sample
  field records (SFR), and **chain of custody** (QC‑U5).
- **Standalone leaves** — water tests, stability studies, sample transports (QC‑U6).
- **Annex‑11 audit** expectations (satisfied by the platform's existing hash‑chained
  audit, not a second audit table) and its **barcode/QR** sample workflow idea.
- Its **task‑lifecycle bits** (accept/decline, outcome, node‑kind task tree, dependency
  graph, handoff lifecycle) fed the **TMS** (see §2.11).

Where the prototype and the **approved QCSOP 001–024** disagreed, the SOPs won.

### 2.6 QC_LIMS_APP — sampling sub‑domain (lifecycle app)

- **Adopted:** the **QC RSA sampling‑form** detail and sampling‑process fields — merged
  into the custody/sampling‑request sub‑domain of the QC LIMS module.

### 2.7 QC_APP — placeholder

- Near‑empty README stub; **no unique code**. Folded into the QC LIMS module conceptually;
  nothing to port.

### 2.8 cannabis‑sample‑tracker‑89871 — UI reference (lifecycle app)

- **Adopted:** sample‑tracking **UI/UX ideas** (the sample registry/board layout, tracking
  affordances) informing the `qcsample` / `qcgenealogy` views. Not run as an app.

### 2.9 CoA_TRACK (v3.0.0) — **merged into the one certificate pipeline**

A CoA management system (React + FastAPI + Letta, 9 routers). **Not stood up separately** —
its capabilities were reconciled into the single extract→verify→generate pipeline:

- **CoA ingestion** (incoming supplier/contract‑lab certificates) + **AI PDF field
  extraction** → the eCoA‑in half (QC certificate pipeline U2).
- **Annex‑11 e‑signature controls** on certificate approvals.
- **Source provenance** carried onto every extracted result.

### 2.10 COQ_GEN — **same pipeline** (certificate generation)

The eCOA → Certificate‑of‑Quality generation engine. Reconciled with CoA_TRACK + the
DocEngine into **one** pipeline (never triplicated):

- The **COQ release‑certificate generation rules** → the COQ‑out half (QC certificate
  pipeline U1): `POST /qc/certificates/{id}/coq` renders a **RELEASED** certificate to a
  PASS‑gated bilingual `.docx` CoQ via the DocEngine, QP‑gated, with a GxP data gate
  (every result must comply — never fabricate a conformant certificate over a FAIL).
- Its **OCR/visual‑parse ingestion** idea reinforced the eCoA extraction workbench.

### 2.11 Kade (CoA Tracker) — confirmed the pipeline, gave the placeholder idea

A fourth certificate source (Ingest · Track · **RAG** · **Discover Placeholders**). It
**confirmed** rather than expanded the consolidation, and contributed two concrete ideas:

- **Adaptive placeholder discovery** — unknown lab labels queue for a human to MAP
  (map‑once → auto‑map future CoAs) or IGNORE — now the eCoA review queue (U2).
- **Grounded RAG Q&A over ingested CoAs** — `POST /coa-qa` returns **cited** passages,
  never a fabricated synthesis (Postgres FTS; U4).

### 2.12 SUMA / ISO17025 corpus (3 variants) — the ancestor, one real delta

Deep‑analysed (`WEEKLY_SUMA_ISO17_v2` canonical / `suma-platform` history /
`01_TASKMASTA_ISO17025` legacy). **Finding: SUMA is the *ancestor* of WWF/GrowFlow** —
its task model, roles, approval workflow, ALCOA+ audit, and executive dashboard are
already **surpassed** by the platform. So almost nothing needed porting. The genuine
deltas that *were* taken:

- **Executive GMP audit‑prep readiness tracker** — assimilated natively as a pure read
  layer over task tags (`GET /reports/audit-prep` + the bilingual "Audit readiness" view;
  no migration). Kept a **planning aid**, not a controlled record.
- **The SUMA v2 workflow sign‑off layer** (`workflow_state`) — later activated into a
  manager submit → approve/reject sign‑off + **QP‑remark block** (TMS T5).
- **Dropped/superseded:** SUMA's cosmetic e‑signature + report‑versioning schema — the
  DocEngine + the platform's Annex‑11 e‑signatures supersede them.

### 2.13 QCSOP 001–024 + regulatory canon — the source of truth

Not a codebase — the **approved SOPs** and regulatory references that the QC LIMS +
certificate modules were built *to*. They are the authority wherever a prototype disagreed:

- Per‑SOP fields, formats, control №, and gates (e.g. QCSOP‑011 columns; the 24 h RQS
  registration window per SOP‑017; RQS‑before‑sampling ordering per §6.1.1; the external‑
  CoA review checklist **QCT‑018**; §6.16 deviation logging; the 5‑working‑day eCoA review
  clock §6.3.1).
- **Annex 11** → password‑reauth **electronic signatures** on QC approvals + tamper‑evident
  audit. **Annex 16** → **QP‑gated** batch release. **WHO TRS 1010** → the CoQ mandatory‑
  field manifest. **ALCOA+** → blank‑not‑fabricated, immutability‑by‑revision, second‑
  person review. A **URS gap analysis** drove ten increments (OOS gate, supersession
  chains, computed total THC/CBD, a Laboratory master entity, the certificate register,
  per‑type/per‑year certificate numbering, lab‑verdict on the permanent record, PDF‑
  original custody + SHA‑256, m:n batch genealogy incl. blending).

---

## 3. Adoption grouped by the three systems you named

### 3.1 Task‑management system (Zone A — Operations)

**Base:** WWF/GrowFlow. **Enhanced by:** qc‑lims‑ao (task‑lifecycle bits) + SUMA (sign‑off).

- Departments · weeks · tasks with owner/helpers, status (6), priority (4), due, day,
  type, progress notes, dependencies, cross‑department handoffs, custom department field
  templates — *(WWF)*.
- Board / Timeline / Calendar / Coordination / Dashboard / Executive Overview / Team /
  Workload / My Week / My Day / Department Home — *(WWF)*.
- **Node‑kind task tree + dependency graph with a cycle guard** and the **propose/accept
  handoff lifecycle** — *(TMS T1, harvested from qc‑lims‑ao)*.
- **In‑app team digest** + notification inbox filters — *(TMS T2)*.
- **AI‑native planning** — workload balancing, next‑week plan, dependency advisor —
  *(TMS T3, on the existing Letta catalog)*.
- **Manager submit → approve/reject sign‑off + QP‑remark block** — *(TMS T5, from SUMA v2
  workflow_state)*.
- Weekly Plan/Report documents, Analytics, **Audit‑Prep readiness** *(SUMA delta)*, AI
  Intake, Bulk Import, Notifications inbox, Facility board (rooms + plant batches).

### 3.2 QMS *creation* system (Zone B — Document Studio)

**Base:** pp‑document‑suite v1.7.0 (adopted completely) + ACME_SOP (newest layout brain) +
qms‑creator (workflow shape).

- The **`docengine/` service** — a dedicated Letta‑powered FastAPI service.
- **Questionnaire → section‑author agents → per‑section regulatory check → assemble →
  house‑style format → `pp_verify` PASS gate → DOCX/PDF** — the full creation wizard
  (`qmsstudio`).
- House style (navy, 6 pt floor, bilingual MK|EN), the `fixed()`/grid layout brain,
  Gotenberg PDF, the `gf_*` Letta fleet.
- **Grounded knowledge search** (cited passages, never invented) and the document
  **registry**.

### 3.3 QMS / QC‑LIMS *lifecycle* application (Zone C — GMP records)

**Base:** qc‑lims‑ao (primary) + QC_LIMS_APP + cannabis‑sample‑tracker (UI) + CoA_TRACK +
COQ_GEN + Kade + QCSOP/Annex/WHO canon.

- **Specifications** + parameters/limits, one‑ACTIVE‑per‑material, supersession, computed
  total THC/CBD.
- **Samples** + full lifecycle state machine + **genealogy** (m:n, incl. blending) + QR.
- **Certificates / CoA** — results grid, `complies` auto‑eval, **second‑person review**,
  **QP‑gated release**, per‑type/per‑year numbering (iCoA/eCoA/CoQ/WCoA/CoA), the
  certificate **register**, lab dashboard, revision/void, Annex‑11 **e‑signatures**, PDF‑
  original custody + SHA‑256, lab‑verdict on the permanent record.
- **eCoA intake** — register → extract → auto‑map → **placeholder discovery** → **QCT‑018
  review checklist gate** → promote (provenance‑carrying) → **verify vs source
  (VERIFIED/DISCREPANCY)** → **CoQ generation** → **grounded CoA Q&A**.
- **OOS/CAPA** — two‑phase investigation, append‑only register, QP‑gated disposition.
- **Custody** — RQS (24 h window, RQS‑before‑sampling), SFR, chain of custody.
- **Leaves** — water / stability / transport.
- All on the shared spine: RLS, hash‑chained audit, **blank‑not‑fabricated**,
  immutability‑by‑revision, §6.16 deviation logging.

---

## 4. Consolidation decisions (why nine became four)

1. **CoA_TRACK + COQ_GEN + Kade + the QC‑LIMS CoA parts → one certificate pipeline** on the
   DocEngine core. Building them separately would have duplicated ingestion, extraction,
   verification, and rendering four times over divergent CoA data models.
2. **qms‑creator's texts → superseded** by the newer pp‑suite v1.7.0 + ACME_SOP canon; only
   its *workflow shape* and *fleet concept* survive.
3. **SUMA → recognized as the ancestor**, not a peer — only its audit‑prep readiness view
   and workflow sign‑off were genuinely absent and worth porting.
4. **QC_APP → nothing to port** (stub). **cannabis‑sample‑tracker → UI ideas only.**
5. **The two‑zone boundary held:** operations stayed non‑GMP; QC/certificates/document
   authoring are the GMP‑records zones on their own lifecycle — the merge never blurred it.

---

## 5. Deliberately NOT adopted (recorded)

- qms‑creator's standalone `qms-api` registry service — **retired** (Document Studio is the
  sole QMS surface).
- SUMA's cosmetic e‑signature + report‑versioning schema — superseded by the DocEngine +
  platform e‑signatures.
- Any second app, forked stack, or parallel Postgres cluster — everything is additive on
  the one spine, same containers, same URL.
- Prototype RBAC / audit tables from the QC repos — replaced by the platform's 13‑role
  model + hash‑chained audit.

---

*This document is a companion to `docs/PLATFORM-ROADMAP-2026-07.md` §3, which carries the
original overlap analysis and the dependency‑ordered build sequence. Every "done" claim
here corresponds to a shipped, tested, and (on the test stack) live‑smoked increment.*
