# Production deploy: growflow-docengine v24 (2026-09-02)

DocEngine-only deploy from `241f714` — the merge commit of PR #46, which makes
the Letta fleet's reconcile loop convergent instead of merely additive.
Swapped at 2026-09-02 11:05 UTC.

## What shipped

`growflow-docengine:v24` (`sha256:65c9556d…`). Every fleet-layer finding of the
2026-08-31 architecture review, as one change:

| behaviour | v23 | v24 |
| --- | --- | --- |
| remove `datasets:` from an agent | scope block rewritten; tool, allowlist and tenant key stayed forever | credentials stripped, tool **detached** |
| undeclared custom tool on an agent | held the tenant key with no allowlist | reported; key withheld or revoked |
| `ensure_tool` cannot update the tool | returned the id anyway; every agent wired to an unverified tool | raises; the job fails closed |
| "not yet ingested" | a hand-maintained YAML list | resolved against RAGflow at every pass; YAML is the fallback |
| orphaned `gf_*_tmp_*` clones | a sweep `pipeline.py` cited did not exist | swept once older than 3× read-timeout |
| `context_window` the server normalises | re-PATCHed on every job, forever | pushed once, re-read, reported, never re-pushed |
| `defaults.model` on an existing agent | silently inert, presented as a declaration | reported as drift; `fleet.yaml` says it is create-time only |
| what a pass found | discarded | `FleetReport` → `/fleet/status`, summarised on `/health` |
| `/health` | "a Letta URL is set" | probes Letta and RAGflow; lists unresolved datasets; `ready` |
| `spawn_ephemeral` per section | 6 calls (4 listings) | 2 calls, reusing the job's `FleetContext` |
| how the pipeline drives each agent | `fleet.yaml` flags, tests restating names | `pipeline.DRIVEN_AGENTS`; `test_fleet` derives the check from it |

Twenty new tests; nineteen confirmed to fail on the unfixed code first.

## Built before the merge, verified against it

`main` carried no `docengine/` change since `084a295`, so the merge commit's
`docengine/` tree is the branch tip's tree. The image was built from
`dd30f3a` while CI ran, then held until the merge landed and the check passed:

```
dd30f3a:docengine = a46578bd431b27d48cc900fb6710899cd908e68a
241f714:docengine = a46578bd431b27d48cc900fb6710899cd908e68a   (merge commit)
```

Same credential-free route as v91/v23 — `git archive` → base64 through the
runner's `/shell` in 100 KB chunks → `sha256 b7ca4672…` equal on both ends
(386,010 bytes, 59 files). In-image checksums of `app/fleet.py`, `app/letta.py`,
`app/pipeline.py`, `app/main.py`, `app/ragflow_api.py`, `agents/ragflow_search.py`
and `agents/fleet.yaml` all equal the repo; five commit-unique markers
(`_sweep_orphans`, `detach_tool`, `DRIVEN_AGENTS`, `/fleet/status`, the
paginated `page=%d`) present in v24 and absent from v23.

## Previewed read-only before the swap

The new code's read-side functions were run from the v24 image against the
live fleet and tenant, with no writes issued, so the first real pass could be
predicted from evidence rather than reasoning:

```
live gf_ agents: 8; declared: 8
orphans that would be swept: none
(all 8) unknown_tools=- tool=no-op env=no-op/grant-diff
RAGflow reachable; tenant datasets: DB01_REG, WATER_QC_REZULTS, eCOA_DB, eCOA_SS
declared-but-unresolved: DB1_REGULATORY, DB3_PP_CURRENT_unified,
                         GrowFlow_Weekly_Snapshots, eCoA_DATABASE
```

So the first document job will revoke nothing, detach nothing and sweep
nothing. It **will** rewrite every agent's `ragflow_scope` block to say its
corpus is not yet ingested — because all four declared names are absent from
the rebuilt tenant. That is review finding R1 becoming visible; v23 had been
writing scope blocks that named `eCoA_DATABASE` as live.

## Sequence

1. PR #46 green on all 9 checks → marked ready → merged as `241f714`.
2. Working branch restarted from `origin/main`; tree hash asserted equal.
3. `compose.yaml` backed up to `compose.yaml.bak-pre-v24`; line 151 bumped;
   `docker compose config -q` clean; diff against backup exactly one line.
4. `docker compose up -d --no-deps docengine`. Nothing else touched.

## Verification, on the running container

```
/health → {"ok":true,"db":true,"letta":true,"ragflow":true,
           "datasets_unresolved":["DB1_REGULATORY","DB3_PP_CURRENT_unified",
                                  "GrowFlow_Weekly_Snapshots","eCoA_DATABASE"],
           "fleet":null,"engine":"engine","ready":false}
```

`ready: false` is correct and is the whole point: the service is up, Letta and
RAGflow both answer, and the fleet's declared corpus does not exist. v23 said
`ok` in the identical condition. `fleet` stays `null` until the first document
job runs a reconcile pass; `/fleet/status` (API-keyed) returns `last_pass: null`
plus the same live dataset resolution. `engine` now names the tree the service
imports (`engine/`), not the dead `pp-document-suite/`.

Digest `sha256:65c9556d…` equals the built image; all seven in-container
checksums equal the repo; `LETTA_READ_TIMEOUT=900` and
`DOCENGINE_MAX_REPAIR_ROUNDS=2` survived the swap; the log shows the two
probes actually reaching RAGflow and Letta; no errors.

## Rollback — and what a rollback would undo

`growflow-docengine:v23` (`sha256:73e74aee…`) is retained;
`compose.yaml.bak-pre-v24` restores the tag. Two asymmetries to know before
using it:

- **The Letta-side tool follows the image.** After v24's first job the
  registered `ragflow_search` is the paginated version; a rollback to v23
  pushes the single-page one back at its next job.
- **The scope blocks follow the image too.** After v24's first job every
  block says the corpus is not ingested (true). Rolling back re-derives them
  from `fleet.yaml`'s YAML lists, which still call `eCoA_DATABASE` live — a
  rollback restores the false statement, not just the old container.

## What this does not do

It does not map the declared dataset names onto the rebuilt tenant. That is
a `fleet.yaml` change pending the owner's confirmation of the mapping
(`eCoA_DATABASE→eCOA_DB`, `DB1_REGULATORY→DB01_REG`, and which of `eCOA_SS` /
`WATER_QC_REZULTS` is the withheld stability set). Until then `/health` will
keep reporting `ready: false` with those four names — which is the correct
state to be in loudly.

The compose service still has no healthcheck (a medium from the review);
`ready` is reported for a human or a dashboard, not yet acted on by compose.
