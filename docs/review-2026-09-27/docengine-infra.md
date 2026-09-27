# Review — DocEngine, connector, infrastructure (HEAD 807d60f)

## Summary
DocEngine is a single-worker FastAPI service that drives a Letta `gf_*` fleet through a long sequential pipeline (draft → per-section reg-check → bilingual/structure gates → §6A LLM audit with a repair loop → `pp_verify` → registry row). Job state lives in Postgres. The API-key gate is constant-time and fails closed, and the backend proxy's path guard is sound. The gates hold on the workflow and revise paths.
The weak points are around those gates. The questionnaire gate can be bypassed with unknown keys. The §6A verdict parser is looser than the docs say. `/build` and `/revise` register documents whose registry metadata, lineage and content floor are not controlled. Stale-job recovery misses the redeploy case. Persistent agents are shared across concurrent jobs.
Infrastructure is careful in its details. `deploy.yml` in particular has good guards, but its smoke phase cannot work in the container it runs in. The single self-hosted runner sits on the production host with the docker socket, which makes any pushed PR root on production. DocEngine itself has no version-controlled compose entry, no deploy path, no backup of its output volume and no monitoring.

Severity counts: high 2 · medium 12 · low 9.

---

### DI-01 [high] correctness/ops — `deploy.yml` smoke phase cannot pass inside kvm4-runner: every dispatched deploy ends red *after* images are swapped and tells the operator to roll back
**Where:** `.github/workflows/deploy.yml:1102-1110` (`http_get`: curl → wget → `die`), used at `:1122` (smoke loop) and `:1225` (status). The failure message is at `:1139`.
**What happens:** `deploy.sh` runs through `/shell`, which executes inside the kvm4-runner container (`ops/README.md:167-172`, `ops/agent/rsh.py:10-12`). CLAUDE.md ("Gotchas", corrected 2026-09-06) records that the container is `python:3.12-slim` and has neither curl nor wget. `http_get` therefore dies inside `$(…)`. Its stderr is discarded (`2>/dev/null`) and `|| true` turns the result into an empty body. All 24 attempts log `<empty response>`. The phase then dies with "did not report ready … Images are already swapped: use the rollback recipe". This happens after migrate and swap have already changed production. So a healthy deploy reads as a failed one, and the recipe tells the operator to revert it. The container-tag assertion after the loop never runs. `phase_status` prints `health: <unreachable>`. A second risk: the probe targets the public hostname from inside the host, and `ops/watchdog.sh:418-426` documents that this can fail without NAT hairpinning.
**Evidence:** Read `deploy.sh` end to end. Cross-checked the execution environment in CLAUDE.md, `ops/README.md` and `rsh.py`. `ops/watchdog.sh:341-356` already learned this lesson ("curl is NOT guaranteed … rc=127") and falls back to python3; `deploy.sh` did not. No record in `docs/` of `deploy.yml` completing since the container change.
**Fix:** Replace `http_get` with the python3 urllib probe `watchdog.sh` uses (`python3 -c 'import urllib.request…'`). Keep the "neither available" branch as a hard `die` that is not swallowed by `|| true`: test for the tool once, before the loop. Optionally fall back to probing `http://127.0.0.1:8000/health/ready` via `docker exec $BACKEND_CT python -c …`, labelled as a fallback.

### DI-02 [high] security/design — The production host's docker socket is reachable by any `pull_request` workflow, so anyone who can push a branch is root on production
**Where:** `.github/workflows/ci.yml:3-5` (`on: pull_request`, every job `runs-on: self-hosted`); `ops/gh-runner/compose.yaml:13-18` (`network_mode: host`, `/var/run/docker.sock` mounted, docker GID added).
**What happens:** For `pull_request`, GitHub runs the workflow file from the PR's own merge ref. A branch that edits `ci.yml` (or adds a workflow) and opens a PR runs arbitrary steps on `gh-runner-wwf`. From there `docker run -v /:/host …` or `docker exec wwf-db-tasks psql …` gives full control of production data, `.env` files and every other stack on the box. Same-repo PRs also receive repository secrets (`KVM4_RUNNER_TOKEN`, etc.) if the edited workflow references them.
This defeats the boundary CLAUDE.md relies on: "Actions write is owner-only; the agent can only watch a run". Agent sessions routinely push branches and open PRs (#53/#55 in `docs/HANDOFF.md`). It also weakens the deploy gate: `deploy.yml`'s "CI green on the exact commit" only proves that the `ci.yml` *at that commit* passed. A commit that neuters `ci.yml` is green by construction.
**Evidence:** Read both files. The runner is the only runner (HANDOFF). `images` job at `ci.yml:453` already runs a host-wide `docker image prune -f` from PR context (see DI-20). That proves PR jobs act on the production daemon.
**Fix:** Pick one. (a) Move CI to a runner that does not share the production daemon: a separate VM, or rootless docker/sysbox. (b) Require approval for all outside-collaborator/bot PR runs, and gate PR workflows behind an environment with required reviewers. Also make `deploy.yml` verify that the `ci.yml` blob at the deployed SHA equals the one on the default branch.

### DI-03 [medium] security — Pre-approved `gh_api.py` lets any session merge PRs, force-move refs, rewrite files and change repo settings with the owner's PAT; the PAT also travels inside the `/shell` command string
**Where:** `ops/agent/gh_api.py:118-119, 153-162` (only method ∉ {DELETE} and path-prefix checks), `:179-181` (token base64-encoded into `cmd`). Allow rule `Bash(python3 ops/agent/gh_api.py *)` per CLAUDE.md "Agent helpers".
**What happens:** The helper is described as "deliberately narrow", but it only refuses DELETE. All of these pass without per-call classifier review:
- `PUT …/pulls/52/merge`, which overrides the owner's "Owner merges it" decision in HANDOFF
- `PATCH …/git/refs/heads/<default> {"sha":…, "force":true}`, which destroys history in effect
- `PUT …/contents/<path>`, a direct commit to the default branch that bypasses review
- `PUT …/collaborators/<user>`, `PUT …/branches/<b>/protection`, `PUT …/actions/secrets/<n>`

The PAT's own scopes are the only limit (UNVERIFIED which scopes it has). Separately, the token is placed base64-encoded in the `/shell` `cmd`. `deploy.yml:1279-1283` says the kvm4-runner keeps a "/shell audit trail" of command strings, so the PAT is written to disk on the host. That contradicts the docstring's "never written to disk there". UNVERIFIED because `runner.py` is not in git.
**Evidence:** Read the path/method checks. Traced how the body is built.
**Fix:** Replace the prefix check with an explicit allowlist of (method, path-regex) pairs for the needed operations: runs list/rerun, workflow dispatch, runners list. Pass the token through stdin (`/shell` with a heredoc read by `sys.stdin`) or an env file that is shredded afterwards, never in `cmd`.

### DI-04 [medium] correctness — The stale-job reaper cannot reap the jobs a redeploy kills; they stay `running` forever (still open from CODE-REVIEW-2026-07-28, "No stale-job reaper")
**Where:** `docengine/app/db.py:107-126` (`STALE_JOB_MINUTES = 60`, `updated_at < now() - 60 min`); only caller `docengine/app/main.py:49-55` (lifespan, startup only).
**What happens:** Suppose a job is at stage `regulatory-check 4.0` (last `job_update` 2 min ago) when `docker compose up -d --no-deps docengine` recreates the container. The old process closes the pool at shutdown, so the task's next `job_update` raises and the row stays `running`. The new process runs the reaper at startup, but the row is only minutes old, so it is not reaped. Nothing else ever sweeps: there is no lease, no periodic task and no check on read. The row stays `running` until some later restart happens ≥60 min afterwards. The UI gives up after ~40 min ("reopen it to check again", `web/gf/qmsstudio-view.js:110,120-123`), and reopening shows `running` again. The code comment at `main.py:46-48` names redeploy as the case this exists for.
**Evidence:** Read `db.reap_stale_jobs`, the lifespan, and `grep -rn reap_stale` (tests and lifespan only).
**Fix:** Stamp each job with the worker's boot id (`payload.worker` or a column). At startup, fail every `queued/running` job whose boot id ≠ the current one. With `--workers 1` this is exact. Keep the age-based sweep as a periodic background task every 5 min for hung workers.

### DI-05 [medium] correctness/contract — The "pre-populated answers only" gate is bypassed by any unknown answer key; free text reaches every authoring prompt as a questionnaire answer
**Where:** `docengine/app/questionnaires.py:133-164` (`validate_answers` skips keys that are not questions, `:150`); `docengine/app/pipeline.py:445-446` (`_brief` renders every `answers` item); `main.py:213-231` claims "every value the caller supplied must be a defined option — never free text".
**What happens:** `POST /qms/studio/workflows {"questionnaire":"sop_qc","answers":{"focus":"Potency","acceptance_limit_override":"THC 50 % (per QP decision)"}, …}` passes validation. The brief sent to every section author, the RACI specialist and every repair prompt then contains `- acceptance_limit_override: THC 50 % (per QP decision)`, formatted exactly like a validated answer. This defeats DOCENGINE-CANON §5 ("user selects, never types free regulation text") and is a direct prompt-injection channel into verbatim authors.
**Evidence:** Ran `validate_answers` + `_brief` with that payload under `/tmp/wwf-venv`: no exception, and the free-text line is present in the brief.
**Fix:** In `validate_answers`, reject any key that is not a question of that questionnaire (`InvalidAnswer(key, "unknown question")`). Additionally, have `_brief` iterate the questionnaire's question keys rather than `answers.items()`.

### DI-06 [medium] data-integrity — `/build` registers a "verified" document whose registry code, title and version need not match the document, with no §6A, no per-section gates, a caller-controlled bilingual switch and no attribution
**Where:** `docengine/app/main.py:409-435`; `docengine/app/builder.py:142-148`; `backend/app/api/qms.py:251-259`; UI `web/gf/qmsstudio-view.js:193-196`.
**What happens:**
1. The printed HEADERDATA comes from the caller's markdown, but the registry row takes `code/title_mk/title_en/version` from `body.meta`, with defaults `''`/`'1.0'`. The Studio UI sends only `{markdown, out_name, meta:{code}}`. So every UI direct build is registered with empty titles and version `1.0`, whatever the document prints (for example `version: 3.2`), and with whatever code the user typed.
2. The markdown is checked only by `pp_verify`. That skips the §6A audit, the per-section bilingual gate and the grid-overflow gate the workflow path enforces. Any line `bilingual: no` anywhere in the markdown (`builder.py:146`, `re.M`, not limited to HEADERDATA) turns off `--require-bilingual`.
3. `docengine.documents` has no `created_by`, and `studio_build` writes no `audit_log` event. The registered controlled document is not attributable to anyone.
**Evidence:** Read the handler, the builder regexes and the UI request body.
**Fix:** Parse HEADERDATA once (reuse `builder._strip_headerdata`'s scan) and take the registry `code/version/titles/doctype` from it. Reject `meta` that disagrees. Read `bilingual:` only inside HEADERDATA. Add `created_by` + `source` (`workflow|revise|build`) to `documents`, and have the backend stamp `requested_by` and emit an audit event. Mark `/build` rows as "unaudited" in the registry and UI.

### DI-07 [medium] data-integrity/canon — Revisions register a second document with the same code+version, no link to the source, and no content floor against the prior version (contradicts canon D5)
**Where:** `docengine/app/pipeline.py:1195-1226` (`run_revision` registers with the source's unchanged `meta`); schema `docengine/app/db.py:30-42` (no parent/lineage column); canon `docs/DOCENGINE-CANON-2026-07.md:129-131` (D5: revisions *regenerated* "with the full prior version as context (≥100 % content — §5A), never row-patched").
**What happens:** A "tighten" or "simplify" preset on SOP-X v1.0 produces a second registry row `SOP-X / 1.0` with different content. `/documents` lists both with nothing marking one as a revision of the other (`source_document_id` lives only in the job result). §5A fidelity compares the new .docx with the *revised* markdown, not with the prior version, so content removal passes. The revise path also runs no `gf_reg_checker`. A citation added by the `add_citation` preset is judged only by the auditor, whose persona says to reject "any clause reference that the regulatory findings do not support", and it receives no findings on this path. The same code/version with different bytes is a document-control defect in a GMP registry.
**Evidence:** Read `run_revision`, the `documents` DDL, the presets and the canon.
**Fix:** Add `parent_document_id` and `kind` to `documents`. Require either a version bump on revise or a draft status (`version` suffixed `-draft.N`) until a human approves. Run `builder`'s §5A with the *source* markdown as the floor (or report a signed delta). Run the reg-check on changed sections.

### DI-08 [medium] concurrency — Every job and every chat question re-runs a mutating fleet reconcile that resets message buffers of persistent agents another job may be using mid-turn
**Where:** `docengine/app/fleet.py:690, 717-722` (`stale_buffer = want_autoclear and len(message_ids) > 1` → `reset_messages`); called via `ensure_fleet_ctx` from `pipeline.py:794, 1116` and `main.py:312` (chat). Section drafting and the §6A audit use the persistent `gf_sop_author` / `gf_raci_specialist` / `gf_qa_auditor` directly (`pipeline.py:801-811, 931-948`), not clones.
**What happens:** Job B is inside a multi-step turn on `gf_qa_auditor` (tool call, then answer), so its `message_ids` holds more than one entry. Job A starts, or anyone asks a chat question, and `_reconcile_config` sees a "stale buffer" and resets the auditor's messages under B's in-flight turn. Two concurrent workflows also send to the same persistent author at once. Nothing serialises per agent (no lock in `docengine/app`). Whether Letta then drops B's context or leaks A's prompt into B is UNVERIFIED, but the race exists in this code. It lands on the verbatim authors, whose output goes straight into a controlled document.
**Evidence:** Read `_reconcile_config`, `ensure_fleet_ctx`, and the three call sites. `grep Lock|Semaphore docengine/app` finds only the build lock.
**Fix:** Put an `asyncio.Lock` per persistent agent name around `send_message` (a single worker makes this sufficient). Run `ensure_fleet_ctx` at most once per N minutes under a global lock instead of per job/chat. Or drive section authors and the auditor through `spawn_ephemeral` clones as the reg-checker already is.

### DI-09 [medium] security — DocEngine connects to the tasks DB as `app_admin` (BYPASSRLS, DML on every table) although it only needs its own schema
**Where:** `docs/DEPLOY.md:707-712` ("`GRANT CREATE ON DATABASE wwf_tasks TO app_admin`" for DocEngine), `:319`; `docengine/app/db.py:48-54` (creates schema/tables at startup, hence the CREATE grant).
**What happens:** The service with the largest untrusted-input surface (LLM output, retrieved documents, author markdown) holds a role that can read and modify every org's task, QC-LIMS and audit rows regardless of RLS. A bug or compromise in DocEngine or its dependencies is a full tasks-DB compromise. Today's SQL is parameterised, so this is defence in depth, not an open hole.
**Evidence:** Deploy docs; `demo_org.py` docstring confirms `app_admin` holds S/I/U/D on all tables.
**Fix:** Create a `docengine` login role that owns only schema `docengine` (no BYPASSRLS, no grants on `public`/`app`), create the schema once as superuser, and point `DOCENGINE_DATABASE_URL` at it.

### DI-10 [medium] data-integrity/ops — Produced controlled documents and released COQ artefacts live only in an unbacked-up volume; the offsite copy is down and nothing monitors backup freshness
**Where:** `docs/BACKUP.md:9-17` (scope excludes "Docker volumes for any other service"); `docengine_out` volume (`docs/DEPLOY.md:332`); COQ build stores only the id (`backend/app/api/qc/coq_docx.py:552-567`, `coq_aggregation.py:726-740`); `backend/scripts/offsite_backup.sh:33`; `ops/watchdog.sh` checks (`:205-520`, no backup check); `docs/HANDOFF.md` ("Offsite backups are not running").
**What happens:**
1. Host or volume loss restores `docengine.documents` rows from the `wwf_tasks` dump, but every `.docx` they point to is gone. Downloads answer 410, including every released certificate's COQ artefact.
2. `wwf-backup-offsite` has not run since the 2026-09-19 VM migration. BACKUP.md still describes it as active, and neither watchdog half checks the age of the newest local dump or offsite copy. The only freshness check is a warning in the nightly rehearsal (>48 h).
3. `rclone delete --min-age 60d` runs unconditionally every cycle. If dumps stop (db-backup wedged) while rclone works, the offsite set ages to empty in 60 days. The local rotation, by contrast, is guarded by `ok=1`.
4. The restore procedure stops backend + scheduler but not DocEngine, which writes to `wwf_tasks`.
**Evidence:** Read the scripts, BACKUP.md and HANDOFF. Traced the COQ path (only `document_id` is persisted in the backend DB).
**Fix:** Add `docengine_out` to the backup (tar into `/backups` in `db_backup.sh`, or have DocEngine store the verified bytes in Postgres). Add a `backup_fresh` watchdog check on the newest dump pair (FAIL > 30 h) and on `rclone lsl` age. Skip `rclone delete` unless the newest local dump is under 30 h old. Add DocEngine to BACKUP.md step 1.

### DI-11 [medium] ops/drift — DocEngine has no version-controlled compose entry, no deploy path, no healthcheck and no monitoring
**Where:** `docker-compose.yml:1-39, 42-223` (header "mirrors what runs on KVM4"; no `docengine` service, no `docengine_out` volume); `ci.yml:440-441` ("docengine and connector are both DEPLOYED services (docker-compose.yml)"); `deploy.yml:70-75` (scopes: frontend / backend+scheduler / full); `docengine/Dockerfile:26-40` (3.5 h crash loop after the 2026-09-07 reboot); `ops/watchdog.sh` (no docengine check).
**What happens:** DocEngine's env, restart policy, limits and network exist only in `/opt/stacks/wwf_app/compose.yaml` on the host. CI's `compose` job validates a file that is not what runs. Every DocEngine release is an ad-hoc `/shell` session with no CI gate. `deploy.yml` cannot ship it, which is the class of mistake that broke the Studio chat UI for a day (CLAUDE.md, 2026-09-07). The 3.5 h crash loop served nothing, and no check noticed.
**Evidence:** `grep -n docengine docker-compose.yml deploy.yml ops/` shows none.
**Fix:** Add the `docengine` service (image tag, `docengine.env`, `docengine_out`, `restart: unless-stopped`, `mem_limit`, a healthcheck on `/health` that requires `db:true`) to `docker-compose.yml`. Add a `docengine` scope to `deploy.yml` (build from `docengine/`, grep-verify, `up -d --no-deps`, probe `/health`). Add a `docengine_ready` check to `watchdog.sh`.

### DI-12 [medium] contract/timeout — Studio chat is cut off at 150 s by the backend while one DocEngine turn is budgeted at 900 s; every question also runs a full fleet reconcile, and a timeout surfaces as "DocEngine unavailable"
**Where:** `backend/app/api/qms.py:232` (`timeout=150.0`); `web/nginx.conf:75-83` (180 s); `web/gf/api.js:36` (190 s); `docengine/app/main.py:310-333` (`ensure_fleet_ctx` + spawn + `send_message`); `docengine/app/config.py:36-48` (a single turn over a whole annex exceeded 300 s on Kimi K2.6); `backend/app/docengine.py:57-61` (any `httpx.HTTPError` → 503 `DocEngine unavailable`).
**What happens:** A chat question sends the whole document (`_section_context`) to a reasoning model. Before that it runs `ensure_fleet_ctx`: about 40 sequential Letta/RAGflow calls, including block and config writes. Whenever that exceeds 150 s, the backend returns 503 "DocEngine unavailable". Meanwhile DocEngine keeps working, finishes, and throws the answer away. The error misreports a slow answer as an outage. UNVERIFIED: typical chat latency in production (no timings recorded).
**Evidence:** Traced the timeout chain across the four hops. Read the chat handler.
**Fix:** Make chat asynchronous like `/revise`: create a job, return its id, and poll. Or at least map `httpx.TimeoutException` to 504 "DocEngine is still answering" and reuse a cached `FleetContext` instead of reconciling on every question.

### DI-13 [medium] security — The DocEngine registry is not org-scoped; with the public demo enabled, an anonymous visitor becomes a DocEngine author on the real fleet and registry
**Where:** `docengine/app/db.py:17-42` (no `org_id` on jobs/documents); `backend/app/api/qms.py:44-49, 162-169` (role-only gates); `backend/app/api/demo.py:52-72` (anonymous `/demo/start` mints an `ADMIN` token when `DEMO_ENABLED`); `backend/app/demo_org.py:18-19` ("anonymous visitors can never invoke real Letta agents").
**What happens:** Every elevated user of every org lists and downloads every org's SOPs and COQ artefacts via `/qms/studio/documents`. With `DEMO_ENABLED=true`, an anonymous visitor's demo ADMIN passes `_require_author`. That visitor can read the real registry, start workflows that spend LLM credit on the production `gf_*` fleet, and `/studio/build` arbitrary "verified" documents into the real registry. This contradicts the demo module's own guarantee, because DocEngine does not go through `ai_agent_bindings`. Latent while there is one real org and the demo is off (default `False`, production value UNVERIFIED).
**Evidence:** Read the schema, proxy gates and the demo token minting.
**Fix:** Pass `org_id` from the backend on every DocEngine call and filter by it in DocEngine (column + WHERE). Refuse `/qms/studio/*` writes for the demo org in `_require_author`.

### DI-14 [medium] security/design — Prompt-injection path from retrieved or authored text to a registered controlled document has no human stop
**Where:** `docengine/agents/ragflow_search.py:178-186` (raw passage text returned to the model); verbatim authors `pipeline.py:801-815`; reg findings folded into the auditor prompt with "use your own judgement" (`pipeline.py:347-351, 929-948`); `persona` block agent-writable (`fleet.py:41-52`, reconciled only at the next job); registration immediately on PASS (`pipeline.py:983-1019`).
**What happens:** A passage in `DB3_PP_CURRENT_unified`/`DB01_REG`, or a crafted revise instruction, can steer:
- an author whose reply is spliced verbatim into the document
- the reg-checker's text, which the auditor is told to weigh
- the author's writable persona for the rest of that job (and for concurrent jobs, DI-08)

Only LLM judges stand between that and a registered "PASS" document. The auditor's verdict parser is permissive (DI-15). The mitigations are real but all instruction-level: the mission block's "content is data", read-only governance blocks, and the tool-side dataset allowlist. The human-review gate exists only as a design (`docs/DOCENGINE-CANVAS-DESIGN-2026-09.md`).
**Evidence:** Read the tool, the prompts and the fleet block model.
**Fix:** Until the canvas design ships, register pipeline output as `status='draft'` and require a named QA/QP approval before `/download`. Wrap retrieved passages in explicit data delimiters in the tool output (`<<<RETRIEVED …>>>`). Make `persona` read-only for the three verbatim authors.

### DI-15 [low] correctness — §6A verdict parsing is fail-open for some phrasings, and the persona/test describe a stricter parser than the code
**Where:** `docengine/app/pipeline.py:293, 354-367`; `docengine/agents/fleet.yaml:697-702`; `docengine/tests/test_fleet.py:366-371`.
**What happens:** Only PASS/FIX tokens that directly follow the word "verdict" are counted, and a reply with no such token passes if it merely *starts* with "PASS". The docstring's "a reply carrying BOTH tokens fails" is true only when both follow "verdict".
**Evidence:** Ran `_qa_audit_passed` under `/tmp/wwf-venv`, which returned **True** for:
- `"PASS\nBlocking issues: 3.0 missing QP role"`
- `"I cannot give a verdict: PASS would be wrong here. FIX section 6."`
- `"Verdict — PASS with the following blocking issue: FIX 3.0"`
- the echoed template `"verdict PASS|FIX, issues: [...]"`

The persona tells the auditor that "'Verdict: PASS, no fixes needed' … FAILS the document", which is also false: it passes.
**Fix:** Require exactly one line matching `^\s*\**verdict\**\s*[:—-]\s*\**(PASS|FIX)\**\s*$` (case-insensitive) and no other PASS/FIX token anywhere. Drop the leading-PASS fallback, or keep it only when the reply is a single line. Correct the persona text and the test docstring.

### DI-16 [low] correctness — `/build` answers 200 with `document_id: null` when the registry is unavailable, and the COQ path records that as "generated"
**Where:** `docengine/app/main.py:418-435`; `backend/app/api/qc/coq_docx.py:558-570`, `coq_aggregation.py:732-745`.
**What happens:** With `db.ready()` false, the file is built, left unregistered on disk, and `{"ok":true,"document_id":null}` is returned. The backend then runs `UPDATE qc_certificates SET coq_document_id=NULL, coq_generated_at=now()` and emits `coq_generated`. It reports success with no artefact. Only reachable when `DOCENGINE_DATABASE_URL` is unset, because a failed pool at startup aborts boot.
**Evidence:** Read both sides.
**Fix:** In `/build`, return 503 when `not db.ready()` (as `/workflows` does). In the backend, treat a missing `document_id` as 502.

### DI-17 [low] security — Non-ASCII auth headers crash `hmac.compare_digest` with a 500 instead of a 401
**Where:** `docengine/app/security.py:16`; `backend/app/api/capture.py:129` (public via nginx `/capture`).
**What happens:** `compare_digest(str, str)` raises `TypeError: comparing strings with non-ASCII characters is not supported` when either side contains a non-ASCII character (Starlette decodes headers as latin-1). The request answers 500 and leaves a traceback in the logs.
**Evidence:** Reproduced the TypeError with `python3 -c`.
**Fix:** Compare bytes: `hmac.compare_digest(x.encode(), key.encode())`.

### DI-18 [low] design — The Letta pipeline has no retry; one transient error throws away a 20-40 call job (documented known gap)
**Where:** `docengine/app/pipeline.py:759-770` (docstring "KNOWN GAP"); `docengine/app/letta.py:74-84` (no retry on 5xx/connect).
**What happens:** A single 502 from LiteLLM or a connection reset on section 8 of 9 fails the job and discards sections 1-7. The planned fix is in the canvas design.
**Evidence:** Read the code. No retry wrapper exists.
**Fix:** Until checkpointing lands, retry `send_message` once on connect errors and 502/503/504 (idempotency risk is low for a one-shot, autoclear worker).

### DI-19 [low] correctness — Unpaginated Letta listings (UNVERIFIED default page size) would make `ensure_fleet` create duplicate agents or tools
**Where:** `docengine/app/letta.py:87-93` (`GET /agents/`, `GET /tools/` with no `limit`/cursor); consumers `fleet.py:839-843` (name → agent map), `fleet.py:229` (`ensure_tool`).
**What happens:** If the server's default page is smaller than the agent count (orphan clones, other stacks), a declared `gf_*` agent missing from page 1 is re-created on every job. `ragflow_search` missing from page 1 leads to `create_tool`, a name conflict, and every job failing. Today letta-6ou3 carries about 11 agents, so this is latent.
**Evidence:** Read the calls. Letta's default `limit` not verified here.
**Fix:** Page through `after=<last id>` until empty, or pass `name=` (already supported by `list_agents`) for each declared agent.

### DI-20 [low] ops — CI prunes dangling images on the production docker daemon
**Where:** `.github/workflows/ci.yml:447-453` (`docker image prune -f` in `images`, runs for every PR).
**What happens:** The runner's socket is production's (DI-02). An image left dangling by a re-tag of another stack on the host (Letta `latest`, RAGflow) is deleted by any PR run. CLAUDE.md treats old images as the rollback path and warns to reclaim deliberately.
**Evidence:** Read the step. See DI-02 for the socket.
**Fix:** Remove the global prune. `docker rmi` of the four `:ci` tags plus `docker builder prune --filter until=24h` is enough.

### DI-21 [low] correctness — The registry list is capped at 100 rows with no paging
**Where:** `docengine/app/db.py:156-160`; `main.py:439-443`.
**What happens:** Every COQ regeneration and every revision adds a row. Past 100 rows, older controlled documents drop out of `/qms/studio/documents` with no way to page to them.
**Evidence:** Read the query.
**Fix:** Add `limit/offset` (or keyset) parameters and pass them through the backend proxy.

### DI-22 [low] security/design — The connector runs as root beside the databases, with a global rate limit and a named-person default identity
**Where:** `connector/Dockerfile` (no `USER`); `docker-compose.yml:215` (`networks: [internal, traefik]`, the same network as `wwf-db-*` and DocEngine); `connector/server.py:49-60` (one global bucket); `backend/app/api/capture.py:111` (`CAPTURE_IMPORT_USER` defaults to a real person's username).
**What happens:** The only internet-facing Python service can open TCP connections to both Postgres containers and DocEngine. Anyone who learns the secret path can burn the 30-call window and lock the owner out for 5 min. If the env var is dropped, imports silently act as that named user.
**Evidence:** Read the files.
**Fix:** Add `USER 1000` and put the connector on its own network with only the backend attached. Remove the default username so an unset variable disables the route. Key the rate limit per client IP (`X-Forwarded-For` from Traefik).

### DI-23 [low] dead code / stale docs — contradicting or unused material in this area
**Where / what:**
- `docengine/pp-document-suite/`: a second copy of the engine, not in the image and not imported, and all six shared scripts differ from `docengine/engine/scripts/`. This is the "OTHER copy" confusion that DEPLOY-2026-08-31 R3 already hit.
- `docengine/app/needs.py:151-157` `needs_summary`: no caller.
- `db.py:20-21`: schema comments list kind `'build'` and status `awaiting_review`, neither of which is ever written; real kinds are `workflow|revise`.
- `pipeline.py:630-632, 1089-1098`: `_direct_edit_sections` and `run_revision` docstrings say "no reviewer verdict downstream / no accept/reject step … pp_verify PASS gate together ARE the new document", but `run_revision` runs the full §6A loop (`:1144-1193`).
- `fleet.py:804`, `builder.py:132-133`, `config.py:37-38`: "two uvicorn workers", "multiple uvicorn workers", "each polled as a background job". The Dockerfile runs one worker, and `send_message` is a synchronous POST.
- `fleet.yaml:422, 561`: `gf_doc_orchestrator` and `gf_translator_mk_en` are created and reconciled on every job, but nothing in the repo drives them.
- `ci.yml:440`: "docengine … (docker-compose.yml)" is false (DI-11).
- `migration-rehearsal.yml:436-438` says `/shell` runs inside `gh-runner-wwf`; `ops/README.md:167-172` and `rsh.py` say kvm4-runner.
- `fleet.yaml:742-790` `gf_app_assistant` is `autoclear: false` and described as the agent "staff" talk to. If the backend binds several AI functions or users to this one agent id (`backend/app/api/ai.py:483`, `intake.py:209,249`; binding rows are data, UNVERIFIED), every user's prompts and retrieved results share one buffer. That is a cross-user leak for the AI-area reviewer to confirm.

**Evidence:** `grep` for callers; `diff -rq` of the two engine trees.
**Fix:** Delete `pp-document-suite/` and `needs_summary`, correct the comments/docstrings, and drop or wire the two undriven agents.
