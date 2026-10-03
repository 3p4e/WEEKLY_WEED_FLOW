# Frontend re-review — `web/` (index.html, sw.js, web/gf/*, nginx.conf, tests/frontend, web/e2e)

Reviewed at `0984dc8` (branch `claude/weekly-read-flow-setup-yft7if`). Read-only; no production, no GitHub writes, no backend pytest. Verification: static reading of every changed view against `backend/app/api/**`, an AST extraction of all 272 backend routes with their `require_role` sets (reviewer's scratch, not in the repo), a script comparing every `GF.API.*` call site with `api.js` (250 methods, 0 duplicates, 0 undefined callers), a script comparing floor-view request-body keys with the Pydantic models, a script comparing every inbox `sentence()` param with the backend `safe_emit(params=…)` per verb, jsdom runs of the real sources (reviewer's jsdom scripts, not in the repo), and single-file runs of 19 `tests/frontend/*.test.js` (all green).

## Summary

The frontend fixes are real and mostly well made: the stored XSS is gone and guarded by a scan, the datepicker highlights without choosing, the facility clock rides the login and `/auth/me`, the product catalogue screen exists and the CoQ compile form names a product, decon cycles can be failed and pending biosecurity checks read, the custody form sends origin and recipient, Workload/Exec overview live in the Analytics rail, the two retired stubs are gone, and index/sw/disk agree. The shell is coherent: every nav key resolves to a registered renderer, `api.js` and `app.css` took the six parallel edits without a duplicate or a shadow, and `qmsstudio-view.js` was adapted to the new `{documents,…}` envelope.

What did not close sits exactly where the workstream boundaries were drawn. The timestamp guard test excludes seven files "owned by other workstreams", and the highest-impact FE-05 sites (the pesticide re-entry line, e-signature and CoQ issue times) are in those files and still print UTC. The new "Handoffs to your department" list is in a view that six of the eight department-scoped manager roles — including PR_MGR, the canonical receiver — cannot open, because `approvals` lives in the `audit` module keyed to QA/QC/QP; clicking the handoff notification bounces them to My Week. The backend opened waste/decon/biosecurity to PR_MGR (A-2) but the module and view gates still hide all of it. Two DECISIONS rows describe code that does not do what they say (E-2 contradicts B-12; E-5's list is unreachable for its main actor). Several "closed" items are helpers that were added but never wired (`GF.daysSince`), or fixed in three files and left in the fourth (INS-12, FE-16, FE-20).

Severity counts: **critical 0 · high 3 · medium 6 · low 9**.

## Closure table

| Finding | Status | Evidence |
| --- | --- | --- |
| FE-01 (product catalogue UI) | **CLOSED** | `qcpotency-view.js` rewritten (a85a94b): list/import/dry-run/approve/supersede/history/conformance, `data-qcp-act` delegation; compile form sends `product_id` (`qccoa-view.js:660-662`); `GET /qc/products/{id}/document` now exists (`spec_html.py:180`). Tests `qcpotency-view.test.js` (13), `qccoa-coq-potency.test.js` (9). Deploy record `DEPLOY-2026-09-06-v92.md:15-16` still claims v133 shipped the catalogue views (not corrected; INS scope). |
| FE-02 (custody second hop) | **CLOSED with a seam** | `qccustody-view.js:199-209` sends `from_location`, `from_user_id`, `to_user_id`; test `qccustody-chain.test.js` (4). But see R2-FE-05: the pre-filled `from_user_id` collides with the backend's new B-12 rule. |
| FE-03 (decon fail) | **CLOSED** | `api.js:282`, `decon-view.js:160-166` (QA-only, positive/inconclusive > 0), `deconFailForm/Save:715-750`; `decon-fail-biosecurity.test.js` (10). |
| FE-04 (swab XSS) | **CLOSED** | `decon-view.js:871-891` data-attributes + one assigned listener; genealogy links `qcgenealogy-view.js:63,72`; eCoA download `qcecoa-view.js:600-601`; guard `xss-inline-handlers.test.js` (4). One free-text field escaped the denylist — R2-FE-15 (low). |
| FE-05 (UTC timestamps) | **PARTIAL** | `GF.fmtDateTime/fmtTime/fmtDate` (`core.js:319-359`) and 20 sites converted. **Not converted:** `harvest-view.js:232,236,237,433` (REI "no entry until", applied date), `qccoa-view.js:348,395,426` (signature and CoQ issue times). `timestamps.test.js:127-130` excludes those files. R2-FE-02. |
| FE-06 (handoffs) | **PARTIAL** | `handoffRights` (`task-extras.js:183-199`) mirrors `collab.py:351-395` case by case; `_assert_scope_visible` (`tasks.py:59-96`) now admits a task with a proposed handoff to my family; Approvals list `approvals-view.js:24-45,222-234`; `handoffs.test.js` (10). **But the Approvals view is unreachable for PR_MGR/CU_MGR/WH_MGR/IR_MGR/SE_MGR/MU_MGR** — R2-FE-01. |
| FE-07 (facility today) | **CLOSED** | Login carries `facility_tz/facility_today` (`auth.py:245-246`); `loadAndRender` refreshes a stored session from `/auth/me` (`integrate.js:308-320`); `GF.todayDay` is a live getter (`core.js:259-268`); render/myday/depthome/report/worklog/calendar/buildCalendar switched to `GF.facilityToday()`. |
| FE-08 (arrow keys) | **CLOSED** | `datepicker.js:31-37,112-120,231-268` cursor model; `datepicker-keys.test.js` (6). |
| FE-09 (A4 link 401) | **CLOSED** | `qcpotency-view.js:175-195` fetches with the bearer and opens a blob; ladders too (`ladder-doc`). |
| FE-10 (pending biosecurity) | **CLOSED** | `api.js:305`; board loads `{limit:200}` (≤ `le=500`, `biosecurity.py:123`) and splits fails/pending (`decon-view.js:372-430`); `bioResultForm/Save:528-576`. |
| FE-11 (batch↔product/task links) | **PARTIAL** | `cultEditForm/Save` (`cultivation-view.js:1152-1201`) sends `product_id/clone_source/note` = `BatchPatch`; `cultLinkTask:659-669` sends `batch_id` via task PATCH. Task create/edit forms still have no batch chooser; `dept-templates.js:42,78,121` still offer free-text `batch_ref` with placeholder `B-2026-041`. |
| FE-12 (rail) | **CLOSED** | `render.js:150-158,193` emit Workload/Exec in the Analytics group only; exec landing sets the module (`integrate.js:376-387`); `nav-rail-modules.test.js` (3). |
| FE-13 (SW freshness) | **PARTIAL** | `cache:'reload'` on install (`sw.js:41`) and VERSION → v3.103.0 (8c6a5bc). No check enforces a bump: `a248dc4` and `f73bba7` changed `notifications-view.js`, `codefield.js`, `qcecoa/qcoos/qcsample-view.js`, `integrate.js` AFTER the bump with no new VERSION. `shell-and-gates.test.js` does not test this. Harmless only because v3.103.0 has not shipped. |
| FE-14 (role gates showing 403s) | **CLOSED** | `intake-view.js:214-216` guard; `document-view.js:24-29,411-412` renders nothing for USER; tests in `shell-and-gates.test.js`. |
| FE-15 (hiding what the server allows) | **(1) NOT FIXED, (2) CLOSED** | (1) Void CoA/CoQ still gated by `_COQ = ['ADMIN','QC_MGR']` (`qccoa-view.js:30,534,776`) vs `_HOQC = (ADMIN, QC_MGR, QP)` (`certificates.py:831`, `coq_aggregation.py:798`) — QP cannot void from the UI. (2) parent chooser `integrate.js:1005-1010,1028,1035`. |
| FE-16 (stale-response guards) | **PARTIAL** | `lseq` added to `waste-view.js:89-101` and `decon-view.js:50-81` only. `loadCultivation` (`cultivation-view.js:146`), `loadPropagation` (`propagation-view.js:69`), `loadFacility` (`facility-view.js:72`), `loadIrrigation` (`irrigation-view.js:28`) are unguarded; the "include closed batches" double-toggle race of the original finding is unchanged. |
| FE-17 (days in phase drift) | **NOT FIXED** | `GF.daysSince` exists (`core.js:364`) and is tested, but neither board calls it: `facility-view.js:67-70` still `Date.now()`-based and rounded, `cultivation-view.js:134-138` still its own facility-day copy. The "1 d vs 0 d after noon" discrepancy is unchanged. The conventions appendix (`FRONTEND-DESIGN-HANDOVER.md`) and `shell-and-gates.test.js:13` say it is "the one rule". |
| FE-18 (verb sentences) | **PARTIAL** | 40+ sentences added, generic bilingual fallback (`notifications-view.js:177-183`), `batch_closed` dropped. Two sentences use params the backend never sends and print `undefined` — R2-FE-04. |
| FE-19 (swallowed note save) | **CLOSED** | `integrate.js:487-501` awaits, removes the optimistic note (`main.js:9` shape `{d,n}`), toasts. |
| FE-20 (dated records without a date input) | **PARTIAL** | Biosecurity `occurred_on` added (`decon-view.js:449-454,516`). Irrigation `applied_on` (`irrigation-view.js:119-128`) and IPM `applied_at` (`harvest-view.js:702-712`) still not sent; `FeedIn.applied_on` / `IpmIn.applied_at` still default to server today/now. R2-FE-12. |
| FE-21 (dead code) | **PARTIAL** | Stubs deleted, assets deleted, `mobile.css` dead selectors and `#today-btn` fixed, `core.js` demo state gone, `GF.HANDOFF` seed fixed. Still: 14 uncalled `api.js` wrappers (`cultivationBatchCode, trichomeChecks, campaignPatch, qcCreatePotencySpec, qcApprovePotencySpec, qcSupersedePotencySpec, qcPotencyDisposition, qcProductCreate, qcProductPatch, qcProductLadderCreate, qcProductPotency, qcCommercialIdentities, qcImportCommercial, qcSignatures`); `/qms/rag-query` still in `api.js:40` and `nginx.conf:100`; `pp-logo.png` still only in the precache (`sw.js:22`); `cultivation-view.js:904` bypasses the `cultivationBatchCode` wrapper with an inline `_req` because "api.js is not this view's to change". |
| FE-22 (routes with no caller) | info | Now called: `/decon/cycles/{id}/fail`, `/decon/biosecurity/{id}/result`, `PATCH /cultivation/batches/{id}`, all `/qc/products*` except create/patch/ladder/potency-history. Still no caller: `GET /cultivation/trichome-checks` and **`PATCH /cultivation/trichome-checks/{id}`** (a correction route added by the cultivation workstream, `trichome.py:179`, with a `trichome_corrected` inbox sentence but no UI that can produce the event), `PATCH /cultivation/campaigns/{id}`, `PATCH /departments/{id}`, positive-controls, tool-log, commercial identities, `GET /qc/certificates/{id}/signatures`, `/icoa-html`, `GET /tasks/tree`, `GET /auth/users`. |
| INS-02 (catalogue UI) | **CLOSED** (frontend half) | As FE-01; ladder import is offered only while the org has no product (`qcpotency-view.js:388`), backend refuses it afterwards (C-7). |
| INS-12 (constant-head code fields) | **PARTIAL** | `GF.batchCodeField` (`codefield.js:90-157`) wired into sample (`qcsample-view.js:385-391`), incoming CoA (`qcecoa-view.js:679-681`) and OOS (`qcoos-view.js:273-275`); `batch-codefield.test.js` (7). **Not** the two fields the finding listed first: CoQ compile `qccoa-view.js:796` and CoA create `qccoa-view.js:849` are plain inputs (product workstream's file; f73bba7 did not touch it). R2-FE-08. |
| BC-04 (frontend half) | **PARTIAL** | as FE-06 / R2-FE-01. `GET /departments` now carries `head_user_id` but `GF.DEPTS` does not map it (`integrate.js:353-361`), so `handoffRights.isHead` (`task-extras.js:188`) is dead — R2-FE-14. |
| BC-10 (frontend half) | **CLOSED** | as FE-03 / FE-10. |
| BC-08 (frontend half, per A-7) | **NOT FIXED** | `audit-view.js:87-89,115` still pages on `before`, which `audit.py:120-123` now documents as lossy; `api.js:141-142` returns only the body so `X-Next-Cursor` cannot even be read. R2-FE-06. |
| BC-12 / A-2 (frontend half) | **NOT FIXED** | R2-FE-03. |

---

### R2-FE-01 [high] role-gate / contract — The "Handoffs to your department" list, and Approvals itself, cannot be opened by six of the eight department-scoped manager roles, including PR_MGR

**Where**
- `web/gf/modules.js:53-60`: `approvals` is a key of the `audit` module, whose `roles` are `['QA_MGR','QC_MGR','QP']` (line 57); `GF.ALWAYS_FULL_ACCESS_ROLES` adds ADMIN/OWNER/CEO/COO.
- `web/gf/integrate.js:1243-1248,1276`: `_registerFullPageView` ANDs every view's guard with `GF.keyVisibleNow(key)`, never renders the rail item otherwise, and `render.all` bounces `GF.state.view === key` to `mywork`.
- `web/gf/modules.js:111-123`: `keyVisibleNow` fails closed on `moduleAccessibleFor`.
- `web/gf/notifications-view.js:449`: a `handoff` notification click does `GF.setView('approvals')` unconditionally; `core.js:613-633` leaves the module alone when the role cannot access it, "render.all() then bounces it".
- `web/gf/approvals-view.js:295-301`: the view's own guard is `role !== 'USER'` and it anchors at `coord` (a task-rail item), which says the author expected it in the task rail.

**What happens**
- PR_MGR (Production) is the receiving manager in the owner's own handoff example (cultivation → production at the cut). A Cultivation manager proposes the handoff; `collab.py:307-316` pings the PR_MGR; the inbox shows "Cveta proposed a handoff to Production: …"; the PR_MGR clicks it → `setView('approvals')` → `moduleAccessibleFor('audit','PR_MGR')` is false → `render.all` bounces to My Week. There is no Approvals entry in any rail for them. The task card is now visible to them (scope guard widened, `tasks.py:90`), but it is in the source department's board, which their `GET /tasks` does not list, so they have no path to the ✓ button either.
- The same for CU_MGR (Cloning/Nursery handoffs), WH_MGR, IR_MGR, SE_MGR, MU_MGR. Only QA_MGR/QC_MGR/QP and the executives — who could already arbitrate — can see the new list. The `E-5` decision row describes a list "derived from notifications"; it does not say that the addressee cannot open it.
- Secondary: every task participant also gets the `handoff` ping (`collab.py:314`); a USER assignee who clicks it used to jump to the task (`xrJump`) and is now bounced to My Week with no message.
- Pre-existing and unrelated to handoffs: `GET /approvals/pending` is `require_password_set` (every role), and the view's "Yours to acknowledge / Team pending" queue is for managers, yet the module gate has hidden Approvals from these six roles since the module split.

**Evidence**
- reviewer's jsdom script (jsdom, real `data.js/core.js/chooser.js/modules.js`): for PR_MGR, CU_MGR, WH_MGR, IR_MGR, SE_MGR, MU_MGR `keyVisibleNow('approvals')` is `false` in both the `tasks` and the `audit` module; `true` only for QA_MGR, QC_MGR, QP, OWNER.
- `tests/frontend/handoffs.test.js` and `approvals-view.test.js` load `approvals-view.js` with a stubbed `_registerFullPageView` and call `GF.views.approvals()` directly, so the module gate is never exercised.

**Fix**
- Move `approvals` into the `tasks` module keys (it anchors at `coord` there anyway) — or list it in every module's rail via `GF.MODULES` `roles: null` — and drop it from `audit`. Keep the `role !== 'USER'` guard.
- In `openNotif`, route to `approvals` only when `GF.keyVisibleNow('approvals')` after `setView` would hold (or simply when the user is not the requester and the view is accessible); otherwise fall back to `xrJump(taskId)`.
- Add a rail test that renders the real `GF.render.sidebar()` for PR_MGR and asserts `[data-nav="approvals"]` exists.

### R2-FE-02 [high] dates / safety — FE-05 is not closed where it matters: the pesticide re-entry line, the IPM date and the certificate signature/issue times still print the UTC string

**Where**
- `web/gf/harvest-view.js:236-237`: `no entry until ${String(a.rei_until).slice(0,16).replace('T',' ')}` (the red REI row); `:433` the harvest-clearance REI list; `:232` `applied_at.slice(0,10)` (UTC day of application).
- `web/gf/qccoa-view.js:348` (signature time on a certificate), `:395` (`issued` = `coq_generated_at`/`report_date` printed on the CoQ render), `:426` (CoQ signature block).
- `tests/frontend/timestamps.test.js:127-130`: `OTHER_WORKSTREAMS` exempts `qcpotency-view.js, qccoa-view.js, cultivation-view.js, propagation-view.js, harvest-view.js, irrigation-view.js, facility-view.js` from the guard.

**What happens**
- Unchanged from FE-05: a REI that ends at 14:00 facility time is shown as "no entry until … 12:00". This was the finding's first-listed, safety-tagged site, and the consolidated review's §2.14 headline example. The convention appendix now states "every instant is printed through `GF.fmtDateTime`" and the test that "guards the retired patterns out of the views" is silent for exactly the file that carries the safety case.
- GxP records: the e-signature time on a certificate and the CoQ "issued" time print an unlabelled UTC time, 1–2 h off the facility clock.

**Evidence**
- `grep -n "slice(0, 16)\|slice(0,16)\|replace('T', ' ')" web/gf/*.js` → the seven lines above and nothing else; every other site converted.
- `git log 549b617..HEAD -- web/gf/harvest-view.js`: only `d186c01` (harvest-date bounds) touched it; `qccoa-view.js` only `a85a94b` (product select). Neither workstream took the timestamp lines.

**Fix**
- Replace the seven sites with `GF.fmtDateTime(...)` (`GF.fmtDate(a.applied_at)` at `:232`), and delete the `OTHER_WORKSTREAMS` exemption from `timestamps.test.js` so the guard covers every file.

### R2-FE-03 [high] owner-instruction / role-gate — Production (PR_MGR) is still hidden from waste manifests, decon and biosecurity, although the backend and DECISIONS A-2 now allow it

**Where**
- `web/gf/modules.js:49`: the `biosecurity` module (keys `decon`, `waste`) has `roles: ['CU_MGR','QA_MGR','SE_MGR']` — no PR_MGR.
- `web/gf/waste-view.js:75`: `canRecord = [ADMIN, OWNER, CEO, COO, CU_MGR]`; `web/gf/decon-view.js:42`: `canClean` same set; `:357` `canBio = canClean() || canQA()`.
- Backend after `f692268` (A-2): `waste.py:83 _RECORDERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR", "PR_MGR")`, `decon.py:62 _CLEAN_WRITERS` and `biosecurity.py:49 _RECORDERS` include `PR_MGR`.
- `docs/DECISIONS-2026-09.md` §2b A-2: "PR_MGR records waste manifests and runs decon / gowning for `dry` rooms". §1 AD-9 was amended to say the same.

**What happens**
- The owner (2026-09-05 17:44): "Everything from harvest onward is production manager's job". BC-12 found that Production could not record destruction or decon of its own post-harvest areas. The backend half was fixed; in the app the PR_MGR has no Biosecurity & Waste module at all (module picker), so the `trim`/`packaging` waste manifests, the dry-room decon cycles, gowning and mat checks the decision grants them cannot be started from the UI. The decision is recorded as "in the code today" and, for the person who uses the app, it is not.
- The convention appendix's rule "never hide a button the server allows" is violated for the whole module.

**Evidence**
- reviewer's jsdom script: PR_MGR → `modules = tasks,cultivation,analytics`; `keyVisibleNow('decon')`/`('waste')` false. Compared the three frontend role arrays with the three backend tuples.

**Fix**
- Add `PR_MGR` to the `biosecurity` module roles and to `canRecord` (waste) / `canClean` (decon). The server already restricts PR_MGR to `dry` rooms and refuses witnessing/swabs/release; mirror that in the room pickers if desired, but the gate must open first.

### R2-FE-04 [medium] i18n / contract — The inbox and activity feed print "undefined" for every batch registration and batch move; the hand-merged sentence table also carries two dead duplicate cases

**Where**
- `web/gf/notifications-view.js:150-155`: `batch_added` reads `p.strain`, `p.room`; `batch_moved` reads `p.plant_count`, `p.strain`, `p.old_room`, `p.room`.
- Backend: `cultivation.py:654-658` sends `{code, cultivar, plant_count, phase, product_code}`; `:988-992` sends `{code, old_phase, phase, room_change, generated_tasks}`.
- `web/gf/views.js:207-209` (dashboard activity) uses the same wrong keys with `|| ''`, so it prints blanks instead.
- `web/gf/notifications-view.js:83-86` and `:167-170`: `case 'product_created'` and `case 'product_approved'` appear twice in one `switch`. JavaScript takes the first; the second pair — the product workstream's richer sentence with `doc_version` — is unreachable.

**What happens**
- reviewer's jsdom script (jsdom, real `notifications-view.js`, the real backend params): "Someone added 2000 × undefined to undefined (clone)", "Someone moved undefined × undefined: undefined (clone) → undefined (veg)". Every batch registration and every phase move — the two most frequent floor events — reach the inbox as this. `product_approved` renders "approved product GP_THC26:CBD1" and drops the cultivar and version the merge intended to show.
- Pre-existing keys (the sentence text is identical at `549b617`), but FE-18 was closed as "every backend event verb has a bilingual sentence … structured params only", and `notifications-view.test.js` does not use the real params for these verbs. The per-verb param check was the part of FE-18 nobody ran.

**Evidence**
- Script over `backend/app/**` `safe_emit(... params={...})` keys vs the `p.<key>` reads per `case`: only these two verbs mismatch; six emitted verbs (`coq_signed`, `commercial_identity_upserted`, `facility_layout_imported`, `portfolio_master_imported`, `potency_catalogue_imported`, the `workflow_` family) fall to the generic line, which is the intended fallback.

**Fix**
- `batch_added`: `${a} registered ${p.code} — ${p.plant_count} × ${p.cultivar} (${p.phase})`; `batch_moved`: `${a}: ${p.code} ${p.old_phase} → ${p.phase}` with a "room change" variant when `room_change`. Same in `views.js`. Delete the first `product_created`/`product_approved` pair (lines 83-86). Add a test that feeds each sentence the backend's real param keys and asserts no `undefined`.

### R2-FE-05 [medium] contract seam — The custody form pre-fills `from_user_id` with the previous recipient, which the backend's new B-12 rule refuses unless the recorder is that person; DECISIONS E-2 states the opposite

**Where**
- `web/gf/qccustody-view.js:349` (hidden `qcu-xfromuser` = last entry's `to_user_id`), `:207-209` (sent as `from_user_id`).
- `backend/app/api/qc/custody.py:628-637` (QC-29 / B-12): `if user.id not in {from_user, to_user_id}: 403 "a custody transfer is recorded by the person handing the sample over … or the person receiving it — not by a third party"`.
- `docs/DECISIONS-2026-09.md` §2b E-2: "The custody form sends `from_user_id` = previous recipient, **so a QC writer can log a hop on the custodian's behalf**." §2b B-12: "No ADMIN exemption for third-party custody entries: the recorder must be the giver or the receiver."

**What happens**
- Sample left with sampler S (entry 1: `to_user_id = S`). QC_MGR Q logs entry 2 "S → lab tech L": form sends `from_user_id = S`, `to_user_id = L`, recorder Q → 403. Sending nothing is no better: the server then takes `from_user = Q` and the continuity guard (`custody.py:648-653`) answers 409. So from the app, a hop can only be recorded by one of its two parties, which is the B-12 rule — but the form shows a "Collected from: S" line and a free recipient picker to every QC writer and says nothing until the refusal.
- `qccustody-chain.test.js:73-94` passes only because its recorder (`u1`) happens to be the chosen recipient.
- E-2 is a false statement about what the code does, filed for the owner's approval alongside the B-12 row it contradicts.

**Evidence**
- Read both sides; traced the three cases (recorder = previous custodian, recorder = recipient, recorder = neither).

**Fix**
- Keep sending the previous custodian (continuity needs it), but in the form: when the signed-in user is neither the previous custodian nor the chosen recipient, disable "Log transfer" with the server's own sentence, and default the recipient picker to the signed-in user. Correct E-2 in DECISIONS to "the form sends the previous recipient as `from_user_id` for continuity; the recorder must be the giver or the receiver (B-12)".

### R2-FE-06 [medium] data completeness (GxP) — The audit viewer still pages on the `before` timestamp the backend now documents as lossy, and the client cannot read the cursor the fix introduced

**Where**
- `web/gf/audit-view.js:87-89,115-116`: `q.before = last row's created_at`.
- `backend/app/api/audit.py:120-123`: `before` is "LEGACY keyset … Lossy at a page boundary inside one transaction's rows — prefer `cursor`"; `:186-190` the `X-Next-Cursor` header.
- `web/gf/api.js:141-142`: `_req` returns `res.json()`; response headers are discarded.
- DECISIONS A-7: "`before` stays as the documented lossy legacy until the audit view switches."

**What happens**
- BC-08 ("the audit viewer drops rows at page boundaries, still open from July") is fixed on the server and unchanged for the reader: a bulk write whose rows share one `created_at` (audit triggers use `now()`, constant per transaction) straddling the 100-row page boundary still loses rows in the trail the QA manager reads and the auditor is shown. The view's own comment (`audit-view.js:102-114`) describes this exact residual risk and says closing it "needs a compound `(created_at, id)` keyset on the server" — which now exists.

**Evidence**
- Read both files; `_req` has no header return path, so no caller could adopt `cursor` without an `api.js` change.

**Fix**
- Add `auditPage(q)` to `api.js` that returns `{rows, next}` from `res.json()` and `res.headers.get('X-Next-Cursor')`; in `loadAudit` send `cursor` instead of `before`; keep `source+id` dedupe. Then retire `before` server-side.

### R2-FE-07 [medium] contract gap — A CoQ cannot be compiled as a RETEST, cannot name its sources, and the list/detail cannot tell an INITIAL from a RETEST CoQ

**Where**
- `backend/app/api/qc/coq_aggregation.py:118-125` (`purpose`, `timepoint`, `source_coa_ids` on `CoqIn`), `:396-405` (validation), `:755-764` (one live APPROVED CoQ per batch/spec/purpose/timepoint), `:156-157` (`_coq_out` carries them). DECISIONS B-8.
- `web/gf/qccoa-view.js:640-662` (compile body: batch, spec, product/cultivar, product_name, batch_size, mfg date only), and no `purpose`/`timepoint` anywhere in the file (`grep`).

**What happens**
- The QC workstream made the 6-month/12-month stability re-test a first-class CoQ (`purpose=RETEST`, `timepoint='6M'`), and the product workstream's compile form cannot send it: every CoQ compiled from the app is INITIAL. The owner's 2026-09-18 messages (retest results linked to their initial on the scales) describe exactly the retest record this was built for.
- With no source selection, a batch with two usable certificates always aggregates both; QC-15's explicit-source choice is API-only.
- Two CoQs for one batch (INITIAL and RETEST, or after a void/recompile) list identically — `purpose`/`timepoint` are not rendered.

**Evidence**
- Compared the compile body keys with `CoqIn`; read `_coq_out` and the list/detail renderers.

**Fix**
- Add a purpose toggle (INITIAL/RETEST) and a timepoint input (required for RETEST) to the compile form; a multi-select of the batch's usable certificates (`qcCoas({batch_id, status})`) feeding `source_coa_ids`; print `purpose · timepoint` on the CoQ row and detail.

### R2-FE-08 [medium] owner-instruction — INS-12 was applied to three QC forms and skipped on the two closest to the owner's example (the CoQ compile and CoA create batch ids)

**Where**
- `web/gf/qccoa-view.js:796` (`qcq-batch`, CoQ compile) and `:849` (`qco-batch`, CoA create): plain `<input placeholder="Batch id">`.
- `web/gf/codefield.js:90-157` `GF.batchCodeField` exists; used at `qcsample-view.js:385`, `qcecoa-view.js:679`, `qcoos-view.js:273` (f73bba7). `qccoa-view.js` was the product workstream's file and f73bba7 did not touch it.
- INS-12 listed `qccoa-view.js:762,814` first; the owner's 2026-09-05 17:00 message named the certificate of quality.

**What happens**
- A batch id typed on the CoA/CoQ forms has no strain head and no chooser; the catalogue's `certificate_level` history (`products.py:394-400`) joins certificates to the strain by the batch code's head, so a mistyped head on exactly these forms is what silently drops a certificate from "tested so far".

**Fix**
- Replace both inputs with `GF.batchCodeField(...)` as in `qcsample-view.js:385-391`; extend `batch-codefield.test.js`.

### R2-FE-09 [medium] contract / data-integrity — The Approvals handoff list is built from the inbox's first page and disappears when the recipient marks the notification done

**Where**
- `web/gf/approvals-view.js:24-45` `loadHandoffs`: `GF.API.notifications({})` (no `limit`, so `notifications.py:63` default 50, `done_at IS NULL`), then `handoffs(task_id)` per `handoff` notification.
- `web/gf/notifications-view.js:456-464` `notifDone` soft-archives the row.

**What happens**
- A receiving manager reads the proposal in the inbox, presses ✓ Done (the row's only action besides opening it), and the handoff leaves "Handoffs to your department" although it is still `proposed` on the server and still blocks the task from moving. A proposal older than the 50 most recent notifications is never listed. A manager who also receives dozens of `due_soon`/`overdue` rows a week is past 50 in days.
- DECISIONS E-5 records the derivation but not that "done" or volume hides an open proposal.

**Evidence**
- Read the list query and `notifDone`; the fixture in `handoffs.test.js` never exceeds one notification.

**Fix**
- Until the `GET /handoffs?to_dept=mine&status=proposed` endpoint the E-5 row itself proposes exists, call `notifications({limit: 200})` and do not exclude done rows for this purpose (the per-task `handoffs()` call is the truth: it already filters `status === 'proposed'`).

### R2-FE-10 [low] role-gate — FE-15 (1) not fixed: QP cannot void a certificate or a CoQ from the UI

**Where** `web/gf/qccoa-view.js:30,534,776` (`canCoq()` = `['ADMIN','QC_MGR']` guards Void) vs `certificates.py:831` and `coq_aggregation.py:798` (`_HOQC` = ADMIN, QC_MGR, QP).
**What happens** Unchanged from the first review; `GF.QC_HOQC` exists in `core.js` and is what `qcpotency-view.js:28` uses. The other `canCoq()` uses (review, generate, render) correctly mirror `_COQ_ROLES`.
**Fix** Gate the two Void buttons on `GF.QC_HOQC`.

### R2-FE-11 [low] duplicated logic that has drifted — FE-17 closed on paper only: both boards still count "days in phase" their own way

**Where** `web/gf/facility-view.js:67-70` (`Date.now()`, rounded), `web/gf/cultivation-view.js:134-138` (facility day), `web/gf/core.js:364` `GF.daysSince` (added, tested in `shell-and-gates.test.js:117-128`, called by nothing: `grep daysSince web/gf/*.js` → core.js only).
**What happens** The original scenario stands: a batch whose `phase_since` is today reads "1 d" on the Facility board after 12:00 and "0 d" on the Cultivation board. The conventions appendix now asserts "`GF.daysSince(day)` is the one 'days in phase' rule".
**Fix** Replace both local `daysIn` with `GF.daysSince`.

### R2-FE-12 [low] owner-instruction / dates — FE-20 two-thirds open: feeding and IPM records still carry no date, so a spray logged the next morning shifts the PHI/REI windows

**Where** `web/gf/irrigation-view.js:119-128` (no `applied_on`; `FeedIn.applied_on` defaults server-side), `web/gf/harvest-view.js:702-712` (no `applied_at`; `IpmIn.applied_at` defaults to now, and `rei_until`/PHI clearance are computed from it — `harvest.py`). Only the biosecurity form got `occurred_on`.
**Fix** `GF.dateField` pre-filled with `GF.facilityToday()` (and a time for IPM), sent as `applied_on` / `applied_at`.

### R2-FE-13 [low] race — FE-16 applied to two of six loaders

**Where** `cultivation-view.js:146-163`, `propagation-view.js:69-84`, `facility-view.js:72`, `irrigation-view.js:28` have no `lseq`; `waste-view.js:89-101` and `decon-view.js:50-81` do. The cultivation loader's "include closed batches" toggle (`showClosed`) is the race the finding described.
**Fix** Same `my = (st.lseq = …)` guard, as in `waste-view.js`.

### R2-FE-14 [low] dead code / contract — `GF.DEPTS` never carries `head_user_id`, so the department-head branch of `handoffRights` is unreachable; `PATCH /departments/{id}` has no UI

**Where** `web/gf/integrate.js:353-361` maps `{id, code, name, mk, parent_id, abbr, icon, color}` from `GET /departments`, which now returns `head_user_id` (`tasks.py:97-101`); `web/gf/task-extras.js:187-190` reads `dept.head_user_id`; `handoffs.test.js:110-115` injects it by hand ("once the payload carries it"). No caller of `PATCH /departments/{id}` (A-3: "ADMIN may set it").
**What happens** A head who is not a dept-scoped manager of the target family (A-3 lets ADMIN set any elevated user) gets the server's `target_side` but no button; a head who proposed the handoff is shown no Accept although the server allows it. Practically rare because A-3's automatic head is always in the family.
**Fix** Carry `head_user_id` through in `integrate.js`; add a head chooser to the ADMIN department form (`PATCH`).

### R2-FE-15 [low] security hygiene — A free-text layout `grade` is interpolated into an inline handler; the FE-04 guard's denylist does not include it

**Where** `web/gf/facility-view.js:381` `onclick="GF.WWF.planGrade('${GF.esc(k)}')"` where `k = gradeKey(r)` (`:194-198`) is `r.grade` upper-cased — free text set by QA via `LayoutPatch.grade` (`facility_layout.py:65`, `max_length=40`); the column is `text` (tasks 0068). `tests/frontend/xss-inline-handlers.test.js:150` lists neither `grade` nor the alias.
**What happens** A grade `A'B` breaks the legend chip's handler (SyntaxError, chip dead). Execution is impractical — `toUpperCase()` destroys every lowercase identifier and 40 characters are too few for an octal-escaped `URL['constructor']…` chain — but the file violates the rule its own review established ("typed text never"), and the denylist would not catch a copy of this pattern with a longer field.
**Fix** `data-grade="${GF.esc(k)}"` + `this.dataset.grade`; add `grade` to `FREE_TEXT`.

### R2-FE-16 [low] dates — The catalogue's "tested so far" chips print a time of 02:00 on date-only certificate results

**Where** `web/gf/qcpotency-view.js:258-262` `GF.fmtDateTime(v.on)`; for `certificate_level` rows `on` is `report_date` (a date, `products.py:397`). `core.js:322-327` appends `Z` to a bare date; `new Date('2026-07-30Z')` is valid in V8 and renders "2026-07-30 02:00" in Skopje (verified with node).
**Fix** `GF.fmtDate(v.on)` for the chip title, or make `fmtDateTime` return bare dates unchanged as `fmtDate` already does.

### R2-FE-17 [low] service worker / process — Two shell-changing commits followed the VERSION bump with no new VERSION, and nothing checks for it (FE-13 second half)

**Where** `web/sw.js:8` `v3.103.0` set in `8c6a5bc`; `a248dc4` (`notifications-view.js`) and `f73bba7` (`codefield.js`, `qcecoa/qcoos/qcsample-view.js`, `integrate.js`) came after; `tests/frontend/shell-and-gates.test.js:28-47` checks `cache:'reload'` and the list, not the bump.
**What happens** Harmless now (v3.103.0 has not shipped, so the next image carries everything), but the conventions appendix says "VERSION is bumped whenever a shell file changes" and the first commits under that rule did not. The next time a bump lands mid-series and ships, cache-first serves the older files until someone notices.
**Fix** A test that hashes `web/gf/*` + `index.html` and compares with a hash recorded next to VERSION, or a CI step diffing `git log -1 -- web/gf web/index.html` against `git log -1 -G"const VERSION" -- web/sw.js`.

### R2-FE-18 [low] dead code — FE-21 remainder

- 14 uncalled `api.js` wrappers (list in the closure table); `cultivationBatchCode` is bypassed by an inline `GF.API._req` in `cultivation-view.js:904` because the wrapper takes no `clone_date`.
- `/qms/rag-query` still in `api.js:40 _SLOW_PATHS` and `nginx.conf:100` (the route is gone with BC-19).
- `assets/pp-logo.png` referenced only by the precache (`sw.js:22`).
- `PATCH /cultivation/trichome-checks/{id}` and the `trichome_corrected` sentence (a248dc4) have no UI that can produce the event.
- `dept-templates.js:42,78,121` `batch_ref` free text with `B-2026-041` placeholder (FE-11).

---

## DECISIONS §2b E-1 … E-6 against the owner's words

- **E-1** (QC batch-id fields carry the cultivar code). The owner's instruction (2026-09-05 17:00) was about the certificate-of-quality code; CoA/CoQ numbers are server-minted, so extending the idea to the batch id is a reasonable reading and does not contradict anything. Coverage is partial (R2-FE-08).
- **E-2** (custody `from_user_id` "so a QC writer can log a hop on the custodian's behalf"). **Contradicts B-12**, which is what the backend enforces; the sentence is false about the code (R2-FE-05). Not an owner instruction either way.
- **E-3** (SOP Registry / Knowledge stubs deleted). No owner instruction kept them; the stubs printed "retired". The owner's standing wish (owner-messages.md line 30) that the RAGflow knowledge bases be "available to the app and Letta agents" remains unbuilt and is not listed in DECISIONS §4.
- **E-4** (biosecurity 200 unfiltered). Matches the code (`decon-view.js:76`); no owner instruction touches it.
- **E-5** (handoff list derived from notifications). Matches the code, but the row omits that the list is unreachable for the roles it is for (R2-FE-01) and lossy (R2-FE-09). The row's own suggestion (`GET /handoffs?to_dept=mine`) is the right fix.
- **E-6** (executives land in Analytics). No owner instruction on landing; the earlier "executives land on the Exec overview" behaviour was the agent's, now actually working.

## Checked and found clean

- `api.js`: 250 methods, no duplicate names; every `GF.API.*` call in `web/gf` resolves; the only "undefined" hits (`login`, `changePassword`) are `entry.js`/`integrate.js` calls on methods defined under those names (my extractor's regex missed the `async` forms).
- `app.css`: additions only (`.dp-cursor`, `.qcprod-*`); no selector redefined; `.fp-badge` used by the facility view is defined (`app.css:1503`).
- `index.html` scripts ↔ `sw.js` SHELL ↔ `web/gf/*.js` on disk agree; `API_RE` ↔ nginx (`sw-api-routes.test.js`); every `modules.js` nav key resolves to a registered renderer (`exec` is a `views.js` literal; script `review2/fe`).
- `qmsstudio-view.js:46` reads `docs.documents` from the new `{documents,total,limit,offset}` envelope. DocEngine 504 (`docengine.py:80-84`, "still answering") vs 503 reaches the user as the detail string through `_req`; the chat path is on the 190 s `_SLOW_PATHS`. The view's header comment (`:16-17`) still mentions only 503 — cosmetic.
- Product catalogue calls: `qcProductConformance({cultivar_id,total_d9_thc,product_id})`, `qcImportFittedProducts({specs,doc_version,dry_run})`, `qcImportProducts({dry_run})`, `qcImportPotencySpecs({family})` and the `{product, tested, cultivar_level, certificate_level}` / `{spec, ranges}` detail shapes all match `products.py` / `potency.py`.
- Floor views' request bodies match `BatchIn/BatchPatch/MoveIn/TrichomeIn/CampaignIn/MotherIn/CloneRunIn/HarvestIn/DryIn/LayoutPatch/CorridorCleaningIn/…` (script); `motherNextCode` → `acronym`, `motherPotency` → `{strain, sources, product, traced, window}` match `propagation.py`.
- Role mirrors: cultivation `_WRITERS/_CORRECTORS`, propagation `_WRITERS/_INITIATORS`, harvest `_RECORDERS/_PHI_OVERRIDERS/_POST_HARVEST`, facility `_ROOM_WRITERS/_KINDS_BY_ROLE`, irrigation, intake (ELEVATED), audit verify (ADMIN/QA_MGR/QP), studio authoring — all match. Only the waste/decon/biosecurity PR_MGR gap (R2-FE-03) and the Void gate (R2-FE-10) differ.
- Inline handlers across all 55 files: apart from R2-FE-15, every interpolated value is a uuid, an enum key, a date, a server-generated number, or a code constrained server-side to `[A-Za-z0-9_/-]` (`cultivation.py:153,175`, `propagation.py:140`, `harvest.py:181`).
- Datepicker: cursor starts on the chosen date or the facility's today, highlighted not written — the owner's "always start with the current date highlighted".
- e2e changes (`254c7f1` seed code `GGE092701`, `ca4bec3` viewport 660, `qms-studio.spec.js` asserting the stubs are gone) are consistent with the code.
- Test adaptations were legitimate: `modules.test.js` (removed keys), `decon-view.test.js` (fixture now carries `result`), `assistant.test.js` (state fields removed), `qc-role-gates/qcecoa/qcoos/qcsample` (load `codefield.js`, which the views now require at render).
