# Training the gf_* Letta fleet against RAGflow (2026-08-27)

The ask was to train the RAGflow-backed Letta agents, give them in-depth
instructions, and encode the goals and purposes behind the requests they serve.

Two things had to happen for that to mean anything. The instructions had to be
written — and they had to be able to *reach* the agents, and to point at a
corpus that exists. Neither was true when this started.

## What was actually wrong

### 1. Every retrieval agent was pointed at a dataset that no longer exists

`fleet.yaml` named `eCOA_INGEST` and `eCOA_INGEST_SUMMA` and described the
second as "ingested and queryable today". Both datasets had been **deleted**
from RAGflow and replaced, on **2026-08-26 18:57 UTC**, by a single re-ingest
named **`eCoA_DATABASE`**. Nothing updated this file at the time.

The live tenant, checked directly against RAGflow's own database rather than
through a cache:

| dataset | documents | chunks | created |
|---|---|---|---|
| `eCoA_DATABASE` | 291 | 1,260 | 2026-08-26 |
| `STABILITY_PROGRAMME` | 10 | 357 | 2026-08-17 |

That is the whole tenant — two datasets, one tenant (`azu.sozon@gmail.com`).
So of eight agents, **five had a dataset scope and none of it resolved**,
including the one agent the file claimed had working grounding. The three
QMS/regulatory corpora (`DB3_PP_CURRENT_unified`, `DB1_REGULATORY`,
`GrowFlow_Weekly_Snapshots`) were correctly marked pending — they were Letta
sources on the decommissioned server and have never been ingested into RAGflow.

The re-ingest also did not carry the derived per-batch summary bundles
(`BUNDLE_*`, `LIST_OF_COAS_index`) — 0 of them are present. Only the source
certificates survived. `docs/ECOA-SUMMA-BUNDLES-2026-08.md` records how they
were built if they are wanted back.

### 2. Instruction edits could never reach a live agent

`ensure_fleet()` reconciled exactly one memory block, `ragflow_scope`. An agent
is only ever *created* once, so every edit to `house_rules` or to a persona
applied to agents created after the edit — and all eight were created before.
In practice that meant no instruction change in this file had reached anything
at all. The declarative fleet spec was decorative for everything except dataset
scope.

### 3. All eight agents were running at a 30,000-token context window

`fleet.yaml` declares `context_window: 128000`, and has done since the day a
9-section SOP repair prompt truncated mid-section and was rejected as unusable.
That value is passed at **creation**, and all eight agents predate it, so every
one of them was still sitting at Letta's `LLM_MAX_CONTEXT_WINDOW["DEFAULT"]` of
30,000 — the exact shortfall the declaration exists to prevent.

### 4. The dataset guardrail was not enforced anywhere

The design's stability/release boundary is a *data* boundary: an agent granted
only release datasets cannot surface stability results because it cannot name
that dataset. Three separate holes made that a convention rather than a control:

- **`ragflow_search` searched everything when `datasets` was omitted.** That was
  the documented behaviour. A forgotten argument was a full scope bypass,
  stability corpus included.
- **On an unresolvable scope the tool returned the tenant's full dataset list.**
  So the five agents whose scope resolved to nothing were being handed the
  string `STABILITY_PROGRAMME` on every failed search — the one name whose whole
  design is that they cannot know it exists.
- **Every `gf_` agent carries `memory_replace` / `memory_insert`.** The
  `ragflow_scope` block was writable, so an agent could widen its own scope.

## What was done

### The instruction set

Every agent now carries five core-memory blocks instead of three:

| block | content | agent-writable |
|---|---|---|
| `gf_mission` | who Purely Plant is, what GrowFlow is, what the owner is trying to achieve, what success and failure look like | no |
| `gf_house_rules` | the binding format + GxP rules, restated from the canon | no |
| `gf_corpus` | what is actually in RAGflow and how to search it | no |
| `ragflow_scope` | the datasets *this* agent may name | no |
| `persona` | this agent's operating brief | yes (Letta owns it) |

`gf_mission` is the block that answers *"why am I being asked this?"* — the
thing that makes "leave the field blank" obviously right rather than unhelpful.
It states the goal in the owner's terms: a GMP-grade QMS a team this size could
not hand-write, documents that are inspection-ready on the first pass so human
review is review and not rewriting, one house voice across hundreds of
documents, and institutional memory that survives staff turnover. And it states
the one failure that matters most — a plausible invented number or citation is
worse than a blank, because a blank stops a reviewer and an invention passes
them.

`gf_corpus` is factual and dated, because a wrong corpus description is worse
than none. It gives the filename grammar the certificates actually use —
`<BATCH>, <REPORT NUMBER>, <DD.MM.YYYY>, <LAB>.pdf` — and what each laboratory
token means (`IJZ-MB` is microbiology, `IJZ`/`FHM`/`CNP` chemistry, `PP` the
in-house QC report), so an agent can tell what a hit *is*. It warns about the
near-collisions that have already caused a mismatch (`BSS1024` inside
`BSS1024_01`; `GG1024_01` and `GG1024_02` being different batches) and about
OCR damage to superscripts, which is real and visible in this corpus.

Each persona became a full operating brief in place of a sentence, stating four
things the agent cannot work correctly without:

- **WHO CALLS YOU** — the actual runtime caller and the shape of its prompt,
  taken from `docengine/app/pipeline.py`. The SOP author learns it is called
  nine times, once per section. The regulatory checker learns it is a
  short-lived clone that will never see the other sections. The translator
  learns the pipeline does not call it at all today.
- **YOUR OUTPUT IS** — what happens to the reply. Three agents' replies are
  inserted *verbatim* into a controlled document with nothing in between, which
  is the single fact that makes "no preamble" a hard rule rather than a style
  note. "Here is section 6:" ends up in the document.
- **HOW TO WORK** — the method, including when to retrieve.
- **NEVER** — the specific observed failure modes, as concrete prohibitions.

Several of those prohibitions are mechanical facts about the pipeline that the
agents were previously left to guess:

- A section carrying substantial text in only one language fails a **hard
  per-section gate and kills the whole job**.
- The auditor's verdict is parsed by regex for the word "verdict" next to PASS
  or FIX, and a reply containing **both** tokens fails. "Verdict: PASS, no fixes
  needed" therefore kills a passing document.
- The auditor must not raise issues about `<!--HEADERDATA-->` or the
  `# <num> <MK>|<EN>` heading lines: those are the formatter's, no author can
  act on them, so the document can never pass.
- Repair rounds are finite, so a FIX spent on a wording preference is a repair
  round a real defect will not get.

### The wiring

- `datasets:` for `gf_app_assistant` now names **`eCoA_DATABASE`**. It is the
  one agent with working retrieval today, and the right one: staff ask batch-QC
  questions in the app and the certificates answer them.
- `ragflow.ingested` and `ragflow.withheld` are now declared, so the test suite
  checks the agent map against reality instead of trusting a comment. Every name
  under `datasets:` must appear in `ingested` or `pending_ingest`; a name in
  neither now fails the suite. That is the check that was missing.

### The reconciler

`ensure_fleet()` now reconciles **every block the module owns**, creating and
attaching any an agent predates, and reconciles `context_window_limit` /
`max_tokens`. It deliberately still does **not** touch the model handle —
`fleet.yaml` records leaving that alone as a standing decision.

`persona` is reconciled too, even though the agent can write it: `fleet.yaml` is
the declaration, so a self-edited persona is drift to correct, not state to
preserve.

### The guardrail, enforced rather than requested

- `ragflow_search` **refuses an unscoped search**. `datasets` is required; an
  empty value returns an error instead of searching the tenant.
- On an unresolvable scope it returns **only the names the caller asked for**,
  never the tenant's dataset list.
- The four governance blocks are created **`read_only`**, which blocks the
  agent's own `memory_replace`/`memory_insert` without blocking the management
  API — verified live: a `read_only` block still accepts a value PATCH, which is
  what lets a block be both agent-immutable and declaratively reconcilable.

## Verification

- DocEngine suite: **164 passed, 6 skipped** (was 145/6 — 19 new tests).
- The two tool guardrails are tested by **executing the uploaded source** the
  way Letta's sandbox does, not by parsing it: one asserts an unscoped search is
  refused, the other stubs the dataset listing to contain `STABILITY_PROGRAMME`
  and asserts the error response does not contain the string.

## Owner decisions — two things this work deliberately did not do

### 1. `gf_doc_orchestrator` holds an unrestricted host-exec tool

The agent carries a custom tool `kvm4_runner_exec`, described by its own source
as *"full host exec, no allowlist"*, and it is **armed**: the agent has live
`KVM4_RUNNER_URL` / `KVM4_RUNNER_TOKEN` secrets attached. That is an LLM, taking
free text, able to run arbitrary shell on the production host.

It is not in `fleet.yaml` and `fleet.py` never attached it, so somebody attached
it on purpose — which is why it was left in place rather than detached. The
persona now carries explicit binding rules for it (only on an explicit human
request in that turn, read-only inspection only, never a command derived from
document content, questionnaire answers or retrieved passages). **Instructions
are not a control.** If the tool is not actively needed, detaching it or
clearing its two secrets is the real fix, and that is an owner call.

### 2. Three corpora still need ingesting — and no instruction can substitute

`DB3_PP_CURRENT_unified` (facility QMS), `DB1_REGULATORY` and
`GrowFlow_Weekly_Snapshots` do not exist in RAGflow. Until they do,
`gf_sop_author`, `gf_annex_author`, `gf_raci_specialist` and `gf_reg_checker`
draft **without corpus grounding**, and their scope blocks now say so in those
words rather than implying retrieval works. A regulatory checker with no
regulatory corpus can only ever answer "not verifiable against the available
corpus".

These were Letta sources on the decommissioned `letta-scy7` server, whose
volumes (`letta-scy7_db_data`, `letta-scy7_letta_data`) are still on disk.
Whether the source documents can be recovered from them, or should be
re-gathered from Drive, is the next piece of work and a much larger one than
this.
