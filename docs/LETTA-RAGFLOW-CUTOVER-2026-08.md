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

## ~~BLOCKER~~ RESOLVED — see `LETTA-DEEPSEEK-VIA-LITELLM-2026-08.md`

The blocker below was real and is kept for the record, but it no longer stands.
The fleet was moved to **DeepSeek v4-flash through the LiteLLM gateway** (funded,
$3.00 balance) with **local Ollama embeddings**, and the agent-turn → tool-call
link that this section calls unproven is now **proven**: `gf_app_assistant` calls
`ragflow_search` itself, scopes it to its permitted dataset from its own memory
block, and quotes values and source documents that match the corpus exactly.
`gf_reg_checker` correctly returns NO-FINDING for its un-ingested corpora.

Topping up OpenAI/Anthropic is still worthwhile — with the precedence fix in
`_resolve_model`, switching back is a one-line `fleet.yaml` change plus a fleet
recreate — but nothing is waiting on it.

## BLOCKER (historical): both cloud provider accounts on letta-6ou3 are out of credit

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
*(Superseded: proven the same day via DeepSeek — see the note at the top of this
section.)*

## Not done, and why

- ~~**`LETTA_BASE_URL` is NOT switched.**~~ **DONE 2026-08-17, owner-approved.**
  `wwf-docengine` now runs `growflow-docengine:v12`, is attached to **both**
  `weekly_weed_flow_internal` and `ai-net`, and points at
  `http://letta-6ou3-letta-1:8283`. It also carries `RAGFLOW_BASE_URL` /
  `RAGFLOW_API_KEY`, which `spawn_ephemeral` stamps onto every clone it creates —
  without them an ephemeral reg-checker gets the tool but no way to authenticate.
  See "The cutover" below.
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

---

# The cutover (2026-08-17, owner-approved)

`wwf-docengine` now talks to letta-6ou3. The old `wwf-letta` container is no
longer referenced by the app.

## What changed on kvm4

`/opt/stacks/wwf_app/` — backups `compose.yaml.bak-pre-letta6ou3` and
`docengine.env.bak-pre-letta6ou3`:

| | before | after |
|---|---|---|
| image | `growflow-docengine:v8` | `growflow-docengine:v12` |
| networks | `[internal]` | `[internal, ainet]` (`ai-net`, external) |
| `LETTA_BASE_URL` | `http://letta:8283` | `http://letta-6ou3-letta-1:8283` |
| `LETTA_API_KEY` | old server | letta-6ou3 |
| `RAGFLOW_BASE_URL` / `_API_KEY` | absent | set |

The RAGflow pair is not optional: `spawn_ephemeral` stamps it onto every clone
it creates as `tool_exec_environment_variables`, so without it an ephemeral
reg-checker gets `ragflow_search` attached and no way to authenticate.

Followed the deploy discipline in CLAUDE.md: both DBs snapshotted and **verified**
(`gzip -t` + end-marker + size) before touching anything, config backed up, image
built from a pushed SHA and proved to carry the new code by grepping for symbols
only it has, then `docker compose up -d --no-deps docengine` — one service, never
`down`, no DB service touched. No migration was involved.

**Rollback:** restore the two `.bak-pre-letta6ou3` files and
`docker compose up -d --no-deps docengine`. Images v8–v12 are all retained;
snapshots in `/opt/wwf-deploy/snap/`.

## Verified after the swap

- `/health` → `{"ok":true,"db":true,"letta":true}`; container on both networks.
- From inside the container: 8 gf_ agents visible, `ensure_fleet()` created
  nothing (idempotent), 377 LLM / 8 embedding handles served, RAGflow key present.
- Rest of the `wwf_app` stack untouched (14 h uptime), backend
  `/health/ready` → `{"ready":true,"databases":{"users":"ok","tasks":"ok"}}`,
  `https://wwf.srv1231216.hstgr.cloud` → **200**.
- A real annex driven through `POST /workflows`: the log shows the whole chain —
  `ragflow_scope` reconcile on all 8 agents, author turn, `_served_handles`,
  `ensure_tool`, ephemeral clone created, **tool attached to the clone**,
  reg-check turn, clone deleted. The cutover works end to end.

## Three real defects the live runs exposed

Running actual documents through the pipeline for the first time since the
provider change found three bugs, all fixed and pinned by tests. Note the §6A
auditor caught all three — the gate is doing its job well.

1. **An agent's own `<!--HEADERDATA-->` reaching the document.**
   `assemble_markdown` prepends the authoritative block and `build_from_md.py`'s
   parser is line-anchored on the *first* one, so a second block declares a
   conflicting version or leaks its fields into the body as text. Now stripped in
   `_clean_section` wherever it sits — a block placed after the first heading
   survived the structural-token search, which is exactly where it appeared.
2. **GMP clause references presented as field values.** Options read
   `Version (4.3)` / `Doc ID (EU GMP 4.2)` / `Date (4.8)`, where the number is
   the clause requiring the field. The author wrote a form stamped *version 4.3*
   against a document at 1.0. The auditor's objection was the right one: someone
   could sign off against the wrong revision. `_brief` now says what the
   parentheses mean and passes the authoritative code/version through.
3. **A passing audit recorded as a failure.** `_qa_audit_passed` required the
   reply to *start with* `PASS`; the auditor opens with a line of preamble and
   announces `**Verdict: PASS**`. An audit that cleared all six checks was logged
   as "§6A audit did not pass" and the .docx was never built — meaning the
   pipeline could essentially never complete. Now reads an explicit
   `Verdict: X` anywhere, still fail-closed on empty / unrecognisable / both-token
   replies. The old tests missed it because their fake replies with a bare `PASS`,
   a shape no real model produces.

Progression across four runs, same annex, as the fixes landed:

| run | image | auditor findings |
|---|---|---|
| 1 | v9 | 4 — duplicate HEADERDATA, version conflict, grid columns, SOP numbering in a FORM |
| 2 | v10 | 2 — version conflict (clause ref read as a value) |
| 3 | v11 | **PASS** — all six checks cleared (blocked only by defect 3) |
| 4 | v12 | 1 — missing `Шифра | Code` grid row; 8 checks ✓ |

## ~~Known gap: there is no repair loop~~ — CLOSED

A §6A FIX is now handed back to the authoring agent once before the job fails
(`DOCENGINE_MAX_REPAIR_ROUNDS`, default 1; `0` restores the old
fail-on-first-FIX behaviour). The gate is **not** relaxed — `_qa_audit_passed`
still has to return True on the final verdict; repair only buys more attempts at
earning it. Live, on the same annex:

```
audit 1 -> FIX      (missing ~~Шифра | Code~~ row)
repair  -> one hand-back to an ephemeral clone of gf_annex_author
audit 2 -> PASS
document built: 57,964 bytes, verify RESULT: PASS, bilingual MK+EN OK
qa_repair_rounds: 1
```

That is the first complete document the pipeline has produced since the cutover.

**The repair behaved correctly under real pressure.** It added only the Code row,
taking the value from the authoritative meta, and left Doc ID, Date, Reviewed by
and Signature **blank**. That matters more than the convergence: a repair loop is
fabrication pressure by construction — told an issue is blocking, the cheapest
way for a model to satisfy "field X is empty" is to fill X in, which is the one
thing the house rules forbid. The prompt is explicit that facility specifics,
measured values, dates, names and signatures stay blank write-ins and that an
issue which cannot be fixed without inventing something is left unfixed and
declared.

Every verdict is kept in order (`qa_audit_history`, `qa_repair_rounds`) on both
the success and failure paths, so a repaired document never reads as one that
passed first time.

### Three iterations it took to get right, all found by running it

1. **A "PASS" that was not a pass.** The first repair was discarded with only
   "unusable" in the log. Making the rejection explain itself was the fix that
   unlocked everything else.
2. **The delimiter collided with the payload.** Sections were split on the
   document's own `# num MK|EN` headings — but section CONTENT legitimately
   contains Markdown headings (an annex body carries its own title line). A
   correct repair was rejected over `# Образец ...` inside the body it had
   faithfully reproduced. Sections now use `<<<PP-SECTION ...>>>` markers, which
   cannot occur in document text.
3. **Agent commentary reached a controlled document.** With sections only
   *opened*, a repair appended "Corrected as required: added the missing
   `~~Шифра | Code~~` row ... All other content left byte for byte unchanged." —
   and it was built into the .docx, with the §6A auditor passing it without
   comment. Sections are now opened **and closed** (`<<<PP-END num>>>`); only
   text between a matching pair becomes document content, so commentary before,
   between or after sections is discarded, and an unclosed section is refused
   rather than silently swallowing the rest of the reply.

Structural safety: the agent is handed section bodies only, never the HEADERDATA
block; numbering and titles are carried from the originals, so a repair cannot
rename, reorder, add or drop a section; anything that does not line up exactly is
refused and the job fails on the auditor's original verdict; and bilingual parity
is re-checked on the repair, since rewording a cell can drop a language.

Test artifacts `QASOP_TEST_A7` and `QASOP_TEST_A8` were removed from
`docengine.documents` and their .docx files deleted — A7 was built before fix 3
and contained the agent commentary. The registry holds only
`WWF-TIMELINE-2026-0814` and `PP-QC-WR-011/2026`, as before.


---

# The SOP path (2026-08-17)

Everything above was verified on the single-section annex. The SOP — 9 sections,
9 ephemeral reg-checkers, translator, audit — is the primary document type and
was entirely unexercised. It now works:

```
9 sections generated · 9 ephemeral reg-checks · bilingual gate
audit 1 -> FIX
repair accepted: ok (8 of 9 sections rewritten: 1.0,3.0,4.0,5.0,6.0,7.0,8.0,9.0)
audit 2 -> PASS
built: 71,873 bytes · 3,578 words · 5 tables · RESULT: PASS · bilingual MK+EN OK
```

Note the repair left section 2.0 alone — the all-or-nothing protocol could never
have produced that. Integrity of the built document: 9 section headings and **0**
doubled, no `PP-SECTION`/`PP-END` leak, one HEADERDATA block, no agent
commentary, all 9 sections present.

It took four runs, and each failure was a different real defect:

| run | failed on | cause |
|---|---|---|
| 1 | repair rejected | all-or-nothing protocol; model rewrote only what it changed |
| 2 | repair truncated | `context_window` 30000 — Letta's DEFAULT for an unknown model |
| 3 | repair empty | agent spent its turn deliberating and stopped |
| 4 | — | **passed** |

Fixes, in order:

1. **Partial repairs.** The agent returns only the sections it changed; anything
   omitted keeps its original content, so order stops mattering and a nine-section
   document is never echoed back. Still strict on what a returned section may be:
   one of the originals, closed, non-empty, at most once, titles carried over.
2. **Doubled headings.** `assemble_markdown` emits `# <num> <MK>|<EN>` and the
   author wrote its own heading too, so every section carried its title twice —
   the auditor caught it across all nine at once. `_drop_echoed_heading` removes a
   leading heading that echoes the section's own number or titles, and only that.
3. **A real context window.** Letta sizes an unknown model from
   `LLM_MAX_CONTEXT_WINDOW["DEFAULT"]` = 30000; LiteLLM reports deepseek-v4-flash
   at 1,000,000 input tokens. `fleet.yaml` now declares `context_window: 128000`
   and `max_tokens: 16384`, passed at agent creation — so the fleet had to be
   recreated, which `ensure_fleet` does not do for an existing agent.
4. **The auditor was rejecting structure it does not own.** It failed the document
   because `# 1.0 ЦЕЛ|PURPOSE` lacks spaces around the pipe — but that line is
   emitted by the formatter in the canon's own `MK|EN` form. No author could act
   on it, so the document could never pass. The audit prompt now puts the
   HEADERDATA block and the section heading lines out of scope, leaving the
   auditor on content, which is where all its useful findings came from.
5. **A nudge when the agent deliberates.** One follow-up to the same clone, sent
   only when the reply contains no section marker at all.

**Cost:** the whole session's document runs — 5 annexes, 4 SOPs, plus probes —
took DeepSeek from $3.00 to **$2.83**. About 2 cents per SOP.

Known cosmetic residue, deliberately not chased: section bodies open with a bold
restatement of the title (`**6.0 ПОСТАПКА | PROCEDURE**`). It is bold text, not a
heading, the §6A auditor passes it, and removing it would be a style opinion
rather than a correctness fix.

All `QASOP_TEST_*` documents were removed from `docengine.documents` and their
.docx files deleted; the registry holds only `WWF-TIMELINE-2026-0814` and
`PP-QC-WR-011/2026`.
