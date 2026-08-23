# Decommissioning the old Letta deployment (`ui.srv1231216.hstgr.cloud`)

**Audience:** the agent/engineer who owns the QMS / eCoA / CoQ / sentinel
codebases. This is the hand-off for moving what still matters off the old Letta
server and onto **`letta-6ou3`**
(`https://letta-6ou3.srv1231216.hstgr.cloud`) — a stock Letta server, image `letta/letta:latest`/`0.16.8`, the same image the old server ran. It is NOT `letta-ai/letta-code` (a separate CLI product); an earlier draft of this migration's docs used that name in error.

**Status: STOPPED as of 2026-08-23 04:04 UTC.** Step 1 of "Suggested order of
work" below is done — see the "Execution record" section near the end for
exactly what ran and what was verified afterward. Nothing has been deleted
except the two containers step 1 always intended to remove (`wwf-letta`,
`wwf-letta-db` — already stopped in a prior session, snapshot verified, volume
and image kept). The rest of this document — which agents to keep, how to
rebuild them on `letta-6ou3`, and how to repoint the three consumers — is
still open work and unaffected by the stop.

Companion document: `LETTA-CUTOVER-PHASE1-2026-08-22.md` covers the *WWF app's*
own migration — a different, already-completed job. The app no longer touches
either old server.

---

## 🔴 Read this first: the old server is on the public internet with no auth

```
GET https://ui.srv1231216.hstgr.cloud/v1/agents/     (no Authorization header)
  -> HTTP 200, full agent list as JSON
```

Verified twice, from outside the Docker network. This is not one misconfigured
route — the whole `/v1` API is exposed:

- Every one of the **66 agents'** personas and memory blocks is readable by
  anyone who knows the hostname.
- Agent `tool_exec_environment_variables` are readable — that is where
  per-agent API keys live.
- Anything readable is also writable: agents can be messaged, reconfigured,
  created or deleted.

Its credentials make this worse, and both sit in plaintext in the container env:

| Variable | Value |
| --- | --- |
| `LETTA_SERVER_PASS` | `letta-master-key` |
| `LETTA_PG_URI` password | `letta_password_123` |

These are guessable defaults. Treat both as compromised, and treat any key
stored *inside* an agent on this server as compromised too.

**This is the same class of bug found and fixed on `letta-6ou3` on 2026-08-22**
(its image only passes `--secure` when `SECURE=true`; see the cutover doc). The
fix did not apply here because this is a separate stack.

**Consequence for planning:** stopping this stack is not merely tidy-up, it
closes a live exposure. If migration work has to be scheduled rather than done
now, stopping the stack *first* and restarting it privately for the migration is
the safer order.

---

## What "the old Letta deployment" actually is

One Docker Compose project, **`letta`**, at **`/opt/stacks/letta`** — five
services, not one:

| Container | Image | Public route | Role |
| --- | --- | --- | --- |
| `letta` | `letta/letta:latest` | `ui.srv1231216.hstgr.cloud/v1` | the server itself, port 8283 |
| `letta-postgres` | `pgvector/pgvector:pg15` | — | its database (all 66 agents live here) |
| `letta-mcp-rust` | `ghcr.io/oculairmedia/letta-mcp-server-rust` | `mcp-letta.srv1231216.hstgr.cloud` | MCP bridge, port 6507 |
| `qms-api` | `qms-api:latest` | — (host port 8500) | consumer |
| `suma-api` | `suma-api:latest` | — (host port 8501) | consumer |

Because they are one compose project, `docker compose stop` in that directory
takes down all five together — which is what "stop everything connected to the
old Letta" means in practice.

Volumes (**do not delete any of these**):

- `letta_postgres_data` — the 66 agents and 5,934 messages
- `letta_letta_data` — the server's `/root/.letta`
- one anonymous volume on `letta` at `/var/lib/postgresql/data` (unused stub)

### Related but separate

- **`letta-scy7`** (`/docker/letta-scy7`, `lettaai/letta:latest`, routed at
  `letta-scy7.srv1231216.hstgr.cloud`) is a **completely empty** server: 0
  agents, 0 messages, never used. Not part of this stack, nothing depends on
  it. Stopping it is free.
- **`wwf-letta` / `wwf-letta-db`** — the WWF app's own old Letta. Already
  stopped and snapshotted on 2026-08-22. Separate stack, separate document.

---

## Verified snapshots (taken before anything was touched)

| File | Size | Verification |
| --- | --- | --- |
| `/opt/backups/old-letta-db-20260823-preshutdown.sql.gz` | 142,909,154 B | `gzip -t` OK; `-- PostgreSQL database dump complete` present; 49 `CREATE TABLE` = 49 live tables; **agents 66**; **messages 5,934 in dump = 5,934 live** |
| `/opt/backups/old-letta-appdata-20260823-preshutdown.tgz` | 88,505,798 B | `tar -t` OK |

The dump is a complete `pg_dump` of the `letta` database. **Everything this
document summarises — every persona, memory block, tool source, and message —
is inside it.** Prefer reading the dump over trusting this summary when
rebuilding.

Restore into a scratch Postgres to inspect, without restarting the old server:

```bash
docker run -d --name letta-inspect -e POSTGRES_USER=letta \
  -e POSTGRES_PASSWORD=x -e POSTGRES_DB=letta pgvector/pgvector:pg15
zcat /opt/backups/old-letta-db-20260823-preshutdown.sql.gz \
  | docker exec -i letta-inspect psql -U letta -d letta
```

---

## What is on the old server

**66 agents, all of them used at least once** (zero agents have no messages).
Model mix as stored: `deepseek-v4-pro` ×31, `deepseek-v4-flash` ×17,
`deepseek-reasoner` ×7, `gpt-4o` ×7, `deepseek-chat` ×4.

### Still active in August — migrate these first

| Agent | Messages | Last used |
| --- | --- | --- |
| `sentinel_analyst` | 3,185 | 2026-08-16 |
| `sentinel_journal` | 230 | 2026-08-16 |
| `sentinel_risk_officer` | 55 | 2026-08-12 |
| `VariationF-Spec-Author` | 9 | 2026-08-14 |
| `VariationF` | 7 | 2026-08-14 |
| `imb_qc_coa_agent` | 221 | 2026-08-12 |
| `ecoa_retrieval_gpt4o` | 211 | 2026-08-12 |
| `Specification Advisor Agent` | 39 | 2026-08-10 |

These eight are the only ones with activity in the two weeks before the
cutover. **Everything else is dormant** — the next most recent is 2026-07-19.

### Already migrated — do NOT rebuild

The eight `gf_*` document-fleet agents exist on **both** servers; the
letta-6ou3 copies are the live ones (built from `docengine/agents/fleet.yaml`,
which is the source of truth and is idempotent). Their old copies stop at
2026-07-19 because the fleet moved on 2026-08-17.

Likewise the `planner-*` family (`planner-weekly-report`,
`planner-next-week-plan`, `planner-template-narrative`, `planner-task-rewrite`,
`planner-executive-analytics`) is **superseded** by `wwf_weekly_report` /
`wwf_next_week_plan` / `wwf_coordinator` on letta-6ou3. Do not port them.

### Dormant families (decide keep-or-drop per family)

- `qms_*` (5) — SOP expert, GMP auditor, docx formatter, pipeline orchestrator
- `pp_annex_*` (5) — orchestrator / translator / body formatter / table specialist / auditor
- `ars_*` (5) — integrity verifier, devil's advocate, field analyst, collaboration depth, orchestrator
- `VariationF-*` (the remaining ones) — iCoA-Author, CoQ-Aggregator, Compliance-Sentinel
- CoQ/CoA set — `CoQ Assembly Agent`, `CoA Ingestion Agent`,
  `Parameter Extraction Agent`, `Compliance Analysis Agent`,
  `Report Generation Agent`, `Search Assistant Agent`
- singles — `gmp_rag_agent`, `eu_gmp_compliance_expert`, `ecoa-qc-agent`,
  `pq1_water_qc_agent`, `equipment_manuals_agent`,
  `warehouse_quarantine_ocr_agent`, `wwf-bilingual-translator`,
  `wwf_weekly_coordinator`, `wwf_qms_architect`, `wwf_schema_advisor`,
  `letta_manager`, `letta_chat_interface`, `code_reviewer`, `security_auditor`,
  `web_design_reviewer`, `pharma_docx_formatter`,
  `fastapi_letta_qms_patterns`, `excalidraw_diagram_generator`,
  `penpot_uiux_design`, `weekly_report_analyst`, `executive_summarizer`,
  `trend_detector`

### Custom tools (7) — none of these exist on letta-6ou3

| Tool | Type | Source | Purpose |
| --- | --- | --- | --- |
| `build_pp_document` | python | 2,072 B | bilingual MK\|EN controlled `.docx` from bilingual Markdown |
| `fetch_pp_document` | python | 537 B | return a generated `.docx` from `/opt/pp-out` as base64 |
| `pp_ocr_scanned_pdf` | json | 6,488 B | OCR a scanned PDF certificate via an OpenAI vision model |
| `validate_gmp_section` | json | 1,866 B | validate SOP section content against EU GMP |
| `perplexity_search` | json | 1,926 B | autonomous web research for GMP regulations |
| `generate_mermaid_flowchart` | json | 1,304 B | Mermaid flowchart from structured steps |
| `format_raci_matrix` | json | 1,092 B | RACI matrix as a markdown table |

`build_pp_document` and `fetch_pp_document` are each attached to the same nine
agents: `qms_sop_expert`, `qms_docx_formatter`, `qms_pipeline_orchestrator`,
`pharma_docx_formatter`, and all five `pp_annex_*`. **Porting any of those nine
without porting both tools produces an agent that cannot do its job.**

Extract sources from the dump with:

```sql
select name, source_type, source_code from tools where tool_type = 'custom';
```

Note that `build_pp_document` / `fetch_pp_document` read and write **`/opt/pp-out`
on the Letta host**. letta-6ou3 is a different container with a different
filesystem — that path must be provisioned there, or the tools rewritten to
return bytes directly.

### What is already on letta-6ou3

11 agents — the 8 `gf_*` plus `wwf_weekly_report`, `wwf_next_week_plan`,
`wwf_coordinator` — and exactly **one** custom tool, `ragflow_search`.

---

## Why this is not a lift-and-shift

**1. Model handles differ.** The old server stores bare handles
(`deepseek-v4-pro`, `gpt-4o`, `deepseek-reasoner`, `deepseek-chat`) resolved by
its own `LETTA_LLM_PROVIDER=deepseek`. letta-6ou3 routes **through the LiteLLM
gateway on `ai-net`** and uses `deepseek/deepseek-v4-flash`. Restoring the old
dump into letta-6ou3 would import 66 agents pointing at handles that server does
not serve.

**2. Letta's DeepSeek provider is broken for v4 models.** Documented in
`docs/LETTA-DEEPSEEK-VIA-LITELLM-2026-08.md` and encoded in
`docengine/agents/fleet.yaml`. Two independent failures:

- `provider_type: "deepseek"` drops every current model — its hardcoded
  context-window map knows only `deepseek-chat` / `deepseek-reasoner` and
  returns `None` (= skip) for `v4-*`.
- v4 models default to thinking mode and then reject any follow-up turn that
  does not echo `reasoning_content` back, which Letta never does — so every tool
  call dies on its second hop. LiteLLM disables thinking via `extra_body`.

**Therefore: it must go through LiteLLM, never straight at `api.deepseek.com`.**

**3. Context window must be set explicitly.** Letta sizes an unknown model from
`LLM_MAX_CONTEXT_WINDOW["DEFAULT"] = 30000`, far below what the model takes.
That already broke a real run (a 9-section SOP repair truncated mid-section).
Pass `context_window_limit: 128000` and `max_tokens: 16384` at creation, as
`fleet.yaml` does.

**4. The 7 `gpt-4o` agents need a funded OpenAI route.** As of 2026-08-17
letta-6ou3's own OpenAI key reported "no credits remaining" and its Anthropic
key "credit balance is too low". Route them via LiteLLM or re-fund before
porting `warehouse_quarantine_ocr_agent`, the `VariationF-*` set, and
`ecoa_retrieval_gpt4o`.

**5. Do not point anything at local Ollama models.** Verified live: `phi4-mini`,
asked a retrieval question, invented both a source filename and an out-of-range
analytical finding. Fabricating pharmaceutical data is the one thing the house
rules forbid outright.

**Recommendation: rebuild declaratively, do not restore the dump.** Follow the
`fleet.yaml` + `fleet.py` pattern already proven for the `gf_*` fleet — a YAML
manifest of personas plus an idempotent `ensure_fleet()` that creates missing
agents by name. That converts "migrate 58 agents" into "declare the ones still
wanted", which for the dormant families is likely far fewer.

---

## ~~Consumers that must be repointed~~ — corrected 2026-08-23: none are live WWF dependencies

The three containers below carry `LETTA_URL`/`LETTA_BASE_URL=http://letta:8283`,
which looked like an active dependency chain. A full code-level audit of this
repo (`git grep` across `backend/`, `docengine/`, `web/`, `qms-creator/` — see
`AI-FEATURE-INVENTORY-2026-08-23.md`) found **none of them are actually called
by the running WWF app**:

| Container | Reality |
| --- | --- |
| `qms-api` | This is the **`qms-creator/` app's own container** (separate deployable, own compose stack, imported into this repo 2026-07-15 as "nothing under `qms-creator/` is imported by `backend/` or `web/`"). The WWF backend's *own* QMS federation proxy (`backend/app/api/qms.py`, hitting the *same default hostname* `qms-api:8000`) has had `QMS_API_KEY` unset in every environment since the 2026-07-16 retirement (`docs/DEPLOY.md` §"qms-api (Phase-1 QMS registry) retired") — confirmed still unset in prod `app.env` tonight. The frontend doesn't even attempt the call any more: `web/gf/qmsknow-view.js` hardcodes "Knowledge search retired (503)" without hitting the network. Also carries `LETTA_DAEMON_URL=http://letta-daemon:8420` pointing at a container that doesn't exist anywhere on this host — a second sign this instance is orphaned, not live infrastructure. **No repoint needed for WWF's sake.**
| `suma-api` | Zero references anywhere in `backend/` or `web/` — grep confirms nothing in this repo calls it. It belongs to the separate SUMA/ISO17 product line (`docs/DEPLOY.md`'s "SUMA assimilation" section). **Out of scope for this app's migration.**
| `letta-mcp-rust` | The `LETTA_MCP_URL` setting it would be reached through (`backend/app/config.py`) is dead code — no backend module reads it, confirmed by grep and already dropped from `.env.example` in this migration. `docengine/` explicitly avoids it ("direct REST — deliberately not the Rust MCP bridge — documented decode bug"). Likely serves **operator/tooling MCP access** (e.g. a Claude Code session's Letta MCP connector) rather than the app runtime. **Not an app dependency; repoint only if an operator wants MCP tooling access to letta-6ou3 instead of the old server.**

None of this changes the 🔴 finding at the top of this document — the old
server's `/v1` API being unauthenticated and public is exactly as serious
regardless of whether anything still calls it. It does mean the "repoint three
consumers" step is not blocking, and can be dropped from the critical path if
you'd rather retire `qms-api`/`suma-api` outright than migrate them.

If `letta-mcp-rust` IS repointed for operator convenience, the same two changes
apply as they did for the WWF backend on 2026-08-22: new target
`http://letta-6ou3-letta-1:8283` over the **`ai-net`** Docker network (it isn't
on that network today, so it cannot resolve the new hostname at all —
`socket.gaierror: [Errno -3] Temporary failure in name resolution` is the
symptom), plus `LETTA_API_KEY` = letta-6ou3's `LETTA_SERVER_PASSWORD`.

---

## Execution record — the stop (2026-08-23 04:04 UTC)

Run from this session, using the runner `/shell` path, mirroring the plan
below exactly. In order:

1. Both snapshots (`old-letta-db-20260823-preshutdown.sql.gz`,
   `old-letta-appdata-20260823-preshutdown.tgz`) re-verified: `gzip -t` clean,
   dump-complete marker present, `tar -t` clean.
2. `wwf-letta` / `wwf-letta-db` (already `exited` from a prior session)
   removed with `docker rm`. Verified still present afterward: volume
   `wwf_mass_letta_pgdata`, image `letta/letta:0.16.8-wwf`.
3. `letta-scy7-letta-1` / `letta-scy7-db-1` (0 agents, 0 messages, unused)
   stopped.
4. `cd /opt/stacks/letta && docker compose stop` — all five services
   (`letta-mcp-rust`, `suma-api`, `qms-api`, `letta`, `letta-postgres`)
   stopped cleanly, in that order, exit 0 each.
5. Verified the public exposure this document opened with is closed:

   | Check | Before | After |
   | --- | --- | --- |
   | `GET https://ui.srv1231216.hstgr.cloud/v1/agents/` (no auth) | 200, full agent list | **404** |
   | `GET https://mcp-letta.srv1231216.hstgr.cloud/` | reachable | **404** |

   404 here means Traefik has no live backend to route to — the routers
   still exist (nothing in Traefik's own config was touched), they just have
   nothing running behind them.
6. Volumes confirmed still present: `letta_letta_data`, `letta_postgres_data`,
   `wwf_mass_letta_pgdata`.
7. WWF app and `letta-6ou3` confirmed unaffected by the stop:

   | Check | Result |
   | --- | --- |
   | backend `/health/ready` | `{"ready":true,"databases":{"users":"ok","tasks":"ok"}}` |
   | backend → `letta-6ou3` | HTTP 200, 11 agents |
   | `https://wwf.srv1231216.hstgr.cloud` | HTTP 200 in 23 ms |
   | `https://letta-6ou3.srv1231216.hstgr.cloud/v1/agents/` (no auth) | **401** — still enforced |

**What this did NOT do:** decide which of the 58 dormant agents to keep, port
any custom tool, repoint `qms-api` / `suma-api` / `letta-mcp-rust`, or rotate
any credential. Those containers are stopped, not migrated — see "What is on
the old server" and "Consumers that must be repointed" above for that work.

**Rollback**, if anything below turns out to need the old server back before
migration work starts:

```bash
cd /opt/stacks/letta && docker compose start
docker start letta-scy7-db-1 letta-scy7-letta-1
```

`wwf-letta` / `wwf-letta-db` cannot be rolled back the same way — they were
`rm`'d, not merely stopped — but the volume and image are intact, so they can
be recreated from `/opt/stacks/wwf_app/compose.yaml.bak-pre-letta6ou3-20260822`
(WWF app's own compose backup) if ever needed; the snapshot is the safety net
either way.

## Suggested order of work

1. **Stop the stack** to close the public exposure (commands below). The
   snapshots are verified; this is reversible.
2. Decide, per dormant family, keep or drop. Most of the 58 are likely drop.
3. For those kept: port the custom tools first (nine agents are useless without
   `build_pp_document` + `fetch_pp_document`), then declare the agents in a
   `fleet.yaml`-style manifest with explicit `context_window_limit` and LiteLLM
   model handles.
4. ~~Repoint and re-network `qms-api`, `suma-api`, `letta-mcp-rust`~~ — not
   needed for the app; see the corrected "Consumers" section above. Only
   `letta-mcp-rust` is worth repointing, and only for operator MCP tooling
   access, not app correctness.
5. Rotate every credential that lived on the old server — the master key was
   `letta-master-key` on an unauthenticated public endpoint.
6. Retire the `ui.` and `mcp-letta.` Traefik routes once nothing needs them.

### Commands

```bash
# stop everything in the old stack (all five services)
cd /opt/stacks/letta && docker compose stop

# the empty, unused extra server
docker stop letta-scy7-letta-1 letta-scy7-db-1

# rollback — nothing is deleted by the above
cd /opt/stacks/letta && docker compose start
```

**Never** `docker compose down -v`, and never prune volumes: `letta_postgres_data`
is the only live copy of the 66 agents besides the snapshot.
