# Letta migration: wwf-letta → letta-code (letta-6ou3) — Phase 0/1, 2026-08-22

Owner directive: rewire every app AI function/engine/agent off the old Letta and
onto **letta-code**, with the sequence *fix letta-code security first → full
migration → trace, snapshot, then stop `wwf-letta`*.

This document records what was **traced** (Phase 0) and what was **changed**
(Phase 1). Phases 2–5 are not started. No secret value appears here.

## Phase 0 — the trace, and what it corrected

`LETTA-RAGFLOW-SECURITY-REVIEW-2026-08.md` §MEDIUM guessed `wwf-letta` was "dead
weight" from 48 h of quiet logs, and left an explicit action: trace `app.env`
before decommissioning anything. **That trace now says the opposite — the guess
was wrong.**

| consumer | `LETTA_BASE_URL` | resolves to | server |
|---|---|---|---|
| `weekly_weed_flow-backend-1` | `http://letta:8283` | `172.16.31.6` | **`wwf-letta`** |
| `wwf-scheduler` | `http://letta:8283` | `172.16.31.6` | **`wwf-letta`** |
| `wwf-docengine` | `http://letta-6ou3-letta-1:8283` | — | letta-code ✅ |

`letta` is a **network alias of the `wwf-letta` container** on the network it
shares with the backend — not the unrelated multi-tenant `letta` container
(whose addresses are all `172.16.1x/2x.x`). So `wwf-letta` is **live app
infrastructure**: it still backs the backend `/ai` catalog and the weekly
snapshot. It is quiet because those paths are infrequent (a weekly scheduler run
plus on-demand `/ai`), not because they are gone.

Bound on the old server, and therefore blocking a clean disconnect:

- `LETTA_WEEKLY_REPORT_AGENT_ID`, `LETTA_COORDINATOR_AGENT_ID`,
  `LETTA_NEXT_WEEK_PLAN_AGENT_ID` (three agent ids, backend **and** scheduler)
- `LETTA_SNAPSHOT_SOURCE_ID` — a Letta RAG *source*; letta-code has no Letta
  sources at all (retrieval is RAGflow), and `GrowFlow_Weekly_Snapshots` is
  still in `fleet.yaml`'s `ragflow.pending_ingest`
- every `ai_agent_bindings.letta_agent_id` row, which names agents that exist
  only on the old server

`qms-creator` / `qms-api` still reference Letta but are retired platform-wide
(`QMS_API_KEY` blanked 2026-07-16); nothing there needs cutting over.

## Phase 1 — letta-code security: 🔴 CRITICAL closed

The review found letta-6ou3 answering `/v1/agents/` with **no credential** and
leaking the LiteLLM master key through `/v1/providers/`, and deliberately
stopped without acting. Both are now closed.

**Root cause** (the review left this "unresolved… needs its own investigation"):
the image's `letta/server/startup.sh` only appends `--secure` when `SECURE=true`

```sh
CMD="letta server --host $HOST --port $PORT"
if [ "${SECURE:-false}" = "true" ]; then CMD="$CMD --secure"; fi
```

`LETTA_SERVER_PASSWORD` was set, `SECURE` was not — so the password was loaded
and never enforced. Not a Letta bug, a missing flag.

**Changes to `/docker/letta-6ou3/docker-compose.yml`** (backups
`docker-compose.yml.bak-20260822-presecure`, `.env.bak-20260822-presecure`):

1. added `SECURE: "true"`
2. removed the `ports: ["8283"]` publish — the short form was binding a random
   host port (`0.0.0.0:32770→8283`; the review saw `32769`, proving it drifts on
   every restart)

then `docker compose -p letta-6ou3 up -d`.

**Verified after the recreate**

| check | before | after |
|---|---|---|
| `GET /v1/agents/` no credential (over `ai-net`) | 200 + full agent list | **401** |
| same call with docengine's `LETTA_API_KEY` | 200 | **200** |
| published host port | `0.0.0.0:32770→8283` | none (`8283/tcp` only) |
| `letta-6ou3-letta-1` | — | `running`, `restarts=0` |

Safe because docengine's `LETTA_API_KEY` and letta-6ou3's
`LETTA_SERVER_PASSWORD` were confirmed **identical** (SHA-256 compared, values
never printed) *before* enforcement was switched on — so the one live consumer
was already sending the right bearer. The Traefik route stays, and is now
password-gated like the internal path.

## LiteLLM master-key rotation — DONE

The key had to be treated as compromised (it was readable unauthenticated
through `/v1/providers/` until the fix above). Rotated once kvm4 recovered
(loadavg 55 -> 0.5).

Sequence, both sides swapped back-to-back: new key generated on the box (never
printed) -> litellm `.env` (backup `.env.bak-20260822-rot2`) -> recreate litellm
-> `PATCH /v1/providers/provider-a0f4c547-3651-4a17-8824-a24332776e17` on
letta-code with the same value -> verify -> `shred -u` the staged key.

| check | result |
|---|---|
| `GET /v1/models` with the NEW key | **200** |
| same with the OLD key | **400** — rejected, no longer the master key |
| same with no key | **401** |
| letta-code `/v1/models/` (its patched provider credential) | **377 handles**, DeepSeek routes present |
| `litellm`, `letta-6ou3-letta-1` | `running`, **restarts=0** |

Two gotchas worth keeping:

- **Compose project name matters.** `docker compose up -d` run from a mounted
  directory defaulted the project to the mount name and tried to *create* a
  second `litellm` (name conflict) instead of replacing it. The running
  container has `com.docker.compose.project=litellm` — pass `-p litellm`.
- **Bind mounts resolve on the HOST, not in the helper container.** Running
  compose with the stack bind-mounted at `/w` made Docker resolve
  `./config.yaml` against a path that did not exist on the host and create an
  empty **directory**, so litellm crash-looped on
  `IsADirectoryError: /app/config.yaml`. The host file was never touched. Fix:
  mount the stack at its real path and `-w` there, so relative binds resolve
  identically to a host-side `docker compose`.

### Inference failures seen during verification are NOT from the rotation

Two upstream faults were visible while testing, both pre-existing and unrelated
— the authenticated proxy path itself is proven by the fact that these errors
come back *through* it:

- `deepseek/deepseek-v4-flash` hangs with no response and no litellm log line —
  upstream DeepSeek latency/availability. An unconfigured model name returns a
  clean `400` on the same path, so routing and auth are fine.
- `local-*` (Ollama) returns `500 Ollama_chatException - llama-server process
  has terminated: signal: killed` — the OOM kill is a casualty of the loadavg-55
  spike, not of this work.

Neither blocks the cutover, but **`gf_*` document runs use
`openai-proxy/deepseek/deepseek-v4-flash`**, so DeepSeek reachability should be
re-checked before Phase 3 verification depends on a live agent turn.

## Open item worth its own attention

`AI-STACK-2026-08.md` §3 records that panel-managed `/docker/*` stacks are meant
to be changed **through the Hostinger API**, because a panel redeploy overwrites
direct host edits. The Phase 1 fix above is a direct host edit: correct and live
now, but it should be **mirrored into the panel's compose for `letta-6ou3`** so
a future panel action cannot silently reopen the port or drop `SECURE`. That
mirror needs either a working API path or a manual panel paste.

## What Phase 2+ still needs

1. letta-code has **no planner agents** — nothing to bind `weekly_report`,
   `next_week_plan`, `template_narrative`, … to. Owner chose to create them
   **directly on letta-6ou3** and reconcile into `3p4e/letta-stack` later
   (fleet development lives there per `docengine/DEPRECATED.md`, which is out of
   this repo's scope).
2. `GrowFlow_Weekly_Snapshots`, `DB1_REGULATORY`, `DB3_PP_CURRENT_unified` are
   still un-ingested in RAGflow.
3. Only then: repoint backend + scheduler, rebind `ai_agent_bindings`, verify,
   and finally snapshot and stop `wwf-letta` — **keeping** the
   `wwf_mass_letta_pgdata` volume, which `ops/README.md` flags as live
   production data despite its name.
