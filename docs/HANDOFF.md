# Session handoff — where things stand (2026-09-27 02:30 UTC)

Written at the owner's request so a new agent session can pick up without the
long-running session's history. Read `CLAUDE.md` first (access rules, deploy
procedure, helpers), then this. Anything here that disagrees with the live
system loses: check GitHub and the host before acting on it.

## Pull requests

| PR | Branch / head | State | What it needs |
| --- | --- | --- | --- |
| **#52** | `claude/weekly-read-flow-setup-yft7if` @ `66fb0cd` | All 9 CI checks + production liveness green | **Owner merges it.** Its body has the rollout list (product import + approval by a second QC person, facility layout import, departments, re-kinding clone rooms). |
| #55 | `claude/audit-fixes-2026-09` @ `e18acd2` | 8/9 green | Only *Security scan* fails: `weasyprint==69.0` (PYSEC-2026-3940) inherited from `main`. #52 bumps it to 70.0. After #52 merges: **Update branch**. |
| #53 | `claude/sync-potency-spec-service` @ `63474db` | 8/9 green | Same single failure, same fix. |

Agents must not push to the #53/#55 branches; one explanatory comment is
already on each. The repo's **default branch is still
`claude/weekly-read-flow-setup-yft7if`**, not `main` — the owner's call.

## Production (KVM4, `srv1231216.hstgr.cloud`, new VM since 2026-09-19)

Running, checked 2026-09-27 02:25 UTC:

- WWF: backend + scheduler `weekly_weed_flow-backend:v92`, frontend
  `wwf-growflow:v133`, docengine `growflow-docengine:v26`, `wwf-capture-mcp:v2`,
  Postgres 17 `wwf-db-tasks` / `wwf-db-users`, `wwf-db-backup` (daily pair at
  ~20:03 UTC, confirmed cycling), `wwf-watchdog` (host watchdog, `result=OK`
  every 5 min).
- Alembic in production: tasks **0069**, users **0012** — the same heads as
  #52's branch, so #52's migrations are already live.
- Also on the host: RAGflow (`ragflow-*`), Letta (`letta-6ou3-*`),
  `potency-spec-service`, `gh-runner-wwf`, `kvm4-runner`.
- `/app` disk: 55 % used, 87 GB free.

Infrastructure rebuilt after the VM migration (2026-09-25/26):

- **`gh-runner-wwf`** — rebuilt from `ops/gh-runner/` (see `ops/README.md`),
  registered as `kvm4-wwf`, runner 2.337.0. It is the only runner, so jobs
  queue one at a time: a full CI run takes about 30 minutes.
- **`kvm4-runner`** (`/opt/kvm4-runner/app/runner.py` on the host, *not in
  git*) — rewritten stdlib-only; its response contract
  `{exit_code, output, truncated, bytes}` was restored on 2026-09-26 11:14 UTC
  and proven by a manual migration rehearsal (run 36255624308: restore of the
  real backup pair, both chains to head, no row loss).
- GitHub repo secrets `KVM4_RUNNER_URL` / `KVM4_RUNNER_TOKEN` updated for the
  new VM; the workflows use those.

## Agent access (see CLAUDE.md "Agent helpers")

- `ops/agent/rsh.py` works with the environment's `RUNNER_TOKEN` (fixed
  2026-09-27 02:20 UTC).
- `ops/agent/gh_api.py` + `GITHUB_PAT_WWF`: **untested for real**. The
  owner's setup script writes the allow rules to `~/.claude/settings.json`,
  which only happens when a *new* session starts — a resumed session does not
  re-run it. First thing to try in a new session:
  `python3 ops/agent/rsh.py 'echo ok'` and
  `python3 ops/agent/gh_api.py GET /repos/3p4e/WEEKLY_WEED_FLOW/actions/runners`.
  If auto mode still blocks them, tell the owner; do not route around it.
- Environment variable `KVM4_RUNNER_TOKEN` holds the stale pre-migration value
  and is read by nothing; the owner may delete it.

## Open decisions and actions for the owner

Security (do not act on these yourself):
- **Offsite backups are not running.** `wwf-backup-offsite` was never
  recreated on the new VM; only the on-host daily dumps exist.
- Rotate: the OpenUI key and `HF_TOKEN` (both visible in a screenshot shared in
  chat), `GITHUB_PAT_WWF` (read through a Google Doc; the original
  `1.APIs.md` probably still holds it), the Google Drive OAuth token + rclone
  crypt password (task #47, procedure in `docs/BACKUP.md` on #55), the two older
  PATs noted in CLAUDE.md. The pre-migration kvm4-runner token was printed in
  chat once; it only matters if the old VM still runs.
- Unknown who or what stopped production on 2026-09-19 23:37 UTC.

Product questions (from #52's body, still unanswered):
- Which cleanliness classification scheme the validation master plan uses, and
  the grade for each area type.
- Canonical strain names where the ImB pages and the August catalogue differ
  (Jelly Donutz/Donuts, Wedding Crasher/Crusher, Pure Michigan/Michigen,
  Graps & Crème/Grapes And Cream, Clemosa/Clemosa A Bud).
- Whether a CoQ outside its product's window should be blocked (today it
  prints "does not conform" and still renders).
- Room `E34` and the "FDF 3" premise on the floor plan.
- Which "six CoQs" the owner meant (asked 2026-09-18).
- Whether to extract the DP tolerance-fitting code (`solveTolerances` /
  `scoreLadder` / `candidateNominals` from the potency spec tool) now or after
  #52 merges.

## Work not started or not finished

- **Task #33** — after #52 merges, deploy per service (CLAUDE.md: ask per
  service what commit its running image is built from).
- **Task #18** — CoQ workbook sync: designed in
  `docs/ECOA-MASTER-SYNC-DESIGN-2026-09.md`, not built. The owner's workbook
  has moved on from v9 (v35 by 2026-09-17).
- **DocEngine canvas** — design settled (option A for amendments) in
  `docs/DOCENGINE-CANVAS-DESIGN-2026-09.md`; implementation not requested yet.
- Nightly "Drift check + restore-and-upgrade" runs ~08:36 UTC; the first
  scheduled run on the new runner contract is 2026-09-27.
