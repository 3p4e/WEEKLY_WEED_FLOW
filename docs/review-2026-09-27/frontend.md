# Frontend review — `web/` (index.html, sw.js, web/gf/*.js)

Reviewed at `807d60f` (the branch production frontend v133 was built from; `git log cbfae38..HEAD -- web/` is empty, so HEAD's `web/` is what is live).

## Summary

The frontend is a no-build vanilla-JS SPA: ~60 classic scripts share one global scope, and views register by monkey-patching `GF.render.sidebar` and `GF.render.all`. `api.js` is the single fetch path, with a timeout and 401 handling. The service worker serves a hand-versioned app shell cache-first. `index.html`, the `sw.js` precache and the files on disk agree exactly, and the older modules (tasks, QC LIMS) are careful about escaping, stale responses and role gates. Most of the defects are at the edges of the newest work (propagation, product catalogue, decon, custody, handoffs), where the UI never sends a field the backend now requires, or never calls a route the workflow depends on. Every frontend call matches a backend route and method. The backend has about 40 routes with no frontend caller, and several of them are required to finish a workflow.

Two defects cross the whole app. First, every `timestamptz` is displayed by slicing the UTC ISO string. asyncpg always returns UTC, so times show 1–2 h early, including the pesticide re-entry time. Second, the facility-zone plumbing (`GF.facilityToday`) is never fed on a normal login, so the facility-day date picker falls back to the browser's day. The unit tests are green (spot-run: 11 files, 142 passes) because they inject `facility_tz` directly and mock the API.

Severity counts: **critical 0 · high 6 · medium 6 · low 10**.

---

### FE-01 [high] contract / owner-instruction — The official product catalogue has no UI, which blocks the mother bank and product-based batch registration

**Where**
- `web/gf/api.js:371-380`: 10 product wrappers. Only `qcProducts` is ever called (`propagation-view.js:318`).
- `web/gf/modules.js:30-31`: no product view key.
- `web/gf/qcpotency-view.js:1-13, 163-176`: the only potency screen still imports and approves the legacy "71-strain" ladders.
- `web/gf/cultivation-view.js:696-697`: tells the user the grades are "imported under QC → Product catalogue". That screen does not exist.
- `web/gf/propagation-view.js:317-326`: blocks with "import and approve the ImB catalogue first".
- `web/gf/qccoa-view.js:642-652`: CoQ compile sends `cultivar_id` (ladder) and never `product_id`.
- `web/gf/api.js:380`: `qcProductDocumentUrl` points at `GET /qc/products/{id}/document`. That route does not exist in the backend (only `potency-specs/{id}/document` and `certificates/{id}/icoa-html` exist in `spec_html.py`), yet `docs/PRODUCT-CATALOGUE-2026-09.md:73` lists it.

**What happens**
- `mother_plants.product_id` is NOT NULL and the mother form offers only APPROVED products. On a fresh catalogue there are no approved products, so "Register mother plant" always toasts the error and returns. The mother bank the owner asked for on 2026-09-05 cannot be filled from the app.
- The batch form's "Target product" list only ever holds "— no target product —".
- Import, approve (second person) and supersede of the ImB pages can only be done with raw API calls. HANDOFF's rollout step "product import + approval by a second QC person" has no button.
- The only potency screen promotes the ladder model the owner called stale on 2026-09-18 ("the old internal … specification grading is stale").
- `docs/DEPLOY-2026-09-06-v92.md:15-16` says v133 shipped "the product catalogue … views". It did not.
- The approved plan (`drifting-wibbling-bentley.md` step 6: "qcpotency-view.js becomes the product catalogue … compile form product select") was not implemented.

**Evidence**
- `grep` for every product method: zero callers apart from `qcProducts`.
- Read the mother-form guard and `propagation.py` `MotherIn` (`product_id` required).
- `git log -S qcApproveProduct -- web/`: only added once, in `08c2209` (api.js).
- Backend route extraction (AST) shows no `/qc/products/{id}/document`.

**Fix**
- Implement plan step 6: make `qcpotency-view.js` list `/qc/products` with Import / Approve / Supersede for `GF.QC_HOQC`, and show the ladders read-only.
- Add a product chooser to the CoQ compile form (`body.product_id`).
- Either add the backend `/qc/products/{id}/document` route or delete `qcProductDocumentUrl` and the doc row.
- Correct the deploy record.

### FE-02 [high] contract (GxP) — Chain of custody: every transfer after the first one fails with 409

**Where**
- UI: `web/gf/qccustody-view.js:188-200` (body builder) and `:322-328` (form: type, to-location, reason, condition, intact). There is no from-location and no recipient.
- Server: `backend/app/api/qc/custody.py:557-615`.

**What happens**
- Transfer 1 is stored with `to_location = X` and `to_user_id = NULL`.
- On transfer 2, `add_custody` finds `prev.to_user_id` is None and `prev.to_location` is set, while `body.from_location` is missing. It raises 409: "Custody continuity broken … must state the from_location it is being collected from" (`custody.py:608-612`).
- The UI can never send `from_location` or `to_user_id`, so a sample's field-to-lab chain can never be longer than one hop from the app. The receiving person is also never recorded.

**Evidence**
- Traced the UI body keys (`transfer_type, to_location, transfer_reason, sample_condition, condition_ok`) against `CustodyIn` and the continuity guard.
- No other INSERT into `qc_chain_of_custody` exists apart from `demo_org.py`.

**Fix**
- Add "from location" (pre-filled with the previous entry's `to_location`) and a "received by" person chooser (`to_user_id`, from `GF.PEOPLE`) to the transfer form, and send both.

### FE-03 [high] contract — A decon cycle with a positive or inconclusive swab is a dead end: no UI calls `POST /decon/cycles/{id}/fail`

**Where**
- `web/gf/decon-view.js:105-150`: the card shows "N swab(s) not negative" and offers no way forward.
- `web/gf/decon-view.js:740`: the placeholder says "re-clean and re-test".
- `web/gf/api.js:293-296`: no wrapper for `/fail`.
- Server: `backend/app/api/decon.py:453` (`fail_cycle` docstring: "without this endpoint a cycle that will never pass is a dead end") and `:197-210` (`create_cycle` returns 409 while a cycle is `in_progress` or `awaiting_verification`).

**What happens**
- After a positive swab the cycle cannot be released (release predicate).
- It cannot take more steps (`record_step` returns 409 once `awaiting_verification`).
- A new cycle for the room in the same campaign returns 409 "an open cycle already exists".
- The room stays blocked in the app until someone calls the API by hand.

**Evidence**
- `grep` for `fail` and `/decon` in `web/gf`: no caller.
- Read the three backend guards.

**Fix**
- Add `deconFail(cycleId, {reason})` to `api.js`.
- Add a QA-only "Fail cycle / re-clean" button, with a required reason, on cycles whose swab tally has `positive` or `inconclusive > 0`.

### FE-04 [high] security (stored XSS → privilege escalation) — `swab_code` is injected into an inline `onclick` JS string

**Where**
- `web/gf/decon-view.js:712`: `onclick="GF.WWF.deconSwabResultForm('${x.id}','${GF.esc(x.swab_code)}')"`.
- The server accepts any string of up to 64 characters (`backend/app/api/decon.py:84-89`, `swab_code: str = Field(max_length=64)`).

**What happens**
- `GF.esc` HTML-encodes `'` as `&#39;`. The browser decodes it back before running the handler, so the value breaks out of the JS string.
- A QA writer (QA_MGR, or any of ADMIN/OWNER/CEO/COO) can create a swab with code `S1');<js>;('`.
- When an ADMIN or OWNER opens "Swab results" and clicks "Enter result", the script runs with the victim's bearer token (`sessionStorage.wwf_token`). CSP allows `'unsafe-inline'`, and top-level navigation is not restricted, so the token can also be carried off-site.
- The result is a QA_MGR taking over an ADMIN session. ADMIN is the only role that can create users, set AI bindings or purge accounts.

**Evidence**
- Reproduced in jsdom with the real `decon-view.js` (scratch script `review/fe/xss_swab.js`).
- The rendered attribute was `GF.WWF.deconSwabResultForm('abc','S1');window.__pwned='yes';('')`, and after `.click()` `window.__pwned === 'yes'`.
- The other `('${GF.esc(…)}')` handler sites carry uuids, `^[A-Za-z0-9_-]+$` batch codes, or strip `'` first (`qcecoa-view.js:600`, `qcgenealogy-view.js:59,68`). A backslash in those last two only breaks the button.

**Fix**
- Pass ids only: `deconSwabResultForm('${x.id}')`, and look the code up from the loaded list, or read it from `this.dataset` via a `data-code="${GF.esc(...)}"` attribute.
- Optionally constrain `swab_code` server-side to `^[A-Za-z0-9_./-]{1,64}$`.
- Add a lint or test that forbids `GF.esc(` inside `on*="…'…'"` JS strings.

### FE-05 [high] dates / safety — Every `timestamptz` is displayed by slicing the UTC ISO string, so it shows 1–2 h early

**Where**
- `web/gf/harvest-view.js:236-237` and `:430`: pesticide **REI "no entry until …"**, plus `:232` (`applied_at` date).
- `web/gf/worklog.js:113`: logged work sessions.
- `web/gf/notifications-view.js:93-97, 105, 121`: inbox time and Today/Yesterday grouping.
- `web/gf/qccoa-view.js:348, 395, 426`: e-signature time and CoQ issue time.
- `web/gf/qcecoa-view.js:566`: verification time.
- `web/gf/qcoos-view.js:144`: OOS register.
- `web/gf/qccustody-view.js:47`: all custody and SFR times.
- `web/gf/waste-view.js:328-330`: sealed, witnessed and disposed times.
- `web/gf/decon-view.js:235, 263`.
- `web/gf/execreport-view.js:123, 234`.
- `web/gf/approvals-view.js:229`.
- `web/gf/qmsstudio-view.js:578`.
- `web/gf/document-view.js:364`.

**What happens**
- asyncpg decodes `timestamptz` as a UTC-aware datetime, and handlers emit `.isoformat()`, for example `harvest.py:201`, `tasks.py:844` and `notifications.py:52`. So `"…T12:00:00+00:00".slice(0,16)` is printed as 12:00 when the facility clock reads 14:00 (CEST).
  - **Safety:** the red IPM row "no entry until 2026-09-27 12:00" is two hours before the re-entry interval actually ends. A worker reading local time re-enters a treated room early.
  - **Worklog:** a session typed as 08:00–16:00 (sent without offset; `tasks.py:830-837` interprets it as Europe/Skopje) is listed back as "06:00".
  - **Records:** GxP records (signatures, custody, waste witness) show an unlabelled UTC time.
  - **Inbox:** items created between 00:00 and 02:00 local are grouped under the wrong day.
- `collab.js:17` (`new Date(iso).toLocaleString()`) does this correctly. The helper exists and has drifted from the other sites.

**Evidence**
- Read asyncpg `pgproto/codecs/datetime.pyx`: `timestamptz_decode` returns `pg_epoch_datetime_utc + delta`.
- Traced `_iso` and `_session_out`.
- Traced the worklog round trip (`worklog.js:209` → `tasks.py:855` → `:844` → `worklog.js:113`).

**Fix**
- Add `GF.fmtTs(iso)` = `Intl.DateTimeFormat('en-GB', {timeZone: GF.facilityTZ() || undefined, dateStyle:'short', timeStyle:'short'})` on `new Date(iso)`, and use it at every site above.
- Group the inbox by the facility-zone date of `new Date(created_at)`.

### FE-06 [high] contract / role-gate — Cross-department handoffs cannot be accepted by the department they are sent to, and others see buttons that return 403

**Where**
- `web/gf/task-extras.js:164-176`: `canResolve = GF.WWF.canManageTask(t)` shows Accept/Reject to the task owner and to every elevated role.
- `web/gf/collab.js:14-15`.
- `web/gf/notifications-view.js:29-62, 293-307`: the `handoff` verb has no sentence, and `openNotif` → `xrJump` finds nothing.
- Server: `backend/app/api/collab.py:327-376` (accept = `target_side or (org_wide and not is_requester)`; reject = `target_side or org_wide`), `:318-323` (`list_handoffs` calls `_assert_scope_visible`), `backend/app/api/tasks.py:59-90` (scope = own department, owned, assigned, or parent/child link).

**What happens**
- The person the proposal is addressed to is a department-scoped manager of the target department (for example PR_MGR for cultivation → production). The task still sits in the source department, so it is not in their `GET /tasks`, and `GET /tasks/{id}/handoffs` returns 404 for them. They get a raw notification ("Name: handoff title") that opens nothing. **No UI path exists for the actor the backend designates.**
- Meanwhile these users are shown ✓ and ✕ buttons that return 403 "Not permitted to resolve this handoff":
  - a USER who owns the task;
  - the source-side CU_MGR;
  - an org-wide executive who proposed the handoff.

**Evidence**
- Compared the client predicate with the server predicate case by case.
- Read the scope guard.
- Confirmed with `grep` that no approvals or inbox surface lists pending handoffs.

**Fix**
- Backend: add `GET /handoffs?to_dept=mine&status=proposed` (visible by the target side).
- Frontend: add a "Handoffs to my department" list (Approvals or Inbox) with Accept/Reject.
- Mirror the server predicate on the card:
  - accept = target-side, or (org-wide and not requester);
  - reject = target-side or org-wide;
  - cancel = requester, target-side or org-wide.
- Add a `handoff` / `handoff_resolved` sentence.

### FE-07 [medium] dates / owner-instruction — "Facility today" is never loaded on a normal login, so the date picker and plant ids use the browser's day

**Where**
- `web/gf/core.js:280-295`: `GF.facilityToday()` reads `GF.API.user.facility_tz` and `facility_today`.
- Only `/auth/me` returns them (`backend/app/api/auth.py:234-254`). Login returns `_public(row)` without them (`auth.py:169-174, 232`).
- `web/gf/api.js:145-150` stores that login `user`.
- `web/gf/integrate.js:175-183`: `doLogin` → `loadAndRender` never calls `me()`. It is called only after a forced password change (`integrate.js:206`).

**What happens**
- For every ordinary session (and every reload, since `wwf_user` comes from sessionStorage), `facilityTZ()` is `''`, so the code falls back to `GF.todayISO()`, the browser day.
- The owner-requested date picker (`datepicker.js:99,124,179`), the clone date printed into every plant id (`cultivation-view.js:108-112, 767`), the mother, clone-run and trichome dates, and the journey "d in phase" all use the reader's zone. A manager abroad, or anyone in the 22:00–24:00 UTC window, gets a different date from the server.
- Several views ignore `facilityToday` outright and use the browser day: `render.js:353` (overdue), `myday-view.js:20,31,46,115`, `depthome-view.js:30`, `report-view.js:289`, `worklog.js:93`, `calendar-view.js:41`, `core.js:253` (`todayDay`, frozen at load), and `integrate.js:137` (`todayId`).
- `tests/frontend/datepicker.test.js:28-58` injects `facility_tz` into `GF.API.user`, so the missing wiring is invisible to the tests.

**Evidence**
- Read the login, loadAndRender, change-password and `me()` paths. `grep "\.me()"` → one caller.

**Fix**
- In `loadAndRender`, `GF.API.user = Object.assign(GF.API.user||{}, await GF.API.me())` and persist it (or add `facility_tz`/`facility_today` to the login response).
- Switch the listed "today" sites to `GF.facilityToday()`.

### FE-08 [medium] data-integrity — Date-picker arrow keys write a date the user never picked

**Where**
- `web/gf/datepicker.js:231-245`: the keydown handler writes `inp.value` directly and does not call `cfg.onPick`.
- This contradicts the file's own contract at `:23-27`: "highlighted is not the same as chosen … silently defaulting an expiry or a retest date … would put a real, wrong claim into a record".

**What happens**
- Scenario: open an empty expiry, retest or report date, press ↓ to look at next week, then dismiss with ✕ or Esc. The field now holds and displays that date, and it is saved with the form.
- For fields that keep state through `onPick` (e.g. `document-view.js:415-418` custom range), the displayed date and the submitted state diverge. The field shows 06.08, while `_doc.rangeStart` stays empty or keeps its old value.

**Evidence**
- jsdom with the real `datepicker.js` (`review/fe/dp_arrow.js`).
- Result: empty field → ArrowDown → `closeModal` → value `"2026-08-06"`, label `06.08.2026`, `onPick` never fired.

**Fix**
- Keep a separate "cursor" date for keyboard navigation (highlight only). Write the input and call `onPick` only on Enter or click (`GF.pickDate`).

### FE-09 [medium] broken button — The "A4 document" link on potency ladders always returns 401

**Where**
- `web/gf/qcpotency-view.js:108`: `<a target="_blank" href="${GF.API.qcSpecDocumentUrl(...)}">`.
- `backend/app/deps.py:11`: auth is `HTTPBearer` only; no cookie or query token.

**What happens**
- A plain navigation carries no `Authorization` header, and the token lives in per-tab sessionStorage.
- `GET /qc/potency-specs/{id}/document` (ELEVATED) answers `{"detail":"Not authenticated"}` in the new tab, for every user.

**Evidence**
- Compared with the working download paths, which `fetch` with the bearer header and open a blob: `qccoa-view.js:215-224`, `qcecoa-view.js:300`, `document-view.js:272`.

**Fix**
- Route the link through `fetch` with the header, then `URL.createObjectURL(blob)` → `window.open`, as `qcCoaDlCoq` does.

### FE-10 [medium] contract — Biosecurity checks logged as "not yet read" or "Pending" can never get a result

**Where**
- `web/gf/decon-view.js:409-413` (result options include "— not yet read —" and "Pending"), `:65` (the board loads only `open_only=true`, i.e. fail/below_spec), and `:327-376`.
- `web/gf/api.js:299-300`: no wrapper for `PATCH /decon/biosecurity/{id}/result` (`backend/app/api/biosecurity.py:164`).

**What happens**
- Contact plates and sentinel bioassays are read days after sampling.
- A pending event disappears from the board (not in the open-only list), and no screen can record its result. The backend route built for this has no caller.

**Evidence**
- `grep` for `biosecurity` in `web/gf`.
- Read the list query (`result IN ('fail','below_spec')`).

**Fix**
- Add `biosecurityResult(id, body)`.
- List `result IS NULL OR result = 'pending'` events in the panel with an "Enter result" action (action_taken required for fail/below_spec).

### FE-11 [medium] contract — Batch ↔ product and batch ↔ task links cannot be set from the UI

**Where**
- `web/gf/api.js:220`: `cultivationBatchPatch` has no caller. `PATCH /cultivation/batches/{id}` accepts `product_id`, `clone_source` and `note`.
- `web/gf/cultivation-view.js:799-805`: the product chooser defaults to "— no target product —".
- `web/gf/cultivation-view.js:581-583`: tells users to "link one by hand from the task form".
- `web/gf/integrate.js:576-586` and `:506-520`: `createTask` and `updateTask` never send `batch_id`, although `TaskIn`/`TaskPatch` accept it (`tasks.py:323, 543`).
- `web/gf/dept-templates.js:42,78,121`: offers a free-text `batch_ref` attribute with placeholder `B-2026-041`. That is not the facility's `GP072501` convention and is not what `/cultivation/batches/{id}/tasks` reads.

**What happens**
- A batch registered without a target product (the default) can never be linked to one later. The owner's grading and OOS path depends on that link (2026-09-06 message).
- "Batch tasks" only ever shows the tasks the server generated automatically.
- The text shown on screen describes a control that does not exist.

**Evidence**
- `grep` for callers.
- Compared the body keys at the call sites (extracted with a script) against the Pydantic models.

**Fix**
- Add "Edit batch" (product, clone source, note) on the batch card.
- Replace `batch_ref` in the task form with a batch chooser sending `batch_id` (keep the attribute for legacy display).

### FE-12 [medium] navigation rail — "Workload" and "Executive overview" throw the user into another module whose rail does not list them

**Where**
- `web/gf/render.js:147, 150`: pushed into the tasks-module "Management" group.
- `web/gf/modules.js:67`: both keys belong to the `analytics` module.
- `web/gf/core.js:547-553`: `setView` switches module.
- `web/gf/integrate.js:353-356`: the fresh-browser `exec` landing is dead.

**What happens**
- Clicking Workload in the Tasks rail sets `module='analytics'`. The rail re-renders with only the analytics items, so the current view has no nav entry and the way back is the module picker.
- The exec overview has no rail entry in the Analytics module at all.
- The "executives land on the Exec overview" branch is bounced by `render.js:91-94` back to the task default, because the module is still `tasks`.

**Evidence**
- jsdom with data, core, chooser, modules and render (`review/fe/navcheck.js`).
- Tasks rail: `mywork,board,timeline,calendar,coord,dash,team,workload,inbox`. After `setView('workload')`: module `analytics`, rail `inbox`, panel "workload view".

**Fix**
- Either move `workload` and `exec` into the tasks module keys, or emit them in the analytics module's rail (and remove them from the tasks rail).
- Land executives via `GF.setModule('analytics')` + `setView('exec')`.

### FE-13 [low] service worker — still open (from CODE-REVIEW-2026-07-28): shell freshness depends on a hand-bumped VERSION, and install can cache stale files

**Where**
- `web/sw.js:8` (`VERSION`), `:44-46` (`c.addAll(SHELL)`).
- `web/nginx.conf`: `expires 5m` on js/css. `index.html` has no cache header.

**What happens**
- Nothing (no test, no CI step) enforces a VERSION bump when a shell file changes. `cbfae38` edited `facility-view.js` after the v3.102.0 bump. It was harmless only because v133 shipped that exact commit.
- `cache.addAll` fetches through the HTTP cache. If an old copy is still fresh (≤5 min for JS/CSS, heuristic for `/`), the new worker stores old files under the new VERSION. Cache-first then serves them until the next bump.

**Evidence**
- Read `sw.js`.
- `git log -G"const VERSION" -- web/sw.js` vs `git log -- web/gf` (`488b869` bump, then `cbfae38` web change).

**Fix**
- `c.addAll(SHELL.map(u => new Request(u, {cache: 'reload'})))`.
- Derive VERSION from a content hash at image build (or add a CI check that fails when `web/gf|index.html` change without a `sw.js` VERSION change).

### FE-14 [low] role-gate (shows what the server forbids)

**Where / what**
1. **AI Intake** is registered with no guard (`web/gf/intake-view.js:208-213`, tasks module), so operators (USER) see it. `POST /intake/extract` requires `ELEVATED_ROLES` (`intake.py`), so "Extract" returns 403 for them.
2. **Report view document panel:** for USER, `report-view.js:22-23,383` calls `loadDocument` → `GET /reports/documents` (ELEVATED). The panel shows "Couldn't load the document: Insufficient role" plus a Retry button (`document-view.js:20-40, 430-434`).

**Evidence**
- Route/dependency extraction (`review/fe/routes2.tsv`) vs the view guards.

**Fix**
- Guard intake with `role !== 'USER'`.
- Skip `loadDocument` (render nothing) when the user is not elevated.

### FE-15 [low] role-gate (hides what the server allows)

**Where / what**
1. `web/gf/qccoa-view.js:29, 534, 737-742`: Void CoA and Void CoQ are gated by `_COQ = [ADMIN, QC_MGR]`. The server gates both on `_HOQC = (ADMIN, QC_MGR, QP)` (`certificates.py void_certificate`, `coq_aggregation.py void_coq`), so QP cannot void from the UI.
2. `web/gf/integrate.js:946-975`: the ADMIN "Add department" form has no parent field, although `DepartmentIn.parent_id` exists. Sub-departments (the Cloning/Nursery model) cannot be created from the app.

**Fix**
- Use `GF.QC_HOQC` for the two Void buttons.
- Add a parent chooser to the department form.

### FE-16 [low] race — The newer floor views have no stale-response guard (the pattern that was fixed across the QC views)

**Where**
- `cultivation-view.js:114-131` (`loadCultivation`), `decon-view.js:45` (`loadDecon`), `facility-view.js:69-75`, `irrigation-view.js:28-33`, `propagation-view.js:58` (`loadPropagation`), `waste-view.js:82-95, 289` (`loadWaste`/`wasteFilter`).
- `grep lseq` = 0 in all six.

**What happens**
- Example: toggling "include closed batches" twice quickly issues `active=false` then `active=true`. If the first response lands last, the board lists harvested and destroyed batches while the checkbox is unticked. The waste status filter has the same race.

**Fix**
- Add the `st.lseq` guard, as in `qcpotency-view.js:37-48`.

### FE-17 [low] duplicated logic that has drifted — "days in phase" differs between two boards

**Where**
- `web/gf/facility-view.js:64-67`: `Date.now() - new Date(iso+'T00:00:00')`, rounded.
- `web/gf/cultivation-view.js:102-106`: facility day minus the day.

**What happens**
- A batch whose `phase_since` is today shows "1 d" on the Facility board after 12:00 local and "0 d" on the Cultivation board.

**Fix**
- Make `daysIn` one exported helper (the cultivation one) and use it in both views.

### FE-18 [low] i18n / contract — Most backend event verbs render as raw English machine words

**Where**
- `web/gf/notifications-view.js:29-62` (`sentence` switch) and `views.js:197-211`.
- The backend emits about 55 verbs (`grep 'verb="'`). The inbox handles 13.

**What happens**
- `handoff`, `handoff_resolved`, `oos_opened`, `decon_swab_positive`, `qc_deviation`, `product_approved`, `mother_registered` and the rest fall to the default and display as e.g. "Ana: decon_swab_positive " in both languages. That contradicts the file's own "bilingual by structure" contract.
- `batch_closed` is handled, but no backend code emits it. It is a dead case.

**Fix**
- Add sentences for the emitted verbs (at least handoff*, oos_opened, decon_*, qc_deviation, product_*, harvest_*, waste_manifest_*).
- Map the rest to a localized generic line with `object_type`. Drop `batch_closed`.

### FE-19 [low] data-integrity — A failed note save is swallowed

**Where**
- `web/gf/integrate.js:450-453`: `GF.API.addProgress(...).catch(()=>{})` after `origAddNote` has already added the note to the card.

**What happens**
- On a 403, 409, 422 or network error, the note stays on screen as if it were saved, and vanishes on reload with no message.

**Fix**
- `await` the call, toast on failure, and remove the optimistic note.

### FE-20 [low] owner-instruction ("date picker where dates are entered") / contract — Three dated records have no date input

**Where**
- `web/gf/irrigation-view.js:~100-125`: the body has no `applied_on`.
- `web/gf/decon-view.js:386-470`: the biosecurity form has no `occurred_on`.
- `web/gf/harvest-view.js:604-700`: IPM has no `applied_at`.

**What happens**
- The backend accepts these dates (`FeedIn.applied_on`, `BioIn.occurred_on`, `IpmIn.applied_at`) and defaults them to server today/now. A feeding or spray logged the next morning is recorded on the wrong day.
- For IPM, that shifts the PHI clearance and REI windows, which are computed from `applied_at`.

**Fix**
- Add `GF.dateField` (and a time for IPM), pre-filled with the facility today, and send the value.

### FE-21 [low] dead code / dead files / dead CSS

**Where / what**
- **Unused `api.js` wrappers (23):** `campaignPatch, cultivationBatchPatch, deconBleachLog, deconCorridorCleanings, deconCycle, listUsers, patchDocument, qcApproveProduct, qcCommercialIdentities, qcCreatePotencySpec, qcImportCommercial, qcImportProducts, qcPotencyDisposition, qcProduct, qcProductConformance, qcProductCreate, qcProductDocumentUrl (points at a non-existent route), qcProductPatch, qcProductPotency, qcSignatures, qcSupersedeProduct, taskTree, trichomeChecks`.
- **Retired views still shipped:** `qmsregistry-view.js` and `qmsknow-view.js` are retired stubs, but are still registered in the QC rail, `modules.js:31`, `index.html` and the `sw.js` precache. `qmsknow-view.js:37-55, 92-93` has a result renderer that is unreachable (`st.results` is only ever set to null).
- **Dead slow-path entries:** `api.js:40` `_SLOW_PATHS` and the `nginx.conf` 180 s block still list `/qms/rag-query`, which has no caller.
- **Unreferenced assets (≈216 KB):** `web/assets/PP_Leaf.svg`, `PP_Leaf_3D.glb`, `pp-leaf-outline.svg`, `pp-leaf.svg`. `pp-logo.png` is only in the precache.
- **Dead or harmful CSS:**
  - `mobile.css:26, 58-62` target `#content`, which does not exist.
  - `mobile.css:145` styles `.mobile-bottombar`/`.mobile-fab`, which are never created (the file header promises a phone "bottom nav bar").
  - `mobile.css:19` hides every non-primary header `.btn` at ≤880 px, including the **Today** button, so tablets and phones lose the one-tap jump to the current week.
- **Dead state:** `core.js:78-80` (`user:'marko'`, `aiBase`, `aiProvider`) and `core.js:559` (`GF.setUser`). `render.js:18` seed `GF.HANDOFF` keyed by seed department ids.

**Fix**
- Delete the dead wrappers or wire them (see FE-01, FE-10, FE-11).
- Retire the two stub views from the rail, module keys, index and SW together.
- Drop the dead assets and selectors.
- Exempt `#today-btn` from the ≤880 px hide rule.

### FE-22 [low] contract coverage — Backend routes with no frontend caller (information; the workflow-critical ones are FE-01/03/06/10/11)

- **decon:** `POST /decon/cycles/{id}/fail` (FE-03), `GET/POST /decon/positive-controls`, `GET/POST /decon/tool-log` (tool-sterilisation PPM log, no UI), `GET /decon/cycles/{id}`, `GET /decon/bleach-log`, `GET /decon/corridors/{room}/cleanings`, `PATCH /decon/biosecurity/{id}/result` (FE-10).
- **cultivation:** `PATCH /cultivation/batches/{id}` (FE-11), `PATCH /cultivation/campaigns/{id}`, `GET /cultivation/trichome-checks`. The trichome **history** cannot be viewed; only `latest_trichome` shows. The owner asked for "progressive tracking … with documented records".
- **qc:** all of `/qc/products*` except the list (FE-01), `PATCH /qc/potency-specs/{id}`, `POST /qc/potency-specs`, `GET /qc/potency-disposition`, all of `/qc/commercial-identities*` (list, import, PUT, DELETE — the wrappers exist, no screen), `GET /qc/certificates/{id}/icoa-html`, `GET /qc/certificates/{id}/signatures`, `GET /qc/coa-documents/{id}/originals` (originals come embedded in the detail).
- **qms:** `/qms/documents, /stats, /hierarchy, /families, /documents/{code}, /rag-query, /download/{path}` (retired qms-api, for the backend reviewer).
- **tasks / auth / reports:** `GET /tasks/tree`, `GET /auth/users`, `PATCH /reports/documents/{id}`.
- **Frontend → no backend route:** only `qcProductDocumentUrl` → `/qc/products/{id}/document` (FE-01). Every other `_req` method and path in `api.js`, and the six direct `fetch` sites (`demo.js`, `entry.js`, `document-view.js`, `qccoa-view.js`, `qcecoa-view.js`, `qmsstudio-view.js`), resolve to an existing route and method.

**Evidence**
- AST extraction of all 274 backend routes with their role dependencies (`review/fe/routes2.tsv`).
- Script extraction of the body keys at all 153 write call sites (`review/fe/callkeys.tsv`), compared by hand against the 124 Pydantic request models (`review/fe/models.tsv`).
- No request model sets `extra="forbid"`, so a wrong key would be silently dropped. None was found apart from the omissions above.

**Fix**
- Wire the workflow-critical routes (above). Remove or feature-flag the rest in one place.

---

**Checked and found clean** (not reported):
- `index.html` ↔ `sw.js` SHELL ↔ files on disk: identical.
- The `sw.js` API prefix list matches nginx and every backend prefix.
- The 401, token-rotation and timeout handling in `api.js`.
- Role mirrors match the server for cultivation, propagation, harvest, irrigation, waste, decon, facility rooms/layout, QMS Studio authoring, the QC writer/QP/HoQC arrays, user provisioning, and AI bindings.
- `href` injection: task links are http(s)-only on the server.
- Markdown-lite AI renderer is escape-first.
- The owner's journey lanes do show every open batch at once (`cultivation-view.js:388-416`).
- The batch-number and DocEngine document-code fields pre-fill their constant head and place the caret after it (`codefield.js`).
- There are no native `<input type=date>` left.
- Earlier-review items re-checked and fixed: `window.APP` in `assistant.js`, `leaf3d` failed-fetch memo, the `export.js` rollover shadow, the first-visit SW reload, and `kpiTile` escaping.
