# Inventory, dead code and cross-cutting consistency — second review

HEAD `0984dc8` (2026-09-27), diff base `549b617`. Read-only; no production contact; no pytest run.
Method: `git diff --stat`, decorator diff of the routes, AST/grep scans for unreferenced Python
functions and constants, `ruff --select F401,F811,F841,F821` on HEAD **and** on a `git archive`
of `549b617` (to separate old dead code from new), a GF.*/api.js/CSS reference scan, a
route→caller matrix built from `api.js` `_req` patterns and the views' direct `fetch`/URL builders,
byte diffs of the shared SQL functions, and a read of 0070/0071/0013 against both baselines.

## Summary

The fix cycle is large (44 commits, 218 files, +16,273/−4,998) but tidy at the seams I could
check statically: the two audit triggers and the four shared `app.*` functions are byte-identical
across the users and tasks baselines, both alembic chains have one head (0071, 0013) and the
baselines reproduce every object the three migrations create or drop. Most §5 dead code was
removed (task tree, the report PATCH, the seven retired QMS routes, two stub views, four unused
assets, the second engine copy). What the cycle left behind is small but real: the hand-merged
`notifications-view.js` carries two shadowed `case` labels; five emitted verbs still have no
sentence; the QC-12 CoQ e-signature exists only as an API (no wrapper, no UI); a new route
(`POST /qc/products/ladder`) and its wrapper were born without a caller; two ladder wrappers lost
theirs; 30 routes are unreachable from the product at HEAD; and three living documents still
describe deleted files. No security or data-integrity defect was found in this area.

## Closure table — first review §5, §8 and the inventory's own claims

| Item (first review) | Status | Evidence |
|---|---|---|
| §5 Product helpers: 9 of 10 `api.js` wrappers uncalled | **PARTIAL** | 6 of the 10 now have callers in `web/gf/qcpotency-view.js` / `qccoa-view.js` / `propagation-view.js` (`qcProducts`, `qcProduct`, `qcApproveProduct`, `qcImportProducts`, `qcProductConformance`, `qcProductDocumentUrl`); `qcProductCreate` (api.js:379), `qcProductPatch` (:380), `qcProductPotency` (:386) still have none; `qcProductLadderCreate` (:381) was added without one. |
| §5 `qcProductDocumentUrl` targets a route that does not exist (QC-22/INS-02) | **CLOSED** | `GET /qc/products/{product_id}/document` at `backend/app/api/qc/spec_html.py:179` (a2c0084); caller `qcpotency-view.js` `qcPotOpenDoc`; pinned by `tests/frontend/qcpotency-view.test.js`. |
| §5 API with no UI: task tree | **CLOSED** | Route and `taskTree()` wrapper deleted (`tasks.py:289` comment, api.js diff); pinned by `backend/tests/test_qms_proxy.py:283`. |
| §5 API with no UI: whole-document report PATCH (BC-07) | **CLOSED** | `PATCH /reports/documents/{doc_id}` removed from `documents.py`; `patchDocument()` removed from api.js; `patchDocumentSection` (api.js:552) remains and is called (`document-view.js:237`). |
| §5 API with no UI: decon fail / biosecurity result (BC-10) | **CLOSED** | `deconFail` (api.js:282), `biosecurityResult` (api.js:305) called from `decon-view.js`; `tests/frontend/decon-fail-biosecurity.test.js`. |
| §5 API with no UI: trichome-check list | **NOT FIXED** | `GET /cultivation/trichome-checks` (`trichome.py:130`): wrapper `trichomeChecks` (api.js:222) has no caller. The cycle added `PATCH /cultivation/trichome-checks/{check_id}` (`trichome.py:178`) with **no wrapper at all** (INV-06). |
| §5 API with no UI: commercial identities list/import | **NOT FIXED** | `qcCommercialIdentities` (api.js:395), `qcImportCommercial` (:396) uncalled; the PUT/DELETE wrappers were deleted (api.js:397 comment) while the routes stay (`commercial.py:78,107`). |
| §5 API with no UI: `workload_balance`, on-demand `next_week_plan` | **unchanged** | These are AI function keys (`ai.py:130-131`), not routes; `next_week_plan` is read by `report-view.js:52`; `workload_balance` has no UI trigger. No code change in the cycle. |
| §5 Retired QMS routes (BC-19) | **CLOSED** | 7 routes gone from `qms.py` (decorator diff); the `qms_api_*` settings gone; pinned by `test_qms_proxy.py:275-291`. |
| §5 `qms-creator/` 17 MB vendored | **NOT FIXED** | `du -sh qms-creator` → 17M at HEAD; not mentioned in `docs/HANDOFF.md` or `DECISIONS-2026-09.md`. |
| §5 `GET /cultivation/cultivars` legacy `spec` payload (CS-18) | **CLOSED** | `cultivation.py:440-446` — payload dropped, comment records it. |
| §5 `laboratories.decimal_separator` stored, never read (QC-03) | **CLOSED** | Read at `certificates.py:392` and `ecoa.py:645-653` (`_doc_decimal_separator`), fed to `common.parse_lab_number`. |
| §5 `docengine/DEPRECATED.md` says the tree gets no engine edits | **PARTIAL** | `DEPRECATED.md` rewritten (ac05616) and correct. But `docengine/engine/references/GUIDE_bilingual_markdown.md:11-16` still says `pp-document-suite/` is a frozen snapshot and "engine development moved to letta-stack — see DEPRECATED.md" (INV-07). |
| §5 Generic AI catalogue live but inert (0 bindings) | **unchanged** | No binding code changed; production state not checkable read-only. |
| §5 / FE-22 ~40 routes with no frontend caller | **PARTIAL** | 9 of them deleted, 8 wired (decon fail, biosecurity result, the products screen, `PATCH /cultivation/batches/{id}`); **30 remain UI-unreachable at HEAD**, 5 of them new (INV-06). |
| §8 Most of the app never held production data | unchanged | No deploy record after `DEPLOY-2026-09-07-docengine-v26.md`; `HANDOFF.md:48` — production still tasks 0069 / users 0012. |
| §8 Rollout steps not recorded as done | unchanged | `HANDOFF.md` §"Rollout of the review fixes" is a new, longer list; nothing marked done. UNVERIFIED beyond the docs. |
| §8 Production ≠ git (WeasyPrint 70.0, single-worker DocEngine, PR #53 service, host compose) | unchanged | `backend/requirements.txt:21` weasyprint==70.0 and `docengine/Dockerfile:40` `--workers 1` still undeployed; `HANDOFF.md:32,78` still lists PR #53 as a separate branch and the Potency Spec Service as running. |
| §8 Designed but never built — 17 items | **2 now built, 1 partly** | #4 product-window regrade + OOS: built (`coq_aggregation.py:155-261`, C-1). #5 floor plan by cleanliness grade: built (`facility-view.js:177-192`, seeded by 28049c0). #3 range builder: server side only (`HANDOFF.md:156-159`). The other 14 unchanged; `DECISIONS-2026-09.md` §4 lists the five still open owner requests. |
| Inventory migration table (81, all live) | superseded | 84 now: tasks 0070, 0071; users 0013 — **none deployed** (`HANDOFF.md:48`). |

## 1. Inventory of the fix cycle (549b617..0984dc8)

**Commits.** 44, all dated 2026-09-27, author "Claude". By workstream (letters as in
`DECISIONS-2026-09.md` §2b): A backend core — f7c1a38, da0498d, 9b70786, f692268, b6c9c43,
4f37e51, a710887, 83812c8; B QC — 04b83ee, c89f33e, 829bae1, f01499b, 9601235, a248dc4;
C product catalogue — a2c0084, 97f75f4, a85a94b, b2b2451; D cultivation — cf33801, 1c5c884,
80d4e0a, ce7ecdb, 28049c0, d186c01, 254c7f1; E frontend — e454e0a, 0c2da3f, 7b0e558, b2a7638,
3854447, ae24ea7, 3105b5c, 8c6a5bc, f73bba7, 77f8650, ca4bec3; F DocEngine/infra — 291c8da,
5f66ee7, ac05616, 7102bfb, 8717fa4, c046014, 18a2659; hand-off — 0984dc8.

**Files by area** (`git diff --stat`): 218 files, +16,273/−4,998.

| Area | Files | Notes |
|---|---|---|
| `backend/app` | 50 | largest: `qc/products.py` +584/−…, `cultivation.py` 467, `coq_aggregation.py` 448, `propagation.py` 415, `tasks.py` 239, `ecoa.py` 221, `qms.py` 208 (mostly deletions) |
| `backend/alembic_*` | 3 new | tasks 0070, 0071; users 0013 |
| `backend/schema.*.sql` | 2 | tasks −139/+…, users −14 (policies) |
| `backend/tests` | 43 | 3 new files (`test_qc_review_2026_09.py` 882 lines, `test_docengine_client.py`, `test_users_rls_policies.py`); test functions 789 → 914 |
| `backend/scripts`, `backend/app/data` | 6 | `facility_layout.json` 766 lines (grades), `imb_products.json`, backups |
| `web/gf` | 45 | 2 deleted (`qmsknow-view.js`, `qmsregistry-view.js`); 0 added; `qcpotency-view.js` 449, `cultivation-view.js` 299, `decon-view.js` 219, `notifications-view.js` 167 |
| `web/assets` | 4 deleted | `PP_Leaf.svg`, `PP_Leaf_3D.glb`, `pp-leaf-outline.svg`, `pp-leaf.svg` — no remaining reference (`sw.js`/`brand.css` use `pp-leaf.png` / `pp-leaf-3d.obj`, both present) |
| `web/` shell | 4 | `index.html` −2 script tags, `sw.js` v3.102.0 → v3.103.0 (+`cache:'reload'`), `nginx.conf`, `data.js` −4 i18n keys |
| `tests/frontend` | 23 | 9 new files; `test(` count 569 → 648 |
| `docengine` | 27 | `pp-document-suite/` (10 files) deleted; `sql/docengine_role.sql` added; `app/pipeline.py` 445, `main.py` 285, `db.py` 181 |
| `connector`, `ops`, `.github`, compose, `.env.example` | 10 | `deploy.yml` +300, `watchdog.sh` +172, `gh_api.py` +186 |
| `docs`, `CLAUDE.md` | 14 | `HANDOFF.md`, `DECISIONS-2026-09.md` §2b, `PRODUCT-CATALOGUE`, `PROPAGATION`, `FACILITY-LAYOUT`, `FRONTEND-DESIGN-HANDOVER`, `BACKUP`, `DEPLOY` |

**Routes** (decorator diff, `backend/app`): 274 → 272.
Removed (9): `PATCH /reports/documents/{doc_id}`; `GET /qms/documents`, `/qms/documents/{code}`,
`/qms/download/{path}`, `/qms/families`, `/qms/hierarchy`, `/qms/stats`, `POST /qms/rag-query`;
`GET /tasks/tree`.
Added (7): `POST /qc/products/import-fitted` (products.py), `POST /qc/products/ladder`
(products.py), `GET /qc/coq/{coq_id}/signatures` and `POST /qc/coq/{coq_id}/sign`
(signatures.py:170,180), `GET /qc/products/{product_id}/document` (spec_html.py:179),
`PATCH /departments/{dept_id}` (tasks.py:173), `PATCH /cultivation/trichome-checks/{check_id}`
(trichome.py:178). A decorator diff cannot see routes whose body changed under the same path;
those are the other reviewers' areas.

**Schema objects** added/dropped by the three migrations (all reproduced in the baselines):

| Migration | DDL |
|---|---|
| tasks 0070 | `mother_plants_line_key` re-keyed to `(org_id, campaign_id, mother_no, generation, stock_no)` — `product_id` dropped from the key |
| tasks 0071 | `qc_coq.purpose text NOT NULL DEFAULT 'INITIAL'`, `qc_coq.timepoint text`; CHECKs `qc_coq_purpose_check`, `qc_coq_retest_timepoint_check`; `qc_coq_one_approved_idx` rebuilt on `(org_id, batch_id, specification_id, purpose, COALESCE(timepoint,''))`; `qc_signatures_meaning_check` + `'COMPILED'`; `qc_oos_register` policy `org_isolation` (ALL) → `org_isolation_select` + `org_isolation_insert`; sequences dropped: `qc_spec_id_seq`, `qc_sample_id_seq`, `qc_sampling_plan_id_seq`, `qc_lab_id_seq`, `qc_sfr_id_seq`, `qc_wt_id_seq`, `qc_stb_id_seq`, `qc_trn_id_seq` (no `nextval`/`setval` reference survives in `backend/`) |
| users 0013 | policies `profiles_manage`, `profiles_self` dropped; `profiles_read` kept |

**Notification verbs.** 62 literal `verb="…"` emitters under `backend/app` plus the dynamic
`workflow_{submit,approve,reject,block,unblock}` (tasks.py:1209) and `due_soon`/`overdue`
(duescan.py:70) — 69 verbs. `notifications-view.js` `sentence()` has 66 `case` labels (64 distinct).
- **Verb with no sentence (5):** `coq_signed` (signatures.py:220, new), `commercial_identity_upserted`
  (commercial.py:100), `portfolio_master_imported` (commercial.py:158), `potency_catalogue_imported`
  (potency_import.py:200), `facility_layout_imported` (facility_layout.py:310). All fall to the
  generic line (`:176-182`).
- **Sentence with no emitter: none** (`batch_closed` was dropped as FE-18 asked).
- **Duplicate `case` labels (2):** `product_created` (:83 and :167), `product_approved` (:85 and :169) — INV-02.
- `VERB_LBL` (:200-224) lacks labels for the five verbs above and for `coq_*`, `harvest_dried/closed`,
  `sample_*`, `spec_created`, `coa_*`, `ipm_applied`, `irrigation_logged`, `waste_manifest_*`,
  `facility_room_classified`, `campaign_started`, `mother_registered` — the digest prints them as
  de-underscored words (by design per the comment at :225).

## 2. Findings

### INV-01 [medium] contract coverage — the QC-12 CoQ e-signature has no path from the product
**Where** `backend/app/api/qc/signatures.py:170-225` (`GET/POST /qc/coq/{coq_id}/signatures|sign`);
`web/gf/api.js` (no wrapper — the only sign wrappers are `qcSign`/`qcSignatures` for
`/qc/certificates/{id}`, :430-431); `web/gf/qccoa-view.js:276-364` (`qcCoaSign` → certificates only).
`render_coq` (`coq_aggregation.py:906-970`) prints the CoQ's own COMPILED/APPROVED signatures.
**What happens** No user can apply the compiler's or the HoQC's signature to an aggregation CoQ
from the UI, so in use the printed CoQ still carries no electronic signature — the very defect
QC-12 named. The backend fix is exercised only by `test_qc_review_2026_09.py:546-566`.
**Evidence** route→caller matrix; `grep -rn "coq.*sign" web/gf tests/frontend` → nothing.
**Fix** Add `qcCoqSign(id,b)` / `qcCoqSignatures(id)` to api.js and reuse `signaturesPanel` on the
CoQ detail (meaning COMPILED for `compiled_by`, APPROVED for `reviewed_by` once APPROVED).

### INV-02 [low] merge seam / unreachable code — two `case` labels are shadowed in the sentence switch
**Where** `web/gf/notifications-view.js:83,85` (from 3854447, workstream E) vs `:167,169`
(from a85a94b, workstream C).
**What happens** JavaScript runs the first matching `case`, so C's sentences never render: an
approved product shows "approved product GP-20" instead of "approved product GP-20 (GP, v.03)"
— the `doc_version` that `products.py:618-625` emits is never displayed — and the Macedonian
wording differs (`креираше` vs `состави`). Verified with `node -e` (duplicate case → first wins).
**Fix** Delete one pair; C's carries more of the emitted params.

### INV-03 [low] contract — five emitted verbs still fall to the generic line (FE-18 PARTIAL)
**Where** listed under "Notification verbs" above; the file's own contract at
`notifications-view.js:51-52` says every emitted verb has a sentence.
**What happens** "Ana · coq signed: <object>" in both languages — legible, but not the
bilingual sentence the fix promised; `coq_signed` is new in this cycle.
**Fix** Five `case`s plus `VERB_LBL` entries.

### INV-04 [low] stale string — `dotKind` checks `'acknowledged'`; the verb is `ack`
**Where** `web/gf/notifications-view.js:254` vs `backend/app/api/collab.py:259` (`verb="ack"`).
Pre-existing (549b617:113). An acknowledgement never gets the green dot. **Fix** `'ack'`.

### INV-05 [low] dead code — 13 `api.js` wrappers with no caller (1 born dead, 2 newly dead)
| Wrapper (api.js line) | Route | Since |
|---|---|---|
| `qcProductLadderCreate` (:381) | `POST /qc/products/ladder` | **new, never called** (a2c0084) |
| `qcApprovePotencySpec` (:368), `qcSupersedePotencySpec` (:369) | `POST /qc/potency-specs/{id}/approve`, `/supersede` | had a caller at 549b617; lost it when the potency screen became the catalogue (a85a94b) |
| `qcCreatePotencySpec` (:367), `qcPotencyDisposition` (:371), `qcProductCreate` (:379), `qcProductPatch` (:380), `qcProductPotency` (:386), `qcCommercialIdentities` (:395), `qcImportCommercial` (:396), `qcSignatures` (:431), `campaignPatch` (:227), `trichomeChecks` (:222) | as named | pre-existing |
**Evidence** reference scan over `web/`, `tests/frontend`, `docs/*.html`; 549b617 comparison.
**Fix** Delete the wrappers or wire the screens; for the ladder ones, consistent with C-7 is deletion.

### INV-06 [low] API-only surface — 30 routes are unreachable from the product at HEAD
No wrapper and no direct call (17): `GET /auth/users` (script client only:
`backend/scripts/provision_test_accounts.py`), `GET /decon/cycles/{id}`, `GET /decon/bleach-log`,
`GET|POST /decon/positive-controls`, `GET|POST /decon/tool-log`, `GET /decon/corridors/{room}/cleanings`
(their wrappers were deleted in 8c6a5bc, so these are now doubly orphaned),
`PUT|DELETE /qc/commercial-identities/{code}`, `GET /qc/coa-documents/{id}/originals`,
`PATCH /qc/potency-specs/{id}`, `GET /qc/certificates/{id}/icoa-html`, **`GET|POST /qc/coq/{id}/signatures|sign`**
(INV-01), **`PATCH /departments/{dept_id}`** (tasks.py:173 — the A-3 "ADMIN may set the head"
has no screen), **`PATCH /cultivation/trichome-checks/{id}`** (trichome.py:178 — the
`trichome_corrected` sentence exists but nothing in the UI can emit it; the owner asked for
"progressive tracking … with documented records" and neither the history list nor the correction
is reachable).
Reachable only through a dead wrapper (13): the routes in INV-05.
**Evidence** `scratchpad/review2/routes_callers2.py` (272 routes, 257 call patterns) cross-checked
by literal grep; false positives (query-string list routes, URL builders) removed by hand.
**Fix** Decide per route: wire, or delete with its wrapper. The decon logs and commercial
identities have been API-only since July.

### INV-07 [low] stale documents — three living files describe deleted code
- `docs/FRONTEND-DESIGN-HANDOVER.md:224` and §9.22 (`:697-706`): edited in this cycle
  (77f8650) yet still lists `qmsregistry` / `qmsknow` as Zone B views; both were deleted (8c6a5bc, E-3).
- `docengine/engine/references/GUIDE_bilingual_markdown.md:11-16`: "`docengine/pp-document-suite/`
  is a frozen preservation snapshot … Both trees are frozen. Engine development moved to letta-stack
  — see `../../DEPRECATED.md`." The directory was deleted (ac05616) and `DEPRECATED.md` now says
  the opposite; a reader of the engine's own reference gets the retracted story.
- `docengine/engine/scripts/build_from_md.py:21-25` still probes `../pp-document-suite/scripts`
  as a fallback (harmless, but it names a directory that no longer exists).
- Historical only, no fix needed: `docs/MASTER-PLAN-2026-08.md:157` plans a UI over the deleted
  `GET /tasks/tree`; `web/gf/qcspec-view.js:12,23` comments cite `qmsregistry`.

### INV-08 [low] dead code — pre-existing items the cycle did not touch (none introduced)
ruff on HEAD and on 549b617 report the same four: `backend/app/api/ai.py:23` `EXECUTIVE_ROLES`
unused import; `api/capture.py:30` `require_password_set`; `api/qc/potency.py:23` `date`;
`demo_org.py:494` local `qp` assigned, unused. Unreferenced functions: `api/documents.py:1005`
`_numf`, `:1014` `_numi`; `db.py:64` `users_user_pool`, `:72` `tasks_user_pool`. Unreferenced
constants: `api/qms.py:46` `_DE_UNAVAILABLE`, `api/qc/coq_aggregation.py:21` `_COQ_STATUSES`,
`docengine/app/config.py:8` `ENGINE_ASSETS`, `docengine/app/needs.py:43` `MARKER`. JS locals:
`web/gf/datepicker.js:50` `monthName`, `web/gf/qcpotency-view.js:29` `canWrite`. CSS classes in
`app.css` with no element and no dynamic constructor (the `s-*` status classes are built as
`s-${t.status}` and are fine): `brand-mark` (:257), `brand-name` (:259), `cj-chips` (:1403),
`cj-chip` (:1404), `hide-sm` (:692), `pressable` (:379), `sess-hours` (:709), `stt` (:560),
`sub-add` (:562). And `qms-creator/` (17 MB) is still vendored.
**Evidence** `scratchpad/review2/{pydead,pyconst,jsdead,jslocal,cssdead}.py`; ruff on both trees.

### INV-09 [low] duplicated logic — consistent today, still two copies
(a) **Potency history.** `products.py:335-341` `_TOTAL_LINE` and `propagation.py:356-361` are
byte-identical; the three source SQLs (`products.py:376-397` vs `propagation.py:365-390`) differ only
in aliases; `propagation.py:363` even says "self-contained copies". One intended semantic
difference: products scopes "tested" by `product_id`, propagation by `product_code` (any version).
Nothing ties the copies together; a change to the certificate join in one will not reach the other.
(b) **CoQ derived totals.** One computation now (`common.derived_total` + `check_derived_total_units`
called from `coq_docx.py:583-585` and `coq_aggregation.py:640-642`); the markdown is one function
(`_coq_markdown`, imported at `coq_aggregation.py:14`). Residual drift: a certificate that carries a
*transcribed* value for the computed parameter makes the single-certificate path refuse with 409
(`coq_docx.py:566-579`), while the aggregation path never looks at `latest[pid]` for a computed
parameter and silently computes from components (`:630-655`). Same certificate, two verdicts.
(c) **Facility today.** Seven helpers: `worktime.facility_today()` and `SITE_TODAY_SQL`;
`documents.py:43 _today()` (a Python duplicate of `facility_today`); identical `_site_tz()` +
`_site_today(c)` pairs in `harvest.py:144-160`, `biosecurity.py:63-69`, `irrigation.py:54-62`; and
`cultivation.py:333` `_site_today` on the SQL literal. All resolve `settings.snapshot_tz`; the
`or "UTC"` fallback in the three copies is dead because `worktime.TZ = ZoneInfo(settings.snapshot_tz)`
fails at import on an empty value. Not drifted; ae24ea7 routed callers to `facility_today` but left
the copies.
(d) **Department family.** `app.dept_family` (schema.tasks.sql:73) is canonical; `deps.dept_family`
wraps it; `facility._actor_family` uses the wrapper; `auth._actor_family` (:317-325) re-implements
the wrapper and its `[root]` fallback instead of calling it; `deps.dept_lineage` is the inverse with
the same depth cap; `GF.WWF.deptFamily` (`integrate.js:973-982`) walks `GF.DEPTS` with a 64-step cap,
UI-only. Consistent.
(e) **Audit triggers.** `app.fn_audit_row` byte-identical in `schema.users.sql:73-107` and
`schema.tasks.sql:91-125`; `is_elevated`, `current_org_id`, `current_user_id`, `"current_role"`
identical (md5). `dept_family` exists only in tasks, correctly.
**Fix** (a) import `_TOTAL_LINE` and the three SQLs from `products.py`; (b) either check
`latest[pid]` in the aggregation path the way `coq_docx` does, or drop the 409 there — one rule;
(c) replace `documents._today` and the three `_site_today` copies with `worktime` calls;
(d) `auth._actor_family` → `deps.dept_family`.

### INV-10 [low] migrations vs baselines — match by inspection; three downgrade properties a dump diff cannot show
Both baselines reproduce every object in the table under §1 (checked object by object; the
coordinator's dump diff agrees). One head per chain (`0071`, `0013`). `qc_oos_register` has no
UPDATE/DELETE in app code; `demo_org.py:69` and `conftest.purge_org` use the BYPASSRLS admin pool;
`test_qc_review_2026_09.py:877-879` pins the policy.
What the dumps would not show, all in `0071_qc_review_fixes.py:95-121 downgrade()`:
1. `DELETE FROM qc_signatures WHERE meaning='COMPILED'` destroys Annex 11 signature records — a
   downgrade erases evidence, and the docstring does not say so.
2. The eight sequences are recreated `START WITH 1` (0062 precedent). After a downgrade the
   pre-0071 `nextval()` minting collides with numbers already minted per-(org, year) by
   `mint_series_number` (`PP-SPEC-2026-0001` …) → unique-violation 500s on every new spec / sample /
   lab / SFR / water test / stability study / transport until each sequence is `setval`'d.
3. The old `qc_coq_one_approved_idx` cannot be recreated once an INITIAL and a RETEST CoQ are both
   APPROVED for one (org, batch, spec).
`0070` relies on "production's cultivation tables are empty" (docstring) — UNVERIFIED from here; if
false, `ADD CONSTRAINT` refuses, which is the intended outcome.
**Fix** State 1-3 in the docstring; `setval` each recreated sequence to the org-wide maximum (or
leave them dropped: nothing reads them).

### INV-11 [info] test helpers — nothing dead
`conftest._reset_login_rate_limit` is `autouse=True`; `admin_token` is consumed by `admin_headers`;
`iter_routes` has 2 users; every `tests/frontend/helpers/gf-window.js` export is used
(`FREEZE_CLOCK_SRC`, `BASE_HTML` are internal). The cycle also removed `docengine/app/needs.py`
`needs_summary`, which was dead.

## Instruction conformance of the fixes (this area)
Nothing in the inventory contradicts `DECISIONS-2026-09.md` §1. E-3 (delete the stub views) is done
as recorded. C-7 (ladders retired) is what left the two ladder wrappers dead (INV-05); the decision
does not say to delete the routes, so that is a tidy-up, not a deviation.
