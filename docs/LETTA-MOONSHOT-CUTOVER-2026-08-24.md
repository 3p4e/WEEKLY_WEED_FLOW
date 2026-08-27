# letta-6ou3 fleet switched to Moonshot Kimi K2.6 (2026-08-24)

Owner directive: pick a model provider for "all Letta Code AI functions" from
Moonshot AI, DeepSeek, or OpenAI, decide on Moonshot, and set it up. RAGflow
stays the RAG/ingestion engine for eCOA/iCOA/CoQ and EU-GMP regulatory
knowledge unchanged — this only concerns the LLM backing the agents
themselves.

**Status: done and verified.** All 11 agents on letta-6ou3 (the 8 `gf_*`
document-fleet agents + the 3 `wwf_*` scheduler planners) now run
`openai-proxy/moonshot/kimi-k2.6`, moved in place via `PATCH
/v1/agents/{id}` — no agent was deleted or recreated, so accumulated
memory/history on every agent survived the switch.

## The key

LiteLLM already had a `moonshot/*` provider entry and a `MOONSHOT_API_KEY` in
`/opt/stacks/litellm/.env` from earlier provisioning, but it had never been
wired into any agent — and the stored key turned out to be dead (well-formed,
51 chars, but LiteLLM got a clean 401 `AuthenticationError` from Moonshot on
test). The owner supplied a fresh key. It was staged to a `chmod 600` file on
kvm4, substituted into the existing `MOONSHOT_API_KEY=` line (backup:
`.env.bak-20260824-moonshot-rotate`), the staging file `shred -u`'d, and the
`litellm` container recreated (`--force-recreate`, `--no-deps`) so the new
value actually loads — LiteLLM only reads `.env` at container start.

## Model choice: Kimi K2.6, not K3, not moonshot-v1-*

Researched against Moonshot's live docs, not training data — several of
these models postdate every earlier session's knowledge:

- **`moonshot-v1-*`** (the whole classic series, still present in LiteLLM's
  bundled static cost-map) — Moonshot is **retiring it entirely on
  2026-08-31**, six days after this cutover. Never point anything at it.
- **Kimi K3** (current flagship, 1M context) — reasoning is **always on with
  no way to disable it**, and Moonshot's own docs require echoing
  `reasoning_content` back on every follow-up turn. That is *exactly* the
  failure mode that broke DeepSeek v4's direct-to-provider integration
  (`docs/LETTA-DEEPSEEK-VIA-LITELLM-2026-08.md`): Letta never echoes
  reasoning content back, so every tool call died on its second hop. There is
  no LiteLLM-side fix available for K3 the way there was for DeepSeek,
  because there's nothing to disable. Held back from the fleet for this
  reason.
- **Kimi K2.6** (general-purpose, 262,144-token context, vision) — thinking
  defaults on but *can* be disabled (`extra_body:
  {"thinking":{"type":"disabled"}}`), the same shape of fix that made
  DeepSeek v4 work. A previously-reported LiteLLM bug in exactly this area
  (`reasoning_content missing in assistant tool call message during
  multi-turn tool calling`, GitHub BerriAI/litellm#21672) is closed, fixed by
  PR #23580; the LiteLLM build running here
  (`ghcr.io/berriai/litellm:main-stable`, pulled 2026-08-22) postdates that
  fix. Cheaper than K3 too: $0.95/$4.00 vs $3.00/$15.00 per M input/output
  tokens.

## Verification (the real bar, not a smoke test)

Two levels, both live:

1. **Raw multi-turn tool-calling through LiteLLM directly** (`moonshot/kimi-k2.6`,
   `extra_body` thinking disabled): turn 1 returned a correctly-formed
   `tool_calls` response; turn 2, given the echoed assistant message + a tool
   result, completed cleanly with the exact expected answer. No
   `reasoning_content` error.
2. **A real Letta agent, in production config** — `gf_app_assistant`
   (patched first: zero live callers in the codebase, safest to test on)
   asked a genuine retrieval question. Result: two clean `reasoning_message`
   steps (Letta separates thinking cleanly into its own message type — no
   `extra_body` flag was set anywhere for this call, and it still worked),
   a correctly-scoped `ragflow_search` tool call (only the agent's permitted
   datasets), a real tool return, and a final answer quoting an exact,
   correct value with its exact source document:
   > **Batch:** CJ062501-2 (Cap Junkie) · **Total Δ9-THC:** 18,91 % (U: 1,16 %)
   > · **Source document:** `BUNDLE_CapJunkie_CJ062501-2_full_panel.txt`

   This is the same bar `fleet.yaml`'s own comment sets for the DeepSeek
   verification, and it passed without needing the `extra_body` workaround at
   all — Letta's agent loop appears to manage the reasoning/tool-call
   round-trip correctly on its own for this provider.

`wwf_coordinator` (one of the three scheduler planners, different system
prompt shape than the `gf_*` fleet) was sanity-checked separately with a
trivial message after its own PATCH — 200, correct reply. `docengine`'s own
`/health` still reports `{"ok":true,"db":true,"letta":true}` after all 11
switches.

## The mechanism, and a wrong assumption corrected mid-task

`fleet.yaml`'s `defaults.model` was updated to the Moonshot handle, but that
**alone would have done nothing** for the 11 already-existing agents.
`fleet.py:ensure_fleet()` is deliberately create-if-missing only — its own
comment says the server used to reject a model/provider config write on an
already-existing agent. That comment turns out to describe the *old*
`llm_config` object specifically (still present in the API, now marked
`deprecated: "Use model field instead"`). The **current** server
(`letta/letta` 0.16.8, upgraded 2026-08-17) exposes a first-class, non-deprecated
`model: string` field on `PATCH /v1/agents/{agent_id}` — format
`"provider/model-name"`, exactly the same string shape `fleet.yaml` already
uses. That's what actually moved the 11 live agents; `fleet.yaml` only
governs what a *newly created* agent gets from here on.

Confirmed served handle before using it: `openai-proxy/moonshot/kimi-k2.6`
appears in letta-6ou3's own `/v1/models/` listing (**not** `kimi-k3`, which
is absent from that list — irrelevant here since K3 wasn't the choice, but
worth knowing if a future session reaches for it).

## What did not change

- **RAGflow** stays the RAG/ingestion engine for eCOA, iCOA, CoQ, and
  EU-GMP regulatory knowledge, per the owner's explicit directive — this
  cutover is model-provider only.
- **Embeddings** — RAGflow already uses `voyage-3-large` (Voyage AI);
  letta-6ou3's own internal archival/recall memory already uses local Ollama
  `nomic-embed-text`. Neither needed a change; both were already configured
  before this task started.
- **`context_window`/`max_tokens`** in `fleet.yaml` (128000 / 16384) were
  left as-is — still well inside K2.6's 262,144-token window, and the
  original reasoning for 128k (headroom for a full SOP-repair round without
  truncation) is provider-independent.
- **DeepSeek v4-flash** stays documented as a working fallback (previously
  verified the same way) — not removed, just no longer the default.

## Open items

- LiteLLM's `.env` and `config.yaml` are host-managed (`/opt/stacks/litellm/`),
  not deployed from this repo — same panel-mirror caveat noted in
  `LETTA-CUTOVER-PHASE1-2026-08-22.md` for letta-6ou3's own compose file
  applies here if this stack is ever panel-managed.
- No repo-tracked provenance copy of `litellm/config.yaml` exists in this
  repo (`ops/stacks/litellm.config.yaml` was flagged in an earlier session as
  a provenance copy, not the live file) — worth reconciling at some point so
  the Moonshot provider entry isn't only visible by SSHing into kvm4.
