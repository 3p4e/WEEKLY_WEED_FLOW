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

## The second pass converges

The same read-only preview, re-run from the v25 image after the job
(15:00 UTC): every one of the eight agents reports `unknown_tools=- tool=no-op
env=no-op`, no undeclared agent exists, and `resolve_pending` still returns
exactly the two names that are not on the tenant. The loop has reached its
fixed point; the next document job's pass will report `converged: true`.

## Trial: the analytical-dossier SOP (job `2f4297b9-7ceb-4f0b-8a7f-261890617c0e`)

Submitted at 13:14:57 UTC on the v25 container, `sop_qc` questionnaire,
eleven answers, code `QASOP_TRIAL_AD01`, title *Compilation and Review of the
Batch Analytical Dossier*. Terminal state at 14:55:38, 1 h 41 min later:
**`failed` — "§6A audit did not pass"**. The full result (document, verdict,
findings) is in the job row and in `/opt/wwf-deploy/trial/result-2f4297b9.json`
on the box.

| stage | window | what happened |
| --- | --- | --- |
| generate | 13:15 – 13:48 | nine sections, 2.5 – 6 min each; 35,139 chars, 248 lines, 6 FORM/TABLE blocks, 40 blank write-ins |
| regulatory-check | 13:48 – 14:39 | nine clone exchanges, 5 – 8 min each |
| bilingual + structure | 14:39 | passed |
| qa-audit | 14:39 – 14:43 | verdict **FIX**, four issues |
| qa-repair 1 | 14:43 – 14:55 | clone reply unusable twice → job failed closed |

### What v25 was for, and it worked

`gf_reg_checker` retrieved from `DB01_REG` for the first time since the
tenant was rebuilt. RAGflow's own log shows the `POST /api/v1/retrieval`
calls arriving from the Letta container's `ai-net` address (the tool in the
sandbox), roughly twenty per ten minutes, every one `200` with 90 – 240 KB
bodies. The findings are grounded, not recited: 6 CONFLICT, 8 OK, 4
NO-FINDING, 3 GAP across the nine sections, citing twelve distinct documents
by name and clause — EudraLex Part I chapters 2, 4 and 6, Part II, the IMP
guideline, the Macedonian ДПП Правилник §4.11/§6.8/§6.17, the EMA CTD herbal
guide, ICH Q2(R2). In seven of nine sections it also reported
`DB3_PP_CURRENT_unified` as `unknown_datasets` and said so instead of filling
the gap, which is the tool's fail-closed branch behaving.

### The auditor's verdict was right, and one of its inputs was mine

The four FIX issues stand up against the document and the retrieved text:

1. `EU GMP 4.11` cited for record retention (clause 4.11 is about
   specifications; retention is 6.8) — real, in sections 1, 2, 3, 6.10, 7.
2. "Official batch release … remains the exclusive responsibility of an
   accredited laboratory" — contradicts Chapter 2.6 (the QP certifies).
3. `Ph. Eur. monograph 3028 — Cannabis flower` presented as fact in sections
   4, 6.4.1, 6.6 and 8. The number is not in the corpus, so the house rule
   says it stays a blank write-in. The author drew it from model memory; the
   checker marked it NOT-VERIFIABLE; the auditor rejected it. That chain is
   the design working exactly as intended, whether or not the number is true.
4. `EU GMP 6.17` cited for archiving (6.17 lists the data elements of a test
   record) — real.

Issue 1 also demands Annex 13 clause 5.5 / Regulation 2017/1569 retention
"because the document code is QASOP_TRIAL_AD01 (investigational medicinal
product)". Nothing in the questionnaire, the title or the body mentions
clinical trials; both the checker (section 3.0) and the auditor read the word
**TRIAL** in the code I chose and reasoned from it. The code of a trial job
is model-visible text in the HEADERDATA block and flows into every prompt.
Use a neutral code next time; do not read the Annex 13 material as a finding
about the SOP.

### Why the repair round produced nothing — one proven cause, one likely

`_repair_sections` clones `gf_sop_author`, sends the issues plus the document,
and if the reply carries no `<<<PP-SECTION` marker sends one nudge: *"Output
the corrected sections NOW"*. Its comment says "the clone still holds the
context, so one blunt nudge is nearly free."

**It does not.** `fleet._build_body` sets `message_buffer_autoclear` from the
author's `autoclear: true`, which every one-shot verbatim author carries, so
the clone forgets its buffer after each turn. Letta's log for the clone shows
it: the first turn ran at a context estimate of 34,275 tokens (the document
was there); the nudge turn ran at 5,843 (persona and nudge only). The nudge
asked for corrected sections from an agent that no longer had the document
or the issues, and the reply was empty (`first line: ''`). The pipeline then
did the right thing with that — it failed closed rather than shipping an
unrepaired document.

The first reply having no marker at all is not recoverable from the server
(the clone's runs, steps and messages cascade-deleted with the agent). The
likely cause, from the one comparable run that *is* readable: the auditor's
own turn on this document spent 35,257 characters on reasoning before a
3,513-character verdict, under the same `max_tokens: 16384`. A repair that
must rewrite five bilingual sections after reasoning of that size does not
fit in the budget; a truncated turn ends with no assistant text and no
markers. Until the clone's step records are retained, that stays a
hypothesis.

Fix, both halves in `docengine/` (not made here — this record documents a
trial): spawn the repair clone with autoclear off (it is deleted afterwards
anyway, so the buffer-growth reason for autoclear does not apply), and give
the repair path either a larger completion budget or a per-section repair
loop so one turn never has to carry five sections and its reasoning.

### Also seen, not caused by this deploy

RAGflow's log during the run carries repeated LiteLLM errors from RAGflow's
*own* chat model: `deepseek-v4-flash` → `"Insufficient Balance"`, retried
five times, while the owner's DB01_REG re-parse was chunking
`WHO_TRS_902_Annex9.pdf`. Retrieval is unaffected (every call returned 200);
parse-time steps that need the chat model will be degraded until that
account is topped up. Owner action.
