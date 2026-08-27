# Deep review — CoQ compilation engine · certificate register · eCoA pipeline (2026-08-05)

Read-only adversarial audit of the QC certificate subsystem (`backend/app/api/qc/*`
≈ 5,300 lines + `web/gf/qc*-view.js` ≈ 1,600 lines) for **correctness**, **GMP
compliance** (QCSOP-012 v3, EU GMP Annex 11, draft Annex 22, the
`URS-COQ-GAP-ANALYSIS` requirements), and **security**. Six specialist reviewers
fanned out by dimension; every material finding below was then **re-verified
against the source by hand** (flagged ✔verified). No code was changed.

## Verdict

The subsystem is **mature and, on its load-bearing controls, sound.** The
security posture is strong (no injection, no cross-org leak, complete authz,
correct file custody, DB-trigger hash-chained audit on every QC table). The
core certificate **numbering is atomic and race-safe**, and **promote/compile
cannot double-issue**. The defects are concentrated in a few places where a
**wrong `complies` can reach an issued certificate through an unusual-but-legal
operator action**, and where a control the SOP intends is **declared but not
fully wired**. There are **no** confirmed unauthenticated or cross-tenant holes.

Two findings are the ones to action first (**H1, H2** — both can put a false
conformance on a released certificate); the rest are Medium compliance-consistency
and Low hardening items.

---

## Remediation status (2026-08-05)

Implemented in this branch (`claude/weekly-read-flow-setup-yft7if`), each
test-gated:

| ID | Fix | Where |
|----|-----|-------|
| **H1** | A cited-parameter result's limits come from the spec; a supplied bound that disagrees is 422'd | `certificates.py` |
| **H2** | Spec-rebind invalidates an ACCEPTED checklist; promote refuses cross-spec grades | `ecoa.py` |
| **M1** | Aggregation `render_coq` now runs the manifest + per-source ISO-scope + lab resolution | `coq_aggregation.py` |
| **M2** | QP dropped from the CoQ approval gate (URS §3) | `coq_aggregation.py` |
| **M3** | A PASS/FAIL disposition is required before APPROVED/RELEASED (+ revise carries it; frontend guard) | `certificates.py`, `qccoa-view.js` |
| **M4** | The eCoA review-window is stamped at the ACCEPTED decision (and at promote) | `ecoa.py` |
| **M5** | §6.3.2 second-person review: the checklist decider must differ from whoever filled it (owner: multi-person QC) | `ecoa.py` |
| **M6** | Ph. Eur. 3028 derived total refuses unit-inconsistent components | `common.py`, `coq_docx.py`, `coq_aggregation.py` |
| **M7** | eCoA `doc_number` mints per-(org, year); the global `qc_ecoa_id_seq` is dropped (migration 0056) | `ecoa.py`, `0056` |
| **M8** | Register gap-report reframed: per-org RLS-scoped missing-record signal; modern series floor at 0001 | `cert_register.py` |
| **M9** | Explicit 32 MB request-body ceiling (nginx + backend content-length guard) | `nginx.conf`, `main.py` |
| **M10** | A VOIDED/SUPERSEDED certificate refuses a new Annex-11 signature | `signatures.py` |
| LOW | promote uuid-guard; download content-type whitelist + nosniff + CR strip; org-scoped BYPASSRLS profile lookups; checklist writes refuse a terminal parent | `ecoa.py`, `coq_docx.py`, `coq_aggregation.py`, `signatures.py` |

**CoQ spec-must-be-ACTIVE gate (LOW) — RESOLVED, will NOT implement.** Owner
decision (2026-08-06): *do not gate the lifecycle.* CoQ issuance stays independent
of `qc_specifications.status`; the certificate lifecycle is not gated on spec
lifecycle state. No code change — current behaviour already matches this.

**M5 — filler ≠ decider on the eCoA checklist — RESOLVED, implemented.** Owner
decision (2026-08-06): the site has **multiple QC people**, so segregation is
enforced. `decide_checklist` now refuses a decision (ACCEPTED or REJECTED) signed
by whoever authored (`created_by`) or last edited (`updated_by`) the checklist —
the Head of QC signing must be a second person (§6.3.2).

**Deferred — need a migration / heavier change or a design decision:**

- `qc_coa_extractions` UNIQUE(document_id, parameter_id). `submit_extractions`
  **appends** rows (it does not replace), so a hard uniqueness constraint would
  break a legitimate re-extraction / two-labels-one-parameter submission. Needs a
  decision on re-submit semantics (upsert vs reject) before it is safe.
- A DB trigger blocking UPDATE/DELETE on `qc_signatures` (append-only). Attempted
  and **reverted**: an *absolute* BEFORE UPDATE OR DELETE trigger also blocks
  legitimate lifecycle deletes — the test harness's own row cleanup, and more
  importantly an end-of-retention org data-purge — so it is not merely a
  test-fixture inconvenience but a correctness problem. A GUC-gated exemption
  (`app.allow_signature_purge`) would let a deliberate purge through while blocking
  casual/accidental writes, but that is a purge-strategy design decision (owner).
  Current exposure is nil regardless: the app only ever INSERTs signatures, and the
  hash-chain audit trigger already detects any out-of-band tampering.
- Cross-table CoQ uniqueness. Low current exposure (production at zero rows); best
  batched into a dedicated migration PR.

**Not actioned (marginal / requirement-dependent):** the remaining Low
micro-hardening items (TOCTOU status predicates on low-concurrency single-org
admin writes, isolation-level pins, assorted 500→409 refinements, OOS actor
separation) — rated Low by the audit and left for a future hardening pass.

---

## HIGH — a wrong verdict can reach an issued certificate

### H1 — `add_result`: a caller-supplied limit overrides the cited spec parameter ✔verified
`backend/app/api/qc/certificates.py:343,366-369` · CONFIRMED · trusted-writer, review-mitigated
When a result cites a `parameter_id`, the code snapshots the spec's limit **only
for a side the caller left null** (`if lo is None … if hi is None …`); a side the
caller *supplied* is kept as-is and never reconciled against the spec. `_evaluate`
then grades against the caller's bound and the comply gate (`coq_docx.py:467`)
trusts the stored `complies`.
- **Scenario:** spec "Lead ≤ 10 ppm"; POST result citing that parameter with
  `result_numeric=50`, `upper_limit=100` → `complies=True`; the §01 Acceptance
  column prints "…100" (self-consistent, evades eyeballing); a conforming CoQ
  issues over a failing result.
- **Severity corrected to Medium-High** (the finder's Total-THC example is
  *invalid* — computed parameters are rejected at `certificates.py:359-361`, so
  the hole is limited to **non-computed** parameters). Requires a `_WRITERS`
  user to supply an incorrect limit; second-person review catches it only on a
  spec cross-check.
- **Fix:** when `parameter_id` is cited, snapshot **both** bounds from the spec
  unconditionally (ignore request-body limits, or 422 if they disagree).

### H2 — eCoA spec-rebinding after grading → mis-graded conformance on promote ✔verified
`backend/app/api/qc/ecoa.py:354-360` (spec mutable, no re-grade/checklist-invalidate)
+ `ecoa.py:780 vs 783-793` (promote) · CONFIRMED
`update_coa_document` lets `specification_id` change while the doc is
UPLOADED/EXTRACTED/REVIEWED **without** re-grading extractions or invalidating an
ACCEPTED checklist (contrast `update_extraction:661` which *does* invalidate).
`promote` then mints a certificate citing the **new** spec (`doc["specification_id"]`)
while inserting each result's **stored** `parameter_id`/`lower_limit`/`upper_limit`/
`complies` from grading against the **old** spec — with no check that the
parameter belongs to the current spec.
- **Scenario:** grade + ACCEPT under spec A (limit ≤10), then PATCH spec→B
  (limit ≤2); promote issues a cert citing B whose rows carry A's limits/grades →
  an OOS-under-B value certified as complying. Propagates via
  `get_inherited_results`.
- **Fix:** at promote, reject any mapped extraction whose parameter's spec ≠ the
  doc's current spec; make a `specification_id` change invalidate the checklist +
  force re-grade.

---

## MEDIUM — compliance consistency & correctness gaps

### M1 — aggregation CoQ `render_coq` skips the mandatory-content manifest ✔verified (one call-site)
`coq_aggregation.py:458-534` vs `coq_docx.py:486` (only `_coq_manifest` call site) · CONFIRMED
The SOP-preferred C5 aggregation path performs status/`overall_conform`/open-OOS
checks but never runs `_coq_manifest`, never computes the ISO-17025 out-of-scope
flag, and passes `lab=None`. So an aggregation CoQ can issue with a reported test
that has no analytical-method reference and with the §02 laboratory accreditation
stripped — both of which the single-cert path *blocks*
(`test_coq_manifest_requires_method`).
- **Fix:** run `_coq_manifest` + scope flag + lab resolution inside `render_coq`
  (or move the per-test-method/lab checks into `compile_coq`).

### M2 — QP can approve the aggregation CoQ (QP-drop applied inconsistently) ✔verified
`common.py:38` (`_HOQC` includes QP) → `coq_aggregation.py:382` (`review_coq`) → `:416` (`reviewed_by`) · CONFIRMED
URS §3 / QCSOP-012 C5: the CoQ is approved by the Head of QC and carries **no QP
signature**. The *issuing* gate was correctly fixed (`_COQ_ROLES=(ADMIN,QC_MGR)`,
QP→403, test-pinned), but the *approval-of-record* `review_coq` still runs under
`_HOQC`, so a QP becomes the certifying approver on the CoQ.
- **Fix:** gate `review_coq` on `(ADMIN,"QC_MGR")`, not `_HOQC`. *(Owner check:
  confirm QC_MGR = Head of QC and QP must be excluded from CoQ approval.)*

### M3 — a RELEASED cert's blank `decision` (PASS/FAIL) is back-fillable in place ✔verified (server + UI)
`certificates.py:439-441` (set-once branch) + `web/gf/qccoa-view.js:506` (edit form shown on RELEASED) · CONFIRMED
The frozen-content guard correctly refuses *changing* an issued field but permits
setting a **currently-blank** one (`… cur.get(k) in (None,"") … continue`) —
including `decision`, the conformance disposition — and nothing forces `decision`
non-null before RELEASED. The UI compounds it: the metadata-edit panel's guard
excludes only SUPERSEDED/VOIDED, so it renders on RELEASED. Net: a released
certificate's PASS/FAIL can be established post-release in place, not via a
revision.
- **Fix:** require `decision` (+ mandatory disposition fields) non-null as a
  precondition of the APPROVED/RELEASED transition; add `status!=='RELEASED'` to
  the UI guard.

### M4 — promote skips REVIEWED → the §6.3.1 5-working-day review clock is unrecorded ✔verified
`ecoa.py:750` (promote allows EXTRACTED) · `:363-365` (window stamped only on the REVIEWED PATCH) · `:117-120` (`review_overdue` false once past EXTRACTED) · CONFIRMED
A doc promoted directly from EXTRACTED never passes through REVIEWED, so
`reviewed_at`/`review_window_met` stay NULL and `review_overdue` reads false — a
doc reviewed and promoted weeks past its stamped `review_deadline` records no
window breach. The §6.3.2 checklist is the only real gate; the 5-day timeliness
control is not captured on the promote path.
- **Fix:** stamp the window on the ACCEPTED checklist decision or on promote if
  unset; or require REVIEWED before promotion.

### M5 — eCoA QCT-018 checklist has no filler≠decider control  *(= deferred register #13)*
`ecoa.py:438-478` (fill, `_WRITERS`) vs `:481-521` (decide, `_HOQC`) — no actor-inequality check · CONFIRMED
The same person may self-affirm and ACCEPT the external-CoA review. **Backstopped**
by the certificate lifecycle, which *does* enforce analyst≠reviewer≠approver
before release (`certificates.py:513-532`), so an independent second person is
still required before the eCoA data is released — the checklist stage alone lacks
it. This is the known owner-decision (MASTER-PLAN §9 #13).
- **Fix (owner-gated):** 403 in `decide_checklist` when the actor equals the
  checklist's `created_by`/last `updated_by`.

### M6 — Ph.Eur 3028 derived total: no component unit-consistency check
`coq_docx.py:452-461`, `coq_aggregation.py:289-296` · PLAUSIBLE
Both compute `neutral + 0.877×acid` and label with the total's unit, without
asserting the two component results share a unit (and match the total's). Mixed
units (e.g. neutral in `%`, acid in `mg/g`, possible when aggregation pulls
components from different labs) yield a dimensionally meaningless sum that is
still graded and printed. *(The 0.877 factor and neutral+acid direction are
correct — verified against `test_coq_computes_total_thc`.)*
- **Fix:** assert component units match each other and the computed parameter's
  unit before computing; else 409/flag.

### M7 — eCoA document number is on a global, non-resetting, non-transactional sequence ✔verified
`ecoa.py:300-301` (`nextval('qc_ecoa_id_seq')`) vs the fixed per-org cert path at `:774` · CONFIRMED
The QCSOP-012 C2 per-`(org,type,year)` advisory-lock `max+1` remediation was
applied to the certificate number but the **eCoA `doc_number` was left on the old
raw sequence**: it never resets per year, is shared across tenants, and a
rolled-back registration burns a number permanently (a §6.13 "skip"). Not a
duplicate risk (`nextval` is atomic + `UNIQUE(org_id,doc_number)`), and these
skips are invisible to `/register/gaps` (it never scans `doc_number`).
- **Fix:** route `doc_number` through the `_mint_cert_number` per-org path; retire
  `qc_ecoa_id_seq`.

### M8 — `/register/gaps` honesty note is misapplied to the per-org series ✔verified
`cert_register.py:151-155` (note) contradicted by `certificates.py:36-39` (per-org `max+1`) · CONFIRMED
Post-migration series are minted **per-org** and never burn on rollback, so a
per-org series is gap-free by construction — any gap it reports is a **genuine
lost record** (hard delete / manual edit). The blanket note ("a gap may reflect a
certificate issued to another organisation … RLS hides it") is only true for the
**legacy** global `PP-COA` series; applied to every series it plants a
false-benign explanation that could cause an investigator to dismiss a real
ALCOA+ event.
- **Fix:** scope the shared-tenant caveat to the legacy `PP-COA` prefix; for
  per-org series state that a gap is a genuine missing-record signal.

### M9 — upload body buffered/parsed before the 20 MB cap; no edge cap ✔verified (no nginx cap)
`ecoa.py:192-223` (cap post-`b64decode`) · `web/nginx.conf` has **no** `client_max_body_size` · CONFIRMED
The 20 MB limit fires only after Starlette buffers and orjson parses the whole
body; there is no ASGI body-size guard and no nginx `client_max_body_size`, so an
authenticated elevated user can POST a multi-hundred-MB JSON body (held as base64
+ parsed JSON + decoded bytes simultaneously). No per-org file quota either →
authenticated memory/storage-exhaustion vector.
- **Fix:** add an nginx `client_max_body_size ~28m` on the `/qc` (or `/`) location
  **and** an ASGI content-length guard; consider a per-org upload quota.

### M10 — signing is not blocked on VOIDED/SUPERSEDED certificates ✔verified
`signatures.py:26-28` (`_STATUS_RANK` maps SUPERSEDED/VOIDED = RELEASED = 3) + the floor-only check at `:79` · CONFIRMED
The rank gate enforces only a *floor* (a meaning may not out-rank the cert's
progress); VOIDED/SUPERSEDED rank 3, so any meaning (incl. RELEASED) can be signed
onto a dead certificate. Low blast radius (the cert is dead, the log is
append-only + audited), but a fresh Annex-11 attestation on a voided/superseded
record is misleading. The UI likewise offers the signing form on those states
(`qccoa-view.js:509`).
- **Fix:** block signing when status ∈ {VOIDED, SUPERSEDED} (server + hide the UI
  form).

---

## LOW — hardening / hygiene (grouped)

- **Immutability TOCTOU** — several non-terminal write paths read status then
  `UPDATE` with no status predicate (`ecoa.py:370-372, 676-682`); a concurrent
  promote can let an edit land on / flip back a just-locked doc. Also the promote
  ACCEPTED-checklist premise is TOCTOU (`ecoa.py:798-803` re-checks only
  `promoted_coa_id`). *Fix: add `AND status NOT IN ('PROMOTED','REJECTED')` /
  `AND EXISTS(checklist ACCEPTED)` to the guarded UPDATEs.* (B-F2, E-F6)
- **Checklist endpoints** don't refuse when the parent doc is PROMOTED/REJECTED
  (`ecoa.py:454,492-498`). (B-F4)
- **`submit_extractions`** insert-only, no `(document,parameter)` uniqueness →
  duplicate results on a double-submit (mitigated: 2nd submit resets checklist to
  PENDING, forcing re-review). (B-F5)
- **CoQ spec not required ACTIVE** — compile/generate accept any spec status
  (`coq_aggregation.py:147-150`, `coq_docx.py:412`); blast radius limited (spec
  params lock after authoring). (A-F6)
- **Swap guard** for acid/neutral components is a best-effort name heuristic
  (`specs.py:290-296`, acknowledged residual) — *fix properly via an explicit
  neutral/acid flag on the spec-parameter model.* (A-F4)
- **`oos_reference`** written unvalidated when a batch has no masked failures
  (`coq_aggregation.py:246-255` vs `:356`). (A-F5)
- **`qc_signatures` / OOS register** append-only by convention, not a DB
  UPDATE/DELETE-blocking trigger (`0034:78-84`). (C-F5)
- **OOS** has no actor-separation across investigate→disposition→close
  (`oos.py:229-310`) — requirement-dependent (QCSOP-011, out of scope here). (C-F3)
- **Download**: no content-type whitelist, no `X-Content-Type-Options: nosniff`,
  `\r` not stripped from the filename (`ecoa.py:268,276-279`). (D-F2)
- **Two id routes skip uuid validation** → 500 not 404/422 (`promote` `ecoa.py:747`;
  `update_placeholder` `ecoa.py:719`). (D-F3)
- **BYPASSRLS profile name lookups** carry no `org_id` predicate
  (`coq_docx.py:434-436`, `coq_aggregation.py:553-555`) — not currently
  exploitable (ids are always same-org), a defense-in-depth gap. (D-F4)
- **Register**: gap scan misses missing low numbers `1..min-1`
  (`cert_register.py:140`); `/register` listing omits `qc_coq` aggregation records
  that `/register/gaps` includes (`cert_register.py:51-52`). (E-F3, E-F8)
- **Numbering defense-in-depth**: no cross-table unique for the shared `CoQ-PP`
  series (E-F4); the `max+1` scheme relies implicitly on READ COMMITTED, not
  pinned in code (E-F5); concurrent CoQ-approval loser surfaces 500 not 409
  (E-F7). All safe under current config.
- **Retention** fields are uncomputed free entry, no `expiry ≥ start` check, and a
  null-retention issued cert is invisible to retention tracking
  (`certificates.py:102-104`). (E-F9)
- **Frontend** (advisory): stale in-memory "Verified" chip not cleared on reload
  (`qcecoa-view.js:386`); "Mark PASS" offered while a result is OOS
  (`qccoa-view.js:494`); record ids interpolated into `onclick` strings (safe
  while ids stay opaque). (F-#3/#4/#5)

---

## Verified CLEAN (checked and found sound — the audit's negative space matters for GMP)

- **Comply gate** blocks both `False` and `None` (`is not True`); **completeness
  gate** iterates every spec parameter with no silent skip; **Ph.Eur 3028** factor
  (0.877) + neutral+acid direction correct and joined to both gates
  (single-cert path).
- **Grading never copies the lab verdict** — `complies` is always recomputed via
  `_evaluate`; `lab_verdict` is reference-only and feeds only a display mismatch
  flag. **Placeholders never auto-commit** — unmapped labels stay `parameter_id
  NULL`, are queued, and promote filters them out.
- **Supersession/revise** correct (original never mutated, new number,
  `RELEASED→SUPERSEDED` replay-guarded). **OOS gate** re-checked at compile /
  approve / render / single-cert generate, each recording the §6.16 deviation in
  a separate transaction so a 409 can't erase it.
- **Numbering** atomic + per-`(org,type,year)` advisory lock + `max+1` read under
  the lock + rollback-safe + `UNIQUE` backstop; **year rollover resets to 0001**;
  legacy/new prefixes non-colliding. **Promote/compile cannot double-issue**
  (advisory lock + optimistic `WHERE … IS NULL` re-assert; loser rolls back).
- **Annex 11 e-signature** re-authenticates the signer's *own* password (no
  sign-as-another/forgery), append-only, captures name+role+meaning+timestamp+link.
  **QP dropped from CoQ *issuance*** (correct; the *approval* gap is M2).
- **Immutability** — `qc_results` insert-only and only while DRAFT (no
  UPDATE/DELETE anywhere); issued/archived certificates frozen against substantive
  edits with an in-transaction TOCTOU re-check; corrections forced through
  `/revise`.
- **Security** — every one of ~60 routes carries the correct `require_role`; all
  28 `qc_` tables `FORCE ROW LEVEL SECURITY` with `org_isolation` USING+WITH CHECK;
  every query runs as the NOBYPASSRLS `app_user`; **no SQL injection** (params
  everywhere; the `PLACEHOLDER` splice substitutes only an integer arg-count;
  static ORDER BY); **file custody** correct (server SHA-256 + re-verify on read,
  `bytea` so no path traversal, RLS-scoped download so no cross-org IDOR).
- **Audit trail** — DB-trigger hash-chain (`fn_audit_row`) on **every** QC table,
  actor from the per-request GUC, CI-enforced by `test_audit_coverage.py`; no
  mutation escapes it (so "missing `emit()`" is *not* an audit gap).

---

## Recommended fix order (if actioned)

1. **H1, H2** — the two paths that can put a false conformance on an issued
   certificate. Deterministic fixes + regression tests; deploy as a backend
   increment (snapshot → migrate-if-needed → build → swap → verify).
2. **M1, M2, M3, M4, M8, M10** — compliance-consistency fixes, each small and
   test-pinnable. M2 and M5 touch **owner decisions** (QP-on-CoQ-approval;
   filler≠decider = register #13) — confirm intent before changing a role gate.
3. **M7** (eCoA numbering) + **M9** (upload cap: an nginx one-liner ships
   immediately, plus an ASGI guard) + the Low hardening batch.

This review is read-only; nothing above is applied. Each fix, when approved,
lands with a QCSOP-012-cited test and the standard snapshot→migrate→build→
swap→verify deploy.
