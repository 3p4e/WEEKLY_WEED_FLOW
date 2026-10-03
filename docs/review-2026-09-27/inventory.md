# Weekly Weed Flow / GrowFlow — consolidated inventory of every addition

Prepared 2026-09-27 for the owner's request of 2026-09-27T04:32 ("consolidate every
addition to the weekly workflow application that we have made"). This is a
catalogue, not a bug hunt: what the application now contains, where each piece
came from, whether it runs in production, and whether the owner asked for it.

## How this was compiled (and one correction to the brief)

- **Commit history.** The working clone at `/home/user/WEEKLY_WEED_FLOW` is
  **shallow** (`git rev-parse --is-shallow-repository` → `true`); it shows 314
  commits and hides everything between 2026-07-17 and 2026-08-22 (the whole of PR
  #38) plus the first days of July. A full blobless clone of
  `github.com/3p4e/WEEKLY_WEED_FLOW` was made in the scratchpad: the branch
  `claude/weekly-read-flow-setup-yft7if` at `807d60f` actually has **657
  commits** (29.06 → 27.09.2026). Everything below uses the full history.
- **Pull requests**: 55 opened (GitHub MCP `list_pull_requests state=all`). The
  branch was merged into `main` 20+ times; PR #52 (the rest of the branch,
  45 commits) is open. `main` also carries 3 commits that are *not* on the
  branch (PR #54, work record).
- **Code**: `backend/app/api/*` (24 routers + 20 QC modules, **274 routes**),
  `web/gf/*` (61 JS files), `docengine/app/*`, both alembic chains
  (tasks `0001–0069`, users `0001–0012`).
- **Docs**: all deploy records (`DEPLOY.md` + nine dated `DEPLOY-2026-*.md`),
  `HANDOFF.md`, `MASTER-PLAN-2026-08.md`, the feature/design docs.
- **Owner intent**: `owner-messages.md` (246 messages, 2026-08-27 → 09-27) cited
  as `owner <timestamp>`. Earlier owner requests are not in that log; for them the
  citation is the commit message that records the request ("Owner request",
  "Owner directive", "owner's mockup", "CEO's plan") — marked `owner (commit
  <sha>)`. `—` means no owner request could be found for it (agent-initiated,
  review-driven, or pre-log with no citation).

### What "Live" means

Production (HANDOFF.md, checked 2026-09-27 02:25 UTC) runs **backend + scheduler
`v92`** and **frontend `v133`**, both built from `cbfae38` (2026-09-06), and
**docengine `v26`** built from `df1568b` (2026-09-07), whose `docengine/` tree is
byte-identical to `cbfae38`'s. Alembic in production: tasks **0069**, users
**0012**. I verified per service that the only commits after those builds that
touch a service subtree are `9180b5a` (backend `requirements.txt`), `329c4b7`
(`web/e2e/` — stripped from the image, test-only) and `1376253`
(`docengine/Dockerfile`).

| Tag | Meaning |
|---|---|
| **LIVE** | code is in the running v92 / v133 / v26 images |
| **LIVE·inactive** | shipped, but unusable until an operator/data step happens (named in the row) |
| **RETIRED** | was shipped, later removed or switched off |
| **NOT DEPLOYED** | exists in git but is not in any running image |
| **OFF-APP** | a deliverable or service outside the three app images |

---

## Summary

| # | Functional area | Additions |
|---|---|---:|
| 1 | Tasks, weekly planning & weekly documents | 19 |
| 2 | People, roles, departments & access | 10 |
| 3 | Notifications, automation & scheduler | 5 |
| 4 | Reports, analytics, executive & audit readiness | 4 |
| 5 | QC / LIMS (specs, samples, CoA/eCoA/iCoA, CoQ, OOS, potency & products, custody, genealogy, signatures, labs) | 33 |
| 6 | Cultivation & propagation | 11 |
| 7 | Biosecurity, decontamination & waste | 5 |
| 8 | Facility & floor plan | 6 |
| 9 | QMS Studio, DocEngine, AI assistant, Letta, RAGflow | 20 |
| 10 | Admin, demo, audit trail & security hardening | 9 |
| 11 | UI shell & design system | 14 |
| 12 | Infrastructure: CI, deploy, backups, watchdog, runners, agent helpers | 14 |
| 13 | Deliverables and tools outside the app images | 11 |
| | **Total** | **161** |

Plus: 81 Alembic migrations (table at the end), 17 designed-but-not-built items,
and the built-but-not-deployed / built-but-not-reachable lists.

---

## 1. Tasks, weekly planning & weekly documents

| ID | Addition — what it does | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| T01 | **Task tracker core**: tasks with priority/status/owner/helpers, work weeks (Fri→Thu), departments, board and week views. | `api/tasks.py` (`/tasks`, `/weeks`, `/departments`), `gf/views.js`, `render.js`, `integrate.js`, `data.js` | `b43c7c2`, `55e734a` 2026-06-29 (PR #1) | LIVE | owner brief (`docs/SPEC.md`) |
| T02 | **Collaboration**: comments, multi-assignee with accept/decline acknowledgment, cross-department handoffs with resolve. | `api/collab.py` (9 routes), `gf/collab.js` | `f49163d` 06-30 (#1); handoff-resolve deadlock fix `602af67` 07-19 | LIVE | owner brief (SPEC "Assignment lifecycle") |
| T03 | **Weekly report + plan** (Fri→Thu) with activity time band and AI insight pins. | `api/reports.py` `GET /reports/weekly`, `gf/report-view.js` | `a51297c` 06-30 (#1) | LIVE | owner brief (SPEC "Work-week cycle") |
| T04 | **v2 task model + two databases**: identity DB split from work DB; work sessions classified regular/overtime/night/weekend (Europe/Skopje); task links, type, reference code, blocker, recurrence (auto next instance), due date, outcome, archive; date-only sessions. | `api/tasks.py` sessions/links, `gf/worklog.js`; tasks `0001`, `0003`; users `0001` | `560555e` 07-04 (#2); `24ded42` 07-04; `4d7c314` 07-04 | LIVE | — |
| T05 | **Effort capture** (estimated/actual hours). Hour-sum metrics were later removed app-wide by owner decision. | `api/tasks.py`, `reports.py` | `69cf6b8` 07-03; removal `66c17c9` 07-15 | LIVE (hour sums RETIRED) | removal: owner (commit `66c17c9`) |
| T06 | **Capture ingestion**: `POST /capture/import` idempotent upsert keyed on `external_ref`, Import view, and a one-tool claude.ai/Cowork MCP connector (`submit_capture`). | `api/capture.py`, `gf/import-view.js`, `connector/server.py`; tasks `0002` | `fd3c00f` 07-04 (#2); connector image `wwf-capture-mcp:v2` 2026-08-26 | LIVE | — |
| T07 | **Weekly Document Engine**: compile → review → lock → PDF/HTML export for the weekly plan and report; locked documents immutable at DB level; per-department documents + submission status; range export. | `api/documents.py` (10 routes), `gf/document-view.js`; tasks `0007`, `0008`, `0010` | `cfb6acd` 07-06 (#6); `2da8d79` 07-07 (#7); `4af8705` 07-12; `b215c60` 07-11 (#14) | LIVE | — |
| T08 | **AI Intake**: paste an email/plan → Letta extracts tasks+subtasks → review → adopt; bilingual МК \| EN on manual save; on-demand plan/report for any week or range. | `api/intake.py` (`/intake/extract`, `/intake/bilingual`), `gf/intake-view.js` | `23a2c8f`, `d96f20c`, `cc2728a` 07-08 (#9) | LIVE·inactive — needs AI bindings (see A01) | — |
| T09 | **Per-department task attributes** (jsonb) with bilingual department templates, department home screens, board tree rendering, owner/CEO/COO notes highlighted on cards. | `api/tasks.py`, `gf/dept-templates.js`, `gf/depthome-view.js`; tasks `0011` | `73a0e11`, `8958f03` 07-12 (#19); `b215c60` 07-11 (#14) | LIVE | — |
| T10 | **Subtask lifecycle**: subtask completion rules, explicit completion %, subtask status picker, "Add subtask" at any depth. | `api/tasks.py` `/progress`; tasks `0014` | `1fde02a` 07-14, `f9f6aa8` 07-15 (#23), `7c72c01` 07-18 | LIVE | owner (commit `f9f6aa8`: "the owner's mockup") |
| T11 | **TMS T1 dependency graph** + `node_kind` + handoff API + `GET /tasks/tree`. | `api/tasks.py` dependencies/tree; tasks `0017` | `bd82704`, `0107e25` 07-16 (#23) | LIVE (tree endpoint has no UI caller — `taskTree` unused in `web/gf`) | — |
| T12 | **Workflow sign-off (TMS T5)**: submit → approve/reject, QP quality block, second-person rule, append-only history. | `POST/GET /tasks/{id}/workflow`; tasks `0037` | `0cf50a2` 07-21 (#38) | LIVE | — (SUMA assimilation) |
| T13 | **Task surface wiring**: archive round-trip, full recurrence editor, outcome display, digest. | `gf/task-extras.js` | `96adcf9`, `bf496f2` 07-19 (#38) | LIVE | — (audit found backend features with no UI) |
| T14 | **Full-screen task create page and Task Detail screen** (Mass Weed design). | `gf/task-detail-view.js`, `integrate.js` | `22c107a`, `61e1563`, `70277a9`, `d0ca93a`, `b4418c2` 07-31 (#38; frontend v115–v120) | LIVE | owner (commit `70277a9`: "Owner's explicit ask") |
| T15 | **My Day and Approvals queue** (pending acknowledgments, later unified sign-off queue incl. CoQ drafts and doc locks). | `api/approvals.py` `GET /approvals/pending`, `gf/approvals-view.js`, `gf/myday-view.js` | `0cc2f6a` 07-15 (#23); MW-1 `5b521cb`, `e1c237a` 08-05 | LIVE | owner mockup (commit `0cc2f6a`) |
| T16 | **Calendar, workload, ⌘K palette, team roster, full-page search**. | `gf/calendar-view.js`, `workload-view.js`, `cmdk.js`, `search-view.js` | `0c0e827` 07-13 (#22); `b725bb5` 08-05 | LIVE | owner mockup (#22) |
| T17 | **Tasks reference the cultivation batch** they act on; a batch phase move generates that phase's task set. | `tasks.batch_id`, `api/cultivation.py` `_generate_phase_tasks`; tasks `0054` | `36b414f` 2026-08-05 (#38) | LIVE | owner (CEO's plan, `docs/CULTIVATION-DESIGN-2026-07.md`) |
| T18 | **Facility clock**: every "today" is Europe/Skopje (`facility_today()`), in Python, in SQL, and in document numbers; Sunday week-selection fix. | `app/worktime.py`, `tests/test_facility_clock.py` | `9a73faf`, `7d21baf`, `61a9817`, `eb81f8a` 07-30; `e01733a` 08-14; `60909d5` 08-30 | LIVE | — (bug-driven) |
| T19 | **qcm.blani task restructuring** (231 tasks → 39 bilingual themes → document → version hierarchy), applied to production by SQL. | `backend/scripts/oneoff_qcm_*.sql`, `capture/qcm-theme-map-*` | `9ca860a`, `1d93599`, `d011718` 07-12/13 (#19) | RETIRED — data deleted by the owner-ordered wipe of 2026-07-30 | — |

## 2. People, roles, departments & access

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| R01 | **Account provisioning + first-login password change**; admin edit / reset password; "Removed accounts" view with permanent purge; deleted usernames no longer squatted. | `api/auth.py` (11 routes), `integrate.js` | `0cc7109` 06-29; `9aca046` 07-05 (#4); `b4f31c8`, `26a5515` 07-10 (#13) | LIVE | — |
| R02 | **Role model** (7 reshapes): DEP_MGR/PROJECT_LEAD removed, executives + department managers + QP, SE_MGR/MU_MGR, OWNER (executive tier), QA_AUDITOR removed, IR_MGR. | `app/roles.py`; users `0002`–`0005`, `0012`; tasks `0004`, `0005`, `0009` | `a7194df` 07-02; `35c4fa1` 07-04; `a466bbd` 07-05; `b2a2bb8` 07-09; `36a5b7a` 07-10; `5436f17` 09-05 | LIVE | OWNER: — ; IR_MGR: owner 2026-09-05T17:44 |
| R03 | **Department taxonomy**: single QC, bilingual sector names + abbreviations, Security department; `POST /departments` + ADMIN "Add department" UI. | `api/tasks.py`, `gf/data.js` | `58f5b55` 07-09 (#10); `8723230` 07-12; `3ee8202` 07-19 | LIVE | — |
| R04 | **Department scoping**: managers see/write only their department; write-bypass closed; forwarded-IP trust narrowed. | `app/deps.py`, `api/tasks.py`, `collab.py` | `b215c60` 07-11 (#14); `9e73932`, `cd97a14`, `2fb90c4` 07-12 (#17); `cf50d66` 07-14 | LIVE | — |
| R05 | **Department model rebuilt against the facility**: Cultivation runs clone → harvest cut, Production takes over from the cut, Irrigation department + manager, Cloning and Nursery as sub-departments, scope = department + descendants (`dept_family()`), rooms belong to departments, clone room kinds. | `api/tasks.py`, `cultivation.py`, `harvest.py`, `facility.py`; tasks `0064`; `docs/DEPARTMENT-MODEL-2026-09.md` | `5436f17` 2026-09-05 (PR #52) | LIVE·inactive — rollout steps 4–6 of PR #52 (create departments, provision IR_MGR, re-kind clone rooms); HANDOFF lists the rollout with the unmerged PR and no record says it was done | owner 2026-09-05T17:44 |
| R06 | **Role-based module switcher**: six modules (Tasks, QC & QMS, Cultivation & Facility, Biosecurity & Waste, Audit & Compliance, Analytics & Executive), picker at login, views/⌘K filtered by module. | `gf/modules.js` | `d3c2821` 08-19, `2da4053` 08-21 (#38); live in frontend v129 (2026-08-24) | LIVE | — |
| R07 | **Test-account matrix** and API-only provisioning script. | `backend/scripts/provision_test_accounts.py`, `docs/TEST-ACCOUNTS.md` | `8723230`, `03ffc8c` 07-12/13 (#19) | LIVE (script) | — |
| R08 | **Case-insensitive unique usernames**. | users `0011` | `1a70e78` 08-26 (#38) | LIVE | — (audit) |
| R09 | **Server owns the password-length rule** on the first-login screen (client refuses only empty). The owner's "username = password" trial accounts and relaxed minimum were a *production configuration and data change* (env `PASSWORD_MIN_LENGTH`, account renames, `qc_mgr` trial account) — not in git; repo default stays `password_min_length = 12`. | `gf/integrate.js`; `app/config.py:44` | `03222f7` 09-04 | LIVE (probably frontend v132, whose contents are unrecorded — UNVERIFIED) | owner 2026-09-04T14:18, 14:32, 14:51, 15:05 |
| R10 | **Settings panel** (Preferences / Security / AI / Account) incl. the ADMIN "AI agents" binding tab. | `gf/integrate.js` | `0941b6c` 07-05 (#4) | LIVE | — |

## 3. Notifications, automation & scheduler

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| N01 | **Events + per-user inbox + activity feed** (append-only events, recipient-only RLS, coalescing). | `api/notifications.py` (7 routes), `app/notify.py`, `gf/notifications-view.js`; tasks `0013` | `dd4a949` 07-15 (#23) | LIVE | — (design `RESEARCH-NOTIFICATIONS-2026-07.md`) |
| N02 | **Due-soon scan, unassign and @mention notifications**. | `app/duescan.py`, `collab.py` | `66c17c9` 07-15 (#23) | LIVE | — |
| N03 | **Canned automation rules**: CAPA going *stuck* notifies QA+QP; validation going stuck notifies QP. Fixed two-rule set, not a rule builder. | `app/automation.py`; tasks `0016` | `13c8f93` 07-15 (#23) | LIVE | owner (commit: "owner's suggestion queue") |
| N04 | **In-app team digest** (`GET /notifications/digest`). | `api/notifications.py` | `641cb27` 07-16 (#23) | LIVE | — |
| N05 | **Weekly snapshot scheduler**: separate container; Thursday 14:00 Skopje; weekly report + next-week plan via `wwf_*` Letta planner agents, pinned into the app; self-heal on startup. | `backend/scripts/scheduler.py`, `weekly_snapshot.py`, `planner_prompts.py` | `69cf6b8` 07-03 (#1); source-id guard `ed21fae` 08-22 | LIVE (`scheduler` runs v92) | — |

## 4. Reports, analytics, executive & audit readiness

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| P01 | **Executive Overview** (Operations + Direction strips for CEO/COO/Owner) and role-aware landing. | `gf/views.js`, `integrate.js` | `b215c60` 07-11 (#14), `4fabeb2` 07-11 | LIVE | — |
| P02 | **Executive report cockpit**: per-department submission chips, KPI band, drill-down, PDF + interactive HTML export. | `gf/execreport-view.js`, `api/documents.py` `/status`, `/export.html` | `8958f03`, `4af8705` 07-12 (#19); MW-1 `13abfc2` 08-05 | LIVE | — |
| P03 | **Analytics**: cross-week trends (deliberately hour-free) + yield-domain band from harvests. | `api/reports.py` `/reports/analytics`, `gf/analytics-view.js` | `834b5a0` 07-15 (#23); `3e17a4a` 08-05 | LIVE | owner (commit: "owner's suggestion queue") |
| P04 | **GMP audit-prep readiness tracker** (SUMA assimilation): per-programme rollup (MK-GMP / EU-GMP / SOP writing), milestone timeline, overdue flags, over `tasks.tags`. | `api/reports.py` `/reports/audit-prep`, `gf/auditprep-view.js` | `bb96d2d` 07-16 (#35); prod v54/v76 (#36) | LIVE | owner approved prod promotion (commit `437a615`) |

## 5. QC / LIMS

The QC subsystem is 20 modules and **109 routes** under `/qc` (`backend/app/api/qc/*`,
split out of a monolith in `1a1efaf` 07-23). It was a native rebuild of the
`QC_LIMS_Ao` prototype (imported `50f9fc3` 07-16 "on the owner's directive", later
deleted from the repo `64072b6` 07-24), then aligned to the Head-of-QC URS v0.1
(`4f18290` 07-20), QCSOP 011 v3 and QCSOP 012 v3.

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| Q01 | **Specifications master data** (spec + parameters, approve). | `qc/specs.py`, `gf/qcspec-view.js`; tasks `0018` | `67db775` 07-16 (#23) | LIVE | owner (URS / directive `50f9fc3`) |
| Q02 | **Samples + sampling plans + lifecycle**; terminal-sample freeze; second-person gates. | `qc/samples.py`, `gf/qcsample-view.js`; tasks `0019` | `b819433` 07-16 (#23) | LIVE | owner (directive `50f9fc3`) |
| Q03 | **Certificates of analysis + test results**: create, add results, revise, void, translation-verified. | `qc/certificates.py`, `gf/qccoa-view.js`; tasks `0020` | `3a70d23` 07-16 (#23) | LIVE | owner (directive) |
| Q04 | **OOS investigations** (Phase I/II, QP-gated disposition) + append-only OOS register + notifications + derived CAPA list; later per-org OOS numbering. | `qc/oos.py`, `gf/qcoos-view.js`; tasks `0021`, `0062` | `3cf212f` 07-16 (#24); `2dc01ae` 08-26 | LIVE | owner (directive) |
| Q05 | **Certificate of Quality generation** on the DocEngine: RELEASED certificate → bilingual PASS-gated `.docx`. | `qc/coq_docx.py`; tasks `0022` | `1213d03` 07-16 (#25) | LIVE | — (roadmap Phase 3) |
| Q06 | **eCoA ingestion** (CoA-in half): register incoming CoA, human transcription, server grading against spec, adaptive unknown-label queue, promote to DRAFT certificate; per-org doc numbering. No OCR. | `qc/ecoa.py` (17 routes), `gf/qcecoa-view.js`; tasks `0023`, `0056` | `d231dea` 07-16 (#26); `8ff9cda` 08-05 | LIVE | — |
| Q07 | **Certificate verify loop**: reconcile a promoted certificate against its source document, per result. | `qc/ecoa.py` `/verify`; tasks `0024` | `e468faf` 07-16 (#27) | LIVE | — |
| Q08 | **Custody cluster**: sampling requests (RQS, 24 h window), sample field records (SFR), per-sample chain of custody; QCSOP 011 v3 fields/taxonomy; one active custody record per physical sample. | `qc/custody.py`, `gf/qccustody-view.js`; tasks `0025`, `0039`, `0063` | `94e6ab8` 07-16 (#28); `96aab36` 07-21; `65cd1af` 08-29 (#42) | LIVE (0063 since backend v91, 08-30) | 0063: review-driven, owner 2026-08-29T15:06 / 08-30T21:26 ("resolve all issues") |
| Q09 | **QC leaves**: water tests, stability studies (+ pull-schedule drawer), sample transports. | `qc/leaves.py`, `gf/qcleaves-view.js`; tasks `0026` | `7f3f9f8` 07-16 (#30); `19f6113` 08-05 | LIVE | — |
| Q10 | **CoA retrieval Q&A** over ingested CoAs (Postgres full-text search, no LLM). | `qc/coa_qa.py`; tasks `0027` | `7f3f9f8` 07-16 (#30) | LIVE | — |
| Q11 | **URS 1**: OOS gate on CoQ issuance, CoQ issuing restricted to QC, lab-verdict capture on eCoA. | tasks `0028` | `702ddb9` 07-20 | LIVE | owner (URS v0.1, Head of QC) |
| Q12 | **URS 2**: certificate supersession chain + computed Total THC/CBD (Ph. Eur. 3028). | tasks `0029` | `eed67f5` 07-20 | LIVE | owner (URS) |
| Q13 | **URS 3**: accredited laboratory master. | `qc/laboratories.py`, `gf/qclab-view.js`; tasks `0030` | `62c4a91` 07-20 | LIVE | owner (URS) |
| Q14 | **URS 4**: certificate register (QCLB 020 §6.13) + numbering-gap report. | `qc/cert_register.py`, `gf/qcregister-view.js`; tasks `0031` | `c6aa8a5` 07-20 | LIVE | owner (URS) |
| Q15 | **URS 5**: 5-working-day eCoA review clock (QCSOP 012 §6.3.1). | tasks `0032` | `d850b1d` 07-20 | LIVE | owner (URS) |
| Q16 | **URS 6**: CoQ mandatory-content manifest (WHO TRS 1010 / Annex 16). | `qc/coq_docx.py` (no migration) | `6d3f1b3` 07-20 | LIVE | owner (URS) |
| Q17 | **URS 7**: lab's stated verdict carried onto the permanent result. | tasks `0033` | `5a3e86d` 07-21 | LIVE | owner (URS) |
| Q18 | **URS 8: Annex 11 electronic signatures** for QC approvals; one signature per (object, meaning, signer); DB-enforced append-only. | `qc/signatures.py`; tasks `0034`, `0060`, `0061` | `61f0ed0` 07-21; `d2d26d4` 08-14; `8c69295` 08-26 | LIVE | owner (URS) |
| Q19 | **URS 9**: source-document custody — originals stored with SHA-256, download. | `qc/ecoa.py` originals / `document-files`; tasks `0035`, `0044` | `7910d35` 07-21; `e40e3b5` 07-28 | LIVE | owner (URS) |
| Q20 | **URS 10: batch genealogy** (m:n blending, closure check, inherited results). | `qc/genealogy.py`, `gf/qcgenealogy-view.js`; tasks `0036` | `1b9aa71` 07-21 | LIVE | owner (URS, decision D2) |
| Q21 | **CoQ house-template layout parity** (D1) + № typography on documents. | tasks `0038` | `2f536db`, `1689d17` 07-21 | LIVE | owner (commit `1689d17`: standing directive) |
| Q22 | **QCSOP 012 Tier 1**: VOIDED state + External CoA Review Checklist (QCT 018); the checklist decider must differ from the filler. | `qc/ecoa.py` checklist; tasks `0040` | `70a8c88` 07-21; `0ab4178` 08-07 | LIVE | decider≠filler: owner decision 2026-08-06 (commit `0ab4178`) |
| Q23 | **QCSOP 012 B+C**: per-type/per-year certificate numbering; **per-batch CoQ aggregation** (C5) with review/void/render; iCoA field/language polish. | `qc/coq_aggregation.py`; tasks `0041` | `98bb49a`, `41c2b7c`, `fb07522` 07-21 | LIVE | owner (QCSOP 012) |
| Q24 | **QP role correction**: QP is Annex-16 batch release only; CoQ is a QC-manager function. CoQ lifecycle deliberately not gated on spec status. | `qc/*` role tuples | `1ff7111` 07-17; `c94e784` 08-07 | LIVE | owner directive 2026-08-06 (commit `c94e784`) |
| Q25 | **QC deep-review remediation** (12 items: `add_result` limits, spec rebind, signing closed certs blocked, register gap semantics, manifest + ISO-scope parity on aggregation render, disposition before approval, review-window stamp, Ph. Eur. 3028 unit consistency, body-size ceiling…). | `qc/*`; tasks `0042`, `0056` | `2e713aa` 07-23; `6ffa74f`…`be3f00b` 08-05 | LIVE | — (agent review) |
| Q26 | **Potency ladders** per cultivar (PP-QC-SPEC-001): tier specs, approve/supersede, disposition; the CoQ freezes the ladder and shows cultivar + grade ("QC Disposition, not QP batch release"). | `qc/potency.py`, `gf/qcpotency-view.js`; tasks `0057`, `0058` | `4199c4f`, `814df80`, `92a5ff1`, `388cac5`, `eb91fdf`, `02f1460` 08-07 | LIVE (superseded for new work by Q30) | owner decision 2026-08-07 (commit `4199c4f`) |
| Q27 | **Bracket-style ladders + 71-strain QCSP 001 catalogue import** as DRAFT specs (the only QC data known to be populated in production: 71 DRAFT ladders, 71 cultivars — `ECOA-MASTER-SYNC-DESIGN` §1). | `qc/potency_import.py` | `9a73fa8`, `f4f55cd` 08-14 | LIVE | owner (handoff archives, commit `e52aa9a`) |
| Q28 | **Batch commercial identities**: per-batch Original → Neu rename, brand, label (Portfolio Master, 78 batches / 3 tranches). | `qc/commercial.py`; tasks `0059` | `0eb915d` 08-14 | LIVE·inactive — shown on the CoA detail only; list/import/edit have **no UI caller** (`qcCommercialIdentities`, `qcImportCommercial` unused) | owner (Portfolio Master, commit `0eb915d`) |
| Q29 | **Internal CoA 3-tier Head-of-QC sign-off chain** (no QP) + status gate so a VOIDED cert cannot render as an iCoA. | `qc/signatures.py`, `spec_html.py`; tasks `0060` | `d2d26d4` 08-14; `cd4fbab` 08-26 | LIVE | owner decision 2026-08-14 (commit `d2d26d4`) |
| Q30 | **Official ImB product catalogue**: 42 products / 22 strains parsed from 48 ImB pages; window stored per product (± 10 % relative of the printed nominal); approve (second QC person) / supersede; conformance (which products a value satisfies); "tested so far" in three labelled strengths of evidence; approving a strain's first product retires its ladder. | `qc/products.py` (9 routes), `app/data/imb_products.json`; tasks `0066`; `docs/PRODUCT-CATALOGUE-2026-09.md` | `0ad6230` 2026-09-05 (PR #52); verification `9d86791`, `e6b416c`, `fe14b98` 09-06 | LIVE·inactive — tables live, but import + second-person approval (PR #52 rollout step 2) is not recorded as done (HANDOFF lists it with the unmerged PR); import/approve/supersede/conformance/potency-history have **no UI** (only the product list in batch registration) | owner 2026-09-05T22:28 ("two specification PDFs are official") |
| Q31 | **CoQ ↔ product link**: `qc_coq.product_id` validated and stored. The product-window verdict is **not rendered** — a product-graded CoQ prints no grade (recorded in `0b3035c`). | `qc/coq_aggregation.py`; tasks `0066` | `0ad6230` 09-05; `0b3035c` 09-06 | LIVE (partial) | owner 2026-09-06T16:29 ("NO for now" on blocking) |
| Q32 | **A4 HTML documents**: ImB per-strain specification page and single-parameter iCoA, served by the backend for print. | `qc/spec_html.py`, `app/data/imb_spec_template.html` | `e82b40a` 08-14 | LIVE | owner decision 2026-08-14 (commit `e82b40a`) |
| Q33 | **QC screens redesigned (MW-1)**: on-screen A4 CoQ preview before export, eCoA intake workbench (stepper, review countdown, SHA-256 custody bar), QC lifecycle UI aligned to the backend state machines. | `gf/qccoa-view.js`, `qcecoa-view.js` | `5d85bd5`, `17ef1e7`, `fc08a32` 07-19; `70dc0e5`, `70cc879` 08-05 | LIVE | owner mockup |

## 6. Cultivation & propagation

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| C01 | **Cultivar master, coded batches, per-plant identity**, phase events, chunked/resumable plant-ID generation, whole-batch phase moves, paginated plant roster (the cultivation board). | `api/cultivation.py` (11 routes), `app/plantids.py`, `gf/cultivation-view.js`; tasks `0045` | `d6b28f4`, `47ba1dd`, `fbad925` 07-30 (#38) | LIVE (production tables `rooms`, `plants`, `plant_batches` were **empty** on 2026-09-06 — DEPLOY-2026-09-06-v92) | owner (commit `d6b28f4`: owner's identity scheme; CEO's plan) |
| C02 | **Room register seed**: 19 real rooms (C171, C176–C185, C88, C150, C158 + 5 corridors), Rooms 1–6 = C180–C185. | `backend/scripts/oneoff_seed_purelyplant_rooms_20260730.sql` (+2 follow-ups) | `886de15`, `1e08e78`, `60d4289` 07-30 | RETIRED — seeded then deleted by the same day's data wipe; not re-seeded (rooms empty on 09-06) | owner confirmed codes (commit `886de15`) |
| C03 | **Harvest / yield record** (wet → dried → closed lots) + **IPM applications** with REI/PHI that block harvest; fills the genealogy `CULTIVATION` edge into the QC lot. | `api/harvest.py` (9 routes), `gf/harvest-view.js`; tasks `0051` | `036c183` 07-30 (#38) | LIVE | owner (CEO's plan) |
| C04 | **Irrigation / feeding record** (room-level solution log: volume, feed/runoff EC/pH, recipe, method) → own view and department in September. | `api/irrigation.py`, `gf/irrigation-view.js`; tasks `0052` | `75f2a22` 08-05; view `5436f17` 09-05 | LIVE | view/department: owner 2026-09-05T17:44 |
| C05 | **Batch registration from the product specification** by QA, CEO, COO or cultivation manager; cultivar chooser shows each strain's grade line; QA can move batches and edit the cultivar master; a batch names the product it is grown to. | `api/cultivation.py`, `gf/cultivation-view.js` | `3ebb79a` 09-05; `b4c0dee` 09-06 (PR #52) | LIVE | owner 2026-09-05T20:08, 22:28 |
| C06 | **Batch journey**: plan legs computed server-side (cloning 7–14 d with import quarantine allowance, vegetation 14–17 d, flowering 42–63 d); one animated lane per open batch on a shared axis, green inside the window, amber past it. | `api/cultivation.py`, `gf/cultivation-view.js` | `3ebb79a` 09-05; `08c2209` 09-06 | LIVE | owner 2026-09-05T20:08 (animated bar), 22:28 (multiple batches, phase days) |
| C07 | **Mother-plant bank and clone runs** (propagation). | `api/propagation.py` (11 routes), `gf/propagation-view.js` (tabs inside Cultivation); tasks `0065` | `3ebb79a` 09-05 | LIVE | owner 2026-09-05T20:08 |
| C08 | **Selection campaigns + clone lineage**. | `api/propagation.py` `/campaigns`; tasks `0066` | `0ad6230` 09-05 | LIVE | owner 2026-09-05T22:28 (`_S3` campaign in the ID) |
| C09 | **Mother / clone identity** `GP26_S1M03-2_nnn` composed by the server from columns; cuttings numbered at run creation (`…-03.147`); `times_cut`; mother's strain potency "tested so far" (average + individual Total THC). | `api/propagation.py` `/mothers/{id}/potency`; tasks `0067`; `docs/PROPAGATION-2026-09.md` | `7fe5418`, `cd15825` 09-06; `87c3053` 09-06 | LIVE | owner 2026-09-05T22:28 (ID convention, potency on mothers) |
| C10 | **Trichome maturation checks**: microscope, magnification, sample sites, clear/cloudy/amber split, verdict — the documented record behind a harvest date (gates nothing). | `api/trichome.py`; tasks `0066` | `b4c0dee` 09-06 | LIVE (create is in the UI; the list call `trichomeChecks` has no UI caller) | owner 2026-09-05T22:28 |
| C11 | **Batch number convention** `GP072501` pre-filled on registration (strain abbreviation + mmyy + ordinal). | `api/cultivation.py` `/batch-code`, `gf/codefield.js` | `3ebb79a` 09-05; `9e99643` 09-05 | LIVE | owner 2026-09-05T22:28 |

## 7. Biosecurity, decontamination & waste

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| B01 | **HLVd decontamination campaign**: per-room signed 5-step cycle, white-cloth gate before bleach, strip-verified bleach log, clean-lock seal, RT-qPCR swab release gate (QA-only release, positive needs an action). | `api/decon.py` (18 routes), `gf/decon-view.js`; tasks `0046` | `b63a8a1`, `74dc400`, `926da09` 07-30 (#38) | LIVE | owner (CEO's HLVd plan, commit `b63a8a1`) |
| B02 | **Frozen positive controls + tool-sterilisation log** (10,000 ppm). | `api/decon.py`; tasks `0047` | `7fb9c00` 07-30 | LIVE | owner (CEO's plan) |
| B03 | **Destruction / waste manifest**: draft → sealed → witnessed (two-person) → disposed, per-batch reconciliation incl. destroyed-but-never-manifested flag. | `api/waste.py` (9 routes), `gf/waste-view.js`; tasks `0048` | `89ee33e` 07-30 | LIVE | owner (CEO's plan) |
| B04 | **Corridor cleaning cadence** (trigger-classified, overdue derived, joined to waste movements). | `api/decon.py` `/corridors`; tasks `0049` | `91a5259` 07-30 | LIVE | owner (CEO's plan) |
| B05 | **Biosecurity events**: AHU filter pull/refit, disinfection mat, contact plates / sentinel bioassay, gowning — one table with a `kind`; fail/below-spec needs an action. | `api/biosecurity.py`; tasks `0053` | `8d7d9e8` 08-05 | LIVE | owner (CEO's plan §5c) |

## 8. Facility & floor plan

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| F01 | **Facility board**: live plants per room, strain, cultivation phase. Its own batch write path was retired on 2026-08-26 (critical crash / dual-write); batches are managed only in Cultivation. | `api/facility.py` (3 routes), `gf/facility-view.js`; tasks `0015` | `89f2d2a` 07-15 (#23); `70378a1` 08-26 | LIVE (batch editor RETIRED) | owner (commit `89f2d2a`: "owner's top request") |
| F02 | **As-built facility layout register**: 191 rooms read as vector text off the Archicad A0 ground-floor sheet (code, MK/EN names, area, perimeter, wing, zone, regime, sheet anchor); import endpoint; judgement columns (grade, regime, department, link to an operational room) editable, sheet facts not. | `api/facility_layout.py` (4 routes), `app/data/facility_layout.json`; tasks `0068`; `docs/FACILITY-LAYOUT-2026-09.md` | `c95f653`, `41d5a76` 09-06 (PR #52) | LIVE·inactive — import (PR #52 rollout step 3, or the "Load the ground-floor plan" button) not recorded as done | owner supplied the sheet (commit `c95f653`) |
| F03 | **Floor plan tab — "Drawing"**: the scanned sheet with one pin per room, zone legend doubling as filter, search, zoom, room card. | `gf/facility-view.js`, `web/assets/facility-ground-floor.png` | `41d5a76` 09-06 | LIVE | owner (as F02) |
| F04 | **Floor plan tab — "Plan"**: app-drawn SVG from per-room rectangles fitted to the drawing (size exact from area+perimeter, position fitted to wall ink, `box_conf` kept; low confidence drawn dashed). | tasks `0069` | `488b869` 09-06; review fixes `cbfae38` 09-06 | LIVE | owner 2026-09-06T01:55 ("another representation") |
| F05 | **Operational rooms linked to plan rooms** (`rooms.facility_room_id`), rooms owned by departments, clone room kind. | tasks `0064`, `0068` | `5436f17` 09-05; `41d5a76` 09-06 | LIVE·inactive — linking (rollout step 7) pending | owner 2026-09-05T17:44 |
| F06 | **Cleanliness grades**: the owner's scheme (EU GMP D / CNC / unclassified cultivation) is recorded in the doc; `facility_rooms.grade` is a manual free-text field on the room card. Nothing is pre-loaded and the plan is **not** colour-coded by grade. | `docs/FACILITY-LAYOUT-2026-09.md` | `c5776ac` 09-07 (doc only) | doc only | owner 2026-09-06T16:29, 18:02 (asked to colour-code rooms by grade) |

## 9. QMS Studio, DocEngine, AI assistant, Letta, RAGflow

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| A01 | **AI gateway + generic function catalog** (12 functions: weekly_summary, voice_capture, task_extract, translate_bilingual, dependency_advisor, corpus_qa, draft_description, progress_digest, risk_flag, template_narrative, workload_balance, next_week_plan), per-org agent bindings, assistant chat drawer, voice capture. | `api/ai.py` (7 routes), `gf/assistant.js`, `voice.js`; tasks `0006` | `b43c7c2` 06-29; `6baa9c0` 07-05; T3 entries `d7a35bb` 07-16 | LIVE·inactive — `ai_agent_bindings` had **0 rows** in production (`docs/AI-FEATURE-INVENTORY-2026-08-23.md`); every function answers `not_configured` until an ADMIN binds agents. No later binding is recorded in git (current state UNVERIFIED). `workload_balance` and on-demand `next_week_plan` have no UI caller. | — |
| A02 | **AI role → capability matrix** (elevated-only functions; dept-scoped grounding). | `api/ai.py` `FUNCTION_ROLES` | `4e9988d` 07-19 | LIVE | owner directive 2026-07-19 (commit) |
| A03 | **AI pins** (scheduler narratives pinned to weeks), JSON-narrative rendering fix, pre-auth `/ai/pins` guard. | `api/ai.py` `/pins` | `f214c83` 07-13; `9c41aad` 08-26; `7a7dc62` 08-27 (frontend v131) | LIVE | — |
| A04 | **QMS Studio federation** to the imported QMS Creator (`qms-creator/`, 995 files, 17 MB) via an internal `qms-api` container: registry, stats, hierarchy, families, knowledge search, download. | `api/qms.py` (7 non-studio routes), `gf/qmsregistry-view.js`, `qmsknow-view.js` | `1c00b8b`, `5c0e128`, `29364ed` 07-15 (#23) | RETIRED — `qms-api` retired 2026-07-16 (`316eb59`, #33); the routes answer 503 "QMS service unavailable"; `qms-creator/` is still vendored | owner request (commit `1c00b8b`), owner-approved retirement (`b23dc22`) |
| A05 | **GrowFlow DocEngine service**: questionnaire-driven drafting of bilingual MK \| EN controlled documents (SOP / annex) by a Letta agent fleet, deterministic gates (bilingual parity, structure/grid), AI §6A audit, `pp_verify`, `.docx`/PDF build; Studio proxy + Create wizard in the app. | `docengine/app/*` (14 routes), `backend/app/docengine.py`, `api/qms.py` `/studio/*`, `gf/qmsstudio-view.js` | `78b6968`, `587e96a` 07-16 (#23) | LIVE (docengine v26) | — (roadmap Phase 0) |
| A06 | **`pp-document-suite` .docx engine recovered into the repo** (previously only inside the Letta container). | `docengine/engine/`, `docengine/pp-document-suite/` | `5e3e2d8` 08-17 | LIVE | — |
| A07 | **Dedicated Letta per stack**, then cutover to `letta-6ou3`, old Letta decommissioned. | `docs/LETTA-*` | design `0e3b7af` 07-19; `7c05310`, `720747c` 07-20; `11a3a42` 08-22; `27aa6dc`, `3f3c3db` 08-23 | LIVE (Letta runs outside the app images) | — (answers an owner architecture question, commit `0e3b7af`) |
| A08 | **RAGflow as the only RAG**: `ragflow_search` tool, datasets instead of Letta sources, stability data separated so release agents cannot see it. | `docengine/agents/ragflow_search.py`, `agents/fleet.yaml` | `7971d65`, `6b380a1` 08-17 | LIVE | — |
| A09 | **`gf_*` agent fleet** (orchestrator, SOP author, annex author, MK↔EN translator, regulatory checker, RACI specialist, QA auditor, app assistant) declared in YAML and reconciled; models DeepSeek via LiteLLM, then Moonshot Kimi K2.6. | `docengine/app/fleet.py`, `agents/fleet.yaml`, `ops/stacks/litellm.config.yaml` | `de52b7b`, `0ad4606` 08-17; `ddc68f4` 08-24 | LIVE | Kimi: owner directive (commit `ddc68f4`) |
| A10 | **§6A repair loop**: a FIX verdict goes back to the author once, sentinel-delimited sections, partial repairs. | `docengine/app/pipeline.py` | `3c21ab1`…`8f69003` 08-17 | LIVE | — |
| A11 | **Fleet training + enforced dataset scope**: mission/corpus/persona blocks, read-only governance blocks, `RAGFLOW_ALLOWED_DATASETS` as a control; pipeline fixes (buffer autoclear, grid gate, 300 s read timeout). | `docengine/app/fleet.py`, `pipeline.py` | `dabb1e2`, `aee2d63`, `7a548a7` 08-27; `c22f58d`…`f11ddd3` 08-29 (PR #41; docengine v22) | LIVE | — (PR opened before the log starts); merge: owner 2026-08-29T12:19 |
| A12 | **Fail-closed scope, credential rotation reconciled, BilingualGap sections persisted**. | same | `85f2941` 08-30 (#43; docengine v23) | LIVE | owner 2026-08-30T21:26 |
| A13 | **Convergent reconcile loop** (revocation propagates, tool detach, orphan sweep), `/fleet/status`, `/health` probes Letta + RAGflow. | `docengine/app/fleet.py`, `main.py` | `dd30f3a` 09-02 (#46; docengine v24) | LIVE | owner 2026-09-02T10:18, 10:34 |
| A14 | **Dataset names mapped to the rebuilt RAGflow tenant** (`eCOA_DB`, `DB01_REG`; stability `eCOA_SS` withheld). | `agents/fleet.yaml` | `c93f4c2` 09-02 (#48; docengine v25) | LIVE | owner 2026-09-02T11:33, 12:29 |
| A15 | **DocEngine Studio chat + presets + direct-edit revise** (freeform or preset instruction → new verified revision; read-only Q&A on a finished document). Three-tier change: frontend + backend proxy went live 09-06, the docengine routes only on 09-07 — 404 for a day. | `docengine/app/presets.py`, `main.py` (`/presets`, `/workflows/{jid}/chat`, `/revise`), `api/qms.py`, `gf/qmsstudio-view.js` | `9d40f5d` 2026-09-04 (PR #52) | LIVE (since docengine v26, 2026-09-07) | owner 2026-09-04T23:06 |
| A16 | **§6A audit enforced on the revision path**, grid gate re-run after repairs, 72-byte bcrypt input fix, client request deadline. | `docengine/app/pipeline.py`, `gf/api.js`, `api/auth.py` | `ff7f481` 09-05 | LIVE | owner 2026-09-05T12:21, 15:24 |
| A17 | **`[NEEDS INPUT: …]` contract**: agents mark unknown facility facts in place; `needs_input` list returned with the job. | `docengine/app/needs.py` | `25f9e8f` 09-05 | LIVE | owner 2026-09-05T15:55, 17:00 |
| A18 | **SOP trial** (analytical-dossier SOP driven through the engine; draft + audit verdict committed). | `docs/trials/2026-09-02-*` | `74f8072` 09-02 (docengine v25 record) | doc | owner 2026-09-02T12:58 |
| A19 | **DocEngine single uvicorn worker** (fixes a post-reboot crash loop). | `docengine/Dockerfile` | `1376253` 09-07 | NOT DEPLOYED in an image (production was switched via its compose file per the commit; whether that survived the VM rebuild is UNVERIFIED) | — (production incident) |
| A20 | **DocEngine job trace** (`docengine.job_events`, `GET /workflows/{jid}/trace`). | `docengine/app/db.py`, `main.py` | `bec2720` 09-18 on `claude/audit-fixes-2026-09` (PR #55, draft) | NOT DEPLOYED, not on this branch | owner 2026-09-18T14:36 ("perform fixes on the finds") |

## 10. Admin, demo, audit trail & security hardening

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| D01 | **Hash-chained audit trail** in both databases, `GET /audit`, `/audit/tables`, `/audit/verify`, audit view; chain-tail advisory lock; missing triggers added; UTC-pinned hash; `created_at` index. | `api/audit.py`, `gf/audit-view.js`; tasks `0012`, `0043`, `0044`, `0050`, `0055`; users `0006`, `0007`, `0009`, `0010` | `916696e` 06-30 (#1); `cf50d66` 07-14; `66e7095` 07-24; `e40e3b5` 07-28; `5dc6321` 07-30; `3071510` 08-05 | LIVE | — |
| D02 | **Row-level security org isolation + coverage tests** (RLS, audit-trigger and demo-wipe coverage guards). | `backend/tests/test_rls_coverage.py`, `test_audit_coverage`, `test_demo_wipe_coverage.py` | `ca5684b` 07-02; `e40e3b5` 07-28; `055581c` 09-06 | LIVE | — |
| D03 | **Security hardening**: CORS scoping, secret-key guard, rate limiting, token revocation, structured request logging, body-size ceilings (incl. chunked bypass), committed cookie jar removed. | `app/main.py`, `security.py`, `logging_config.py`, `web/nginx.conf` | `ca5684b`, `5eeaf38`, `7ccdf2c` 07-02; `ca9b588` 07-23; `0fa6e62` 08-05; `c71b5af` 08-26 | LIVE | — |
| D04 | **Review-remediation waves** (agent reviews): 07-05, 07-11, 07-14, 07-19 (round 3), 07-23 (P0–P2, `0042`), 07-24, 07-28, 08-05, **08-26 (1 Critical / 13 High / 49 Medium / 67 Low; `0061`, `0062`)**, 08-29/30 (`0063` + five latent gaps), 09-05 (design review). | many | e.g. `3b140dd`, `4fabeb2`, `9dd0de2`, `e11c722`, `2e713aa`, `702c595`, `c91ad08`, `3071510`, `70378a1`…`c54fb57`, `85f2941`, `ff7f481` | LIVE | reviews asked by owner 2026-08-29T15:06, 09-05T12:21; earlier waves — |
| D05 | **Demo mode**: first a client-side mock (07-11), replaced by a **live demo** in an isolated `demo` org with one Arrakis / spice-production narrative, reserved number range, backend flag; wipe list completed to every org-scoped table. | `api/demo.py`, `app/demo_org.py`, `gf/demo.js` | `b215c60` 07-11; `e83949f` 07-17; `79f37d5` 07-18; `05a0934`, `87c5c55` 07-19; `055581c` 09-06 | LIVE | narrative: owner direction (commit `79f37d5`) |
| D06 | **Owner-ordered full data wipe** (all application data, 58 → 1 profiles, pre-wipe archive kept on the host). | `docs/DEPLOY.md` §"FULL APPLICATION DATA WIPE" | `433085d` 07-30 | operation | owner (commit `433085d`) |
| D07 | **Non-GMP scope decision** (WWF is a planning tool, not a validated system). | `docs/SCOPE.md` | `4afa6e1` 07-04 | doc | — |
| D08 | **Phase-0 validation package** (intended use, AI inventory, GAMP-5, FMEA, traceability) — the basis, not an executed validation. | `docs/VALIDATION-PLAN-2026-07.md` | `89985e4` 07-21 | doc | — (URS §10.4) |
| D09 | **Health endpoints**: `/health` (liveness), then `/health/ready` requiring both databases (used by deploy smoke and watchdog). | `app/main.py` | `/health` in `916696e` 06-30; `/health/ready` `f60495e` 07-28 (H12) | LIVE | — |

## 11. UI shell & design system

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| U01 | **GrowFlow vanilla-JS SPA shell**, bilingual МК/EN, PWA + service worker, design-tweaks editor (gated). | `web/index.html`, `sw.js`, `gf/core.js`, `render.js`, `main.js`, `tweaks-vanilla.js` | `b43c7c2` 06-29; `24ded42` 07-04 | LIVE | owner brief |
| U02 | **3D WebGL leaf** splash + login entry, used for every logo; hover parallax. | `gf/leaf3d.js`, `entry.js`, `leaf-fx.js` | `b2a1602` 07-06; `9508804`, `400f711`, `c9153c4` 07-09 | LIVE | — |
| U03 | **Dark glass-morphism refactor** (TAL SHIAR / plasma-green). | `gf/app.css`, `views.css` | `90eaeb0`, `c49fb71` 07-09 (#11) | RETIRED (superseded by Mass Weed) | — |
| U04 | **Theme system**: light "Cool Mist", SUMA skin, 30 Carbon skins, picker, random splash skin. | `gf/skins.css` | `af7407e`, `d21cfe9`, `c1c5c2a` 07-10 (#13); `6746971` 07-11 (#15) | RETIRED — exclusive Mass Weed `dade257` 07-17, `ab3a62b` 07-31 | retirement: owner (commit `dade257`) |
| U05 | **Mass Weed skin and design system** from the owner's mockup set (59 pages in `design/mass-weed-mockup/`): tokens, component atoms, octagonal dialogs, department colours, hue schemes. | `gf/mass-weed.css`, `design/` | `0c0e827` 07-13 (#22); `35b2674` 07-14; `13726f6` 07-17; `cb74eec`, `6b159ab`, `0ecb562`, `9fa21ca` 07-30 | LIVE | owner (mockup + "MASS WEED theme all the way", commit `dade257`) |
| U06 | **Popup choosers** replacing every native `<select>`. | `gf/chooser.js` | `2476c39` 07-14; `1f09f64` 07-15 | LIVE | owner mockup |
| U07 | **Navigation rail**: grouped rail, scrollable, Floor group, departments as a tree, empty groups pruned, brand shown once. | `gf/render.js`, `integrate.js` | `c2e9311` 07-15; `70dd224` 07-19; `60f8573`, `0387620`, `7f6daea` 09-06 | LIVE | 09-06 fixes: owner ("sloppy and cheap", cited in commit `0387620`); COO-account bug report (`60f8573`) |
| U08 | **MW-1 page redesigns** (frontend v123–v126): audit, calendar, intake, exec report, workload, my day, analytics, dashboard, approvals, eCoA workbench, leaves, team, CoQ print, search. Facility redesign reverted. | `gf/*-view.js` | `16b7e47`…`b725bb5` 08-05; revert `d212346` | LIVE | owner mockup |
| U09 | **Animation quality pass** (15 plans). | `plans/001–015`, `gf/*.css` | `c13fccf`, `51db304` 08-05 | LIVE | — |
| U10 | **Secure Access login screen**. | `gf/entry.js`, `entry.css` | `5ca4f84` 07-31 | LIVE | owner mockup |
| U11 | **Date picker that opens on the facility's today** (25 inputs converted). | `gf/datepicker.js` | `bee0ea5`, `4bdefb8`, `f38e68b` 09-05 | LIVE | owner 2026-09-05T17:00 |
| U12 | **Code fields with the constant head pre-filled**, caret after it. | `gf/codefield.js` | `9e99643` 09-05 | LIVE | owner 2026-09-05T17:00 |
| U13 | **Board swimlanes, board-by-day, clickable header avatars, modal/mobile fixes**. | `gf/views.js`, `mobile.css` | `24bbc1f`, `c4ebff6`, `c26a7ff` 07-10; `48122f2` 07-05 | LIVE | — |
| U14 | **`web-next` React redesign preview** (M1–M3, PREVIEW_MOCK build). | `web-next/` | `9494aed`, `330bc02`, `b086411`, `575d1b8` 07-06 (#6) | RETIRED — deleted `64072b6` 07-24 (React migration decided against, MASTER-PLAN §2) | — |

## 12. Infrastructure: CI, deploy, backups, watchdog, runners, agent helpers

| ID | Addition | Main files | Introduced | Live? | Owner asked? |
|---|---|---|---|---|---|
| O01 | **Single Docker stack on KVM4** behind Traefik: two Postgres 17 DBs, backend, scheduler, nginx frontend, capture MCP, backup containers. Note: the production `compose.yaml` lives on the host; the repo's `docker-compose.yml` has **no docengine service**. | `docker-compose.yml`, `backend/Dockerfile`, `web/Dockerfile` | `b43c7c2` 06-29; `78f2224` 06-30 | LIVE | owner brief |
| O02 | **Alembic tooling, two chains, schema baselines diffed in CI**. | `backend/alembic_*`, `schema.*.sql` | `7cac4f6` 07-02; `560555e` 07-04 | LIVE | — |
| O03 | **CI (9 checks)** on a self-hosted runner: deps, security scan, backend suite, DocEngine suite, alembic baselines, jsdom frontend suite, Playwright e2e, image build, compose validation; timeouts widened for a starved runner. | `.github/workflows/ci.yml`, `tests/frontend/`, `web/e2e/` | `d1f3bf7` 07-17; `c91ad08` 07-28; `f62e0e4` 09-07; `329c4b7` 09-08 | active (the two September timeout commits are CI-only) | — |
| O04 | **Deploy workflow** with mandatory CI-green gate, snapshot → migrate → per-service swap → smoke. Dispatch is owner-only; the agent deploys through the kvm4-runner `/shell` instead. | `.github/workflows/deploy.yml` | `d5d22b2` 07-09; `9afda0f`, `3b1ee24` 07-30 | active | — |
| O05 | **Nightly migration rehearsal + drift check** on a restored copy of the real backup; drift judged against the default branch. | `.github/workflows/migration-rehearsal.yml` | `9afda0f` 07-30; `0f0cdd8` 08-05; `85f2941` 08-30 | active | re-arm: owner request (commit `0f0cdd8`) |
| O06 | **Watchdog**: host `ops/watchdog.sh` (runner, prod, DBs, CI freshness) as its own container + `watchdog.yml`. Alert channel still unset (MASTER-PLAN Track E). | `ops/watchdog.sh`, `.github/workflows/watchdog.yml` | `9afda0f`, `06509f7`, `6abc05d` 07-30; `bacac42` 08-05 | LIVE (`wwf-watchdog`) | — |
| O07 | **Backups**: daily dump pair + offsite rclone crypt to Google Drive. | `backend/scripts/db_backup.sh`, `offsite_backup.sh`, `docs/BACKUP.md` | `4afa6e1` 07-04 | partly LIVE — on-host daily pair runs; **offsite container not recreated on the new VM** (HANDOFF) | — |
| O08 | **`wwf_mass` parallel test instance** (test-first rule). | `docs/DEPLOY.md` | `1601aee` 07-13 | RETIRED 07-29 (`6a768ac`, owner decision) | owner decision to retire |
| O09 | **CLAUDE.md operating notes + session handoff**. | `CLAUDE.md`, `docs/HANDOFF.md` | `f7934ec` 08-07; `e2c797b` 08-31; `807d60f` 09-27 | doc | handoff: owner 2026-09-27T02:25 |
| O10 | **`gh-runner-wwf` defined in git** + re-registration procedure. | `ops/gh-runner/` | `04b2f91` 09-25 | LIVE (runner rebuilt 09-25/26) | owner 2026-09-24T14:59, 09-25T19:34 |
| O11 | **Agent helpers** `rsh.py` / `gh_api.py` (pre-approvable KVM4 shell and repo-scoped GitHub API). | `ops/agent/` | `66fb0cd` 09-26 | tooling | owner 2026-09-26T11:17, 22:17 |
| O12 | **AI infrastructure on the host**: LiteLLM gateway, RAGflow, Ollama evaluations, disk reclaim (documented, configured outside the images). | `ops/stacks/litellm.config.yaml`, `docs/AI-STACK-2026-08.md`, `docs/DISK-RECLAIM-2026-08.md` | `8e88b8b`…`d6a1b9b` 08-16; `6c24391` 08-16 | LIVE (host services) | — |
| O13 | **WeasyPrint 70.0** (PYSEC-2026-3940). | `backend/requirements.txt` | `9180b5a` 09-25 | **NOT DEPLOYED** (v92 predates it) | — (security scan) |
| O14 | **VM rebuild and restore** (backup of the whole estate to Drive 09-08/09, reinstall, restore, runner + kvm4-runner rebuilt 09-25/26). Only HANDOFF records it; `kvm4-runner` source is not in git. | `docs/HANDOFF.md` | 09-08 → 09-26 | done | owner 2026-09-08T13:33 onward |

## 13. Deliverables and tools outside the app images

| ID | Addition | Where | Introduced | Status | Owner asked? |
|---|---|---|---|---|---|
| X01 | **Potency range builder** — standalone, theme-aware HTML (one strain per THC scale, nominal toggles, symmetric tolerance sliders, border points, auto-propose). | `docs/tools/potency-range-builder.html` | `81ac1c9`, `465e811`, `4eab036` 09-07 | OFF-APP (repo file, not served by the app) | owner 2026-09-07T05:51, 06:24, 06:44, 07:25, 09:20 |
| X02 | **Potency Spec Service** — the builder grown into a multi-user FastAPI + SQLite service (Draft / Finished / Tetra Hip → Versa catalogues, retest chains, PDF export), running at `specs.srv1231216.hstgr.cloud`. | `tools/potency-spec-service/` **only on PR #53's branch** (`63474db`, draft, unmerged) | 09-11 → 09-16 (v13 → v27/28) | OFF-APP — **running in production from source that is not merged anywhere** | owner 2026-09-11T15:05, 15:54, 09-12T13:25, 09-15T11:39, 09-16T13:16 and others |
| X03 | **Integration analysis** of the range builder into the app (backend already stores explicit windows). | `docs/RANGE-BUILDER-INTEGRATION-2026-09.md` | `a8601ed` 09-07 | analysis only | owner 2026-09-07T06:57 |
| X04 | **Potency data record** (106 Total-THC results per strain; why windows overlap — ladder spacing). | `docs/POTENCY-DATA-2026-09.md` | `c5776ac`, `df1568b` 09-07 | doc | owner 2026-09-07T01:09, 03:36, 03:48 |
| X05 | **CoQ parameter tracker workbook** from RAGflow `eCoA_DB` (mirrors CoQ Analysis Master v9 + register, index, dashboard). | `docs/coq-tracker/` | `da1cca9` 09-04 (#51) | OFF-APP | owner 2026-09-04T03:50 |
| X06 | **Corrected Batch Release QC Register** (4 transcription errors fixed from CoAs; stability sheet; THC-by-strain sheet). | `qc-corrections/` | `d253d1a`, `68ce263`, `c3d7ac2`, `d0c8a09`, `e54e673` 08-17 | OFF-APP | — (commit says scope "by request"; request not in the log) |
| X07 | **RAGflow corpus curation**: stability programme separated (`STABILITY-PROGRAMME-SEPARATION`), 80 per-batch summary bundles (`eCOA_INGEST_SUMMA`), 66-agent Letta inventory. | `docs/STABILITY-PROGRAMME-SEPARATION-2026-08.md`, `ECOA-SUMMA-BUNDLES-2026-08.md`, `LETTA-AGENT-INVENTORY-2026-08.md` | `b621817`…`230ad53`, `ad22986` 08-17 | OFF-APP (RAGflow) | — |
| X08 | **Work timeline** document. | `docs/timeline/` | `494ba57` 08-14 | doc | owner-requested (commit `494ba57`) |
| X09 | **Work record** from primary sources (GitHub + repo metrics). | `docs/WORK-RECORD-2026-09.md`, `tools/work-record/collect.py` — **on `main` only** (PR #54) | `4baee7e`, `dbf88e0` 09-17 | doc, not on this branch | owner 2026-09-17T10:48, 14:51 |
| X10 | **Google Drive task capture** for qcm.blani (30.06.2025 → 04.07.2026). | `capture/` | `9fb3204`, `025a061`, `56b98bf` 07-04 | data file (the ingested rows went with the 07-30 wipe) | — |
| X11 | **Bridge** multi-agent coding workspace; **Emil Kowalski design skills** for agent sessions. | PR #50 (closed, moved to its own repo); `.agents/`, `.claude/` (`06f2c4f` 07-31) | 09-03 / 07-31 | Bridge: not in this repo; skills: agent tooling | skills: owner-invoked (commit) |

---

## Alembic migrations (every one is live: production tasks 0069, users 0012)

### Tasks chain

| # | Date | Commit | What it adds |
|---|---|---|---|
| 0001 | 07-04 | `560555e` | tasks DB baseline (v2 task model, own audit chain) |
| 0002 | 07-04 | `fd3c00f` | `tasks.external_ref` — capture dedup key |
| 0003 | 07-04 | `4d7c314` | date-only work sessions |
| 0004 | 07-04 | `35c4fa1` | `app.is_elevated()` knows DEP_MGR |
| 0005 | 07-05 | `a466bbd` | `is_elevated()` executive/manager/QP set |
| 0006 | 07-05 | `6baa9c0` | AI binding org-scope uniqueness |
| 0007 | 07-06 | `cfb6acd` | `weekly_documents` (plan/report lock lifecycle) |
| 0008 | 07-07 | `2da8d79` | locked-document immutability in RLS |
| 0009 | 07-11 | `b215c60` | `is_elevated()` adds OWNER, SE_MGR, MU_MGR |
| 0010 | 07-11 | `b215c60` | per-department weekly documents |
| 0011 | 07-12 | `73a0e11` | `tasks.attributes` jsonb |
| 0012 | 07-14 | `cf50d66` | audit chain-tail advisory lock |
| 0013 | 07-15 | `dd4a949` | events + notifications |
| 0014 | 07-15 | `f9f6aa8` | explicit task completion % |
| 0015 | 07-15 | `89f2d2a` | facility rooms + plant batches |
| 0016 | 07-15 | `13c8f93` | notification reasons for canned rules |
| 0017 | 07-16 | `bd82704` | task dependency graph + node_kind |
| 0018 | 07-16 | `67db775` | QC specifications + parameters |
| 0019 | 07-16 | `b819433` | QC sampling plans + samples |
| 0020 | 07-16 | `3a70d23` | certificates of analysis + results |
| 0021 | 07-16 | `3cf212f` | OOS investigations + register + notifications |
| 0022 | 07-16 | `1213d03` | CoQ generation fields |
| 0023 | 07-16 | `d231dea` | eCoA ingestion |
| 0024 | 07-16 | `e468faf` | certificate verification records |
| 0025 | 07-16 | `94e6ab8` | RQS + SFR + chain of custody |
| 0026 | 07-16 | `7f3f9f8` | water tests, stability studies, transports |
| 0027 | 07-16 | `7f3f9f8` | CoA chunks + full-text search |
| 0028 | 07-20 | `702ddb9` | eCoA lab verdict |
| 0029 | 07-20 | `eed67f5` | supersession chain + computed totals |
| 0030 | 07-20 | `62c4a91` | laboratory master |
| 0031 | 07-20 | `c6aa8a5` | certificate register completeness |
| 0032 | 07-20 | `d850b1d` | 5-working-day eCoA review clock |
| 0033 | 07-21 | `5a3e86d` | lab verdict on the permanent result |
| 0034 | 07-21 | `61f0ed0` | QC electronic signatures |
| 0035 | 07-21 | `7910d35` | source-document custody + SHA-256 |
| 0036 | 07-21 | `1b9aa71` | batch genealogy |
| 0037 | 07-21 | `0cf50a2` | task workflow sign-off events |
| 0038 | 07-21 | `2f536db` | CoQ certificate metadata (house layout) |
| 0039 | 07-21 | `96aab36` | QCSOP 011 sampling alignment |
| 0040 | 07-21 | `70a8c88` | VOIDED + External CoA Review Checklist |
| 0041 | 07-21 | `41c2b7c` | CoQ per-batch aggregation + iCoA polish |
| 0042 | 07-23 | `2e713aa` | deep-review remediation schema |
| 0043 | 07-24 | `66e7095` | missing audit triggers (6 tables) |
| 0044 | 07-28 | `e40e3b5` | audit trigger on QC document custody |
| 0045 | 07-30 | `d6b28f4` | cultivar master, batch codes, per-plant identity |
| 0046 | 07-30 | `b63a8a1` | decontamination campaign |
| 0047 | 07-30 | `7fb9c00` | positive controls + tool sterilisation |
| 0048 | 07-30 | `89ee33e` | destruction / waste manifest |
| 0049 | 07-30 | `91a5259` | corridor cleaning cadence |
| 0050 | 07-30 | `5dc6321` | audit hash timezone pinned to UTC |
| 0051 | 07-30 | `036c183` | harvest / yield + IPM |
| 0052 | 08-05 | `75f2a22` | irrigation / feeding record |
| 0053 | 08-05 | `8d7d9e8` | biosecurity events |
| 0054 | 08-05 | `36b414f` | `tasks.batch_id` |
| 0055 | 08-05 | `3071510` | `audit_log.created_at` index |
| 0056 | 08-05 | `8ff9cda` | drop global eCoA sequence (per-org numbering) |
| 0057 | 08-07 | `4199c4f` | potency ladders |
| 0058 | 08-07 | `814df80` | CoQ cultivar + frozen ladder |
| 0059 | 08-14 | `0eb915d` | batch commercial identities |
| 0060 | 08-14 | `d2d26d4` | signature dedup |
| 0061 | 08-26 | `8c69295` | signatures append-only |
| 0062 | 08-26 | `2dc01ae` | drop global OOS sequence |
| 0063 | 08-29 | `65cd1af` | one active custody record per sample |
| 0064 | 09-05 | `5436f17` | department model (IR_MGR, rooms→departments, clone rooms, `dept_family()`) |
| 0065 | 09-05 | `3ebb79a` | mother-plant bank + clone runs |
| 0066 | 09-05 | `0ad6230` | product catalogue, selection campaigns, trichome checks, clone lineage |
| 0067 | 09-06 | `7fe5418` | mother identity columns |
| 0068 | 09-06 | `41d5a76` | as-built facility layout register |
| 0069 | 09-06 | `488b869` | room rectangles on the register |

### Users chain

| # | Date | Commit | What it adds |
|---|---|---|---|
| 0001 | 07-04 | `560555e` | users DB baseline (organizations, profiles, audit) |
| 0002 | 07-04 | `35c4fa1` | DEPT_HEAD → DEP_MGR, drop PROJECT_LEAD |
| 0003 | 07-05 | `a466bbd` | executives + department managers + QP |
| 0004 | 07-09 | `b2a2bb8` | SC_MGR → SE_MGR, add MU_MGR |
| 0005 | 07-10 | `36a5b7a` | OWNER role |
| 0006 | 07-14 | `cf50d66` | audit chain-tail advisory lock |
| 0007 | 07-24 | `66e7095` | organizations audit trigger |
| 0008 | 07-28 | `e40e3b5` | drop dead `password_reset_codes` |
| 0009 | 07-30 | `5dc6321` | audit hash timezone pinned |
| 0010 | 08-05 | `3071510` | `audit_log.created_at` index |
| 0011 | 08-26 | `1a70e78` | case-insensitive unique username |
| 0012 | 09-05 | `5436f17` | IR_MGR role |

---

## Designed but never built (design or analysis exists, no code)

| # | Item | Design | Asked by owner? |
|---|---|---|---|
| 1 | **DocEngine canvas** — checkpointed, human-reviewed authoring (between-step corrections, context amendments, option A for amendments, fresh audit before finishing). | `docs/DOCENGINE-CANVAS-DESIGN-2026-09.md` (`7586c02`, `bee6ae6` 09-24) | yes — 2026-09-04T23:06, 09-16T16:53, 09-24T10:11, 13:14, 15:11 |
| 2 | **QC database ↔ `CoQ_Analysis_Master` workbook sync** (task #18); workbook has since moved from v9 to v35+. | `docs/ECOA-MASTER-SYNC-DESIGN-2026-09.md` (`2d330ab` 09-04) | yes — 2026-09-04T06:35 |
| 3 | **Range builder inside the app** for existing and future strains. | `docs/RANGE-BUILDER-INTEGRATION-2026-09.md` (`a8601ed`) | yes — 2026-09-07T06:57 |
| 4 | **Product-window grade on the CoQ**, and regrade to the next grade + visual flag + formal OOS/deviation when Total THC falls outside the product window. | `docs/PRODUCT-CATALOGUE-2026-09.md` ("Not yet built"), `POTENCY-DATA-2026-09.md` §Open | yes — 2026-09-06T18:02 |
| 5 | **Floor plan coloured by cleanliness grade**, grades loaded for each room. | `docs/FACILITY-LAYOUT-2026-09.md` (3 wings still `[NEEDS INPUT]`) | yes — 2026-09-06T16:29 |
| 6 | **Owner weekly-report redesign** (requirements, gap analysis, design). | PR #18 (open since 2026-07-12) | not in log |
| 7 | **Cultivation & Harvest Plan screen** (mockup only). | PR #39 (open since 2026-07-29) | not in log |
| 8 | **MW-2 pages**: batch dossier, harvest scheduler, report builder, SOP step library; `doc-control` page. | `MASTER-PLAN-2026-08.md` §3.1–3.2 | owner mockup |
| 9 | **16 mockup pages with no backend** (orders, packaging, genetics, nutrients, environment telemetry, cure, automations/rule builder, settings console, compliance reporting, CAPA/change-control detail, inventory…). | `MASTER-PLAN-2026-08.md` §3.4 (owner-decision register) | owner mockup; decision pending |
| 10 | **Notifications v2**: email/SMTP, digests, quiet-hours web push, per-user toggles. | `RESEARCH-NOTIFICATIONS-2026-07.md`, MASTER-PLAN Track C | — |
| 11 | **Frontend ESM / Vite modernization**. | `FRONTEND-ESM-PROPOSAL-2026-07.md` (explicitly not accepted) | — |
| 12 | **OCR / automatic eCoA extraction pipeline**. | MASTER-PLAN Track F (blocked on URS decision D5) | — |
| 13 | **MFA, external audit-chain anchoring, viewer role, training matrix, task file attachments, barcode/QR samples, `qc_batches` master table**. | MASTER-PLAN Tracks C/D | — |
| 14 | **Post-harvest beyond the close** (curing, trimming, packaging) and room↔phase validation. | `DEPARTMENT-MODEL-2026-09.md` §Still open | partly (owner 09-05T17:44 names production's scope) |
| 15 | **Unification Phases 2–3** (federated third DB / QMS on the platform model) — superseded by the DocEngine route. | `UNIFICATION-ANALYSIS-2026-07.md` | owner asked about merging (commit `5c0e128`) |
| 16 | **"Adopt the bulk-spec / CoQ / iCoA template work into the app as one function."** | none found in the repo | yes — 2026-09-18T15:55 |
| 17 | **Live self-updating tracking system for QC certificate issuance.** | none found in the repo | yes — 2026-09-24T09:41 |

## Built but not deployed

| Item | Where | Why it matters |
|---|---|---|
| WeasyPrint 70.0 security bump | `9180b5a` (backend) | production backend v92 still carries 69.0 (PYSEC-2026-3940) |
| DocEngine single uvicorn worker | `1376253` (`docengine/Dockerfile`) | v26 image still says `--workers 2`; production relied on a compose override (survival after the VM rebuild UNVERIFIED) |
| DocEngine job trace (`job_events`, `/trace`) | PR #55 `bec2720` (draft, not on this branch) | prerequisite for the canvas design (§13 of that doc) |
| Potency range builder HTML | `docs/tools/` | not served by any app image |
| Work record | PR #54, `main` only | docs; not on the production branch |
| CI/e2e timeout changes | `f62e0e4`, `329c4b7` | no runtime artefact |

The reverse case, **deployed but not in git on any merged branch**: the Potency Spec
Service (PR #53 source), the host `compose.yaml` (docengine service definition), the
`kvm4-runner` (`/opt/kvm4-runner/app/runner.py`), the production password-length
override and account renames of 2026-09-04.

## Built and deployed, but not usable yet (activation or rollout gaps)

| Item | Gap | Evidence |
|---|---|---|
| Generic AI catalog (12 functions: assistant drawer, AI intake, voice capture, weekly summary, document AI sections…) | zero `ai_agent_bindings` rows in production | `docs/AI-FEATURE-INVENTORY-2026-08-23.md`; no later binding in git |
| Product catalogue (Q30) | import and approval not recorded as done; no UI for import/approve/supersede/conformance/potency history | PR #52 rollout step 2, not recorded as done; `grep` shows no caller of `qcImportProducts`, `qcApproveProduct`, `qcProductConformance`, `qcProductPotency` outside `api.js` |
| Facility layout (F02) | 191-room import and room linking not recorded as done | PR #52 rollout steps 3 and 7; HANDOFF |
| Department model (R05) | Irrigation/Cloning/Nursery departments and IR_MGR not provisioned; clone rooms not re-kinded | PR #52 rollout steps 4–6 |
| Commercial identities (Q28) | no list/import/edit UI | no caller of `qcCommercialIdentities`, `qcImportCommercial` |
| Task tree, `workload_balance`, on-demand `next_week_plan`, trichome list | API only | no UI caller (`taskTree`, `trichomeChecks`) |
| QMS registry / knowledge views (A04) | upstream `qms-api` retired → 503 | `api/qms.py`; `b23dc22` |
| Cultivation, QC certificates, CoQ | modules live but tables empty in production (only 71 DRAFT ladders + 71 cultivars populated) | DEPLOY-2026-09-06-v92 ("cultivation subsystem has never been used live"), ECOA-MASTER-SYNC-DESIGN §1 |

## Observations

1. **Most of what was built has never held production data.** After the owner-ordered
   wipe of 2026-07-30, production on 2026-09-06 had empty `rooms`, `plants`,
   `plant_batches`, `qc_coq`, and (per the 2026-09-04 sync design) an empty QC model
   apart from 71 DRAFT potency ladders and 71 cultivars. The cultivation, CoQ and
   eCoA pipelines are shipped but unexercised on real records.
2. **Several September features are deployed but switched off by missing rollout
   steps** that no record shows as done: the product catalogue (import and
   second-person approval — and there is no UI for either), the 191-room facility
   layout import, the department model (departments / IR_MGR), and the whole generic
   AI catalog (zero agent bindings as of 2026-08-23, nothing since in git). Until
   those steps run, the screens exist but hold nothing.
3. **Owner requests still open**: the DocEngine canvas (asked four times since
   09-04, designed 09-24), the workbook ↔ QC-DB sync (09-04), the in-app range
   builder (09-07), product-window regrading with an OOS (09-06), grade
   colour-coding of the plan (09-06), adopting the spec/CoQ/iCoA template work into
   the app (09-18) and a live QC issuance tracker (09-24) — none has code.
4. **Production runs code that is not in any merged branch**: the Potency Spec
   Service (PR #53 draft), the docengine service definition in the host
   `compose.yaml` (absent from the repo's `docker-compose.yml`), the rewritten
   `kvm4-runner`, and the 2026-09-04 password/account overrides. Conversely,
   `9180b5a` (a security fix) and `1376253` are in git but not in the images.
5. **The record in the repo is incomplete in places that affect decisions**: the
   local clone is shallow (314 of 657 commits visible), frontend `v132` has no
   deploy record, `docengine/DEPRECATED.md` still says the tree is a frozen mirror
   that "receives no engine edits" although 38 docengine commits (4 in
   `docengine/engine/`) followed it, `MASTER-PLAN-2026-08.md` predates everything
   from 08-07 on, and 17 MB of the retired `qms-creator/` import is still vendored.
