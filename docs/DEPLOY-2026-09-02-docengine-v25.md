# Production deploy: growflow-docengine v25 (2026-09-02)

DocEngine-only deploy from `52ab89b` — the merge commit of PR #48, which maps
the fleet's declared dataset names onto the RAGflow tenant as it was rebuilt on
08-29. Swapped at 2026-09-02 13:13 UTC, two hours after v24.

## What shipped

`growflow-docengine:v25` (`sha256:f1dd7b3c…`). One file of substance,
`agents/fleet.yaml`, plus the tests that read names from it:

| declared in v24 | declared in v25 | on the tenant |
| --- | --- | --- |
| `eCoA_DATABASE` | `eCOA_DB` | 253 certificates, 317 chunks, parsed |
| `DB1_REGULATORY` | `DB01_REG` | 79 documents, 18 chunks, parse still being re-run |
| `STABILITY_PROGRAMME` | `eCOA_SS` | withheld from every agent, as before |
| — | `WATER_QC_REZULTS` | not granted until the owner says it is ready |
| `DB3_PP_CURRENT_unified`, `GrowFlow_Weekly_Snapshots` | unchanged | not on the tenant |

No code changed. v24 had already made the reconciler *notice* that its corpus
did not exist; v25 is the declaration catching up with the tenant.

## Built before the merge, verified against it

Same pattern as v24: the image was built from the branch tip `c93f4c2` while
CI ran (credential-free `git archive` → base64 through the runner's `/shell`
→ sha256 equal on both ends), and held until the merge landed:

```
c93f4c2:docengine = 58dd6c9c030014628153854e54de5b8a26d4e3fd
52ab89b:docengine = 58dd6c9c030014628153854e54de5b8a26d4e3fd   (merge commit)
```

In-image sha256 of `app/fleet.py`, `app/letta.py`, `app/pipeline.py`,
`app/main.py`, `app/ragflow_api.py`, `agents/ragflow_search.py` and
`agents/fleet.yaml` all equal `git show 52ab89b:docengine/<file>`;
`fleet.yaml` is `17aedb9b…`. All nine PR checks green (backend suite 18 min).

## Previewed read-only before the swap

v24's own read-side functions, run from the v25 image against the live fleet
with no writes issued:

```
tenant datasets: DB01_REG, WATER_QC_REZULTS, eCOA_DB, eCOA_SS
resolve_pending -> DB3_PP_CURRENT_unified, GrowFlow_Weekly_Snapshots
gf_app_assistant: env eCoA_DATABASE,DB3_…,GrowFlow_… -> eCOA_DB,DB3_…,GrowFlow_…
gf_reg_checker:   env DB1_REGULATORY,DB3_…            -> DB01_REG,DB3_…
(other six)       no-op
unknown tools: none · tool attach/detach: none · orphans: none
```

So the prediction was: two `RAGFLOW_ALLOWED_DATASETS` rewrites, scope blocks
that now name a live corpus, nothing revoked, nothing detached.

## Sequence

1. PR #48 green on all 9 checks → marked ready → merged as `52ab89b`.
2. Working branch restarted from `origin/main`; `docengine/` tree hash
   asserted equal to the built tree.
3. `compose.yaml` backed up to `compose.yaml.bak-pre-v25`; line 151 bumped;
   `docker compose config -q` clean; diff against backup exactly one line.
4. `docker compose up -d --no-deps docengine`. Nothing else touched.

## Verification, on the running container (13:14 UTC)

```
/health → {"ok":true,"db":true,"letta":true,"ragflow":true,
           "datasets_unresolved":["DB3_PP_CURRENT_unified","GrowFlow_Weekly_Snapshots"],
           "fleet":null,"engine":"engine","ready":false}
/fleet/status → last_pass: null; declared: DB01_REG, DB3_PP_CURRENT_unified,
                GrowFlow_Weekly_Snapshots, eCOA_DB; unresolved: the two above
```

`eCOA_DB` and `DB01_REG` resolve; the two names still unresolved are corpora
that genuinely do not exist on the tenant, so `ready: false` stays and is
correct. Container image id equals the built digest; `LETTA_READ_TIMEOUT=900`
and `DOCENGINE_MAX_REPAIR_ROUNDS=2` survived; the log shows both probes
reaching RAGflow and Letta; zero errors.

## The first reconcile pass (13:14:59–13:15:21 UTC)

Triggered by the first document job on v25 (the analytical-dossier SOP trial
below). `/fleet/status` afterwards:

```
changed: gf_sop_author      [block gf_corpus]
         gf_annex_author    [block gf_corpus, config]
         gf_reg_checker     [block ragflow_scope, block gf_corpus, tool env]
         gf_raci_specialist [block gf_corpus]
         gf_qa_auditor      [config]
         gf_app_assistant   [block persona, block ragflow_scope, block gf_corpus, tool env]
drift: [] · warnings: [] · unknown_tools: {} · swept_orphans: [] · created: []
converged: false
```

Exactly the two `tool env` rewrites the preview predicted, and no others.
The block rewrites are the corpus guide (renamed dataset in every agent's
`gf_corpus`), the two scope blocks whose grants were renamed, and the
assistant's persona. The two `config` entries are the one-time message-buffer
clear the reconciler performs when it turns autoclear on. `converged: false`
is the honest first-pass answer — something changed — and the next pass is
what proves the loop has a fixed point.
