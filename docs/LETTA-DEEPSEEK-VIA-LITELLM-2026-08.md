# DeepSeek on letta-6ou3, via LiteLLM — and why not directly (2026-08-17)

Owner asked for DeepSeek plus the Ollama/OpenAI-compatible locals to be wired up
as working Letta models while the OpenAI and Anthropic accounts are topped up.
Done: the `gf_*` fleet now runs on DeepSeek and **makes real, verified
`ragflow_search` tool calls**. That closes the blocker left in
`LETTA-RAGFLOW-CUTOVER-2026-08.md`.

## Final state

| | value |
|---|---|
| fleet model | `openai-proxy/deepseek/deepseek-v4-flash` (DeepSeek v4-flash via LiteLLM) |
| fleet embedding | `ollama-local/nomic-embed-text:latest` (local, free, dim 768) |
| Letta providers added | `litellm` (openai type → `http://litellm:4000/v1`), `ollama-local` (ollama type) |
| DeepSeek balance at setup | **$3.00** — the key already existed in RAGflow's `tenant_llm` |
| gf_ agents | all 8 recreated on this route; 5 with a corpus carry the tool |

`docengine/agents/fleet.yaml` declares both handles; `fleet.py` now honours the
declaration whenever the server serves it (see "The precedence bug" below).

## Why NOT straight at api.deepseek.com

Letta has a native `deepseek` provider type. It does not work with current
DeepSeek models, for two independent reasons — both confirmed live.

**1. Every current model is silently dropped.**
`letta/schemas/providers/deepseek.py` overrides
`get_model_context_window_size()` with a hardcoded map that knows only
`deepseek-chat` and `deepseek-reasoner`, returning `None` for anything else.
`_do_model_checks_for_name_and_context_size` treats `None` as "skip". DeepSeek's
`/models` today returns exactly `deepseek-v4-flash` and `deepseek-v4-pro`, so
**all** models are filtered out:

```
Letta.letta.services.provider_manager - INFO - Processing 0 LLM models for provider deepseek
Letta.letta.schemas.providers.openai - INFO - No context window size found for model: deepseek-v4-flash
```

The source even carries `# TODO (cliandy): this may need to be updated to
reflect current models`. Note `OpenAIProvider` does **not** have this problem —
its version falls back to `LLM_MAX_CONTEXT_WINDOW["DEFAULT"]` and never returns
`None`. So registering DeepSeek as an **`openai`-type provider with a DeepSeek
`base_url`** already fixes the dropped models, with no patching of Letta.

**2. Thinking mode breaks the tool loop on the second hop.**
`deepseek-v4-*` default to thinking mode, and DeepSeek then rejects any
follow-up turn whose assistant message does not echo `reasoning_content` back:

```
400 The `reasoning_content` in the thinking mode must be passed back to the API.
```

Letta never echoes it. The first hop (model emits a tool call) succeeds, Letta
appends the tool result and calls again, and that second hop always 400s — so
every tool call dies. Isolated against the raw API with a 3-message
user/assistant-tool_call/tool conversation:

| request | result |
|---|---|
| `deepseek-v4-flash`, as-is | FAIL — `reasoning_content` must be passed back |
| `+ "thinking": {"type": "disabled"}` | **OK** |
| `+ "reasoning_effort": "none"` | **OK** |
| `deepseek-v4-pro`, as-is | FAIL (same) |
| `deepseek-v4-pro + thinking disabled` | **OK** |

Letta cannot send either param: `LLMConfig.reasoning_effort` exists and accepts
`"none"`, but `openai_client.py:624` only forwards it when
`is_openai_reasoning_model(model)` **and** the value is not `"none"` — so for a
DeepSeek model it is never sent. That leaves a gateway as the only clean place
to inject it, which is what LiteLLM is for.

## What was changed on kvm4

`/opt/stacks/litellm/config.yaml` (backup: `config.yaml.bak-2026-08-17`):

- **Added** explicit `deepseek/deepseek-v4-flash` and `deepseek/deepseek-v4-pro`
  entries carrying `extra_body: {thinking: {type: disabled}}`.
- **Removed** the `deepseek/*` wildcard. A wildcard cannot carry per-model
  params, so anyone routing through it got the broken thinking-mode behaviour;
  it also advertised four models DeepSeek no longer serves (`deepseek-coder`,
  `-r1`, `-v3`, `-v3.2`). Removing it means every DeepSeek route the gateway
  offers is the fixed one.
- The explicit entries are deliberately **named** `deepseek/deepseek-v4-flash`
  (not the bare model id) so they match the handle Letta had already registered.

Then in Letta: providers `litellm` and `ollama-local` created via
`POST /v1/providers`, and `nomic-embed-text` pulled into Ollama (274 MB).

## Two Letta registry traps for whoever comes next

- **`GET /v1/models` is an accumulating registry, not a live list.** Letta adds a
  handle when a provider syncs and never prunes. Deleting the provider does not
  remove its models either. `openai-proxy/deepseek/deepseek-coder` and friends
  are still listed and will 400 if used — they are leftovers from the wildcard.
  Treat the listing as "names Letta will accept", not "routes that work".
- **An agent's model cannot be changed in place.** `ensure_fleet` is
  create-if-missing, and `llm_config` is not patchable, so moving the fleet to a
  new provider means deleting and recreating the agents. That was safe here (they
  had never completed a turn, so no memory was lost) but will not be later.

## The precedence bug this exposed

`_resolve_model` adopted a handle from any existing agent **before** considering
the fleet.yaml default. With the fleet already created on Anthropic, editing
fleet.yaml could never move it to DeepSeek — the old handle kept winning, and the
declarative file was a lie for the one setting most likely to change: which
provider is currently funded.

Now the declared handle wins whenever the server serves it, and adoption is the
fallback for an unserved handle (the invented-handle case the original guard was
written for). If listing the server's handles fails, behaviour reverts to the old
adoption path rather than failing. Four tests pin this, including one asserting
the declared default is not an `anthropic/` or `openai/` handle.

## Verification (all live, against the real fleet agents)

**`gf_app_assistant`** — "which document reports the loss on drying for batch
CJ062501-2, and what is the value?":

```
TOOL CALL   -> ragflow_search {"question": "loss on drying batch CJ062501-2",
                               "datasets": "eCOA_INGEST_SUMMA"}
TOOL RETURN -> {"ok": true, "searched": ["eCOA_INGEST_SUMMA"], "hits": [...]}
ASSISTANT   -> 6.70% (≤ 10.00%), from BUNDLE_CapJunkie_CJ062501-2_full_panel.txt,
               ЈЗУ Институт report 1032/1851/25 — and notes the second lab report
               in the bundle (Фармахем) covers cannabinoids only and does NOT
               report loss on drying.
```

It scoped the search to its permitted dataset **on its own**, from the
`ragflow_scope` memory block — it was not told which dataset to use.

An earlier run was checked digit-for-digit against the corpus: the agent reported
Total Δ⁹-THC 7.91% (0.49%) for P060242 from
`BUNDLE_OrangePunchMimosa_P060242_full_panel.txt`, and the chunk reads
`Вкупно Δ9-Tetrahydrocannabinol (Total Δ9-THC): 7.91% (0.49%)`. Exact match on
value, uncertainty and document.

**`gf_reg_checker`** — the guardrail, asked for an EU GMP clause it has no
ingested corpus for:

```
TOOL CALL   -> ragflow_search {"datasets": "DB1_REGULATORY, DB3_PP_CURRENT_unified"}
TOOL RETURN -> {"ok": false, "err": "no known dataset named",
                "available": ["STABILITY_PROGRAMME","eCOA_INGEST","eCOA_INGEST_SUMMA"]}
ASSISTANT   -> NO-FINDING. States the corpora are not yet ingested, and that it
               must not search the datasets it can see because they are outside
               its permitted scope, nor fill the gap from memory.
```

It saw three real datasets listed in the error and still refused to touch them.
That is the dataset-scoping guardrail and the no-fabrication house rule holding
under real conditions.

## The local models: available, and still not for this fleet

The locals are now reachable from Letta two ways — `ollama/*` (Letta's own Ollama
env) and `openai-proxy/local-*` (through LiteLLM, OpenAI-compatible, which is
what the owner asked for). `nomic-embed-text` is what the fleet actually uses,
for embeddings.

They remain unfit as the **chat** model here, and the reason is on record: asked
a retrieval question, `phi4-mini` never called `ragflow_search` and fabricated a
tool result inside its reply — inventing a filename
(`batch_p060242_panel_analytical_report.pdf`) and an out-of-range analytical
finding. Compare DeepSeek on the same question above. Fine for cheap non-document
work; not for anything that touches pharmaceutical data.

## Still open

- Ingest `DB3_PP_CURRENT_unified`, `DB1_REGULATORY`,
  `GrowFlow_Weekly_Snapshots` — until then only `gf_app_assistant` has grounding.
- `LETTA_BASE_URL` still points `wwf-docengine` at the old `wwf-letta`, and that
  container is on `weekly_weed_flow_internal` with **no route to ai-net**. The
  cutover needs both the env change and a network attach; it repoints the live
  app, so it needs the owner's go-ahead.
- $3.00 of DeepSeek credit is enough to prove the route and draft a handful of
  documents, not to run the fleet continuously.
- The OpenAI/Anthropic top-up is still worth doing: once funded, switching back
  or comparing quality is a one-line fleet.yaml change plus a fleet recreate.
