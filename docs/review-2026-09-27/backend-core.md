# Backend platform core — review (HEAD 807d60f)

**Scope:** `backend/app/{main,config,db,deps,security,roles,roster,automation,duescan,notify,worktime,logging_config,docengine,demo_org}.py`, `backend/app/api/{auth,tasks,approvals,collab,notifications,reports,audit,weekwindow,capture,ai,demo,intake,waste,decon,biosecurity,qms,documents}.py`, `scripts/scheduler.py` + `scripts/weekly_snapshot.py` (the background jobs), the users alembic chain and the RLS/audit/grant patterns of the tasks chain.

**Summary.** The core is carefully built: every request handler runs on the NOBYPASSRLS pool through `rls()`/`rls_users()` with transaction-local GUCs, every BYPASSRLS query carries an explicit `org_id` filter, all 73 tasks-DB tables have FORCE RLS and the audit trigger (except `audit_log`/`events`/`notifications`, by design), `is_elevated()` and the role CHECK agree across both DBs and `roles.py`, SQL is parameterised throughout (dynamic identifiers come only from fixed tuples/Pydantic field names), and the facility clock is respected in Python. No cross-org leak or SQL injection was found. The problems are elsewhere: the login IP limiter is one global bucket in the production topology; the archived AI weekly digest is readable by base USERs; the 2026-09-05 sub-department model was applied to the read paths but not to several write and notification paths; the GMP-style state machines in waste/decon are check-then-act; and the audit viewer still drops rows at page boundaries (open since the July deep review).

Counts: **2 high, 10 medium, 15 low.**

---

### BC-01 [high] security/availability — The per-IP login limiter is one global bucket: every client resolves to Traefik's IP
**Where:** `backend/app/api/auth.py:179,209,220,228` (`ip = request.client.host`, `_rate_limit_check(id_key, f"ip:{ip}")`); `docker-compose.yml:86` (`FORWARDED_ALLOW_IPS=172.16.31.20`, nginx only); `web/nginx.conf:99` (`X-Forwarded-For $proxy_add_x_forwarded_for`); `backend/app/main.py:176` (request-log `client`).
**What happens:** The production path is client → Traefik → nginx (frontend) → uvicorn. Traefik sets `X-Forwarded-For: <client>`. nginx appends its own peer, Traefik, so the header reaches the backend as `<client>, <traefik-ip>`. uvicorn 0.34 trusts only nginx and takes the right-most untrusted entry, which is **Traefik's IP for every request**. As a result:
- `ip:<traefik>` is one shared bucket. Any anonymous client that sends 30 wrong passwords in 5 minutes makes `/auth/login` return 429 for **every** user, including those with the correct password, because the check runs before bcrypt. Tokens last 15 minutes, there is no refresh endpoint, and the UI never sends `remember_device`, so the whole facility is locked out within 15 minutes. It can stay locked out for as long as the attacker keeps up about 6 requests per minute.
- Any successful login in the org clears the shared bucket (`_rate_limit_clear(f"ip:{ip}", …)`), so the IP limit also stops working as brute-force protection.
- The `login_failed` "ip" field and the request log's `client` field always record Traefik, which defeats their stated purpose as a forensic anchor.
**Evidence:** I ran uvicorn's own `_TrustedHosts('172.16.31.20').get_trusted_client_host('203.0.113.7, 172.18.0.5')` from the installed uvicorn 0.34.0 and it returned `172.18.0.5` for every client address. I read the nginx `location` for `/auth` and the Traefik labels on `frontend`; there are no published ports, so Traefik is the only ingress. I found no `set_real_ip_from` in nginx. I did not check production logs (rule 2); a single `docker logs` of `login_failed` would confirm it.
**Fix:** Pick one. Either add Traefik's `traefik_network` address or subnet to `FORWARDED_ALLOW_IPS`, or in nginx use `set_real_ip_from <traefik subnet>; real_ip_header X-Forwarded-For;` and send `X-Forwarded-For $remote_addr`. Separately, stop clearing the IP bucket on success, or key the clear to the account only.

### BC-02 [high] authz — Base USERs (and department-scoped managers) can read the org-wide weekly digest and AI weekly report through `GET /ai/pins`
**Where:** `backend/app/api/ai.py:147-158` (`FUNCTION_ROLES`), `:301-356` (`list_pins`, `restricted = [k for k in FUNCTION_ROLES …]`); `backend/scripts/weekly_snapshot.py:497-500` (`_replace_pin(… "weekly_snapshot" …)`, `(… "weekly_report" …)` with no `subject_user_id`); `web/gf/report-view.js:52-55,400` (the report view, open to every role, fetches `weekly_report`).
**What happens:** The `ai_pins` RLS policy opens subject-less pins to every org member. `list_pins` then filters out only the function keys that appear in `FUNCTION_ROLES`. The scheduler writes the org-wide pins under `weekly_snapshot` and `weekly_report`, and neither key is in `FUNCTION_ROLES`; only `next_week_plan` is. A `USER` calling `GET /ai/pins?function_key=weekly_snapshot`, or opening the Weekly report screen, gets the whole org's digest: every active task title with its status, owner and department, the overdue list with owners, stuck tasks, and declined assignments with who declined. RLS (`tasks_read`) and `reports.py` exist to hide exactly this from a USER. A department-scoped manager likewise gets every other department's work, which contradicts the scope rule in DEPARTMENT-MODEL-2026-09 ("AI context"). The code comment and test at `tests/test_ai.py:549-557` say the "weekly_report/next_week_plan" leak was fixed, but the test only covers `next_week_plan`.
**Evidence:** I read `list_pins`, the `FUNCTION_ROLES` keys, the `ai_pins` policy in `schema.tasks.sql:5600`, the pin writes in `weekly_snapshot.py`, `build_digest` (lines 122-205, which shows the digest content), and the `report-view.js` loader. `modules.js:18` gives the `report` view `roles: null`.
**Fix:** Build the restricted set from the pin keys, not the invoke keys: `weekly_snapshot`, `weekly_report` and `next_week_plan` become elevated-only when `subject_user_id IS NULL`. Either scope or hide the org-wide pins for department-scoped managers. Extend the test to `weekly_report` and `weekly_snapshot`.

### BC-03 [medium] authz/correctness — The task department-move guard ignores sub-departments
**Where:** `backend/app/api/tasks.py:711-729` (`delegable … == scope`, `src_ok = cur_dept == scope …`, `dst_ok = … == scope or delegable`).
**What happens:** `create_task` (`:422-457`) lets a Cultivation manager file tasks in Cultivation, Cloning or Nursery, because it uses the family. `update_task` still compares against the exact scope. So a CU_MGR who re-files a task from Cultivation to Cloning gets `403 "Managers may not move tasks outside their own department"`. That includes moving their **own** task, because `dst_ok` also requires `== scope`. Moving a Cloning task back to Cultivation fails `src_ok` unless the manager owns it, and a subtask under a Cloning parent is never "delegable". DEPARTMENT-MODEL-2026-09 says scope is "department and its descendants … in the by-id guard every task route calls". This path was missed.
**Evidence:** I traced `update_task` with scope = Cultivation and a task in Cultivation, patch `department_id` = Cloning: `src_ok` is True (cur == scope), `dst_ok` is False (Cloning ≠ scope, no parent), so it returns 403. `create_task` accepts the same department at `:424`.
**Fix:** Compute `fam = await dept_family(c, scope)` and use `cur_dept in fam`, `new in fam` and `pd in fam` in place of the three `== scope` tests.

### BC-04 [medium] contract/functional — A cross-department handoff cannot reach a department-scoped receiver
**Where:** `backend/app/api/collab.py:291-308` (ping goes only to `departments.head_user_id`), `:317-323` (`list_handoffs` → `_assert_scope_visible`); `backend/app/api/tasks.py:259-261` (`get_task` scope guard); `web/gf/task-extras.js:35-37,170-177` (the Accept/Reject buttons live only in the task detail).
**What happens:** `departments.head_user_id` is never written. No route, migration after the baseline, seed or one-off script sets it, so `propose_handoff` never notifies the receiving department. The receiving manager (for example PR_MGR for a QC task) also cannot open the task: `GET /tasks/{id}` and `GET /tasks/{id}/handoffs` both return 404 from `_assert_scope_visible`, because the task still sits in the source department. The Accept button therefore never renders for them. `resolve_handoff` deliberately lets the target side resolve without visibility (`:350-379`), but the UI gives that target side no way to reach it. In practice only org-wide roles who did not propose the handoff can accept one, and the "handoffs" scope surface in DEPARTMENT-MODEL does not work for its main actor.
**Evidence:** `grep head_user_id` over the app, scripts, alembic and docs finds only the baseline column and `collab.py`. `tests/test_collab.py:222` accepts only as ADMIN.
**Fix:** Notify the managers of `dept_family⁻¹(to_dept)`: the target department's DEPT_SCOPED managers and its ancestors' managers. Also either widen `_assert_scope_visible` or the handoff listing to include "open handoff addressed to my family", or add a "handoffs waiting for my department" list endpoint.

### BC-05 [medium] correctness/owner-model — Sub-departments fall through exact-match notification and reporting paths
**Where:** `backend/app/duescan.py:31-39,62` (`_dept_managers … department_id=$2`); `backend/app/api/documents.py:115-117,748-797` (per-department exact match, and a status board that lists every active department).
**What happens:** Cloning and Nursery have no manager of their own; the CU_MGR runs them (roles.py, DEPARTMENT-MODEL). Two consequences:
1. The daily scan's `overdue` escalation looks for managers whose `department_id` equals the task's, so an overdue Cloning or Nursery task escalates to **no manager**.
2. The weekly GMP document is exact-match by design, but the CU_MGR is forced to their own department (`_effective_dept_id`), so Cloning's and Nursery's records can only be compiled by an executive. `GET /reports/documents/status` lists both as `missing` every week, and their work appears in no manager-submitted record.
**Evidence:** I read `duescan.run_for_org` and `_dept_managers`, and checked `provision_test_accounts.py:47` ("Sub-departments get no accounts"). The documents behaviour is described as "deliberately unchanged" in DEPARTMENT-MODEL; the consequence for the status board is not mentioned there.
**Fix:** In duescan, resolve managers of the task's department **or any ancestor** (walk `parent_id` up). For documents, let a scoped manager compile descendants (`dept_id IN family`), or leave sub-departments off the status board and fold them into the parent's document. That is the owner's decision.

### BC-06 [medium] race/data-integrity — Waste-manifest and decon-release gates are check-then-act
**Where:** `backend/app/api/waste.py:344-356` (seal), `:371-385` (witness), `:397-412` (dispose), `:270,326` (add/delete line read the status without a lock); `backend/app/api/decon.py:418-446` (release), `:453-490` (fail), `:371-405` (swab result).
**What happens:** Each transition reads the row with a plain SELECT (`_manifest_or_404` / `_cycle_or_404`) and then runs `UPDATE … WHERE id=$n` with no status predicate and no `FOR UPDATE`. Line inserts and deletes do not lock the manifest row; an FK KEY SHARE lock does not conflict with the seal's NO KEY UPDATE. Under READ COMMITTED:
- `seal` concurrent with `delete_line` on a one-line draft produces a **sealed manifest with 0 lines**, breaking Gate 1.
- `add_line` concurrent with `seal` produces a line added after the seal, breaking Gate 2, with a `gross_weight_kg` that no longer covers it.
- Two concurrent `seal` calls leave the last writer in `weighed_by`, which is the field Gate 3's "witness ≠ weigher" check reads.
- `release_room` concurrent with `record_swab` (a new pending swab) or with re-patching a swab from negative to positive gives a **released room with a pending or positive swab**, the exact case the module says "no room is released on".
- `release` and `fail` racing each other both succeed, and the last writer's status wins.
**Evidence:** I read every UPDATE and confirmed none carries `AND status=…`. The lock modes are standard Postgres behaviour. I did not reproduce this (no pytest, per rule 3).
**Fix:** Take `SELECT … FOR UPDATE` on the manifest or cycle row in every mutating path, including `add_line`, `delete_line` and swab insert/result, which should lock the parent cycle. Also add `AND status=<expected>` to each transition UPDATE and return 409 on 0 rows.

### BC-07 [medium] data-integrity/dead-code — `PATCH /reports/documents/{id}` lets any elevated user rewrite the evidence of the "submitted record"
**Where:** `backend/app/api/documents.py:829-866` (`patch_document`, replaces the whole `content`); `web/gf/api.js:542` (`patchDocument`, which has no caller anywhere in `web/gf`).
**What happens:** The module's evidence rule is that the ribbon and metrics come only from real logged sessions and are never fabricated. `patch_document` accepts arbitrary JSON up to 5 MB and overwrites `tasks`, `ribbon`, `metrics` and `ai_sections`. The owner, or a department manager for their own department, can then lock it (`lock_document`), and the "immutable submitted record" contains invented tasks and hours. The UI only ever uses `patch_section`, which edits reviewer text and approvals. The whole-document route is unused and has no reason to exist.
**Evidence:** `grep patchDocument web/gf/*.js` finds only the api.js definition. I read `patch_document` and `lock_document`.
**Fix:** Delete the route and the api.js wrapper, or restrict it to reviewer-editable keys, as `patch_section` already does.

### BC-08 [medium] data-integrity — The audit-trail viewer drops rows at page boundaries (still open, from CODE-REVIEW-DEEP-2026-07 M7)
**Where:** `backend/app/api/audit.py:93-98,118` (`created_at < before`, `ORDER BY created_at DESC LIMIT n`); `web/gf/audit-view.js:88-115` (the cursor is the last row's `created_at`; the file's own "RESIDUAL RISK" comment describes this).
**What happens:** `audit_log.created_at` defaults to `now()`, which is constant for a whole transaction, so every row of one write shares a timestamp. For example, plant generation writes 50 rows per transaction (`cultivation.py:93,707`), and `update_task` plus the recurrence insert writes two. When a page of 100 ends inside such a group, the next page's strict `< before` skips the rest of the group permanently. An auditor paging through the trail never sees those rows. The July remediation list closes M1-M6 and M8-M9, not M7.
**Evidence:** I read the schema default (`schema.tasks.sql`, `audit_log.created_at timestamptz DEFAULT now()`), the keyset, and the frontend cursor.
**Fix:** Use a composite keyset per source, `(created_at, id) < ($before_ts, $before_id)`, return a cursor object, and merge the two chains on the pair.

### BC-09 [medium] duplicated-logic-drifted — The weekly snapshot and AI report use a different week membership from the live report and the locked document
**Where:** `backend/scripts/weekly_snapshot.py:339-355` (5-term activity predicate) versus `backend/app/api/weekwindow.py:133-167` (`activity_window_sql`, 8 terms).
**What happens:** `activity_window_sql` counts comments, assignments and acknowledgements, and rejected or cancelled handoffs. The snapshot's hand-copied predicate does not. A task whose only activity in the week was a comment, an assignment or an acknowledgement appears on `/reports/weekly` and in the compiled document, but is absent from the `weekly_snapshot` digest, the `weekly_report` AI narrative and the RAG upload. The weekwindow docstring says one definition exists "so the report screen and the locked document agree", and the snapshot is the copy it was meant to prevent (ARCHITECTURE-REVIEW-2026-07 §2.1).
**Evidence:** I diffed the two predicates by reading them.
**Fix:** Import `activity_window_sql` in `weekly_snapshot.gather`. It is a pure string builder with no app-state dependency. Alternatively, add a test that asserts the two predicates are identical.

### BC-10 [medium] contract — The decon cycle "fail" and biosecurity "resolve result" routes have no UI, so rooms and records get stuck
**Where:** `backend/app/api/decon.py:452-495` (`POST /decon/cycles/{id}/fail`); `backend/app/api/biosecurity.py:163-207` (`PATCH /decon/biosecurity/{id}/result`); `web/gf/api.js` (no wrapper for either); `web/gf/decon-view.js:65,331-346`.
**What happens:**
1. After a positive swab, a cycle in `awaiting_verification` cannot be released and cannot be failed from the UI. `create_cycle` returns 409 for any new cycle in the same room and campaign (`:204-211`), so the room is stuck in the app. `fail_cycle`'s own docstring says it exists to prevent exactly this.
2. The biosecurity form offers a `pending` result (contact plates, bioassay), but the board fetches only `open_only` (`fail`/`below_spec`). A pending check therefore **disappears from the UI once saved** and can never be resolved there, even though the backend added a PATCH route specifically so pending checks could be completed.
**Evidence:** `grep` of `web/gf` finds no call to `/fail` or `/biosecurity/…/result`, and I read decon-view.js lines 331-346 and 65. `api.js:294-297` itself notes that positive-controls and tool-log also have no UI.
**Fix:** Add a "Fail cycle (reason)" action beside Release for QA-tier roles. Include `pending` events in the biosecurity panel with an "Enter result" action that calls the PATCH route.

### BC-11 [medium] config — `CAPTURE_IMPORT_TOKEN` has no placeholder guard; `.env.example` ships `change-me` for an ADMIN-equivalent, internet-reachable credential
**Where:** `backend/app/api/capture.py:107-135`; `.env.example:77-78` (`CAPTURE_IMPORT_TOKEN=change-me`, `CAPTURE_IMPORT_USER=qcm.blani`, which `auth.py:318` describes as an ADMIN); `web/nginx.conf:93` (proxies `/capture`).
**What happens:** `config.py` refuses to boot with a placeholder or short `SECRET_KEY`, and its comment explains why ("A guard that only caught its own default would pass a deployer who copied .env.example"). The capture token has no equivalent guard. A deployment that copied `.env.example` accepts `Authorization: Bearer change-me` on `/capture/import` and acts as the ADMIN capture user. That user can import tasks for any owner, add `work_sessions` (overtime evidence) attributed to anyone, and overwrite title and status on any task matched by `external_ref`. **UNVERIFIED** whether production uses the placeholder; I did not contact production.
**Fix:** At startup, treat a token that is in a placeholder set or shorter than 32 characters as unset (the route falls back to normal auth), and log a warning, mirroring the SECRET_KEY guard.

### BC-12 [medium] owner-instructions — Production (PR_MGR) cannot record the destruction or decon of its own post-harvest areas
**Where:** `backend/app/api/waste.py:66` (`_RECORDERS = (ADMIN, *EXECUTIVE_ROLES, "CU_MGR")`); `backend/app/api/decon.py:45`; `backend/app/api/biosecurity.py:44`.
**What happens:** The owner's model (message 2026-09-05T17:44, DEPARTMENT-MODEL) is that "everything from harvest onward is production manager's job" and that the cultivation manager's work ends at the cut. The waste register offers `trim` and `packaging` waste types, but only CU_MGR among the managers can draft, seal or dispose a manifest. Dry-room decontamination and gowning checks are likewise CU_MGR and QA only. Production can read these records but cannot record its own destruction; the post-cut crew would need the cultivation manager to sign for it. DEPARTMENT-MODEL's "Still open" list mentions only the security manager's gap here.
**Evidence:** I read the three role tuples and checked them against DEPARTMENT-MODEL-2026-09 and the owner message.
**Fix:** Owner decision. The likely change is to add `PR_MGR` to the waste recorders (at least) and to decon cleaning for `dry` rooms, then update the UI role gates.

### BC-13 [low] correctness — Swallowed DB errors on the transaction connection silently roll back work that the API reports as successful
**Where:** `backend/app/api/tasks.py:779-796` (update_task), `:1140-1150` (workflow_transition); `backend/app/api/collab.py:118-149,204-211,226-233,256-264,305-313,408-416`.
**What happens:** `participants(c, …)` and `c.fetchrow(...)` run on the request's transaction without a savepoint, inside `try/except Exception: pass|log`. If one of them raises (a cancelled statement, a timeout), Postgres marks the transaction aborted. asyncpg then "commits" it **without raising**: the server answers ROLLBACK. The PATCH, the workflow sign-off or the comment is lost while the client receives 200/201 with the new state. `safe_emit` savepoints exactly to avoid this, but the wrappers around it do not. This is still open (CODE-REVIEW-2026-07-24 LOW: redundant try/except around `safe_emit`).
**Evidence:** Against the local test DB I ran a transaction with an INSERT, then a caught `SELECT 1/0`, then a normal context exit; asyncpg raised no exception.
**Fix:** Move `participants()` and the title lookups inside `safe_emit`'s savepoint (pass a callable), or wrap each block in `async with c.transaction():`.

### BC-14 [low] error-handling — Malformed UUIDs in request bodies still cause 500s
**Where:** `backend/app/api/tasks.py:466-488` (create: `department_id`, `week_id`, `batch_id` pre-checks run outside the `_FK_ERRORS` try), `:735-747` (update, same pattern); `backend/app/api/ai.py:331-332` (`/ai/pins?week_id=`).
**What happens:** `POST /tasks {"title":"x","department_id":"abc"}` from any org-wide caller or USER raises `asyncpg.DataError` in the existence check, which is outside the try, and returns 500. `GET /ai/pins?week_id=abc` also returns 500. This is the remainder of H7/H11.
**Evidence:** Against local Postgres, `fetchval('SELECT 1 FROM departments WHERE id=$1','abc')` raises `DataError: invalid input for query argument $1`.
**Fix:** Call `_uuid_or_422` on `department_id`, `parent_id`, `week_id` and `batch_id` in both handlers, and on `week_id` in `list_pins`.

### BC-15 [low] facility-clock — A decon cycle's `started_on` is the UTC date
**Where:** `backend/app/api/decon.py:212-215` (the INSERT omits `started_on`); `schema.tasks.sql:434` (`started_on date DEFAULT CURRENT_DATE`).
**What happens:** A cycle started between facility midnight and UTC midnight (00:00-01:59 in Skopje) records the previous day. The app bans `CURRENT_DATE` in code (`test_facility_clock.py`) but not in schema defaults. `biosecurity.py` passes the site date explicitly; decon does not.
**Evidence:** I read the INSERT and the column default. The DB zone is UTC per the `worktime.py:28-34` note.
**Fix:** Insert `started_on = (now() AT TIME ZONE <site>)::date`, using `SITE_TODAY_SQL`.

### BC-16 [low] duplicated-logic-drifted — The locked weekly document carries a different week number from the live report
**Where:** `backend/app/api/documents.py:535-548` (`_period`: `start.isocalendar()[1]`, `start.year`) versus `backend/app/api/reports.py:272-279` (labels from the window's Monday with that Monday's ISO year).
**What happens:** For the window Fri 2026-09-25 to Thu 10-01, the document reads "W39 2026" and `/reports/weekly` reads "W40 2026". For Fri 2027-01-01, the document reads "W53 2027", a week that does not exist, and the report reads "W1 2027".
**Evidence:** I ran `_period(fri_thu(...))` directly for both dates.
**Fix:** Share one label function in `weekwindow.py` that uses Monday = fri+3 and its ISO year and week.

### BC-17 [low] authz — Minor scope leaks: @mentions, the activity feed, and the dependency advisor
**Where:** `backend/app/api/collab.py:136-141`; `backend/app/api/notifications.py:135-146,182-192`; `backend/app/api/ai.py:418-445` (`_family_context`).
**What happens:**
- **Mentions:** the filter assumes "same-department staff" can see the task. `tasks_read` gives USERs only their own or assigned tasks, so an @mentioned department USER receives the title and an 80-character comment preview for a task that returns 404 to them. The comparison is also exact-department, not family.
- **Activity feed:** `/activity` and `/digest` show a department's USERs every event in the department, including comment previews and workflow remarks, for tasks they cannot open. That contradicts the docstring's claim that it "mirrors the task board".
- **Dependency advisor:** `dependency_advisor` checks scope on the root task only. A manager who sees a task only because they are assigned to it receives its parent and all siblings in the prompt context.
**Evidence:** I read `tasks_read` (`schema.tasks.sql:6341`) and compared it with each filter.
**Fix:** For mentions, keep elevated users, participants, and users that pass `tasks_read`. Filter USER activity by task visibility. Apply `_scope_clause` rows in `_family_context`.

### BC-18 [low] info-leak/robustness — Unauthenticated error text and a 500 on a non-ASCII header
**Where:** `backend/app/main.py:241-246`; `backend/app/api/ai.py:215`; `backend/app/api/capture.py:129`.
**What happens:**
- `/health/ready` is public through nginx (`location … |health`) and returns `f"{type(e).__name__}: {e}"` from asyncpg, which includes DB host or IP, role name and auth errors.
- `/ai/functions` returns the internal `letta_base_url` to any user.
- `hmac.compare_digest(str, str)` raises TypeError on a non-ASCII `Authorization` header, which returns 500 whenever `CAPTURE_IMPORT_TOKEN` is set.
**Evidence:** I verified the `compare_digest` TypeError with python3 and read the nginx route list.
**Fix:** Report `"error"` only (log the detail), drop `letta_base_url`, and compare bytes (`.encode()`) after an ASCII check.

### BC-19 [low] dead-code — Unreachable routes and settings
**Where:**
- `backend/app/api/qms.py:32-150`: the legacy qms-api proxy, 7 routes (`/qms/documents`, `/stats`, `/hierarchy`, `/families`, `/documents/{code}`, `/rag-query`, `/download/{path}`). qms-api is "retired platform-wide" (`web/gf/qmsregistry-view.js:1-15`, `api.js:322`) and there are no callers.
- `config.py:57-58` `letta_mcp_url` and `qdrant_url` (0 readers), plus `qms_api_url` and `qms_api_key`.
- `GET /tasks/tree` (`tasks.py:229`): `taskTree` is never called.
- `remember_device` in `LoginReq` and `remember_device_expire_days`: `api.js:146` never sends it.
- `PATCH /reports/documents/{id}`, covered in BC-07.
**Fix:** Delete them, or record why each is kept, as `api.js` already does for decon positive-controls and tool-log.

### BC-20 [low] DoS hygiene — Unbounded inputs reach the LLM and WeasyPrint
**Where:** `backend/app/api/intake.py:148-150` (`BilingualReq.title/description`, no `max_length`; any USER); `backend/app/api/documents.py:1561-1563` (`RangeExportReq.content: dict` is unbounded and rendered by WeasyPrint).
**What happens:** A 30 MB body (below the 32 MB middleware cap) is forwarded to Letta in full, or laid out by WeasyPrint in a worker thread. `/ai/{fn}` was capped at 32 KB in the July P2 work; these siblings were not.
**Fix:** Apply `Field(max_length=…)` caps to the intake fields, and apply the 5 MB serialized cap from `PatchReq` to `RangeExportReq.content`.

### BC-21 [low] latent-authz — The users-DB RLS policies are broader than the API (still open, APP-REVIEW-2026-07-14 L7)
**Where:** `schema.users.sql:331` (`profiles_manage`: any elevated role has full write on the org's profiles); `:345` (`profiles_self FOR UPDATE`, all columns, including `role`).
**What happens:** Nothing is exploitable today, because every profile write goes through the admin pool behind `_can_manage`. But the database would let a QC_MGR session update any profile, and let any user update their own `role`, the moment one `rls_users(user)` UPDATE is added. RLS is described as the real security boundary, and here it is not one.
**Fix:** Restrict `profiles_manage` to ADMIN and managers, or drop it (the admin pool does the writes), and make `profiles_self` column-safe (a trigger or column-level grants).

### BC-22 [low] latent cross-org — Audit rows written without identity GUCs are readable by every org
**Where:** users/tasks `fn_audit_row` (`org_id := current_setting('app.org_id')`); `audit_read` policy `… OR org_id IS NULL`; the writers are `scripts/weekly_snapshot.py:476-527` (raw admin connections, full report bodies in `new_values`) and `backend/app/demo_org.py:257,311-320,376`.
**What happens:** These writes produce audit rows with `org_id NULL` and `user_id NULL`. Every org's org-wide elevated users can read them through `GET /audit`. Today there is one real org, so there is no leak yet. With a second tenant, or the demo org on the same DB, one org's weekly AI reports and profile rows become visible to the other.
**Fix:** Set the GUCs on scheduler and demo connections (`set_config('app.org_id', …)`), or have the trigger take `org_id` from the row when a table has one.

### BC-23 [low] config/owner-risk — There is no production floor on the password policy, and weak credentials were requested on the production system (UNVERIFIED)
**Where:** `backend/app/config.py:42-44` (`password_min_length`, `access_token_expire_minutes`, `remember_device_expire_days` have no bounds); `auth.py:260`.
**What happens:** The owner's message 2026-09-04T14:51 asked for the password rules to be relaxed "because this is not a production version", with username-equals-password trial accounts (see the credential in message 2026-09-04T14:50), and message 2026-09-04T15:05 granted permission to "add the line" (commit 03222f7 made the client defer to `PASSWORD_MIN_LENGTH`). The credential in message 2026-09-14T10:09 is a weak ADMIN password requested "for a short while". This stack **is** production. If those changes were applied, manager and ADMIN accounts with guessable passwords are on the internet-facing login, and with BC-01 the IP limit gives no protection. I could not verify the live `.env` or accounts (rule 2).
**Fix:** Add a production floor (for example, refuse `PASSWORD_MIN_LENGTH < 12` unless `ENVIRONMENT=development`), then ask the owner to rotate or purge the trial and admin credentials.

### BC-24 [low] design — Work sessions are classified entirely by their start hour, with no upper bound on hours
**Where:** `backend/app/worktime.py:61-69` (`classify(started_at)`); `backend/app/api/tasks.py:825` (`hours` is only `gt=0`); `reports.py:160-172` (`hours_by_person`).
**What happens:** A 07:30-16:00 weekday shift counts as 8.5 h of **overtime**. A 16:00-24:00 shift counts as 8 h of **regular** time. A typo of `80` instead of `8.0` is accepted as one 80-hour session, all in one bucket. This feeds the Thursday report's off-hours evidence.
**Fix:** Split each session across bucket boundaries in local time, and cap `hours` (for example `le=24`) or require `ended_at`.

### BC-25 [low] data-integrity — Decon child records accept a `cycle_id` from a different room
**Where:** `backend/app/api/decon.py:352-358` (swab), `:302-307` (bleach), `:573-576` (tool log): `_cycle_or_404` is called, but `cycle.room_id` is never compared with `body.room_id`.
**What happens:** A swab posted with room A and room B's cycle id is excluded from both release gates (`_swab_summary` filters on room **and** cycle), so a positive swab can be orphaned. The UI always sends a matching pair, so this is API-only.
**Fix:** Return 422 when `cyc["room_id"] != body.room_id`.

### BC-26 [low] race — Duplicate-code pre-checks return 500 when two requests race
**Where:** `waste.py:241-246`, `decon.py:203-211,355-360,531-536`: SELECT then INSERT, against `waste_manifests_org_id_manifest_code_key`, `decon_swabs_org_id_swab_code_key`, `decon_positive_controls_…_key` and `decon_room_cycles_open_idx`.
**What happens:** Two simultaneous creates with the same code: one wins, and the other gets an unmapped `UniqueViolationError`, which is a 500. `main.py:41-50` maps only the two QC sample indexes.
**Fix:** Catch `UniqueViolationError` around the INSERT and return the same 409 as the pre-check.

### BC-27 [low] latent (demo) — The anonymous demo ADMIN can bind any agent on the shared Letta instance (CODE-REVIEW-DEEP M3, partially fixed)
**Where:** `backend/app/api/demo.py:57-62` (the token is the cast's ADMIN); `backend/app/api/ai.py:232-283` (`list_agents` and `set_binding` check only that the id exists on the instance).
**What happens:** Wherever `DEMO_ENABLED=true`, an internet visitor becomes ADMIN of the demo org. They can list every Letta agent and bind one to `corpus_qa`, then query another tenant's agent and its archival memory. The `demo_org.py` docstring claims visitors "can never invoke real Letta agents". Production has the demo off, and `wwf_mass` appears decommissioned, so this is latent.
**Fix:** Refuse `/ai/agents` and `/ai/bindings` writes for the demo org, or give the demo cast a non-ADMIN top role.

---

## Checked and found sound (no finding)
- **Org isolation:** every `*_admin_pool()` query in scope filters `org_id` or is an auth lookup by id. `_actor_family` and `dept_family` cannot cross orgs, because `create_department` validates `parent_id` under RLS. No `*_user_pool()` is used without GUCs.
- **SQL construction:** f-strings interpolate only fixed column names, placeholders, the config TZ literal (quote-doubled) or a constant table tuple (demo wipe).
- **JWT:** the algorithm is pinned, the claims are re-read from the DB on every request, `pwv` invalidates tokens on password change and reset, and inactive or deleted accounts are refused. bcrypt input is bounded to 72 bytes and runs off the event loop. Login timing is equal for unknown users.
- **Background jobs:** the API process runs no background tasks, so there is no double-fire across workers. The scheduler is a single container with a heartbeat and per-org missed-run recovery. duescan is idempotent per day through its `events` check. Every tick is wrapped in try/except and logged.
- **Grants:** default privileges cover new tables. Migrations 0065-0068 enable RLS and add audit triggers. `is_elevated()` matches `roles.ELEVATED_ROLES` in both DBs, and `IR_MGR` is present in users 0012 and tasks 0064.
- **Items confirmed fixed from earlier reviews:** the CODE-REVIEW-2026-07-28 capture department bypass (H2), the `create_user` blanket 409, the forced-change OTP reuse, the `notify.emit` fan-out rollback, the `CapturePayload` bounds; the 07-24 intake role gate (H10), workflow TOCTOU (H8), the capture priority downgrade (H9), `patch_section` locking, duescan's `LIKE '%_MGR'`, and the dead `password_reset_codes` table.
