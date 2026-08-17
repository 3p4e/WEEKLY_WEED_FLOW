# Letta → RAGflow cutover: rebuilding the gf_* fleet on letta-6ou3 (2026-08-17)

Owner decisions this implements:

1. **RAGflow is the only RAG.** Letta does not keep its own retrieval corpus; it
   calls RAGflow. ("SINCE WE HAVE SUPERIOR RAG LIKE RAGFLOW NOW; WE ARE NOT GOING
   TO USE THE LETTA-CODE RAG AND WE ARE GOING TO USE RAGFLOW FOR THAT, AND LETTA
   IS GOING TO CALL ON IT.")
2. **No dead weight.** The 21 generic standalone agents and the 18 that never ran
   are not transferred. The 13 doc-engine agents are **recreated from
   Letta-code**, not migrated — the inventory established the rebuild is
   lossless (`LETTA-AGENT-INVENTORY-2026-08.md`: 16 of 66 had a source, 50 had
   none, and every prompt is already in `agents/fleet.yaml`).
3. Stop using the old `letta` container for eCoA retrieval.

## What is live on letta-6ou3

8 `gf_*` agents, one registered tool, no Letta sources anywhere:

| agent | RAGflow datasets | `ragflow_search` |
|---|---|---|
| `gf_doc_orchestrator` | — | no |
| `gf_sop_author` | DB3_PP_CURRENT_unified | yes |
| `gf_annex_author` | DB3_PP_CURRENT_unified | yes |
| `gf_translator_mk_en` | — | no |
| `gf_reg_checker` | DB1_REGULATORY, DB3_PP_CURRENT_unified | yes |
| `gf_raci_specialist` | DB3_PP_CURRENT_unified | yes |
| `gf_qa_auditor` | — | no |
| `gf_app_assistant` | **eCOA_INGEST_SUMMA**, DB3_PP_CURRENT_unified, GrowFlow_Weekly_Snapshots | yes |

An agent with no dataset scope gets neither the tool nor the credentials — it
should not have a search button it has no corpus for.

Each agent carries three core-memory blocks: `gf_house_rules`, `persona`, and
`ragflow_scope` (generated from its `datasets:`, so the model can read its own
retrieval limits instead of being told each turn).

## Dataset scoping is the guardrail

The stability/release boundary is enforced as a **data** boundary, not as an
instruction. `STABILITY_PROGRAMME` is granted to no document agent, so a
stability figure cannot be surfaced as a release value — it is not in any
dataset those agents may name. A test asserts no agent's `datasets:` contains
`STABILITY`.

Three corpora the document agents need are **not yet in RAGflow**:
`DB3_PP_CURRENT_unified`, `DB1_REGULATORY`, `GrowFlow_Weekly_Snapshots`. They
were Letta sources on the old server. `ragflow.pending_ingest` lists them, and
the scope block tells the affected agent it is drafting **without corpus
grounding** and must say so rather than invent citations. `gf_app_assistant` is
the only agent with live grounding today, via `eCOA_INGEST_SUMMA`.

RAGflow currently holds: `eCOA_INGEST` (255 docs / 1,267 chunks),
`eCOA_INGEST_SUMMA` (81 / 1,583), `STABILITY_PROGRAMME` (10 / 357).

## The tool

`docengine/agents/ragflow_search.py` **is** the tool — `fleet.py` reads its text
by path and POSTs it as `source_code`, so what is committed is what runs in
Letta's sandbox. Constraints learned the hard way against letta-6ou3, each now
pinned by a test:

- Letta derives a JSON schema from **every** function in the source. A nested
  `_call` helper was rejected first for a missing docstring, then for an
  unannotated parameter. The file is now **exactly one function** — the two API
  calls are written out in full rather than sharing a helper.
- Tool registration is **non-fatal** by design. That means a fleet can come up
  with all agents and no tool at all: observed live, agents created, retrieval
  silently absent. `ensure_fleet` therefore **reconciles existing agents** — it
  attaches the tool to a gf_ agent that lacks it, and rewrites a drifted
  `ragflow_scope` block. Create-if-missing alone can never repair either, because
  the agent is no longer missing.

Verified by direct invocation against live RAGflow:

| call | result |
|---|---|
| real dataset, real question | `ok`, 3 hits from the SUMMA bundles with source document names |
| `DB1_REGULATORY` (not ingested) | `ok:false`, lists what *is* available — no silent empty answer |
| `eCOA_INGEST,DB1_REGULATORY` | searches the real one, returns `unknown_datasets: [DB1_REGULATORY]` |

## BLOCKER: both cloud provider accounts on letta-6ou3 are out of credit

No agent can complete a turn. A handle appearing in `/v1/models` does not mean it
is billable:

| handle | result on a one-word message |
|---|---|
| `anthropic/claude-sonnet-4-6` | 400 — "Your credit balance is too low" |
| `openai/gpt-4.1`, `gpt-4o`, `gpt-5.2`, `gpt-5.4` | 429 — "You have no credits remaining" |
| `ollama/phi4-mini:latest` | works (local) |

This needs credit added to the OpenAI and/or Anthropic account behind the keys in
the `letta-6ou3-letta-1` container. **Owner action — not something the session can
do.** Nothing needs rebuilding afterwards: the ensure loop is idempotent and the
fleet is already in place.

**Do not fall back to the local ollama/\* handles for this fleet.** Verified
live: asked to search the corpus, `phi4-mini` never called `ragflow_search` and
instead fabricated a tool result inside its reply — inventing a source filename
(`batch_p060242_panel_analytical_report.pdf`; the real document is
`BUNDLE_OrangePunchMimosa_P060242_full_panel.txt`) and an out-of-range analytical
finding that does not exist. Fabricating pharmaceutical data is precisely what
the house rules forbid.

Consequently one link is **proven** (tool → RAGflow, above) and one is
**unproven**: agent turn → tool call. It cannot be tested until a billable model
is available, and the local model is not a valid substitute for that test.

## Not done, and why

- **`LETTA_BASE_URL` is NOT switched.** `wwf-docengine` still points at the old
  `wwf-letta`. Two reasons: it repoints the live WWF app and should be confirmed;
  and it would be pointless now, since the target fleet cannot complete a turn.
  Note also that `wwf-docengine` sits only on `weekly_weed_flow_internal` — it
  has **no route to ai-net**, so the cutover also means attaching it to that
  network (letta-6ou3 and RAGflow are both on `ai-net`).
- **Engine evolution is out of scope for this repo.** Per `docengine/DEPRECATED.md`
  (owner decision 2026-08-09) all Letta/engine development happens in
  `3p4e/letta-stack` `apps/wwf-docengine/`. This session's GitHub scope is
  `3p4e/weekly_weed_flow` only. What was done here is *preservation*:
  `docengine/pp-document-suite/` is the recovered **engine line A** (the
  live-volume master that only ever existed on the old container's filesystem),
  which is the input that letta-stack's line A/B merge was missing.
  `docengine/engine/` remains line B and is what the service imports.
- The 6 `-mass` planner variants are still not in `fleet.yaml`.
- letta 0.16.8 (`wwf-letta`) vs `latest` (letta-6ou3) client compatibility is
  still unverified.

## How to re-run

`ensure_fleet()` is idempotent — safe to run repeatedly. It needs
`LETTA_BASE_URL`/`LETTA_API_KEY` for letta-6ou3 and
`RAGFLOW_BASE_URL`/`RAGFLOW_API_KEY`, and must run **on `ai-net`** to reach
either. The RAGflow key must belong to the tenant that owns the datasets;
staged credentials were `chmod 600` and `shred -u`'d after use.
