# Purely Plant Unified Platform — Master Analysis & Implementation Roadmap

**Date:** 2026-07-16 · **Owner:** Purely Plant GmbH (Macedonian EU-GMP medical-cannabis facility)
**Author:** engineering · **Status:** living document — the single source of truth for sequencing every module

> This document exists because the platform's scope expanded rapidly: a document
> engine, a next-generation task manager, and **six imported repositories** now
> all target one system. Grinding them out ad-hoc would multiply data models and
> CoA pipelines. This roadmap fixes a **logical, dependency-aware, GxP-safe
> order** and a **repeatable method**, so every module lands additively on one
> spine, test-first, with the owner gating production.

---

## 1. Executive summary

**One platform. One login. One URL. One database spine.** Everything absorbed
into the live WWF/GrowFlow foundation by the **strangler-fig** pattern
(`docs/UNIFICATION-ANALYSIS-2026-07.md`, Option B) — never a second app, never a
forked stack, always the same containers so executives keep the same links.

Three things are already true and verified:

1. **The foundation is mature and in production** — FastAPI over two Postgres
   DBs (`wwf_users` + `wwf_tasks`), row-level security, per-request identity
   GUCs, hash-chained tamper-evident audit triggers, 13-role model, bilingual
   MK/EN vanilla-JS PWA. ~25 real users. 289 backend tests, path-scoped CI,
   disciplined test→prod deploys on kvm4.
2. **The DocEngine is built and running on the test server** — a dedicated
   Letta-powered FastAPI service that adopts the production pp-document-suite
   formatting engine completely and merges the questionnaire→SOP/annex authoring
   workflow. Verified end-to-end on wwf_mass (a real questionnaire→annex round
   trip produced a `RESULT: PASS` controlled .docx).
3. **The task-management upgrade (priority #1) is complete on the test server**
   — T1–T4 (dependency graph, node-kind task tree, cross-department handoff
   lifecycle, in-app team digest, AI-native planning) built, tested, and
   deployed to wwf_mass.

**Status as of 2026-07-16:** the module-consolidation program is essentially
**done on the test server**. The central §3 finding held — **CoA_TRACK, COQ_GEN,
and the CoA/COQ parts of the QC-LIMS corpus collapsed into a single certificate
pipeline built on the DocEngine** (Phase 3, complete), never triplicated.
Phases 0–3 all live + live-smoked on wwf_mass; the QC LIMS module carries five
units (U1–U5). What remains is **owner-gated** — acceptance tests + the staged
prod promotion (§8) — plus a few deferred low-priority QC leaves.

---

## 2. Current state (verified live 2026-07-16)

| Environment | Backend | Frontend | tasks-DB | Extra services | Notes |
|---|---|---|---|---|---|
| **Production** `wwf_app` (`https://…hstgr.cloud`) | v39 | v63 | alembic **0016** | — | The 25-user live system. No DocEngine, no QMS Studio, no TMS, no QC LIMS — **all new work is test-only** and owner-gated. |
| **Test** `wwf_mass` (`https://wwf-mass…`) | **v52** | **v73** | alembic **0027** | `qms-api:v1`, `growflow-docengine:v3` | DocEngine + TMS (T1–T4) + QC LIMS **U1–U6** + the full certificate pipeline (Phase 3 **U1–U4**) all live + live-smoked. Migrations 0017–0027 applied. |

**Standing rule (owner, non-negotiable):** every upgrade deploys to **wwf_mass
only**; production is promoted **solely** after the owner's own tests +
**explicit approval**. This document never proposes a prod deploy without that
gate.

**Governance boundary (`docs/SCOPE.md`, "one roof two zones"):** the Operations
zone (tasks, weekly reports, facility, analytics) is **non-GMP / informational**;
the QMS Studio + QC zones are where **GMP records** live, on their own
service/lifecycle. This boundary is structural and must survive every merge.

---

## 3. Asset inventory & overlap analysis *(the analytical core)*

Every source now in hand, classified by domain and by what it uniquely
contributes vs what it duplicates:

| Asset | What it is | Domain | Unique value | Overlaps / verdict |
|---|---|---|---|---|
| **WWF/GrowFlow** (this repo) | Live ops + weekly-reporting PWA | Foundation + Operations | The spine: auth, RLS, audit, roles, PWA, notifications | — (base) |
| **pp-document-suite v1.7.0** | House-style bilingual .docx engine | Document generation | The canonical formatting core (navy #2B547E, 6pt floor, `pp_verify` PASS gate) | Vendored into `docengine/` (**done**) |
| **Cannabis-EU-GMP-QMS-Creator** → `qms-creator/` | Questionnaire-driven SOP/annex authoring + 13 Letta agent personas | QMS authoring | The Mode-A workflow shape (questionnaire → section agents → regulatory check) | Instruction texts superseded by the DocEngine canon; **workflow shape kept** (**done, in DocEngine pipeline**) |
| **ACME_SOP** | Engine lineage + `build_from_md.py`/`[[FORM:grid]]` | Document generation | The Jul-14 `fixed()` layout brain + grid adapter | Folded into DocEngine canon (**done**) |
| **QC_LIMS_Ao** → `qc-lims-ao/` | React+FastAPI QC LIMS prototype | **QC LIMS** | Richest QC domain model: samples, specs, CoA, OOS, CAPA, stability, transport, water, Annex-11 audit, barcode | **Primary source for the QC LIMS module.** Its TMS-lifecycle bits feed the TMS. |
| **QC_LIMS_APP** | RSA sampling form + GMP-QC HTML + roadmap | QC LIMS (sampling) | Sampling process detail (QC RSA form) | Merges into QC LIMS module — sampling sub-domain |
| **QC_APP** | LIMS README stub | QC LIMS | (near-empty) | Placeholder — folds into QC LIMS module |
| **cannabis-sample-tracker-89871** | Lovable React sample-tracker SPA | QC LIMS (samples) | A sample-tracking UI reference | UI ideas for QC LIMS sample views; not a separate app |
| **CoA_TRACK** | React+FastAPI+Letta CoA management (v3.0.0, "production") | **Certificates** | CoA ingestion (Drive), AI PDF extraction, Annex-11 controls, 9 routers/services | **Merges into the unified certificate pipeline** — do NOT stand up separately |
| **COQ_GEN** | eCOA→Certificate-of-Quality generation engine (design-first) | **Certificates** | The COQ release-certificate generation rules + OCR/visual-parse ingestion | **Same pipeline as CoA_TRACK + DocEngine** — reconcile, don't triplicate |

### The central finding

The nine assets reduce to **four capability layers**, not nine products:

```
┌─────────────────────────────────────────────────────────────┐
│  SHARED SPINE  (exists)                                       │
│  auth · RLS · hash-chained audit · roles · PWA · Letta fleet │
├───────────────┬───────────────┬─────────────────────────────┤
│  DocEngine    │  Notifications│  (cross-cutting services)    │
│  (done)       │  (v1 done)    │                              │
├───────────────┴───────────────┴─────────────────────────────┤
│  DOMAIN MODULES  (on the spine, sharing the services above)  │
│  1. TMS (priority #1)                                        │
│  2. QC LIMS      ← qc-lims-ao + QC_LIMS_APP + QC_APP + tracker│
│  3. Certificates ← CoA_TRACK + COQ_GEN + QC-LIMS CoA parts    │
│     └─ ONE extract→verify→generate pipeline on the DocEngine │
└─────────────────────────────────────────────────────────────┘
```

**Design consequence:** the certificate pipeline (CoA in, COQ out) is built
**once**, on the DocEngine's formatting core and Letta fleet, consumed by both
the QC LIMS module (per-batch CoA/COQ) and any standalone certificate view.
Building CoA_TRACK and COQ_GEN as separate services would duplicate ingestion,
extraction, verification, and rendering that the DocEngine already centralizes.

---

## 4. Target architecture — the unified spine

- **Data:** two-DB split retained. New domains get their **own schema** inside
  `wwf_tasks` (e.g. `docengine`, later `qc_lims`, `certs`) or a dedicated DB per
  the Phase-2 plan — never a parallel Postgres cluster. Every table carries
  org-isolation RLS + the hash-chained audit trigger (the `id`-surrogate-PK rule
  learned in T1: the shared audit trigger records `NEW.id`).
- **Services (shared, internal-only, fronted by the WWF backend's authed
  proxy):** DocEngine (all document/certificate generation), the Letta `gf_*`
  fleet (additive — existing ~54 agents never blind-flipped), Notifications,
  Audit, Gotenberg (DOCX→PDF).
- **UI:** one bilingual PWA; zones surfaced as nav groups (Operations · QMS
  Studio · QC LIMS · Certificates), each role-gated. Same shell, same SW, same
  URL.
- **AI:** one Letta server; every module's agents namespaced `gf_*`; the
  DocEngine's fleet pattern (Postgres-backed jobs, additive ensure-loop) is the
  template for all future agent work.

---

## 5. Method — the structured, repeatable approach

Every module follows the **same disciplined loop** (proven on DocEngine + TMS T1):

1. **Delta-first analysis.** Before writing code, diff the imported prototype
   against what the platform already has (T1's Explore-agent delta report is the
   template). **Never rebuild what exists.** Build only the genuine gap.
2. **Additive migrations + schema lockstep.** New tables/columns only; regenerate
   `schema.tasks.sql` from alembic-head via pg_dump; the CI drift gate enforces
   lockstep; every migration must downgrade cleanly.
3. **GxP guardrails, always on.** Never fabricate pharmaceutical data — unknown
   values stay blank for a human. Controlled documents ship only on
   `pp_verify → RESULT: PASS`. Every GMP record is audited and RLS-scoped.
4. **Test-first, offline where possible.** pytest for backend, node --check +
   Playwright for frontend, faked-Letta client for pipeline logic. Full local
   gate before any deploy.
5. **wwf_mass only → live smoke → owner approval → prod.** Live verification on
   the test stack (real Letta, real DB, tt.* accounts) before the owner-gated
   promotion. Prod is never touched autonomously.
6. **Adversarial verification for correctness-critical work** (canon decisions,
   regulatory checks, cycle guards).

---

## 6. Sequenced roadmap (dependency-ordered)

### Phase 0 — DocEngine ✅ *(complete, on test)*
Dedicated Letta doc-AI service; pp-document-suite adopted completely;
questionnaire→SOP/annex pipeline; hard PASS gate; deployed + live-verified on
wwf_mass. Remaining: owner acceptance → prod.

### Phase 1 — Task-Management System (priority #1) ✅ *(complete on wwf_mass)*
The owner's explicit #1-to-production. All four increments built, tested,
deployed, and live-verified against real auth + real data on wwf_mass
(backend v44 / frontend v66 / migration 0017):
- **T1** — node-kind task tree, dependency graph with a cycle guard, and the
  pre-existing `handoffs` table surfaced as a full propose/accept lifecycle.
- **T2** — in-app "what did my team do" digest + a real stale-regex bug fix
  in the notifications inbox filter. Emailed digests / quiet-hours push
  explicitly deferred (no SMTP/push channel exists — see
  docs/RESEARCH-NOTIFICATIONS-2026-07.md's own v2 path); building either now
  would be unenforceable dead code.
- **T3** — AI-native planning reusing the existing data-driven agent catalog
  (`app/api/ai.py`): `workload_balance` + `next_week_plan` catalog entries,
  and `dependency_advisor` scoped to a single task's family.
- **T4** — full gate: 298/298 backend tests, zero schema drift, DEPLOY.md
  promotion checklist.
**Exit:** awaiting the owner's tests + explicit approval to promote to prod
(`docs/DEPLOY.md` "Task-Management System v2" section has the exact steps).

### Phase 2 — QC LIMS module ✅ *(U1–U6 on wwf_mass, 2026-07-16)*
Assimilate the QC-domain corpus (`qc-lims-ao` primary + `QC_LIMS_APP` +
`QC_APP` + `cannabis-sample-tracker`) into ONE native module: sample lifecycle
(sample→test→result→OOS→CoA→release), specifications, sampling requests, custody,
Annex-11 audit. Regulatory authority where prototype and SOPs disagree =
**approved QCSOP 001–024** (Drive `1oPEIlNTWMutZIineO6Pb…`).
**Depends on:** DocEngine (controlled forms/CoA), TMS (lifecycle patterns).

Six units built, tested, and deployed to wwf_mass (migrations 0018–0026) —
see `docs/DEPLOY.md`'s "QC LIMS module" section for the full breakdown:
- **U1** specifications (0018), **U2** samples + lifecycle/genealogy (0019),
  **U3** CoA + test results with the auto-quarantine hook (0020),
- **U4** OOS investigations + CAPA (0021),
- **U5** custody cluster — sampling requests (RQS, 24h window) + field records
  (SFR) + chain of custody (0025),
- **U6** the three standalone JSONB leaves — `qc_water_tests` /
  `qc_stability_studies` / `qc_sample_transports` (0026), no cross-dependencies.

The QC-LIMS domain rebuild is now feature-complete against the `qc-lims-ao`
prototype. Prod promotion is owner-gated, pending explicit approval.

### Phase 3 — Certificate pipeline (CoA in → COQ out) ✅ *(complete on wwf_mass, 2026-07-16)*
`CoA_TRACK` + `COQ_GEN` + the QC-LIMS CoA parts reconciled into **one**
extract→verify→generate pipeline on the DocEngine core — built once, **not** two
separate services. Four units (migrations 0022–0024, 0027):
- **U1 — COQ out** (0022): `POST /qc/certificates/{id}/coq` renders a RELEASED
  certificate to a PASS-gated bilingual `.docx` Certificate of Quality via the
  DocEngine; QP-gated + a GxP data gate (every result must comply).
- **U2 — CoA in** (0023): register an incoming supplier/contract-lab CoA,
  transcribe + server-grade its fields against the spec, discover unknown labels
  in an adaptive review queue (map-once → auto-map), promote into a DRAFT ECOA
  certificate + results carrying source provenance.
- **U3 — verify loop** (0024): reconcile a promoted certificate against its
  source eCoA; auditable `qc_coa_verifications` record (VERIFIED/DISCREPANCY).
- **U4 — retrieval Q&A** (0027): `qc_coa_chunks` (Postgres FTS `tsvector` + GIN)
  with `POST /coa-qa` returning **cited** passages as a grounded answer — an
  app-local, records-zone retrieval over ingested CoAs that never fabricates a
  synthesis (no match → `grounded=false`, empty answer). Free-form document
  authoring still belongs to the DocEngine's Letta fleet.
Full flow live-verified end-to-end.

### Phase 4 — Cross-cutting hardening + production cutover — NOT STARTED (owner-gated)
Consolidate the retired Phase-1 `qms-api` shell, unify the nav zones, full
security/audit pass, Letta ops backlog (`docs/LETTA-OPS-BACKLOG.md`), and the
staged owner-approved promotion of each landed module to prod. **This phase is
the owner's decision to open** — it begins with the owner's acceptance tests on
wwf_mass and an explicit go for the first prod promotion.

---

## 7. Risk register & open decisions

| Risk / decision | Impact | Mitigation / needs owner input |
|---|---|---|
| **Duplication across imported repos** | Wasted effort, divergent CoA data | The §3 consolidation (one certificate pipeline) is mandatory, not optional |
| **Live prod stability (25 users)** | A bad migration hurts real work | Test-first + owner-gated prod is the hard rule; additive-only migrations |
| **Letta ops fragility** (Rust-bridge decode bug, provider-enum unwritable, master-key rotation, PQ1 outlier) | Agent features can silently degrade | Use direct REST; additive `gf_*` only; backlog documented; back up pgvector before any Letta upgrade |
| **GxP scope creep** onto the ops zone | Regulatory exposure | The two-zone boundary in SCOPE.md stays structural (separate schema/lifecycle/labels) |
| **CoA/COQ regulatory correctness** | A wrong release certificate is a serious GMP event | Never fabricate; PASS-gate; cite real specs; QP sign-off in the workflow |
| **Owner decision — QC LIMS depth** | Determines Phase-2 size | Ask before Phase 2: full LIMS vs CoA-focused first cut |
| **Owner decision — validation posture** | Affects how formal the GMP lifecycle must be | Confirm before Phase 3 e-signature/lifecycle formality |

---

## 8. Immediate next actions (updated 2026-07-16)

Phases 0–3 are **complete on wwf_mass** and the QC LIMS module is now
feature-complete (U1–U6 + the full certificate pipeline U1–U4). The remaining
work is **owner-gated** or hardening, not net-new features:

1. **Owner acceptance on wwf_mass → prod promotion.** The single biggest
   outstanding decision. Everything built this cycle (DocEngine, TMS, QC LIMS
   U1–U6, the certificate pipeline U1–U4) sits on wwf_mass only; prod is at
   alembic `0016`. `docs/DEPLOY.md` carries the exact promotion recipe + verified
   image tags (backend `v52`+, frontend `v73`+, migrations 0018–0027).
2. **Phase 4 hardening** — the next engineering increment (nav-zone unify, retire
   the `qms-api` shell once the registry read-path fully moves to the DocEngine,
   a security/correctness pass over the QC + certificate surface, doc
   consolidation, Letta ops backlog).
3. **Infra:** GitHub Actions CI has been failing at the workflow-startup level
   (all jobs die in seconds, no logs; a quota/billing or runner issue, not a
   code failure) — needs an owner-side re-run / Actions-minutes check. Merges
   this cycle relied on the local gate (up to 360 backend tests) + live smokes.
4. Keep this document current as each phase lands.

---

*Guardrails recap (never relax): never commit secrets; never fabricate
pharmaceutical data; ship controlled documents only on `RESULT: PASS`; deploy to
wwf_mass only, prod only on explicit owner approval; never blind-flip the live
Letta agents; back up the pgvector volume before any Letta upgrade.*
