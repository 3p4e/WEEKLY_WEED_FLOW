# All-round review: letta-6ou3 + RAGflow stacks (2026-08-19)

> **Status as of 2026-08-22 — read this before acting on anything below.**
> The 🔴 CRITICAL finding is **CLOSED**: `SECURE=true` now reaches the server
> (the image's `startup.sh` only passes `--secure` when that variable is set),
> the `32769:8283` host publish is removed, and the LiteLLM master key has been
> rotated. Verified 200 → 401. See
> `LETTA-CUTOVER-PHASE1-2026-08-22.md` for the fix, the verification table, and
> the rotation.
>
> Item 6 of the priority list — "trace `wwf-letta` before deciding anything
> about it" — was done, and it **overturned this document's guess** that
> `wwf-letta` was dead weight: it was still the app's live Letta server. That
> trace is what the Phase 0–4 cutover was built on.
>
> **Still open and unowned:** the 🟠 RAGflow backup gap, `letta/letta:latest`
> being unpinned, and RAGflow's backing services published on `0.0.0.0`.
> Those are the reasons this file is worth keeping.
>
> No secret values are reproduced anywhere in this document, including the
> exposed key it describes.

Live infrastructure review on kvm4, requested after the DeepSeek cutover and SOP
repair-loop work landed. Read-only — nothing in this document has been acted on.
No secret values are reproduced here, including the one found exposed below.

## 🔴 CRITICAL — letta-6ou3 has no working authentication

`letta-6ou3-letta-1` runs the entire `gf_*` fleet (RAGflow retrieval tool +
credentials, DeepSeek routing) and is the server the whole cutover this session
was built around. `LETTA_SERVER_PASSWORD` is set in its environment — the intent
was clearly to require it — but it is **not enforced**:

```
GET /v1/agents/                          (no Authorization header)   -> HTTP 200, full agent list
GET /v1/agents/  Authorization: Bearer totally-wrong-garbage-token   -> HTTP 200, full agent list
```

Reproduced two ways: over `ai-net` (the internal Docker network docengine uses)
and against the **publicly published host port `0.0.0.0:32769`**. Both return
complete, real data with zero credential.

**This also leaks real credential material.** `GET /v1/providers/` — same,
zero-auth — returns each provider's `api_key_enc` field. For the `litellm`
provider this is not encrypted ciphertext: it is the literal LiteLLM master key,
in the clear, prefixed exactly as generated (`sk-...`, 51 chars — the shape of
the real key, not a hash or token). Anyone who can reach the agent API can read
it. That master key gates the DeepSeek / OpenAI / Anthropic / Moonshot / Voyage
routes on the gateway.

**Practical exposure, unauthenticated:**
- Read every agent's persona, memory blocks, and — where set — its
  `tool_exec_environment_variables` (this is where each agent's RAGflow API key
  lives).
- Send messages to any agent. Five of the eight carry `ragflow_search`, so this
  reaches the ingested lab-certificate corpus.
- `GET /v1/tools/` also answers unauthenticated. `POST /v1/tools/` accepts
  arbitrary Python `source_code` to register a new tool — this was not tested
  further (registering a tool is an action, not a read, and doing so
  unauthenticated on production infra to prove a point is not something this
  review should do), but if it is equally unguarded it is not just data
  exposure, it is arbitrary code execution in the tool sandbox.
- Create, delete, or reconfigure agents outright — i.e. disrupt or hijack the
  document pipeline this session just finished verifying end-to-end.

**What I could not verify from here:** whether the host's public IP is actually
reachable on port 32769 from the open internet, or whether a cloud/hosting-level
firewall (separate from anything on this host) already blocks it. The runner
this session operates through is itself a container with its own network
namespace, so `ss`/`iptables`/`ufw` on the real host aren't visible to it. Take
"HTTP 200 with no credential, on the published port" as the finding — the
blast radius depends on upstream network policy I don't have visibility into
and can't respond for.

**Immediate, low-risk mitigation available:** docengine talks to letta-6ou3
entirely over `ai-net` by container name (`http://letta-6ou3-letta-1:8283`) —
it never uses the published host port at all. Removing the `32769:8283`
publish from `/docker/letta-6ou3/docker-compose.yml` closes the public-internet
vector immediately with **no effect on the working pipeline**, and shrinks the
remaining exposure to the 5 containers on `ai-net` (docengine, ragflow, litellm,
ollama, letta-6ou3 itself) — all first-party. The separate question of *why*
`LETTA_SERVER_PASSWORD` isn't being enforced (a Letta config gap, a missing
flag, or a version-specific bug — `letta/letta:latest` is unpinned, see below)
is unresolved and needs its own investigation; closing the host-port publish
does not depend on answering it first.

**Not done without confirmation:** no network, auth, or credential change has
been made. This needs your go-ahead — it's a production networking change to a
service the pipeline currently depends on, and I'd rather have your sign-off
than get it wrong on my own judgment call.

**Recommend regardless of the above:** rotate the LiteLLM master key once the
exposure is closed, since it has to be treated as compromised.

## 🟠 HIGH — RAGflow has zero backup coverage

`ragflow_esdata01`, `ragflow_minio_data`, `ragflow_mysql_data`,
`ragflow_redis_data` are local, unnamed-external Docker volumes. No cron job,
no `wwf-backup-offsite` entry, no `/opt/backups/ragflow*` file of any kind
targets them. `wwf-backup-offsite` (rclone → Google Drive, confirmed running
nightly) only covers the WWF app's own Postgres DBs.

This is 255 ingested lab certificates (`eCOA_INGEST`), 81 derived per-batch
summaries (`eCOA_INGEST_SUMMA`), and 10 stability records — real proprietary
GMP data that took real ingestion time and OCR cost to build, with **no
recovery path** if the host disk fails, a volume is pruned, or MySQL/MinIO data
corrupts. Compare: the `letta-6ou3-pre-reset` backup at least exists (see
below) even though it's stale; RAGflow has nothing at any point in time.

## 🟡 MEDIUM

- **`letta/letta:latest` is unpinned.** RAGflow is correctly pinned
  (`infiniflow/ragflow:v0.26.4`); letta-6ou3 floats on `latest`. A routine
  `docker compose pull && up` could silently change server behavior — including,
  possibly, the auth behavior this review just found broken, in either
  direction. Pin to the currently-running digest so upgrades are a deliberate
  choice, not something that happens on the next restart.
- **letta-6ou3 backups are stale relative to today's work.** Both dumps
  (`letta-6ou3-pre-reset-20260816.dump`, `letta-db-20260816.dump`, plus
  `letta-app-data-20260816.tgz`) predate the DeepSeek migration, the
  context-window fix, and the SOP repair-loop work — all landed after that
  date. Lower severity than the RAGflow gap because `fleet.yaml` is the
  source of truth in git and `ensure_fleet()` is idempotent — agent
  *configuration* is trivially reconstructable — but any conversation state
  since the 16th would be lost.
- **Three separate Letta server stacks are running on this host.** Only one is
  in active use:
  - `letta-6ou3` (+ `letta-6ou3-db-1`) — **in use**, docengine's production
    target.
  - `wwf-letta` (+ `wwf-letta-db`, image `letta/letta:0.16.8-wwf`) — not on
    `ai-net`, zero requests in its logs over the last 48h. `wwf_app/app.env`
    still carries `LETTA_MCP_URL=http://host.docker.internal:6507` and several
    `LETTA_*_AGENT_ID` values pointing at a Letta instance — I did not trace
    whether those resolve through `wwf-letta`, the old `letta`, or somewhere
    else; that needs an explicit check before anything here is decommissioned.
  - `letta` (bare name, published `0.0.0.0:8283`) — **not WWF's.** It sits on
    ~14 networks shared with entirely unrelated projects on this box
    (agent-zero, coa-tracker, label-studio, supabase, qdrant,
    visual-studio-code-server). This looks like shared multi-tenant
    infrastructure outside this review's ownership. I stopped at confirming
    it answers `/v1/agents/` — I did not enumerate further, since its data
    belongs to those other projects, not this one. If its exposure is also a
    problem, that's for whoever owns those stacks, not something to fix here.

  Net: `wwf-letta` looks like dead weight pending the `app.env` trace above; the
  bare `letta` container is not this review's to touch either way.
- **RAGflow's backing services (MySQL 3306, Redis 6379, MinIO 9000-9001, ES
  1200) are all published on `0.0.0.0`.** Each one correctly requires
  authentication (verified: Redis returns `NOAUTH`, ES returns
  `security_exception`, MySQL/MinIO both carry 32-char generated passwords) —
  so this is a defense-in-depth gap, not an open-data one. Binding these to
  `127.0.0.1` (or dropping the host publish entirely, since only
  `ragflow-ragflow-cpu-1` needs them and that's over the compose network) would
  remove them from internet-facing surface without touching anything that
  currently depends on the public bind.

## 🟢 Confirmed healthy

- **docengine's own auth is correctly built**: `hmac.compare_digest`
  (constant-time), fails closed if unconfigured (`503`, not "open"), every
  route gated except the deliberately-public `/health`, and the service
  publishes no host port at all — it's `ai-net` + `weekly_weed_flow_internal`
  only. Direct contrast to the letta-6ou3 finding above.
- **RAGflow's own API correctly enforces auth**: `GET /api/v1/datasets`
  without a bearer token returns `401 Unauthorized`, not data.
- **No orphaned ephemeral agents.** `spawn_ephemeral`'s cleanup held across
  every SOP/annex run and probe this session ran — 8 agents on letta-6ou3,
  exactly the core fleet, nothing named `_tmp_` or `probe` left behind.
- **The `llm_factories.json` OpenAI-vision patch survived.** Still 20
  vision-capable OpenAI entries — the mount is holding across whatever
  restarts have happened since it was applied.
- **RAGflow ingestion is intact**: `eCOA_INGEST` 255/1,267,
  `eCOA_INGEST_SUMMA` 81/1,583, `STABILITY_PROGRAMME` 10/357 (docs/chunks) —
  unchanged from the cutover work.
- **The SOP + annex pipeline is fully verified working** (see
  `LETTA-RAGFLOW-CUTOVER-2026-08.md` and `LETTA-DEEPSEEK-VIA-LITELLM-2026-08.md`
  for the detailed runs) and this review did not touch or destabilize it —
  `docengine.documents` still holds only the two real production documents.
- **Resource headroom is fine**: nothing in either stack is under memory or CPU
  pressure; 64 GB disk free, 28% of image storage reclaimable if it's ever
  needed (the `growflow-docengine:v8`–`v19` rollback chain accounts for a real
  share of that — don't blanket-prune it).

## Priority order if you want to act on this

1. Remove the `32769:8283` publish on letta-6ou3 (no pipeline impact — confirm,
   then it's a one-line compose edit + recreate).
2. Rotate the LiteLLM master key once (1) is done.
3. Investigate why `LETTA_SERVER_PASSWORD` isn't enforced even internally, and
   fix or compensate for it (a reverse-proxy auth layer in front of `ai-net` is
   one option) — the 5-container internal blast radius is much smaller than
   "the public internet," but it's still not nothing.
4. Stand up a backup for the three RAGflow volumes — this is data that cannot
   be regenerated by rerunning code, unlike almost everything else in this
   review.
5. Pin `letta-6ou3` off `:latest` to its current digest.
6. Trace `wwf-letta` / `LETTA_MCP_URL` / the three `LETTA_*_AGENT_ID` values in
   `wwf_app/app.env` to confirm whether `wwf-letta` is actually dead, before
   deciding anything about it.
