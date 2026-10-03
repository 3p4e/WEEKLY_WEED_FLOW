# Re-review: the QC subsystem and the product catalogue (2026-09-27, HEAD 0984dc8)

Scope: `backend/app/api/qc/*`, `app/plantids.py` (window/grade/conformance helpers),
`app/data/imb_products.json`, `app/data/imb_spec_template.html`, tasks migration 0071,
`schema.tasks.sql`, the QC tests, and the QC↔frontend contract points the fixes touched.
Method: static reading of every changed module end to end, `git diff 549b617..HEAD` on
the merge seams, pure-function runs under the CI env (`_coq_potency`, `conformance_of`,
`nearest_of`, `reconcile_numeric`, `names_total_thc`), one asyncpg temp-table check on the
local cluster (no test DB, no pytest), and no production contact.

## Summary

The QC workstream closed the four high findings on the aggregation path and most of the
medium/low ones the way the first review asked, and the product workstream built the
product branch, the A4 page, the fitted import and the out-of-grade rule; the coordinator's
hand-merge of `coq_aggregation.py`, `spec_html.py`, the template and `test_spec_html.py` is
clean (no dangling `_ACID_FACTOR`, all 19 template tokens substituted, the recorded-approver
rule pinned). The two gate sets run on compile, review and render in a sane order and never
short-circuit each other. What remains is at the seams the workstreams did not share: the
eCoA screen still client-parses numbers the server now refuses (comma-lab transcription is
unusable from the UI), the retired flat-±10 % pages can be approved from the new catalogue
screen and doing so retires a strain's live fitted set, the single-certificate CoQ route
missed the REJECT gate, a RETEST CoQ prints nothing that says it is one, and the ladder
half of QC-11 was not touched. Counts: **0 critical · 0 high · 5 medium · 8 low.**

## Closure table

| id | status | evidence |
| --- | --- | --- |
| QC-01 | PARTIAL | 829bae1: `coq_aggregation.py:53-66` (`_REJECTED_OOS_SQL`, `_assert_batch_not_rejected`), `:615-660` (cover only when `invalidated`; a CLOSED non-invalidating OOS on the test → 409 "CONFIRMED"); run at compile `:501`, review `:773`, render `:842`. Pinned by `test_qc01_retest_does_not_overturn_a_confirmed_oos`, `test_qc01_only_an_invalidating_oos_covers_a_masked_failure`. **Open:** the single-certificate CoQ (`coq_docx.py:473`, `generate_coq`) still checks only open OOS (`:508`) → QR-03. |
| QC-02 | CLOSED | c89f33e: `certificates.py:551-557` (`_live_coq_citing`), `:668-674` (release of a revision refused), `:836-843` (void refused); 829bae1: `coq_aggregation.py:69-86` (`_assert_sources_live`) at review `:774` and render `:843`; `_SOURCES_SQL` returns live status/decision `:333-336`. Tests `test_qc02_*` (two). |
| QC-03 | PARTIAL | Server side closed: 04b83ee `common.py:121-205` (`parse_lab_number`, `reconcile_numeric`), c89f33e `certificates.py:390-395`, `ecoa.py:645-654,748,833`; `laboratories.decimal_separator` is now read. Verified `("0,6", 0, ",") → 422`, `("0,6", 0, ".") → 422`, `("22,61", None, ",") → 22.61`. Tests `test_qc03_*`. **Open:** the UI still `parseFloat`s and sends `numeric_value` (`qcecoa-view.js:127`, `qccoa-view.js:256/262`) → QR-01, QR-13. |
| QC-04 | CLOSED | 97f75f4: product branch `coq_aggregation.py:172-213, 291-300`, `coq_docx.py:189-215`; a2c0084: `potency.py:238-249` (`_refuse_when_products_live` on create/approve), `potency_import.py:151-160` (org-wide 409); a85a94b: compile form sends `product_id` (`qccoa-view.js:660-662, 798`). Tests `test_potency_coq.py:140-270`, `test_products.py:212-247`. |
| QC-05 | CLOSED | 04b83ee `common.py:44-88` (`_dec`, `_evaluate` as Decimal), limits bound as Decimal in `specs.py:373-376`; promote recomputes `complies` `ecoa.py:1046-1050`. Tests `test_qc05_*`. |
| QC-06 | CLOSED | c89f33e `certificates.py:533-548` (`_results_bar_pass`) at PATCH `:617-620` and at APPROVED/RELEASED `:661-666`; iCoA page flags an inconsistent PASS `spec_html.py:404-411`; 829bae1 FAIL sources make the CoQ non-conforming / need an invalidating trail `coq_aggregation.py:571-577, 690`. Tests `test_qc06_*` (three). |
| QC-07 | PARTIAL (by decision B-4) | c89f33e `certificates.py:28` (COQ not creatable), `:329-332` (422), `:644-651` (legacy COQ rows gated on `_COQ_ROLES`); `coq_docx.py:256-258` RELEASED not printed. Tests `test_qc07_*`. The single-certificate render is kept and still unregistered — owner call, recorded. |
| QC-08 | CLOSED | 04b83ee `specs.py:227-231` (effective pair), `:275` + `:303-321` (`_assert_header_window_backed` at QA_APPROVED); c89f33e `coq_docx.py:104-125` prints the parameter's limits. Test `test_qc08_*`. Print caveat → QR-06. |
| QC-09 | CLOSED | c89f33e `certificates.py:451-455` (default facility day), `ecoa.py:989-994` (promote refuses without `report_date`), `:1062` carries it; 829bae1 `coq_aggregation.py:529-541` sorts by measurement date, undated legacy rows by facility day of entry. Test `test_qc09_*`. |
| QC-10 | PARTIAL | Computed parameters never a mapping target `ecoa.py:706-713, 836-841, 927-933, 1040-1044`; `generate_coq` refuses a transcribed total `coq_docx.py:559-569`; one `derived_total` `common.py:98-113` used at `coq_aggregation.py:667` and `coq_docx.py:575`. Tests `test_qc10_*`. **Open:** certificate-level potency history unchanged (`products.py:387-397`) → QR-11. |
| QC-11 | PARTIAL | Spec parameters `specs.py:263-271`; checklist decider `ecoa.py:601-609`. Tests `test_qc11_*`. **NOT FIXED:** ladder `ranges`-only PATCH still stamps no `updated_by` (`potency.py:300-327`), approve checks only the parent row (`:343`) → QR-05. |
| QC-12 | CLOSED | 829bae1 `signatures.py:36-40, 112-140` (role of record, RELEASED per type, COQ_ISSUED to `_COQ_ROLES`), `:178-222` (`POST /qc/coq/{id}/sign`), rendered `coq_aggregation.py:929-933` + `coq_docx.py:401-411`; 0071 adds `COMPILED` to the CHECK (schema `:1738`). Tests `test_qc12_*` (two). |
| QC-13 | CLOSED | 829bae1 `oos.py:255-259` via `leaves._assert_leaf_open` (`:42-55`, notes only). Test `test_qc13_closed_oos_is_frozen`. |
| QC-14 | PARTIAL | Code: explicit windows `products.py:266-281`, `nearest_of` per the owner's rule `:222-244` (verified: inside → closest nominal, lower on tie; outside → nearest edge), `import-fitted` `:823-908`. Data: the facility's `qc_products` still holds the v.03 windows until the owner runs the fitted import and approves (HANDOFF); and a v.03 page remains approvable → QR-02. |
| QC-15 | CLOSED | 0071 (`purpose`, `timepoint`, rescoped `qc_coq_one_approved_idx`; schema `:1146-1149, 3525`); `coq_aggregation.py:101-116, 391-399, 417-428, 757-767`. Test `test_qc15_initial_and_retest_coqs_coexist`. The printed document and the UI carry no period → QR-04. |
| QC-16 | CLOSED | c89f33e `spec_html.py:150-176` (recorded approver, "QA review not captured"); template tokens `__SIG1_*`/`__SIG2_*` present, no hard-coded names (grep clean); a2c0084 `product_document` `:180-233`. Tests `test_spec_document_approved_drops_watermark_and_dates`, `test_product_document_prints_the_stored_window_and_only_recorded_people`. Label caveat → QR-10. |
| QC-17 | CLOSED | c89f33e `certificates.py:441-449`; `ecoa.py:656-672` (`_reconcile_unit`) at `:757, 866, 1045`. Test `test_qc17_*`. |
| QC-18 | CLOSED | c89f33e `certificates.py:779-811` (revise from APPROVED, every template column copied). Test `test_qc18_*`. |
| QC-19 | CLOSED | c89f33e `ecoa.py:431-443`. Test `test_qc19_*`. |
| QC-20 | CLOSED | 04b83ee `common.py:98-113` (Decimal, half-up); both CoQ paths use it. Tests `test_qc20_*` (two). |
| QC-21 | CLOSED | 829bae1 `coq_aggregation.py:911` (report date in `TZ`), c89f33e `certificates.py:307-309`, `custody.py:17` (`SITE_YY_SQL`). Test `test_qc21_*`. |
| QC-22 | CLOSED | `GET /qc/products/{id}/document` exists (`spec_html.py:179`); every product helper in `api.js:377-391` now has a caller in `qcpotency-view.js` / `qccoa-view.js`; the A4 link is fetched with the token (a85a94b). Tests `test_product_document_*`. |
| QC-23 | CLOSED | 829bae1 `custody.py:366-378` (RQS §6.1.4 fields only while OPEN, terminal states note-only), `:552-555` (SFR). Test `test_qc23_*`. |
| QC-24 | CLOSED | 04b83ee `leaves.py:66` (`passed: bool` required), `WaterPatch` without it `:71-75`, `update_water :191`. Test `test_qc24_*`. |
| QC-25 | CLOSED | c89f33e `coq_docx.py:351-366` (∑ cites 3028, Q names the actual in-house tests), `:392-403` (accredited claim conditional); `coq_aggregation.py:880-898, 977-981`. Test `test_qc25_*`. |
| QC-26 | CLOSED | c89f33e `coq_docx.py:19-35`. Test `test_qc26_*`. |
| QC-27 | CLOSED | 04b83ee `common.py:208-217` (`norm_batch`) on `CoqIn`/`OosIn`/`CoaIn`/samples; gates compare `upper()`. Test `test_qc27_*`. Residual exact matches (legacy rows only): `coq_aggregation.py:257, 353`, `cert_register.py:71, 104`, `oos.py:220` — folded into QR-07. |
| QC-28 | CLOSED | 04b83ee `common.py:220-238` (`mint_series_number`) at `specs.py:191`, `samples.py:143,195`, `laboratories.py:124`, `custody.py:526`, `leaves.py:179,227,278`; 0071 drops the eight sequences (verified standalone in the old schema — no column default used them). Test `test_qc28_*`. |
| QC-29 | CLOSED | 829bae1 `custody.py:630-640`. Test `test_qc29_*`. Decision-register conflict with E-2 → QR-08. |
| QC-30 | CLOSED | a2c0084 `products.py:286-311` (`_tie_code_to_grade`, canonical code), `update_product :545-578` validates the merged row before the UPDATE. Tests `test_products.py:107-155`. |
| QC-31 | mostly CLOSED | duplicate extraction rows `ecoa.py:722-727, 755-761, 843-849, 1004-1013`; `oos_reference` always validated `coq_aggregation.py:548-558`; `qc_oos_register` SELECT+INSERT policies (0071; schema `:5948, 5969`; the demo wipe uses the BYPASSRLS admin pool, `demo_org.py:328-335`, so it still works); `/register` lists `qc_coq` `cert_register.py:99-149`; retention window `certificates.py:606-612`; `update_coa_document` status predicate `ecoa.py:419-425`. Tests `test_qc31_*` (five). **NOT FIXED (acknowledged in HANDOFF):** the acid/neutral name heuristic `specs.py:29-48, 356-366`. |
| INS-01 | CLOSED | as QC-04; `test_coq_graded_against_a_product_reports_conformance`. |
| INS-02 | CLOSED | `qcpotency-view.js` is the catalogue (list/approve/supersede/conformance/A4/fitted import); the ladder import is shown only while no product exists (`:399`); `potency_import.py:151-160` 409s org-wide once a product is APPROVED. |
| INS-03 | PARTIAL | Code closed (a2c0084: explicit windows, `POST /qc/products/ladder`, `import-fitted` with the service's arithmetic check and the ±10 % ceiling; `window_for` reference-only, callers are tests only). The rollout — export from the live service, state the document version, second-person approval — is a human step still ahead; see QR-02 for the guard it lacks. |
| INS-04 | CLOSED as C-1 | `coq_aggregation.py:215-241` (regrade + deviation to every CU_MGR/PR_MGR at compile; the roles exist, `roles.py:9-10`), `:243-268` + `:749-751` (approval refused until an OOS naming Total Δ9-THC exists); chips in the UI (`tests/frontend/qccoa-coq-potency.test.js:124-146`). Test `test_out_of_window_coq_is_regraded_flagged_investigated_and_handed_over`. Gate weakness → QR-07. |
| INS-05 | CLOSED | `imb_products.json`: PUM "Pure Michigen", CLE "Clemosa A Bud" canonical with `retired_spellings`; `products.py:716-741` renames on import; the four disputed names flagged `spelling_disputed` and aliased to one cultivar (`potency_import.resolve_or_create_cultivar`). Tests `test_import_renames_a_cultivar_still_carrying_a_retired_spelling`, `test_import_fitted_resolves_a_disputed_spelling_to_the_one_cultivar`. |
| INS-13 | PARTIAL | Ceiling closed (`products.py:266-281`, test `test_a_window_may_not_exceed_ten_percent_of_the_nominal`). Overlap is checked only for ladder/fitted sets (`_validate_grade_set :312-328`); single create/approve never checks siblings → QR-09. |
| INS-14 | NOT FIXED | `origin/claude/sync-potency-spec-service` is still `63474db` (2026-09-16 09:28, build `-27`); the `-28` two-per-page build is not in git. Acknowledged in `PRODUCT-CATALOGUE-2026-09.md` "Open" and by C-8 (which only skips partner ids). |
| AD-12 | refined (C-2) | `nearest_of` verified with a snippet: dead band → nearest edge, `regrade_to` None; on a bound → conforms. |
| AD-14 | kept + extended (C-3) | `approve_product :596-612` also supersedes the cultivar's APPROVED products of any other `doc_version` — in both directions, which is QR-02. |
| §5 dead code (QC-22, QC-03) | CLOSED | product helpers have callers; the document route exists; `decimal_separator` is read. |

## Seam checks the coordinator asked for

- **Gate order.** Compile: open-OOS (409, deviation recorded in its own tx) → `_assert_batch_not_rejected` → `_compile_coq_tx` (oos_reference, FAIL sources, masked-failure cover) → `_grade_against_product` (never blocks; notification inside the same `rls()` transaction, which is a real transaction — `db.py:80-93`). Review: `_regrade_needs_oos` → second person → duplicate period → open-OOS → REJECT → sources live → UPDATE. Render: status/overall_conform → open-OOS → REJECT → sources live → `_coq_disposition` for the Grade cell. Nothing short-circuits; the only quirk is cosmetic (a compiler self-approving an out-of-grade CoQ sees the regrade 409 before the 403).
- **`_coq_out`.** `purpose`/`timepoint` print on list, detail and compile (they are row columns). `product_code`/`product_conforms`/`regrade_to` print on compile (`:503`) and detail (`:378`) and are `None` on the list (documented at `:150-152`); the UI list reads neither, so no contract breaks.
- **`_coq_grade_value` vs `_coq_disposition`.** Same dict; conforms/regrade_to/dead-band branches verified by snippet and by `test_potency_coq.py:168-231`.
- **Decimal vs float.** `conforms`/`nearest_of`/`conformance_of` only read and cast both sides to `float()` with `_EPS`; product windows are float-bound (a numeric tail — verified on a temp table: `23.4` stores as `23.39999999999999857891452847979962825775146484375`) but round-trip through `float()` exactly, and no product value is ever written into `qc_results`/`qc_coq_lines`. The CoQ total is bound as Decimal (`derived_total`). The binding survives.
- **Spec page with `approved_by` NULL.** Renders: `spec_html.py:150-159` guards the lookup and prints "—".
- **0071 vs `schema.tasks.sql`.** Consistent (schema `:1146-1149`, `:1738`, `:3525`, `:5948/5969`; no dead sequence). 0071 is the sole child of 0070. Downgrade order is correct; caveat QR-12.
- **Owner decisions vs C-1…C-8.** 09-06 "falls to the next grade above or below", "indicated visually", "deviation to Cultivation and Production", "value accepted / not blocked" — built. "A formal OOS … should be opened" became "must exist before approval" (C-1, recorded). 09-18 "fitted everywhere / full tolerance for a sparse strain" — the ceiling admits exactly ±10 % (`_check_window` arithmetic checked for nominal 8, 14, 26); but nothing stops the retired v.03 pages being approved (QR-02). 09-06 "ranges not overlapping" — enforced for sets only (QR-09).

## Findings

### QR-01 [medium] contract — The eCoA transcription screen still client-parses numbers, so every comma-decimal line of a comma-laboratory document is now refused

**Where:** `web/gf/qcecoa-view.js:127` (`parseFloat(parts[1])` → `numeric_value`), against `backend/app/api/qc/ecoa.py:748` → `common.py:171-205` (`reconcile_numeric`, disagreement → 422 at `:197`).

**What happens:** The laboratory is registered with `decimal_separator=","` (the case QC-03 was about). The reviewer pastes `Lead | 0,6 | mg/kg`. The UI sends `raw_value="0,6", numeric_value=0`; the server parses `0.6`, sees the supplied `0`, and answers **422 "numeric_value 0 disagrees with the transcribed text '0,6'"**. Every line with a decimal comma fails the same way (`22,61` → 22 vs 22.61), and the bulk submit is one transaction, so nothing of the document can be entered from the screen. The server is right; the UI was not updated. (For a "." laboratory the same paste is refused with the intended message, which is correct.)

**Evidence:** Ran `reconcile_numeric("0,6", 0, ",")` and `("22,61", 22, ",")` → 422 both; `("22,61", None, ",")` → `22.61`. Read the paste parser.

**Fix:** In the paste parser send only `raw_value` (drop the `numeric_value` guess — the server derives it), and in `qcEcoaSaveEx` refuse a value containing a comma instead of `parseFloat`ing it.

### QR-02 [medium] instruction (owner 2026-09-18) — The retired flat-±10 % v.03 pages can still be imported *and approved* from the catalogue screen, and approving one silently retires the strain's live fitted set

**Where:** `backend/app/api/qc/products.py:580-612` (`approve_product`: `versions` UPDATE supersedes every APPROVED product of the cultivar whose `doc_version` differs — in either direction), `:752` (`import_products` always available), `web/gf/qcpotency-view.js:391-397` ("Import ImB pages" offered whether or not products exist) and `:307` (Approve on any DRAFT).

**What happens:** The fitted CJ set (14/17/20/24/28, `v.04`) is APPROVED. The HoQC clicks "Import ImB pages" (idempotent, lands 42 DRAFT `v.03` rows), then Approve on `CJ_THC28:CBD1 v.03`. `approve_product` supersedes the same-code row and then **all five fitted CJ products**; the strain now grades on one flat window 25.20–30.79, exactly the scheme the owner retired ("±10 % flat is not gonna work"). Nothing warns. The reverse direction (approving the first fitted product retires the v.03 set) is C-3 and intended; this direction is not.

**Evidence:** Read `approve_product`; the `versions` statement has no ordering or version comparison. Read the importer panel: the ImB block is unconditional (`hasProducts` only hides the legacy ladder details at `:399`).

**Fix:** Refuse approval of a product whose `doc_version` is the packaged reference version (`imb_products.json.doc_version`) once any product of another version is APPROVED for that cultivar — or, more generally, refuse an approval that would supersede products of a *newer* version; hide the ImB import once any product exists.

### QR-03 [medium] GMP (QC-01 residual) — The single-certificate CoQ route still issues a "Certificate of Quality" for a batch whose investigation closed with REJECT

**Where:** `backend/app/api/qc/coq_docx.py:473-520` (`generate_coq`): the only OOS gate is the open-OOS count at `:508`; `_assert_batch_not_rejected` lives only in `coq_aggregation.py:53-66`.

**What happens:** iCoA-PP-2026-0004 is RELEASED with every line complying; an OOS on the same batch (raised on another certificate, say water content) is CLOSED with QP disposition **REJECT**. `POST /qc/certificates/{id}/coq` renders a .docx headed "Certificate of Quality — Conforms to Specification" for a rejected batch. The aggregation path refuses this at compile, review and render; the route B-4 kept for the UI (`qcCoaGenerateCoq`) does not.

**Evidence:** Read `generate_coq` end to end; grep for `_assert_batch_not_rejected` — one module.

**Fix:** Move `_assert_batch_not_rejected` to `common.py` and call it in `generate_coq` next to the open-OOS gate (or retire the route, which B-4 leaves open).

### QR-04 [medium] document-integrity (QC-15 seam) — A RETEST CoQ prints nothing that identifies it as a re-test, and the UI can neither compile nor display one

**Where:** `backend/app/api/qc/coq_aggregation.py:905-921` (`coa_view` has no purpose/timepoint), `coq_docx.py:312-329` (grid rows: no "testing period"), `web/gf/qccoa-view.js` (no `purpose`, `timepoint` or `source_coa_ids` anywhere).

**What happens:** For batch P050022 the INITIAL CoQ-PP-2026-0007 and the 6-month RETEST CoQ-PP-2026-0012 are both APPROVED (the point of QC-15). Both documents print the same batch, specification, product and "Conforms" — different numbers, different results, no statement of which period each certifies; the register (`/register`) shows them as two COQ rows with nothing to tell them apart either. The QP receives two live conformance certificates for one batch with no printed reason. And because the compile form has no period fields, a RETEST can only be compiled by hand against the API.

**Evidence:** Read the renderer's grid and `render_coq`'s `coa_view`; grep of the view for the three fields returns nothing.

**Fix:** Add a required grid row "Период на тестирање~~Testing period ||| Initial release" / "Re-test 6M" from `coq.purpose`/`timepoint` (and the source certificate numbers already print in §02); add purpose/timepoint/source selection to the compile form and a period column to the CoQ list.

### QR-05 [medium] segregation-of-duties (QC-11 NOT FIXED for ladders) — A ranges-only PATCH still leaves `updated_by` unstamped, so whoever rewrote the tiers can approve them

**Where:** `backend/app/api/qc/potency.py:296-327` (`update_potency_spec`: `ranges` is skipped in the field loop at `:300`, the UPDATE — and the `updated_by` stamp — runs only `if fields:` at `:307`, then `_insert_ranges` at `:323` rewrites the tiers); `:343` (`approve_potency_spec` checks only the parent row's `created_by`/`updated_by`).

**What happens:** Exactly the first review's scenario: A creates a DRAFT ladder, B `PATCH {"ranges": [...]}` with B's tiers (no parent-row change, no stamp), B approves — the check sees A/A. Reachable for every cultivar that has no APPROVED product (C-7 only closes the ladder once a product is live), which today is every cultivar until the fitted import is approved.

**Evidence:** Read the two functions; `git diff 549b617..HEAD -- potency.py` touches only `_refuse_when_products_live`; no test in `test_qc_review_2026_09.py` or `test_potency.py` covers a ranges-only PATCH followed by approval.

**Fix:** Stamp `updated_by`/`updated_at` whenever `ranges` is in the patch (an UPDATE with no other field), and in `approve_potency_spec` also refuse anyone found in `qc_potency_spec_ranges.created_by` for that ladder.

### QR-06 [low] document-integrity — The CoQ Potency row prints a legacy float-bound limit with its 47-digit binary tail

**Where:** `backend/app/api/qc/coq_docx.py:104-119` (`_coq_potency`: `f"THC {lo}–{hi}%"` with the raw `Decimal` from `qc_spec_parameters.lower_limit numeric`, schema `:1506`).

**What happens:** Every `total_thc` parameter created before 04b83ee was bound as a float (`add_parameter` passed `body.lower_limit`), and asyncpg stores a float into an unscaled `numeric` as its binary expansion. The Potency row of the .docx then reads `THC 23.39999999999999857891452847979962825775146484375–28.589999999999999857891452847979962825775146484375%`. The comparison path is immune (`_dec` folds a >15-digit tail, `_coq_criterion` casts to float); only this print is raw. Whether production holds such rows is UNVERIFIED (no production contact), but the fixer's own `_dec` docstring says they exist, and the QC-08 fix moved the print onto exactly these columns.

**Evidence:** asyncpg temp-table check (`INSERT … $1` with `23.4` → `23.39999999999999857891452847979962825775146484375`); `_coq_potency` run with `Decimal(23.4)` printed the tail, with `Decimal("23.4")` printed `THC 23.4–28.59%`.

**Fix:** Format through `_dec()` (or `f"{float(lo):g}"`) in `_coq_potency`; optionally a one-off data normalisation of `qc_spec_parameters` limits to two places.

### QR-07 [low] gate weakness (C-1) — `_regrade_needs_oos` is satisfied by any OOS row on the batch that names Total THC, whatever its status, outcome, period or case

**Where:** `backend/app/api/qc/coq_aggregation.py:243-268`, query at `:256-258` (`WHERE org_id=$1 AND batch_id=$2`, exact match, no status/`invalidated`/date filter).

**What happens:** (1) The INITIAL-period out-of-grade OOS closed RELEASE months ago; the 6-month RETEST CoQ for the same batch is again out of window — approval passes without a new investigation, because a record naming Total THC exists. (2) An OOS closed with `invalidated=true` (assignable lab error on a Total THC result — the batch disposition was never investigated) satisfies the "formal OOS on the batch disposition" the owner asked for. (3) A pre-normalisation OOS filed as `p050022` is invisible to this gate while every other gate compares `upper()` (QC-27 residual, also `:353`, `cert_register.py:71,104`, `oos.py:220`).

**Evidence:** Read the function and `names_total_thc`; compared with the `upper()` idiom of `_OPEN_OOS_SQL`.

**Fix:** Require an OOS naming Total Δ9-THC that was opened at or after this CoQ's `compiled_at` (or that cites the CoQ / its total line via `result_id`), exclude `invalidated=true` records, and compare `upper(batch_id)`.

### QR-08 [low] decision conflict — E-2 (custody form) and B-12 (QC-29) record incompatible rules; the server wins and the form's stated purpose is unreachable

**Where:** `docs/DECISIONS-2026-09.md` §2b rows E-2 and B-12; `web/gf/qccustody-view.js:344, 209` (hidden `from_user_id` = last recipient); `backend/app/api/qc/custody.py:630-640`.

**What happens:** E-2 says the pre-filled `from_user_id` exists "so a QC writer can log a hop on the custodian's behalf". B-12 makes the server refuse exactly that (403 unless the recorder is the giver or the receiver). The form works for the normal case (the recorder names themselves as receiver), but a writer recording "custodian X → sample store" with no receiver gets a 403 the form did not anticipate, and the decision register now asserts two contradictory rationales to the owner.

**Evidence:** Read both rows and both code sites.

**Fix:** Keep B-12; default `to_user_id` to the signed-in user in the form when no receiver is chosen, and rewrite E-2 ("…so the continuity check has the previous custodian; the recorder must still be a party").

### QR-09 [low] owner rule 2026-09-06 (INS-13 residual) — Single-product create/approve never checks overlap with the strain's same-version siblings

**Where:** `backend/app/api/qc/products.py:507-545` (`create_product`), `:580-612` (`approve_product`); `_validate_grade_set` (`:312-328`) runs only for `/ladder` and `import-fitted`.

**What happens:** `POST /qc/products` `GP_THC26:CBD1 v.04 23.40–28.59` and then `GP_THC24:CBD1 v.04 21.60–26.39`, both approved by a second person, gives a fitted version with overlapping windows — which the owner ruled out ("ranges not overlapping") and which makes `nearest`/`regrade_to` depend on the tie-break rather than on the specification. `test_several_products_of_one_strain_coexist_with_overlapping_windows` pins the behaviour for the reference v.03 pages, which is fine for them only.

**Evidence:** Read both handlers; grep for `_validate_grade_set` / `_overlap` callers.

**Fix:** In `approve_product`, refuse (or at least return `overlaps_existing` and require a flag) when the window overlaps an APPROVED sibling of the same `doc_version`, exempting the packaged reference version.

### QR-10 [low] document-integrity — The legacy ladder page labels the recorded approver "Prepared & Approved by"

**Where:** `backend/app/api/qc/spec_html.py:171`.

**What happens:** `approve_potency_spec` forbids the approver being the author, so the person named under "Prepared & Approved by / Изготвил и одобрил" on an APPROVED ladder page by construction did *not* prepare it — the page asserts an act the system knows did not happen, the H5 rule QC-16 was about. The product page (`:180-233`) gets this right with separate "Prepared by"/"Approved by" blocks from `created_by`/`approved_by`.

**Evidence:** Read both renderers and the approval gate.

**Fix:** Label the slot "Approved by", and print `created_by` under "Prepared by" as `product_document` does.

### QR-11 [low] dead code (QC-10 residual) — Certificate-level potency history can no longer be populated, and its join is still exact code equality

**Where:** `backend/app/api/qc/products.py:387-397` (`_potency_history`: `qc_results` rows whose parameter is `computed_kind='total_thc'`, joined on `ct.batch_id`/`ct.cultivation_batch` = `plant_batches.code`).

**What happens:** After c89f33e no path can create such a row (`add_result` 422s, the eCoA mapping/PATCH/placeholder/promote paths refuse a computed parameter), so the source is empty for every certificate issued from now on; the first review's "attribute by the batch-code head, compute from the components" was not done. The mother bank's "tested so far" and the product detail keep showing a third source that is structurally empty.

**Evidence:** Read the query and the five refusal sites.

**Fix:** Compute the total from the component results (`derived_total`) per certificate, and match by the batch-code head (`^<CV>\d`) or drop the source and its UI column.

### QR-12 [low] migration — The 0071 downgrade destroys Annex 11 records and fails on the data 0071 was written to allow

**Where:** `backend/alembic_tasks/versions/0071_qc_review_fixes.py:86-112`: `DELETE FROM public.qc_signatures WHERE meaning='COMPILED'` (`:94`) and the recreation of the old three-column unique index (`:103`).

**What happens:** A rehearsal or rollback on a database holding an INITIAL and a RETEST CoQ both APPROVED for one (batch, spec) aborts at the `CREATE UNIQUE INDEX`; and a downgrade that does run deletes every compiler e-signature rather than leaving the rows (the meaning CHECK could be re-added `NOT VALID`). The upgrade itself and `schema.tasks.sql` are consistent.

**Evidence:** Read the downgrade; the QC-15 test creates exactly this data shape.

**Fix:** In `downgrade`, void RETEST CoQs explicitly (or drop the index without recreating it) and keep the COMPILED rows behind a `NOT VALID` CHECK; at minimum say so in the docstring.

### QR-13 [low] QC-03 residual — The iCoA numeric box still truncates a comma value when the text box is empty

**Where:** `web/gf/qccoa-view.js:256, 262` (`result_numeric: parseFloat(...)`); `backend/app/api/qc/certificates.py:394` (`reconcile_numeric(None, 22, ".")` → 22 — nothing to reconcile against).

**What happens:** An analyst types `22,61` only in the numeric box: the UI sends `result_numeric=22`, `result_value=null`; the server has no raw text and stores 22. With a text value present the server refuses correctly (in-house separator ".").

**Evidence:** Ran `reconcile_numeric(None, 22, ".")` → `22`; read the form builder.

**Fix:** Refuse a comma in the numeric box client-side, and/or always send the typed text as `result_value` so the server reconciles it.

## Not re-reported (still open, acknowledged by the workstreams)

- QC-07 single-certificate CoQ render kept and unregistered (B-4); QC-31 acid/neutral heuristic; INS-14 builder build not in git — all listed in `HANDOFF.md` "Findings deliberately left open".
