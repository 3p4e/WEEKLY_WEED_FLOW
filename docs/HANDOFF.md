# Session handoff — where things stand (2026-09-27 09:00 UTC)

Written so a new agent session can pick up without the long-running session's
history. Read `CLAUDE.md` first (access rules, deploy procedure, helpers), then
this. Anything here that disagrees with the live system loses: check GitHub and
the host before acting on it.

## What happened on 2026-09-27

1. The owner asked for a consolidated inventory and a whole-application review.
   Delivered as `docs/REVIEW-2026-09-27.md` + `docs/review-2026-09-27/` (seven
   area reports; 20 high / 54 medium / 63 low findings, 8 unbuilt owner
   requests, 19 agent-made decisions).
2. The owner then said: *"Rectify all findings and fix all bugs, and then run a
   review again."* Six parallel workstreams (product catalogue, QC, cultivation,
   backend core, frontend, DocEngine + infrastructure) fixed the findings in
   isolated worktrees; their branches were cherry-picked onto
   `claude/weekly-read-flow-setup-yft7if` in ~45 commits, with the
   cross-workstream wiring done on top. The second review is
   `docs/REVIEW-2026-09-27b.md` (written after the fixes; if that file does not
   exist yet, the re-review had not finished when this note was written).
3. Every decision a workstream made on its own is listed in
   `docs/DECISIONS-2026-09.md` §2b, one line each, for the owner's yes or
   correction. Nothing there is hidden in a commit message only.

## Pull requests

| PR | Branch / head | State | What it needs |
| --- | --- | --- | --- |
| **#52** | `claude/weekly-read-flow-setup-yft7if` | Carries the whole September work plus the review fixes. Check the head's CI before trusting it: the single runner takes ~30 min per run and a push cancels the previous run. | **Owner merges it**, then deploys per the rollout below. |
| #55 | `claude/audit-fixes-2026-09` @ `e18acd2` | 8/9 green | Only *Security scan* fails: `weasyprint==69.0` inherited from `main`; #52 bumps it. After #52 merges: **Update branch**. |
| #53 | `claude/sync-potency-spec-service` @ `63474db` | 8/9 green — **and stale**: the branch holds builder `2026.09.16-27`, production runs `-28` (the owner's two-per-page PDF export of 2026-09-16 exists only in the deployed image). | Same single failure, same fix; before merging, copy `web/index.html` off the running container into the branch (the owner, or an agent he authorises — agents must not push to it otherwise). |

Agents must not push to the #53/#55 branches; one explanatory comment is
already on each. The repo's **default branch is still
`claude/weekly-read-flow-setup-yft7if`**, not `main` — the owner's call.

## Production (KVM4, `srv1231216.hstgr.cloud`, new VM since 2026-09-19)

Running, last checked 2026-09-27 07:33 UTC — **unchanged by today's work;
nothing was deployed**:

- WWF: backend + scheduler `weekly_weed_flow-backend:v92`, frontend
  `wwf-growflow:v133`, docengine `growflow-docengine:v26`, `wwf-capture-mcp:v2`,
  Postgres 17 `wwf-db-tasks` / `wwf-db-users`, `wwf-db-backup` (daily pair at
  ~20:03 UTC), `wwf-watchdog` (`result=OK` every 5 min).
- Alembic in production: tasks **0069**, users **0012**. The branch is now at
  tasks **0071** and users **0013** (see rollout).
- Also on the host: RAGflow, Letta, `potency-spec-service`, `gh-runner-wwf`
  (the only CI runner, registered `kvm4-wwf`), `kvm4-runner`.
- Read the running tags off the host before planning a deploy
  (`docker inspect -f '{{.Config.Image}}' <container>`), per CLAUDE.md.

## Rollout of the review fixes (owner-driven; the agent can do the deploy)

All three services change together this time — the DocEngine org scoping is
fail-closed, so backend and docengine must ship in the same window:

1. Snapshot both DBs (deploy.yml sequence). Migrate tasks `0070`
   (cultivation integrity: mother line key) and `0071` (QC review fixes:
   CoQ purpose/timepoint, signatures on CoQs, eight retired id sequences),
   users `0013` (drops the two unused profiles write policies).
2. DocEngine: run `docengine/sql/docengine_role.sql` on `wwf_tasks`, point
   `DOCENGINE_DATABASE_URL` at the new role, recreate `docengine` (procedure in
   `docs/DEPLOY.md`); backfill `org_id` on existing `docengine.documents` /
   `jobs` rows with the real org uuid (never the demo org's) — unscoped rows are
   invisible until then.
3. Host compose: add `docengine_out:/docengine-out:ro` to `db-backup` and
   recreate it; the repo's `docker-compose.yml` now carries the `docengine`
   service and the `ai-net` network the host already has.
4. Set `CAPTURE_IMPORT_USER` explicitly in the production env (the code no
   longer falls back to a named account; empty switches the token path off).
5. Build backend / frontend / docengine from the merge commit, swap one service
   at a time, smoke `/health/ready`.
6. Product catalogue, in this order (owner 2026-09-18: the fitted tolerances
   are the specification; the flat ±10 % pages are retired): run
   `POST /qc/products/import` (dry run, then real) **only for the strain
   renames it carries — do not approve those v.03 products**; then load the
   fitted specifications with `POST /qc/products/import-fitted` from the
   running Potency Spec Service's `GET /api/specs?status=finished` export
   (the owner supplies the document code/version they are issued under); then
   approve each strain's fitted set in one sitting, as a different QC person
   or the QP than the author. Approving a fitted product supersedes the
   strain's v.03 rows; the code refuses to approve an older version once a
   newer one exists.
7. Facility register: re-import the layout (`POST /facility/layout/import`) so
   the 34 rooms now carrying the owner's cleanliness grades get them (the import
   never overwrites a grade QA already set).

## Agent access (see CLAUDE.md "Agent helpers")

- `python3 ops/agent/rsh.py '<cmd>'` works (RUNNER_TOKEN fixed 2026-09-27 02:20).
- `python3 ops/agent/gh_api.py GET|POST … /repos/3p4e/WEEKLY_WEED_FLOW/…` works
  — tested live at 07:50 UTC (runner listing → HTTP 200) after the DI-03
  rewrite: it is now an allow-list (any GET under the repo; POST for rerun,
  rerun-failed-jobs, workflow dispatch and issue comments), and the token
  travels to the host as a 0600 file, never in command text.
- Both must be run as standalone commands from the repo root so the owner's
  allow rules match; the rules are written by the cloud environment's setup
  script, which only runs when a *new* session starts.
- Two different things share the name `KVM4_RUNNER_TOKEN`. The **cloud
  environment variable** of that name (Claude environment settings) is read by
  nothing — the helpers read `RUNNER_TOKEN` — and holds the stale pre-migration
  value; the owner may delete *that one*. The **GitHub Actions secret**
  `KVM4_RUNNER_TOKEN` is required by `deploy.yml` and
  `migration-rehearsal.yml` and must hold the current runner token; do not
  delete it.

## Open decisions and actions for the owner

Security (do not act on these yourself):
- **Offsite backups are not running.** `wwf-backup-offsite` was never
  recreated on the new VM; only the on-host daily dumps exist. The watchdog
  now reports it (WARN while the container is absent).
- The temporary relaxations the owner scoped himself (password floor, the
  renamed accounts, the `admin` password "for a short while", the trial
  `qc_mgr` account) are listed in `docs/DECISIONS-2026-09.md` §3 with what
  reverts them; nothing in this note repeats them.
- Rotate: the OpenUI key and `HF_TOKEN` (visible in a chat screenshot),
  `GITHUB_PAT_WWF` (read through a Google Doc; the original `1.APIs.md`
  probably still holds it), the Google Drive OAuth token + rclone crypt
  password (procedure in `docs/BACKUP.md`), the two older PATs noted in
  CLAUDE.md.
- Unknown who or what stopped production on 2026-09-19 23:37 UTC.
- The CI runner still lives on the production host with the docker socket
  (review DI-02). `ops/README.md` sets out the two remedies (separate runner
  VM, or required approval for PR runs); the deploy workflow now refuses a
  commit whose workflow files differ from the default branch's, which limits
  but does not remove the exposure.

Product decisions — all in `docs/DECISIONS-2026-09.md`:
- §2: the 19 earlier agent-made decisions, several now corrected by the fixes.
- §2b: the decisions the six fix workstreams made (out-of-grade rule as built,
  version-level supersession, ceiling on fitted windows, backward phase moves,
  cuttings from 01, PHI on the cut date, unit matching without conversion,
  role-of-record signatures, session split hours, …). Each needs a yes or a
  correction; each is one line.
- Still unanswered from earlier: room `E34` and the "FDF 3" premise on the
  plan; the four disputed strain spellings (Jelly Donutz/Donuts, Wedding
  Crasher/Crusher, Graps & Crème/Grapes And Cream, Sleepy Joe/Joy) — the code
  treats each pair as one strain until the owner picks.
- The "six CoQs" of 2026-09-18 are answered: the owner (19:14) says they are
  the six certificates the agent reported missing, and the certificates exist.
  What is open is on the agent's side — which six were listed, and where in
  the workbook (v35+) the owner's "everything" is. Locate them and close.

Answered and applied today (do not re-ask): cleanliness grades per area type
(2026-09-06 list, in `facility_layout.json`), "Pure Michigen" / "Clemosa A Bud"
as canonical spellings, and an out-of-window CoQ is **not** blocked from
issuance — it regrades, notifies Cultivation and Production, carries a visible
"OOS pending" flag until the formal OOS on the batch disposition exists, and
the document prints the regrade and the OOS state (the owner's "NO for now" of
2026-09-06; fix round 2 corrected an approval gate one workstream had built).

The owner has asked six times since 2026-09-06 to **merge to `main` and
deploy**. That is the standing instruction this branch is working towards
(task #33); every rollout step above serves it.

## Local development notes learned today

- The e2e suite runs locally: `nginx` installed via apt, `backend/.venv` is a
  symlink to `/tmp/wwf-venv`, Chromium at `/opt/pw-browsers/chromium`
  (`PLAYWRIGHT_CHROMIUM_PATH`), `npm ci` in `web/e2e`. It uses
  `wwf_users_test` / `wwf_tasks_test`, which must be at alembic head.
- The local `postgres` role has the password `postgres` over TCP (set for
  alembic runs as the table owner, like CI); the test DBs are owned by
  `postgres`, so migrations run as it, not as `app_admin`.
- Four extra DB pairs `wwf_{users,tasks}_test_{a,b,c,d}` exist for parallel
  runs; their alembic state is whatever the last workstream left.

## Work not started or not finished

- **Task #33** — after #52 merges, deploy per the rollout above.
- **Task #18** — CoQ workbook sync: designed in
  `docs/ECOA-MASTER-SYNC-DESIGN-2026-09.md`, not built (owner's workbook is at
  v35).
- **DocEngine canvas** — design settled in
  `docs/DOCENGINE-CANVAS-DESIGN-2026-09.md`; the provenance and
  `reviewed_by` columns it needs now exist (DI-14); the UI is not built.
- **Range builder in the app** — the server side now exists (`POST
  /qc/products/ladder`, `import-fitted`, the conformance rule); the in-app
  builder UI and the solver are not built (`docs/RANGE-BUILDER-INTEGRATION-2026-09.md`).
- Findings deliberately left open are listed in `docs/REVIEW-2026-09-27b.md`
  §"Not fixed" (single-certificate CoQ render kept for the UI; DI-06 §6A audit
  not run on direct builds; QC-31 acid/neutral heuristic; the CI runner host).
- Nightly "Drift check + restore-and-upgrade" runs ~08:36 UTC.
