# Production deploy: growflow-docengine v23 (2026-08-31)

DocEngine-only deploy from `484e268` — the merge commit of PR #43. Swapped at
2026-08-30 23:20 UTC, which is 2026-08-31 01:20 at the facility; this record is
dated at the facility clock, for the reason the PR itself is partly about.

## What shipped

`growflow-docengine:v23` (`sha256:73e74aee…`), carrying the five hardening
fixes from PR #43. Three of them live inside this service, and none was
reachable in production before now:

| fix | why it matters here |
| --- | --- |
| `ragflow_search` fails **closed** on an unset `RAGFLOW_ALLOWED_DATASETS` | the running v22 would have searched the whole tenant — stability corpus included — if that variable ever went missing, silently and looking like success |
| `_reconcile_tool_env` compares every value the server shows | a rotated `RAGFLOW_API_KEY` reached no agent under v22, because the comparison short-circuited on the dataset list alone |
| `BilingualGap` persists its sections | under v22 a document failing that gate could only be inspected by re-running the generation, which the agents do not reproduce |

The other two in the PR (`ensure_tool` idempotency, and the migration-rehearsal
drift baseline) also ride in this image and in CI respectively.

`weekly_weed_flow-backend:v91`, `wwf-growflow:v131` and `wwf-capture-mcp:v2`
were **not** touched — v91 shipped earlier the same evening
(`DEPLOY-2026-08-30-backend-v91.md`), and the other two were checksum-verified
current against this commit there.

## Sequence

Same route as v91, for the same reason: the `gh-runner-wwf` checkout does not
survive between workflow runs, so the build context was shipped directly rather
than by staging a PAT on the host.

1. Merged PR #43 → `484e268` (all **10** checks green), restarted the working
   branch from `origin/main`.
2. `git archive 484e268 docengine` → gzip → base64 in 100 KB chunks through the
   runner's `/shell`, decoded on the host and verified:
   `sha256 518e7a19ebd7441a252ca5156f29280542865142838c9cc32ef04436b7e631a7`
   on both ends. No credential involved.
3. Built `growflow-docengine:v23`, backgrounded with `nohup setsid` + a status
   file so no tool timeout could orphan it.
4. **Asserted the image carries the commit**: `app/fleet.py` `64153ac3…`,
   `app/pipeline.py` `a3a9c984…`, `agents/ragflow_search.py` `7521c24a…`, all
   equal to the repo at `484e268`; plus commit-unique markers
   (`RAGFLOW_ALLOWED_DATASETS is not set`, `counting it would make a stricter
   server`, `omits source_code`, `exactly as the structure gate`). **v22 has
   zero of them**, which is what makes the rebuild substantive.
5. Backed up `compose.yaml` to `compose.yaml.bak-pre-v23`, bumped the tag, and
   diffed against the backup — exactly line 151, nothing else.
6. `docker compose up -d --no-deps docengine`. No other service touched.

## Verification

- `/health` → `{"ok":true,"db":true,"letta":true,"engine":"pp-document-suite (canon 2026-07)"}`
- Running container digest `sha256:73e74aee…` equals the built `v23`.
- The three sources above checksum-equal **inside the running container**.
- The v22 configuration overrides survived the swap:
  `LETTA_READ_TIMEOUT=900`, `DOCENGINE_MAX_REPAIR_ROUNDS=2` — both load-bearing
  (see `DEPLOY-2026-08-29-docengine-v22.md`), and both are compose/env rather
  than image state, so they are exactly the sort of thing a swap can lose.
- Clean startup, no errors in the log.
- **The fail-closed guard exercised in the running container**, not inferred:

  | call | result |
  | --- | --- |
  | `RAGFLOW_ALLOWED_DATASETS` unset, asks for `STABILITY_PROGRAMME` | refused — *"RAGFLOW_ALLOWED_DATASETS is not set for this tool"* |
  | allowlist `eCoA_DATABASE`, asks for `STABILITY_PROGRAMME` | refused — *"outside your permitted scope"* |

  Under v22 the first of those would have gone to RAGflow.

## Rollback

`growflow-docengine:v22` (`sha256:ce7745bd…`) is retained and
`compose.yaml.bak-pre-v23` restores the tag verbatim. Nothing in this deploy
touches the database or the Letta fleet's stored state, so a rollback is a tag
flip and a `up -d --no-deps docengine`.

One asymmetry worth knowing before rolling back: `ensure_fleet` runs on every
document job and PATCHes the registered `ragflow_search` tool to match the
image's committed source. Once v23 has run one job, the tool on the Letta
server carries the fail-closed version; rolling the image back to v22 will
restore the fail-OPEN tool on that job's next run. That is correct behaviour
(the image is the declaration), but it means a rollback silently reopens the
gap rather than merely reverting the container.

## Stack after this deploy

| service | image |
| --- | --- |
| backend + scheduler | `weekly_weed_flow-backend:v91` |
| frontend | `wwf-growflow:v131` (byte-identical to `main`, deliberately not rebuilt) |
| docengine | `growflow-docengine:v23` |
| capture-mcp | `wwf-capture-mcp:v2` |

Every repo-built image in the stack now matches `main` at `484e268`.

`/opt` is at **80 %** (154 G of 193 G, 40 G free), up one point from the v91
build. Old image tags are the rollback path and volumes are production data, so
neither is a reclaim target; `docker system df` and the build cache are.
