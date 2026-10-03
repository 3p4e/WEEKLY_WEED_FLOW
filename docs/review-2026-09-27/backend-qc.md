# Backend review: the QC subsystem (`backend/app/api/qc/*`)

Reviewer scope: 21 modules, 7,547 lines, the tasks-chain QC migrations (0018–0067) and
`schema.tasks.sql`, the QC calls in `web/gf/api.js` and the QC views. I read the code
statically and ran pure-Python and node snippets. I did not run pytest and did not
contact production. HEAD is `807d60f`.

## Summary

The subsystem is large and mostly careful. Every route has a role gate, and every
table has RLS and a hash-chained audit trigger. Certificate numbering is per
organisation, per type and per year, and is locked. Most H- and M-findings of
`QC-SUBSYSTEM-REVIEW-2026-08` are fixed and I checked the fixes: H1, H2, M1–M8,
M10, and signatures now append-only (0061). The remaining weaknesses are of three
kinds:

- **Grading gates trust the wrong thing.** Four gates can be defeated:
  - a CLOSED OOS covers a masked failure whatever the OOS concluded;
  - the conformance a CoQ reports is not re-checked when its source certificates are voided;
  - the client parses numbers, and the server believes it;
  - a certificate's PASS/FAIL is never checked against its results.
- **The 2026-09-05 product catalogue is only half built.** The backend tables and
  routes exist. CoQ grading, the A4 page and the whole UI do not. The UI still runs
  the potency ladders the owner superseded, and nothing stops them being approved
  again.
- **Several paths have drifted apart.**
  - Three routes produce a "Certificate of Quality".
  - Total Δ9-THC is read or computed three different ways.
  - Two grade vocabularies plus the product code appear on one document.
  - eCoA grading compares float to Decimal, while manual entry compares float to float.

Counts: **4 high · 13 medium · 14 low**.

---

### QC-01 [high] data-integrity — A retest silently overturns a *confirmed* OOS: any CLOSED OOS that names the test counts as "cover"

**Where:** `coq_aggregation.py:332-373` (the masked-failure cover). The OOS outcome
fields `invalidated`, `lab_error` and `disposition` (`oos.py:62-76`) are written but
never read by any gate.

**What happens:**
1. Total THC fails on iCoA #1 (15.2 % vs ≥ 16).
2. OOS PP-OOS-2026-0001 is opened for "Total THC". Phase I finds no lab error
   (`invalidated=false`). Phase II attributes the failure to the batch. The QP closes it
   with `disposition=REJECT`.
3. A retest on iCoA #2 gives 16.3 %.
4. `compile_coq` picks #2 as the "latest" result, puts #1 in `masked_fails`, and finds a
   CLOSED OOS whose `test_name` matches. The failure counts as covered, and the result
   is `overall_conform=true`.
5. The HoQC approves, and `render_coq` prints "Conforms to Specification".

This is "testing into compliance". Only an OOS that *invalidated* the original result
(an assignable lab error) should let a retest replace it. The code's own docstring says
the CoQ "is compiled only on the investigation-confirmed result set", and the OOS
record's REJECT disposition is ignored.

**Evidence:**
- Read `_compile_coq_tx`. The cover set is built from
  `SELECT result_id, test_name FROM qc_oos_records WHERE … status='CLOSED'`.
- Grepped for `invalidated`, `lab_error` and `disposition`: they appear only in
  `oos.py` (read/write) and nowhere in any gate.

**Fix:**
- Cover a masked failure only with a CLOSED OOS whose `invalidated IS TRUE`, bound to
  that result (`result_id`) or test.
- Refuse the compile outright when any CLOSED OOS on the batch has `disposition='REJECT'`.

### QC-02 [high] data-integrity — An aggregation CoQ is approved and rendered after one of its source certificates was voided or superseded

**Where:**
- `certificates.py:692-711` (`void_certificate`): no check of `qc_coq_sources`.
- `coq_aggregation.py:482-517` (`review_coq`) and `:563-705` (`render_coq`): neither
  re-validates the sources.
- `coq_aggregation.py:141-146` (`_coq_source_out`): the source's current status is not
  returned, so the UI (`qccoa-view.js:717`) shows bare numbers.

**What happens:**
1. A CoQ is compiled from iCoA A and eCoA B.
2. The HoQC voids A under §6.6 as "fundamentally invalid" (wrong sample or batch), or
   revises A and releases the revision (A becomes SUPERSEDED with corrected values).
3. The DRAFT CoQ can still be approved, and the APPROVED CoQ can still be rendered.

The printed CoQ asserts conformance from lines snapshotted off a voided or superseded
record. The comment in `_compile_coq_tx` ("no window for a source to be voided") is
true only inside the compile transaction.

**Evidence:** Traced all three handlers. None of them joins `qc_coq_sources` to
`qc_certificates.status`. The FK is `ON DELETE RESTRICT` only (schema line 5043).

**Fix:**
- In `review_coq` and `render_coq`, 409 when any source's status is not in
  `('APPROVED','RELEASED')`.
- In `void_certificate`, and when a revision is released, refuse or flag when the
  certificate is cited by a DRAFT/APPROVED `qc_coq`.
- Return each source's live status from `GET /qc/coq/{id}`.

### QC-03 [high] correctness — Comma-decimal lab values are truncated by the client, and the server grades the truncated number while printing the original

**Where:**
- The laboratory's `decimal_separator` is stored (`laboratories.py:27,40`) and never
  used anywhere (grep).
- `ecoa.py:650` and `:732` trust `numeric_value`.
- `certificates.py:401` trusts `result_numeric`.
- The UI parses with `parseFloat`: `web/gf/qcecoa-view.js:127,176` and
  `web/gf/qccoa-view.js:256`.

**What happens:** A Macedonian-format CoA line `Lead | 0,6 | mg/kg` (specification ≤ 0.5):
- `parseFloat("0,6")` is `0`, so `numeric_value=0` and `raw_value="0,6"`.
- It is graded `complies=true`.
- Promote copies `result_value="0,6"` and `result_numeric=0`.
- `generate_coq` / `render_coq` print "0,6 mg/kg" against "… 0.5" under
  "Conforms to Specification".
- `verify_certificate` compares the certificate with the extraction (both 0) and says
  VERIFIED.

The same happens in the iCoA "numeric" box (`"22,61"` becomes `22`). Verified with
`node -e`: `parseFloat("22,61") → 22`, `parseFloat("0,6") → 0`,
`parseFloat("1.234,5") → 1.234`.

**Fix:**
- Parse on the server: derive `numeric_value` from `raw_value` using the source lab's
  `decimal_separator`.
- 422 when a supplied numeric value disagrees with the parsed raw value.
- In the UI, reject any value that contains a comma instead of truncating it.

### QC-04 [high] owner-contradiction — The official product catalogue is not wired into CoQ grading or the UI; the UI still runs the superseded ladders, and one can be approved again

**Where:**
- The backend has no product branch:
  - `coq_aggregation.py:89-123` (`_coq_disposition` returns None unless a ladder is frozen);
  - `:63-86` (`_coq_out` has no `product_code` / `product_conforms`);
  - `coq_docx.py:184-205` (`_coq_grade_value`, ladder only);
  - `coq_aggregation.py:663` (`product_code` printed from the source iCoA's free text,
    not from `qc_products`).
- Ladder approval never looks at `qc_products`: `potency.py:314-345`.
- In the UI:
  - `qccoa-view.js:652-653,764`: the compile form sends only `cultivar_id` ("Freezes
    the APPROVED potency ladder").
  - `qcpotency-view.js`: ladders only, including "Import catalogue (71 strains)" and
    Approve ("Ladder approved — it now grades certificates").
  - No QC view calls `qcProducts`, `qcApproveProduct` or `qcImportProducts`. The only
    consumer is `propagation-view.js:318`.

**What happens:** The owner's 2026-09-05 decisions made the ImB product pages the single
live potency catalogue and superseded the ladders. The plan's commits 2 and 6 were not
built:
- A CoQ compiled with a `product_id` (API only) prints **no grade at all**.
- A CoQ compiled from the UI can only freeze a ladder.
- After a product is approved, the cultivar's ladder is SUPERSEDED, so UI-compiled CoQs
  carry no grade.

Nothing stops the ladder coming back:
1. A leftover August DRAFT ladder can be approved from `qcpotency-view`, or a new one
   created with `POST /qc/potency-specs` or `/import`.
2. That makes a live ladder again next to APPROVED products — "two answers to one question".
3. Every later UI compile prints `Spec II · nominal 24 % — PP-QC-SPEC-001 …` on the CoQ.

Products can be imported and approved only by raw API calls (42 approvals).
`docs/HANDOFF.md:81-82` says a CoQ outside its window "today prints 'does not conform'
and still renders". That is false. `PRODUCT-CATALOGUE-2026-09.md:330-338` states the
truth ("Not yet built").

**Evidence:**
- Read the three functions above.
- Grepped `web/gf` for product helpers.
- `backend/tests/test_products.py:193-196` asserts only that `product_id` round-trips.

**Fix:**
- Implement the product branch: `_coq_disposition` returns
  `{kind:"product", product_code, window, total, conforms}`; add it to `_coq_out`; add
  the product string to `_coq_grade_value`; print the `qc_products.product_code`.
- Add the product selector to the compile form.
- Make `approve_potency_spec` / `create_potency_spec` 409 when the cultivar has an
  APPROVED `qc_products` row.
- Turn `qcpotency-view` into the product catalogue (plan commit 6).
- Correct HANDOFF.md.

### QC-05 [medium] correctness — eCoA grading compares a float to a `numeric` limit, so a value exactly on its limit fails about half the time

**Where:**
- `ecoa.py:648-650` (`submit_extractions`: `lo, hi = param.get(...)` are Decimal from
  `qc_spec_parameters.lower_limit numeric`).
- `ecoa.py:732` (`update_extraction` re-map).
- `common.py:53-59` (`_evaluate`).

**What happens:**
- Python compares float and Decimal exactly, so `23.4 >= Decimal('23.4')` is **False**,
  and so are `0.1 <= Decimal('0.1')` and `0.05 <= Decimal('0.05')`.
- A lab reporting exactly the limit (common for LOQ-style limits, "Lead ≤ 0.1") is
  graded FAIL through the eCoA path.
- `add_result` converts limits to float first and grades the same value PASS.
- `promote` recomputes `status` from the extraction's *double precision* limits
  (`ecoa.py:870`) but copies the stale `complies` (`:878`). The result is a
  `qc_results` row with `status='pass'` and `complies=false`.

**Evidence:** Ran `_evaluate(23.4, Decimal('23.40'), None)`, which returns
`(False,'fail')`. Over 2-dp values 0–49.99, 2,396 of 5,000 fail as a lower bound and
2,404 of 5,000 as an upper bound.

**Fix:** In `_evaluate`, compare as `Decimal(str(value))` against `Decimal(limit)`, or
cast limits with `float()` at every call site. Recompute `complies` in promote instead
of copying it.

### QC-06 [medium] GMP — A certificate's PASS/FAIL disposition is never reconciled with its results

**Where:**
- `certificates.py:551-560`: APPROVED/RELEASED needs only *a* decision.
- `spec_html.py:243-248,271`: `all_pass` is computed and never used; the badge prints
  `coa.decision`.
- `coq_aggregation.py:322-446`: compile ignores the source certificate's `decision`.

**What happens:**
- An iCoA carrying a `complies=false` result, an unmeasured result, or **no results at
  all** can be approved and released as PASS. It then shows as PASS in `/register` and
  in `inherited-results`.
- The single-parameter iCoA HTML prints the row "✗ Does not conform" under a
  "Conforms to Specification" badge.
- The other direction also fails. A source certificate the HoQC dispositioned **FAIL**
  (for example on a non-numeric observation) still feeds a conforming aggregation CoQ,
  because compile reads only per-line `complies`.

**Evidence:** Read the transition code. `decision` is referenced only at lines 479 and
555 (grep).

**Fix:**
- Refuse `decision=PASS` when any result `complies IS NOT TRUE` or no result exists.
- Exclude sources with `decision='FAIL'` from compile, or fail the compile on them.
- Use `all_pass` (or the decision check above) in `icoa_document`.

### QC-07 [medium] owner/URS-contradiction — Three routes produce a "Certificate of Quality" under different rules; a COQ-type certificate can be approved only by the QP

**Where:**
- `certificates.py:542-550`: every non-ICOA type, **COQ included**, uses `_QP_ROLES`,
  so QC_MGR gets 403.
- `certificates.py:22` and `:48-57`: a COQ certificate mints from the shared CoQ-PP series.
- `web/gf/qccoa-view.js:53,816`: the UI offers `COQ` as a certificate type.
- `coq_docx.py:395-573` (`generate_coq`) plus `_COQ_SIG_ROLE:81-82`.

**What happens:**
1. **Aggregation** (`qc_coq`, the SOP path). HoQC approves, and no QP signature appears.
2. **A hand-made `cert_type='COQ'` certificate.** It skips compile, citations and
   review, takes a CoQ-PP number, and can be APPROVED/RELEASED **only by the QP**. That
   is the inverse of URS §3 / QCSOP 012 C5 and of the M2 fix, which applied to
   `qc_coq` only.
3. **`generate_coq` on any RELEASED iCoA/eCoA/COQ certificate.**
   - The document code is the iCoA/eCoA number, and no CoQ register entry is made (§6.13).
   - It is issued *after* QP release, which is the ordering QCSOP-012-ADHERENCE #1 flagged.
   - Every certificate e-signature is printed, including the QP's "Пуштил / Released by"
     row on a document that states "not QP batch release".
   - A transcribed total wins over computation (see QC-10).

**Evidence:** Read the transition gate and `generate_coq`. The UI exposes both
`qcCoaGenerateCoq` (`qccoa-view.js:539`) and COQ-type creation.

**Fix:**
- Drop `COQ` from `_CERT_TYPES` for new certificates, or route its approval through
  `_COQ_ROLES`.
- Stop rendering QP meanings (RELEASED) on CoQs.
- Retire the single-certificate CoQ render, or number it as a CoQ in the register.

### QC-08 [medium] document-integrity — The CoQ "Potency" row prints the specification's own THC range and grade, which nothing ever checks

**Where:**
- `coq_docx.py:91-105` (`_coq_potency`) and `:263`.
- `specs.py:74-76,84-86`: `thc_grade`, `thc_acceptance_min/max`. They are used nowhere
  else (grep), and a partial PATCH can store min > max (`specs.py:215-220`).

**What happens:**
1. A specification header says THC 23.40–28.59 %, GRADE_II.
2. Its computed Total THC parameter has no or looser limits.
3. The batch measures 19.5 %.
4. The CoQ prints "Potency: THC 23.4–28.59% · Grade II", the result 19.5 %, and
   "Conforms to Specification".

This is also a third grade vocabulary (GRADE_I–V) on the same document as the ladder
"Spec II" and the product code.

**Evidence:** Grepped `thc_acceptance` / `thc_grade`: only `specs.py`, `coq_docx.py`
and `demo_org.py`.

**Fix:** Either stop printing the header range, or validate it against the Total THC
parameter's limits at approval and grade the measured total against it.

### QC-09 [medium] correctness — "Latest result wins" actually means "last row entered"

**Where:**
- `coq_aggregation.py:324-326`: the sort key is `(result_date or date.min, created_at)`.
- `ecoa.py:872-879`: the promote INSERT has no `result_date`.
- `web/gf/qccoa-view.js:259-261`: the add-result form never sends `result_date`.

**What happens:**
- In practice every `result_date` is NULL, so "latest" is the most recently transcribed
  row, whatever the measurement date. An older lab report entered late replaces a newer
  in-house retest.
- Any dated result, from a programmatic caller, always beats every promoted eCoA
  result, because NULL sorts as `date.min`.

Combined with QC-01, the wrong result can become the batch's value.

**Evidence:** Read the INSERTs and the UI body builders.

**Fix:**
- Set `result_date` on promote from the document's `report_date`, and make it required
  (or defaulted to the facility day) in `add_result`.
- Sort on the measurement date, with NULL last.

### QC-10 [medium] drift — Total Δ9-THC is read or computed three different ways

**Where:**
- `ecoa.py:612-617`: `by_name` includes *computed* parameters, and `update_extraction`
  and `update_placeholder` do not exclude them. `add_result` does
  (`certificates.py:372-376`).
- `coq_docx.py:487`: a transcribed total skips the computation.
- `coq_aggregation.py:381-406`: always computes and ignores a transcribed total.
- `products.py:179-189`: certificate-level history reads **only** transcribed
  `qc_results` totals, joined on *exact* `plant_batches.code`.

**What happens:**
- A lab line "Total Δ9-THC" maps by name onto the computed `total_thc` parameter and is
  promoted as a transcribed total. The Ph. Eur. 3028 "never transcribed" rule is
  bypassed in this path.
- The single-certificate CoQ certifies the lab's figure, which may use another formula
  (the lab's rounding, or THC+THCA without 0.877) and skips `check_derived_total_units`.
- The aggregation CoQ computes its own figure for the same batch.
- Product "certificate-level" history contains only these transcribed totals. It never
  contains computed ones (iCoA totals cannot exist, since `add_result` 422s).
- Its join is exact equality with CU batch codes (`GP072501`), while release
  certificates name processing lots (`P050022`). The plan specified a batch-code-head
  match (`^<CV>\d`).

So certificate-level history is effectively always empty, and
`PRODUCT-CATALOGUE-2026-09.md:90-92` ("the same read the CoQ's own grade uses") is not
true of it.

**Evidence:** Read all four code paths and the `certificates.py:359-376` guard.

**Fix:**
- Exclude `computed_kind` parameters from extraction mapping (422 in `update_extraction`
  and `update_placeholder`).
- Compute the total the same way in both CoQ paths.
- Compute certificate-level history from the components, and attribute it by the
  batch-code head as planned.

### QC-11 [medium] segregation-of-duties — Approval checks miss co-authors

**Where:**
- `potency.py:292-308`: a PATCH carrying only `ranges` rewrites the tiers without
  stamping `qc_potency_specs.updated_by`. `approve_potency_spec` (`:327`) checks only
  `created_by` / `updated_by`.
- `specs.py:251-258`: specification approval ignores who authored the parameters
  (`add_parameter`, `:333-341`, stamps only the parameter row).
- `ecoa.py:552`: the checklist decider may be the person who transcribed the
  extractions.

**What happens:**
1. A creates a DRAFT ladder.
2. B PATCHes `{"ranges": [...]}` with B's own tiers.
3. B approves. The check sees A/A, so it passes.

The same shape exists for specification parameters added by the eventual approver
during QC_REVIEW, and for a HoQC accepting the checklist on values they typed in.

**Evidence:** Traced `update_potency_spec` (`fields` stays empty, so no `updated_by`)
and the approvers.

**Fix:**
- Always stamp `updated_by` when ranges change.
- In the approvers, also refuse anyone found in the child rows' `created_by` (ranges,
  parameters, extractions).

### QC-12 [medium] Annex 11 — E-signatures are not tied to the signer's role of record, and the CoQ prints them as if they were

**Where:**
- `signatures.py:26-28,91-163`: any `_WRITERS` member, OWNER/CEO/COO included, may sign
  any meaning. `COQ_ISSUED` and `VERIFIED` are unranked, so they can be signed on a
  DRAFT. A mismatch is only reported, never refused.
- `coq_docx.py:79-83,360-372` prints every signature as a role row.
- There is no signing route for `qc_coq`.

**What happens:**
- The analyst signs "APPROVED" on their own certificate, and the CoQ shows
  "Одобрил / Approved by: <analyst>".
- A QP signs "COQ_ISSUED", and the CoQ shows "CoQ issued by: <QP>", although QP is
  forbidden to issue CoQs (`_COQ_ROLES`).
- The SOP-path aggregation CoQ can never carry an Annex-11 signature, so it always
  prints "this document carries no electronic signature".

This is the uncertain item from the 2026-08 audit, still open, with concrete
consequences on the printed record.

**Evidence:** Read `sign_certificate` and the renderer's signature loop.

**Fix:**
- Require the signer to match the role of record for AUTHORED, REVIEWED and APPROVED.
- Gate COQ_ISSUED to `_COQ_ROLES`.
- Add `POST /qc/coq/{id}/sign` (meanings COMPILED, APPROVED) and render those signatures.

### QC-13 [medium] GMP — A CLOSED OOS investigation stays editable in place

**Where:** `oos.py:249-362`. Status is used only to check transitions, and there is no
freeze once CLOSED.

**What happens:** After the QP closes an OOS:
- any QC writer can PATCH `root_cause_description`, `impact_assessment`, `lab_error`,
  `invalidated`, `retest_result` and notes;
- the QP can change `disposition`.

The closed investigation record, which the CoQ gates rely on (QC-01), can be rewritten.
The audit trail records the change but nothing prevents it.

**Evidence:** Read `update_oos`. There is no `cur["status"] == "CLOSED"` check before the
field loop.

**Fix:** Freeze CLOSED records except `notes` (the `_assert_leaf_open` pattern from
`leaves.py`), and open a follow-up record for corrections.

### QC-14 [medium] owner-contradiction — The owner's 2026-09-06 and 2026-09-18 potency instructions are not implemented, and the live data contradicts the latest one

**Where:**
- `products.py:108-118,213-250`.
- `app/data/imb_products.json` (42 × ±10 % windows).
- `plantids.py:35-38`.

**What happens:**
- **2026-09-06T18:02.** A Total THC outside the batch's product window "falls to the next
  spec grade above or below … indicated visually, and a formal OOS regarding the Batch
  disposition should be opened". None of this exists: there is no out-of-window
  detection on a batch or CoQ, no regrade, and no automatic OOS.
- **2026-09-18T16:21.** "±10 % flat is not gonna work so the fitted approach is
  applicable everywhere". The only catalogue the app can load is the ±10 % flat
  overlapping set (16 of 20 junctions overlap), and conformance / `nearest` are computed
  against it.
- `nearest` returns the **highest** nominal satisfied, not the nearest. A 25.3 % Grape
  Pie reads `GP_THC28` (2.7 points away) rather than `GP_THC26` (0.7 away), which
  over-labels potency.

**Evidence:**
- Owner messages at those timestamps.
- `products.py:242-245`.
- `PRODUCT-CATALOGUE-2026-09.md:237-257` (the overlap counts).
- `HANDOFF.md:85-87` lists the fitting-code extraction as undecided.

**Fix:**
- Obtain the owner's go-ahead and load the fitted windows as a new `doc_version` (a data
  change, since `qc_products` stores the windows).
- Rename or redefine `nearest` (smallest |value − nominal|).
- Build the out-of-window OOS hook once the windows no longer overlap.

### QC-15 [medium] owner-contradiction — CoQs for the initial release and later retest periods cannot coexist

**Where:**
- `schema.tasks.sql:3625` (`qc_coq_one_approved_idx` on `(org, batch_id,
  specification_id)`).
- `coq_aggregation.py:505-514`.
- `:322-327` (compile merges every usable result, "latest wins").

**What happens:** The owner (2026-09-11T15:28) will "issue the needed iCoA and CoQs for
initial and/or retest periods for every produced batch". For a retest-period CoQ against
the same specification:
- The HoQC must **void** the valid initial-release CoQ. §6.6 reserves voiding for
  "fundamentally invalid" records, so a false void enters the register.
- The initial CoQ can no longer be recompiled as it was once retest results exist,
  because compile always takes the latest result per parameter.

**Evidence:** Read the index and the review duplicate check.

**Fix:** Add a CoQ `purpose` / period column (INITIAL, RETEST-n, with a timepoint). Scope
the unique index and the result selection to it: results by certificate or date window.

### QC-16 [medium] document-integrity — The A4 product specification prints named QC and QA signatories and a date that the system never captured

**Where:**
- `spec_html.py:113-120`.
- `app/data/imb_spec_template.html:397-398`.

**What happens:** For any APPROVED ladder the page prints "Prepared & Approved by — QC
Manager <name>, Date <effective_date>" and "Reviewed by — QA Manager <name>, Date
<effective_date>":
- The names are the two individuals hard-coded in the template.
- The app's actual approver (`approved_by`) is ignored.
- No QA review exists anywhere in the model. QA_MGR is not even a QC writer.

This asserts signatures that were never executed, which is exactly what the CoQ's H5
rule forbids. The code comment cites a "handoff rule", but the date and the QA
attestation are still invented.

**Evidence:** Read the substitutions and the template text.

**Fix:**
- Print `approved_by`'s name and the approval date.
- Print "QA review — not captured" until a QA review step exists.
- Add a QA review step, since the controlled documents say "reviewed by the QA Manager".

### QC-17 [medium] correctness — A result's unit is never reconciled with the cited parameter's unit

**Where:**
- `certificates.py:401-411` (`add_result` stores `body.unit`).
- `ecoa.py:640-656` and `:872-879` (the extraction unit is copied).
- `coq_aggregation.py:419` prints `r["unit"] or p["unit"]`.

Only derived totals are unit-checked (`common.py:66-84`).

**What happens:** Specification "Aflatoxin B1 ≤ 2 µg/kg"; the lab reports `0.004 mg/kg`
(= 4 µg/kg, a failure). The result is graded `0.004 ≤ 2`, so it complies, and the CoQ
prints "0.004 mg/kg" against "… 2 µg/kg" under "Conforms". The only control is the
reviewer's `units_per_spec` checkbox, and iCoAs have none.

**Evidence:** Read both write paths. The spec `unit` is loaded but never compared.

**Fix:** 422 when a result's normalised unit differs from the parameter's. Where
conversion is legitimate, convert explicitly with a unit table.

### QC-18 [low] state-machine — Revise drops the CoQ-template metadata, and an APPROVED certificate found wrong has no correction path

**Where:** `certificates.py:664-684` (revise copies decision, lab and notes only);
`:77`, `:657-659`.

**What happens:**
- A revision loses these fields:
  - `cultivation_batch`, `product_code`, `packaging` / `packaging_date`;
  - manufacture / expiry / retest dates, `botanical_type`, `chemotype`;
  - analysis dates, `sampling_location`, `issue_language`.
- The superseding certificate then renders without them unless someone back-fills them
  by hand.
- An APPROVED (not yet RELEASED) certificate can only go to RELEASED. Revise refuses it
  with "edit or re-review it directly", but it is frozen and has no transition back.
  So a known-wrong certificate must be *released* before it can be revised, or voided.

**Fix:**
- Copy every template column in revise.
- Allow `revise` from APPROVED, or add APPROVED→REVIEWED.

### QC-19 [low] data-integrity — Rebinding an eCoA's sample, lab or report date after the checklist is ACCEPTED leaves the acceptance in force

**Where:** `ecoa.py:347-412`. Only a specification change calls
`_invalidate_checklist` (`:409-411`).

**What happens:** After the HoQC signs `sample_id_match=true`, a writer PATCHes
`sample_id` or `laboratory_id` and promotes. The new certificate cites a sample or lab
that nobody reviewed.

**Fix:** Invalidate on any change to `sample_id`, `laboratory_id`,
`source_institution`, `report_date` or `material_code`.

### QC-20 [low] numeric — Total THC rounding uses Python `round` on a binary float

**Where:** `coq_docx.py:494`, `coq_aggregation.py:392`.

**What happens:** Ties are resolved on the binary representation, not half-up. Examples:
- Δ9-THC 1.47 % with THCA 25.00 % gives exactly 23.395. The correct value is 23.40, but
  the code produces **23.39**. That is below the `GP_THC26:CBD1` window minimum of
  23.40 and moves the ladder grade.
- 0.04 % with 15.00 % gives 13.195, which the code rounds to 13.19. That is inside
  `ACC_THC12`'s 13.19 maximum, when the correct 13.20 is outside it.

**Evidence:** Ran a grid comparison against `Decimal(...).quantize(ROUND_HALF_UP)`: 346
mismatches, 3 of which cross a catalogue window bound.

**Fix:** Compute in Decimal:
`(Decimal(a) + Decimal('0.877')*Decimal(b)).quantize(Decimal('0.01'), ROUND_HALF_UP)`.

### QC-21 [low] facility-clock — Printed dates and counters use UTC

**Where:**
- `coq_aggregation.py:660`: CoQ `report_date = compiled_at.date()`, where asyncpg
  returns a UTC-aware timestamp.
- `certificates.py:292`: `drafted_same_day` uses the UTC date.
- `custody.py:398`: the RQS control number takes `to_char(now(),'YY')`.

**What happens:**
- A CoQ compiled at 23:30 UTC on 31 December is 00:30 on 1 January in Skopje. It is
  numbered `CoQ-PP-2027-0001` (facility year) but prints the report date 2026-12-31.
- The RQS ordinal uses the facility year while its control number uses the UTC `YY`.
- `test_facility_clock.py` does not catch `.date()` on an aware timestamp or `now()` in
  `to_char`.

**Fix:**
- Use `(compiled_at AT TIME ZONE <site tz>)::date` in SQL, or convert through
  `worktime`.
- Use `SITE_YEAR_SQL` for `YY`.

### QC-22 [low] contract — Documented and client-side product routes that do not exist or have no caller

**Where:**
- `web/gf/api.js:380` (`qcProductDocumentUrl` → `GET /qc/products/{id}/document`).
- `PRODUCT-CATALOGUE-2026-09.md:73`.

**What happens:**
- There is no such route: the backend route list has only
  `/potency-specs/{id}/document`.
- The plan's A4 product page (commit 2) was never built.
- `qcProductConformance`, `qcPotencyDisposition`, `qcProductCreate/Patch/Approve/Supersede/Import`
  and `qcProductPotency` have no caller in `web/`, `connector/` or `docengine/`.

**Evidence:** Diffed the extracted `@router` list against `api.js`.

**Fix:** Either build `GET /qc/products/{id}/document` (reuse `_render_spec_page`) and
the QC product UI (QC-04), or remove the helpers and the doc row.

### QC-23 [low] data-integrity — Controlled RQS and SFR fields stay editable after registration or completion

**Where:** `custody.py:426-431` and `:524-527`. There is no status guard on the field
loop; the comment at `:83` says the fields are editable "while the RQS is a draft".

**What happens:**
- A REGISTERED or COMPLETED RQS can have `specification_id`, `storage_location` or
  `num_samples` blanked, undoing the §6.1.6 completeness gate after the fact.
- A COMPLETED SFR can have `actual_arrival` or `received_by_id` rewritten.

**Fix:** Allow §6.1.4 edits only while the RQS is OPEN. Freeze a COMPLETED SFR.

### QC-24 [low] GxP — Water-test verdicts are typed by hand, default to PASS, and can be flipped at any time

**Where:**
- `leaves.py:66` (`passed: bool = True`) and `:190-204`.
- UI "flip" button at `web/gf/qcleaves-view.js:63-70,140`.

**What happens:**
- An API caller that omits `passed` records a PASS.
- Any writer can toggle the verdict indefinitely, and the verdict is never derived from
  `parameters` against the grade's limits.

This contradicts the module's own rule for results: "complies is computed, never typed".

**Fix:**
- Make `passed` required, with no default.
- Derive it from the parameters where limits exist.
- Freeze a result once it is reviewed.

### QC-25 [low] document-integrity — CoQ boilerplate asserts facts that are not derived from the data

**Where:** `coq_docx.py:313-320`, `:345-355` and `:309-312`.

**What happens:**
- **The "Q" footnote.** Whenever *any* in-house result exists it states that "Foreign
  Matter and Macroscopic Identification are performed by the in-house QC Department"
  under QCSOP-005 v.02, whatever tests are actually present.
- **The compliance statement.** It asserts that all outsourced labs are ISO/IEC 17025
  accredited and compliant with the Marketing Authorisation, even when the same document
  prints an out-of-scope note or a lab has no accreditation.
- **The ∑ footnote.** It cites Ph. Eur. 2.2.29 (the HPLC method) for the 0.877 sum,
  while the source column says 3028.

The owner's rule (2026-09-05T17:00) is to use bracketed placeholders, never invented
content.

**Fix:**
- Build the footnote from the actual internal results.
- Drop or condition the accreditation claim on `out_of_scope` being empty and every lab
  carrying an accreditation.
- Cite 3028.

### QC-26 [low] document-generation — CoQ cells are not neutralised for newlines or block markers

**Where:** `coq_docx.py:18-23` (`_coq_cell` strips `|||`, `~~` and `|` only). The
DocEngine parser is line-based: `docengine/app/pipeline.py:190-206`.

**What happens:** A value containing `\n` (possible through the API on `packaging`,
`test_name` or `result_value`) closes the `[[TABLE]]` or `[[FORM:grid]]` block early:
- the following result rows fall out of the table as plain paragraphs;
- a `# …` line injects a heading into an issued certificate.

**Fix:** In `_coq_cell`, replace `\r`/`\n` with a space and neutralise a leading `#` or `[[`.

### QC-27 [low] data-integrity — Every OOS and CoQ gate keys on exact free-text batch equality

**Where:**
- `certificates.py:92`, `oos.py:43` and `ecoa.py:41`: `batch_id` has no normalisation
  or registry check.
- The gates are at `coq_docx.py:431-433` and `coq_aggregation.py:288-290,514-517,583-585`.

**What happens:** An OOS filed as `p050022` or `PO50022` (the OCR variants recorded in
`STABILITY-PROGRAMME-SEPARATION-2026-08.md`) does not block a CoQ for `P050022`. The UI
trims whitespace but does not fix case.

**Fix:** Upper-case and trim `batch_id` on write and compare case-insensitively; better,
validate against the batch registry.

### QC-28 [low] numbering — Other QC identifiers still come from global, cross-tenant sequences that never reset

**Where:**
- `specs.py:193-194` (`qc_spec_id_seq`), `samples.py:145-146,199-200`,
  `laboratories.py:128-129`, `custody.py:488-489`, `leaves.py:182-183,227-228,278-279`.

**What happens:** This is the M7 defect class, fixed for eCoA and OOS but left here:
`PP-SMP-2027-0457` can be the first sample of 2027; a rolled-back insert burns a number;
and the counter is shared across organisations.

**Fix:** Mint these identifiers the same way as `_mint_oos_number`, or at least document
that they are not register series.

### QC-29 [low] custody — The continuity check validates only self-declared fields

**Where:** `custody.py:582-619`.

**What happens:** `from_user_id` is whatever the caller sends, and the caller need be
neither the giver nor the receiver. Any writer can record "A handed it to B" without
either party acting, by copying the previous entry's `to_user_id` into `from_user_id`.

**Fix:** Require `user.id` to be `from_user` or `to_user`, or add a receiver acknowledgement.

### QC-30 [low] validation — Product PATCH problems surface as 500s and codes are not tied to grades

**Where:** `products.py:333-364`, `59-63`, `299-301`.

**What happens:**
- An inverted window on PATCH hits the DB CHECK (`qc_products_window_check`) before the
  422 guard runs, which is a 500. `main.py` maps only UniqueViolation.
- `grade` and `nominal_pct` are never checked against the THC number in `product_code`,
  so `GP_THC26:CBD1` can be stored with grade 18, and the mother ID (`GP18…`) disagrees
  with the product code.
- `GP_THC26` and `GP_THC26.0` are distinct codes.

**Fix:** Validate before the UPDATE; require `float(code_thc) == nominal_pct == grade`;
canonicalise the code.

### QC-31 [low] still open (from QC-SUBSYSTEM-REVIEW-2026-08) — The Low items that were not fixed

Each was re-checked at HEAD:
- `submit_extractions` still only appends rows. A duplicate submit gives two mapped rows
  per parameter, promote inserts both, and `verify_certificate` keys `by_param` on the
  last one (`ecoa.py:593-677,869-879,950`).
- `oos_reference` is validated only when there are masked failures; otherwise it is
  stored unvalidated (`coq_aggregation.py:338-348` vs `:447-456`).
- `qc_oos_register` is still append-only by convention: it has the all-command
  `org_isolation` policy, whereas 0061 hardened only `qc_signatures`.
- `/register` still omits `qc_coq` and eCoA documents (`cert_register.py:51-52`), while
  `/register/gaps` includes `qc_coq`.
- There is no `retention_expiry ≥ retention_start` check (`certificates.py:474-635`).
- `update_coa_document`'s UPDATE has no status predicate (the TOCTOU with promote,
  `ecoa.py:403-405`).
- The acid/neutral swap guard is still a name heuristic (`specs.py:29-48,318-332`).
