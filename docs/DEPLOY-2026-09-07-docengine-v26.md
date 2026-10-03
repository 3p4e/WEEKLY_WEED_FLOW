# Production deploy: growflow-docengine v26 (2026-09-07)

DocEngine-only deploy from `df1568b`, closing a **live production defect**: the
DocEngine Studio chat, preset and revise controls were shipped to users on
2026-09-06 while the service that answers them was not.

## The defect

Commit `9d40f5d` (2026-09-04, "Add chat + preset direct-edit UI to DocEngine
Studio") is a three-tier change. Two tiers went live in the v92/v133 deploy; the
third did not, because docengine is a separate image on its own cadence and its
changes **predate** `cbfae38` rather than following it — so they were invisible to
the `cbfae38..HEAD` diff that the v92 deploy reasoned about.

| tier | change | state before this deploy |
| --- | --- | --- |
| frontend `web/gf/api.js`, `qmsstudio-view.js` | `studioPresets`, `studioChat`, `studioRevise` + the ask/edit panel | **live** in `wwf-growflow:v133` |
| backend `app/api/qms.py` | proxies `/studio/presets`, `/studio/workflows/{jid}/chat`, `/studio/workflows/{jid}/revise` | **live** in `weekly_weed_flow-backend:v92` |
| docengine `app/main.py`, `pipeline.py`, + new `needs.py`, `presets.py` | the routes themselves | **NOT live** — `growflow-docengine:v25`, built 2026-09-02 |

Verified on the host before deploying, not inferred from `docs/`:

```
wwf-docengine   image=growflow-docengine:v25   (built 2026-09-02 from 52ab89b)
  ls app/needs.py    -> No such file or directory
  ls app/presets.py  -> No such file or directory
  routes: /documents /documents/{did} /documents/{did}/download /documents/{did}/pdf
          /fleet/status /health /questionnaires /questionnaires/{key}
          /workflows/{jid} POST /build POST /workflows
          — no /presets, no /workflows/{jid}/chat, no /workflows/{jid}/revise
```

So every click on the Studio's ask/edit box reached a proxy that reached a 404.

**How it was found.** Not by the deploy check — that check asked only whether
anything changed *since the last backend/frontend deploy*, and the honest answer
was no. Three independent agents were asked to refute "no deploy is warranted";
two refuted it, both on docengine, from the same evidence the narrow check had
walked straight past. The lesson is in "Notes for the next session" below.

## What shipped

`growflow-docengine:v26` from `df1568b`. The docengine tree at `df1568b` is
`e1124a4f…`, **identical to `cbfae38`** — the commit backend v92 and frontend v133
were built from — so this ships exactly the code the live tiers were reviewed and
deployed against, not something newer.

Against the deployed v25 tree (`58dd6c9c…`, commit `52ab89b`): 11 files,
+1403/−42, including two new modules.

| file | lines |
| --- | --: |
| `app/pipeline.py` | 346 |
| `tests/test_pipeline.py` | 353 |
| `tests/test_api.py` | 216 |
| `app/main.py` | 151 |
| `tests/test_needs.py` | 101 |
| `app/needs.py` | **new**, 89 |
| `app/presets.py` | **new**, 68 |
| `engine/references/GUIDE_bilingual_markdown.md` | 46 |
| `tests/test_fleet.py` | 42 |
| `app/fleet.py` | 18 |
| `agents/fleet.yaml` | 15 |

## Build context and verification

Credential-free tarball, the standard route: `git archive HEAD docengine` →
`gzip -9` → base64 in 100 KB chunks through the runner's `/shell` → decoded on the
host.

```
local  sha256(docengine.tgz) = 800c2f0bdcb4be726f9cb54f317a0267fb782efb6357fccbc942a9447fb3f005
kvm4   sha256(docengine.tgz) = 800c2f0bdcb4be726f9cb54f317a0267fb782efb6357fccbc942a9447fb3f005
```

Every file of substance checksummed **inside the built image** against
`git show HEAD:docengine/<file>` — all six equal:

| file | sha256 |
| --- | --- |
| `app/main.py` | `00ca0238…cc301` |
| `app/pipeline.py` | `5d9cec6d…068e06` |
| `app/needs.py` | `01d66ada…39cc80` |
| `app/presets.py` | `dbebbfa3…9706a9` |
| `app/fleet.py` | `552aef86…48a1b` |
| `agents/fleet.yaml` | `38374f99…b55ed` |

## Sequence

No database, so no snapshot and no migration. `compose.yaml` backed up
byte-identical to
`/opt/wwf-deploy/snapshots/20260907T062136Z-pre-docengine-v26/compose.yaml.pre-docengine-v26`,
the one image line rewritten and the rewrite proved to have landed, then
`docker compose up -d --no-deps docengine`. The `docengine_out` volume was not
touched; no other service was recreated.

## Post-deploy verification

The three routes that were 404 now answer **401** — they exist and are
auth-gated, which is the check `CLAUDE.md` prescribes:

```
GET  /health                        -> 200  {"ok":true,"db":true,"letta":true,"ragflow":true,…}
GET  /presets                       -> 401  route exists
POST /workflows/{jid}/chat          -> 401  route exists
POST /workflows/{jid}/revise        -> 401  route exists
```

```
wwf-docengine               running  growflow-docengine:v26        restarts=0
weekly_weed_flow-backend-1  running  weekly_weed_flow-backend:v92  restarts=0
wwf-gf-frontend             running  wwf-growflow:v133             restarts=0
wwf-db-users / wwf-db-tasks running  postgres:17-alpine            restarts=0

GET /health/ready -> 200 {"ready":true,"databases":{"users":"ok","tasks":"ok"}}
```

## Rollback

`growflow-docengine:v25` is still on the host, and the compose backup above
restores the tag. DocEngine holds no database, so rollback is a tag swap and a
`--no-deps` recreate — nothing to unwind.

## Notes for the next session

- **A deploy check scoped to "what changed since the last deploy" is wrong when
  the stack has services on independent cadences.** Backend and frontend deploy
  together; docengine does not. The correct question is per service: *what commit
  is each running image built from, and what has changed in its own subtree
  since?* Asking it only of the newest deploy hides exactly this class of defect,
  and it hid it for 24 hours with a user-facing feature broken.
- **The three-tier change is the shape to watch.** When one commit touches
  frontend, backend and docengine, shipping two tiers leaves live callers pointed
  at absent routes. Deploy the service that *serves* a route before the tiers that
  call it, or ship all three together.
- `/opt` is at **94 %, ~13 GB free** — unchanged by this deploy (the docengine
  image is ~273 MB).
- The KVM4 host rebooted unattended on 2026-09-07 at ~05:24:51 UTC (uptime 608 s
  when checked at 05:35). It killed a Playwright CI job mid-run; the whole stack
  came back on its own with `restarts=0` and both databases healthy. Cause
  unknown. Recorded because the next unexplained CI red will otherwise be blamed
  on something else.
