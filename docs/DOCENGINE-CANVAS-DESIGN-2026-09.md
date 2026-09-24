# DocEngine canvas — checkpointed, human-reviewed authoring (design, 2026-09-24)

Today the DocEngine is a black box between "Generate document" and "done": the
Studio shows a spinner and a stage string while the agent fleet writes, checks,
audits and builds, and a person only sees the result — or the failure — at the
end. The request is a canvas: watch each step land, correct it, redirect the
rest of the run, and approve the text before it goes forward.

**Decided by the owner (2026-09-24):**

1. **People act between steps, never mid-generation.** The unit a reviewer
   judges in a controlled document is a finished section, not half a sentence.
   Interrupting an agent mid-reply would buy partial-state resumption and races
   with the Letta turn for no review value.
2. **Two kinds of input.** A *correction* is scoped to the step just finished
   (edit the section, or ask for it again with an instruction). A *context
   amendment* is a new fact ("the facility has two clone rooms, not one") that
   carries forward into everything drafted afterwards.
3. **An amendment re-opens every section approved before it, and the document
   cannot be built until a fresh §6A audit has passed on the amended text.**

---

## 1. What exists today (read from the code)

Read on `claude/weekly-read-flow-setup-yft7if`, which is what production
docengine v26 was built from.

| Piece | Where | The fact that matters here |
|---|---|---|
| `run_workflow` | `docengine/app/pipeline.py` | One coroutine: draft each section → regulatory check per section → bilingual gate → structure gate → §6A audit (+ up to `DOCENGINE_MAX_REPAIR_ROUNDS`, default 1, AI repair) → format + `pp_verify` → `done`. Its own docstring names the gap this design closes: *no per-section checkpointing — a failure on section 8 of 9 discards sections 1–7; "real checkpointing … is intentionally left for a dedicated pass."* This is that pass. |
| Section drafts are independent | same | Each draft prompt is the brief + the section's identity + house rules; no draft sees another. Authors are persistent agents with `autoclear` on; the reg-checker and repairer run on ephemeral clones. **Nothing lives in agent memory between steps**, so a job can wait for a person for days and resume by re-reading Postgres. This is what makes the design cheap. |
| The gates | same | Bilingual and structure: per section, deterministic, hard. Regulatory check: per section, AI, **advisory** — the code calls this a real gap and leaves whether it should block as an open product decision. §6A: whole document, AI, hard. `pp_verify`: at build, deterministic, hard. |
| `run_revision`, `/revise`, presets | `pipeline.py`, `main.py`, `presets.py` | Post-hoc direct edit of a *finished* document, whole or one section, via `_direct_edit_sections` (marker protocol, never-invent rule, scope enforcement). Re-runs bilingual, structure, §6A and `pp_verify`; writes a **new** `documents` row. No accept/reject step, by design. Its comment already applies the rule §2 generalises: the old regulatory findings are not reused "because they would describe a document that no longer exists". |
| `/chat` | `main.py` | Read-only Q&A about a finished document. |
| `[NEEDS INPUT: …]` | `needs.py` | Agents mark facility facts they were not given; `extract_needs` lists them in `result.needs_input`; the Studio's done step shows them. |
| `docengine.jobs.status` | `db.py` | The column comment already lists `awaiting_review`, unused so far — and `test_reaper_spares_everything_it_must` already asserts the startup reaper never touches it ("blocked on a HUMAN. Legitimately days old"). The pause state is reserved; nothing uses it yet. |
| `job_events` + `/workflows/{jid}/trace` | PR #55, **not yet on this branch** | Append-only status/stage/error history per job. A prerequisite (§13). |
| Backend proxy | `backend/app/api/qms.py`, `app/docengine.py` | `/qms/studio/*`, request/response, 20 s default timeout; injects `requested_by` from the session; authoring = ADMIN/OWNER/QP/QA_MGR. The trace is not proxied yet. |
| Studio view | `web/gf/qmsstudio-view.js` | pick → answer → meta → running (spinner + stage, polled every 2.5 s) → done (verify report, regulatory findings, NEEDS INPUT panel, chat/revise with presets) or failed. |
| Annex 11 signature | `backend/app/api/qc/signatures.py`, table `qc_signatures` | Password re-authentication at signing, meaning, immutable row. `object_type` is free text. |

So the checks, the findings and the editing machinery all exist. What is
missing is (a) a place for a job to stop, (b) per-section state that outlives
the coroutine, and (c) a record of who decided what about which text.

---

## 2. The rule everything else follows

> **Every verdict — a reviewer's approval, a check result, the §6A PASS — is
> recorded against the SHA-256 of the exact text it judged. It counts only while
> that text is unchanged and no amendment has landed after it. The build refuses
> unless every verdict it needs is current.**

What follows from it:

- Editing, regenerating or repairing a section makes a new revision with a new
  hash. Its approval and regulatory finding stop counting; it is re-checked and
  must be approved again. Other sections are untouched — drafts are independent.
- An amendment makes every approval older than it stop counting (those sections
  were drafted, or approved, without the new fact), and voids any older §6A
  verdict.
- Unchanged text is never re-judged by an AI check. Deterministic gates are
  free to re-run. Asking a non-deterministic auditor about the same bytes again
  until it says PASS is testing into compliance, so the canvas never offers it.

This is enforced by one server-side function, `build_readiness(job)` (§6) —
not by which buttons the UI happens to enable.

---

## 3. Execution: from one coroutine to `advance()`

```
questionnaire → draft 1.0 → check → [review 1.0] → draft 2.0 → … → [review 9.0]
                                                                        │
   amend ──► re-open sections approved before it, void §6A ◄────────────┤
                                                                        ▼
               §6A audit ──FIX──► [document review] ──► repair / edit ──► re-approve ──► §6A …
                   │PASS
                   ▼
            [sign & build] ──► format + pp_verify ──► done        [ ] = the job parks here
```

`advance(job_id)` replaces the straight-through run for canvas jobs. It loads
the job's persisted state, works out the next automatic step as a pure function
of that state, performs it, persists the result, and loops until it reaches a
gate — where it sets `status='awaiting_review'`, `gate=<which>` and returns.

- **Automatic steps:** draft a section; check a revision (bilingual, structure,
  regulatory check, NEEDS INPUT extraction); run the §6A audit; build.
- **Gates:** review a section; review the document after a §6A FIX; sign & build.
- **Order:** with `review='each_section'` (default) the next section is drafted
  only once every drafted section is approved and current — so an amendment made
  while reviewing section 3 is in the brief for section 4. With
  `review='all_at_end'` every section is drafted and checked without stopping and
  the job parks once with all of them awaiting review. Same model, same rule.
- **Triggers:** job creation (fire-and-forget, as today) and every decision.

**Concurrency.** `jobs` gains a `rev` counter. A decision is accepted only by
`UPDATE docengine.jobs SET status='running', rev=rev+1 WHERE id=$1 AND
status='awaiting_review' AND rev=$2 RETURNING rev`. The request that wins runs
`advance()`; any other (a double click, a second reviewer, a second worker) gets
409 "the document changed — reload". Decisions are accepted only while parked.

---

## 4. Data model (docengine schema, additive)

`docengine.jobs` gains `mode` (`'auto'` default | `'canvas'`), `review`
(`'each_section'` | `'all_at_end'`), `gate`, `rev int`. Status gains
`awaiting_review` (already reserved) and `abandoned`. Added with
`ALTER TABLE … ADD COLUMN IF NOT EXISTS` in `db._SCHEMA`, as today's
`CREATE … IF NOT EXISTS` is.

Three new tables. All **append-only**: a `BEFORE UPDATE OR DELETE` trigger
raises, so nothing — including the application — rewrites the record.

**`job_section_revisions`** — every version of every section.
`job_id, num, rev, content, sha256, origin (draft | regenerate | edit | repair),
instruction, context_version, produced_by, agent_remarks, created_at`;
unique `(job_id, num, rev)`. `produced_by` is `agent:<name>` or the person's
username. `context_version` is how many amendments were in force when it was
produced. `agent_remarks` keeps what an agent wrote *outside* the section
markers on a regenerate or repair — "issue 3 cannot be fixed without inventing a
value" — which `_split_repaired` discards today.

**`job_checks`** — every verdict, bound to what it judged.
`job_id, num (null for the document), rev (null for the document), kind
(bilingual | structure | reg | needs | audit), subject_sha, passed, detail,
created_at`. The §6A audit is a row here with `subject_sha` = SHA-256 of
`assemble_markdown(meta, current sections)`.

**`job_decisions`** — every human act, hash-chained per job.
`job_id, seq, action, num, rev, subject_sha, payload, actor, created_at,
prev_hash, entry_hash`, where `entry_hash = sha256(prev_hash ‖ canonical row)`.
Actions: `approve`, `edit`, `regenerate`, `repair`, `amend`, `continue`,
`abandon`, `sign_build`. `subject_sha` is what was on the reviewer's screen.
`payload` carries the instruction, amendment text, acknowledgement or answered
NEEDS INPUT items.

Amendments are `amend` decisions; the brief handed to every later agent call is
the original brief plus them, in order, under "REVIEWER AMENDMENTS
(authoritative, newest last)". There is no mutable "current state" table: the
current revision, approval and verdict per section are derived from these three
tables (tens of rows per job), so there is one source of truth.

---

## 5. The gates and what a person can do at each

### 5.1 Section review

**Shown:** the current revision rendered MK | EN; a diff against the previous
revision and against the last approved one; the checks on *this* revision; the
NEEDS INPUT markers in it; its history (agent draft, edited by X, regenerated
with "…", repaired) and the decisions made on it.

- **Approve** — only if bilingual and structure pass on this revision. If the
  regulatory check flagged something, approving asks for a one-line
  acknowledgement stored with the decision (§14, decision 2). Records the hash
  on screen.
- **Edit** — the reviewer changes the text. It becomes a new revision
  (`origin=edit`, `produced_by=<username>`), its checks run, and the gate stays
  open: approving is a separate click on the checked revision, because the
  approval must be of text the checks have seen.
- **Regenerate with an instruction** — `_direct_edit_sections` scoped to this
  section, the same protocol as `/revise`; the existing presets work here too.
  New revision, `origin=regenerate`, instruction stored, checks run.
- **Amend** — §5.2.
- **Open any drafted section** — navigation only; each section keeps its state.

### 5.2 Context amendments

Free text (≤ 2 000 characters), or answers to open NEEDS INPUT items: the UI
turns each marker into a question and the answers become one amendment ("drying
room: DR-02"). A fact supplied for section 6 is usually needed in section 7 as
well, which is exactly why an answer is an amendment rather than a local edit.

On `amend`: every approval older than it stops counting, including those of
sections drafted but not yet approved; any older §6A verdict is void; sections
not yet drafted get the fact in their brief. Before confirming, the UI shows the
reach — "re-opens 1.0–4.0 (approved) and voids the §6A PASS".

Re-opening *every* earlier approval is deliberate. Sections are drafted from the
brief independently, so the new fact may belong in any of them; the engine
cannot know which, and a reviewer should not have to trust that it guessed.
Re-confirming an unaffected section is one click (a new `approve` on the same
hash, now newer than the amendment); an affected one is regenerated — the fact
is in the brief now — or edited.

### 5.3 Document review (§6A)

The audit runs by itself once every section is approved and current and there is
no current verdict, with the current regulatory findings as context exactly as
today. PASS → sign & build. FIX → the job parks showing the auditor's issues in
full, pinned to the sections they name where the text makes that clear.

- **Let the agent repair** — `_repair_sections`, as today, but its output lands
  as new, **unapproved** revisions (`origin=repair`) shown as a diff against what
  the reviewer approved. In canvas mode an AI change to text a person approved is
  never applied without that person seeing it.
- **Edit / regenerate** any section; **amend**.
- **No waiver.** A FIX cannot be overridden — the gate is as hard as it is
  today — and re-auditing unchanged text is not offered (§2). §14, decision 1.

### 5.4 Sign & build

**Shown:** the assembled document, the §6A PASS, open NEEDS INPUT items, the
full decision log.

**Sign & build** re-authenticates the reviewer's password through the existing
`qc_signatures` mechanism and records an `AUTHORED` signature with
`object_type='docengine_draft'` and `object_id = uuid5(job id, assembled
hash)`, the statement naming the hash. The object signed is *this text*, not the
job: migration 0060's unique index `(org_id, object_type, object_id, meaning,
signer_id)` then refuses the same person signing the same text twice — its
intent — while a rebuild after any change, which is new text, gets its own
signature. Using the job id would have refused every re-sign after a change.
`qc_signatures` carries the `audit_…` trigger, so the signature also lands in
the backend's hash-chained `audit_log`. DocEngine then re-runs `build_readiness` and, if it is empty,
formats and runs `pp_verify`. PASS writes the `documents` row and the job is
`done` — and `/chat` and `/revise` work on it exactly as they do on a headless
job, because the done result keeps the same `sections`/`meta`/`needs_input`
shape. A `pp_verify` FAIL parks the job back at this gate with the report,
instead of failing it.

The signature comes before the build on purpose: it records an act that
happened — the review of that exact text — whether or not the build then
succeeds. A rebuild after any change needs a new signature, because the hash
changes.

**What the signature is not:** approval or release of a controlled document.
It is the author's attestation that each section was reviewed as the decision
log shows. The second-person REVIEWED/APPROVED lifecycle, effective date and
supersession do not exist for DocEngine output today — `docengine.documents` has
no status column — and are out of scope here (§14, decision 6).

**Why per-section approvals are not signatures:** on paper an author does not
sign each section of a draft, and a password prompt nine times per document
teaches people to sign without reading. Each approval is still attributable,
timestamped and hash-chained.

---

## 6. `build_readiness(job)` — the invariant

Returns the list of reasons the job cannot be built; empty means ready.

1. Every section has a current revision, and bilingual and structure pass on its
   hash.
2. Its latest `approve` has `subject_sha` equal to that hash and is newer than
   the latest amendment; if its regulatory check flagged something, the approval
   carries an acknowledgement.
3. There is a passing `audit` check whose `subject_sha` equals the SHA-256 of the
   document assembled from the current revisions, newer than the latest
   amendment.
4. (`pp_verify` runs inside the build itself, unchanged.)

Called by the sign & build screen (to show what is missing), by the build
endpoint (to refuse), and by the tests. A direct call to the build endpoint on a
job that is not ready gets 409 with the reasons, whatever the UI showed.

---

## 7. API

**DocEngine** (internal, `X-API-Key`):

- `POST /workflows` — gains `mode` and `review`. `mode` defaults to `'auto'`,
  which is today's `run_workflow`, unchanged.
- `GET /workflows/{jid}/canvas?since=<event id>` — one poll payload: job
  (status, gate, rev, stage, amendment count), each section's state and current
  revision with its checks, the document audit, `build_readiness`, amendments,
  NEEDS INPUT, and events since the cursor.
- `GET /workflows/{jid}/sections/{num}/revisions` — full history with content,
  for diffs.
- `POST /workflows/{jid}/decisions` — `{rev, action, num?, subject_sha?,
  content?, instruction? | preset_key?, amendment?, acknowledgement?, actor}`.
  CAS on `rev`, validated against the current gate. Records the decision, starts
  `advance()` in the background and returns at once, so no request waits on an
  agent.
- `POST /workflows/{jid}/build` — `{rev, signature_id, actor}`; refuses unless
  ready; runs in the background like the rest.

**Backend** (`/qms/studio/…`, authoring roles for writes; `actor` is always the
session username, never read from the request body — as `requested_by` is today):
`GET …/workflows/{jid}/canvas`, `GET …/sections/{num}/revisions`,
`POST …/decisions`, and `POST …/sign-and-build {password, statement}`, which
checks readiness, re-authenticates, writes the signature, then forwards the build.

**Polling, not streaming** — a correction to what I suggested in conversation.
With interaction at step boundaries nothing on screen changes faster than a step
(tens of seconds); while a job is parked nothing changes until the reviewer
acts; and the proxy chain is request/response with a 20 s timeout. So the UI
polls the canvas endpoint with an event cursor while the job is running and not
at all while it is parked. Server-sent events would only earn their cost with
token streaming, which decision 1 ruled out.

---

## 8. The canvas (`web/gf/qmsstudio-view.js`)

A new `canvas` step replaces `running` for canvas jobs; `done` keeps today's
panels (verify, NEEDS INPUT, chat/revise) unchanged.

- **Left rail:** the sections with a state chip — not drafted · drafting ·
  needs review · approved · re-confirm (amended) · blocked (bilingual/structure)
  — then "§6A audit", then "Sign & build".
- **Centre:** the selected section rendered MK | EN, with an edit toggle (raw
  bilingual Markdown) and a diff toggle (vs previous, vs approved).
- **Right, Findings:** checks on this revision; the regulatory finding with its
  acknowledgement box; NEEDS INPUT items (answer → amendment); §6A issues naming
  this section; history and decisions.
- **Action bar:** Approve · Save edit & re-check · Regenerate (instruction box
  plus the preset chips) · Amend · and, at the end, Sign & build.
- **Mobile:** the rail becomes a section picker; same actions.
- **Open work:** the Studio lists canvas jobs awaiting review, so a parked job is
  not lost when the tab closes.

Honest limitation for the first cut: editing a `[[FORM:grid]]` or `[[TABLE]]`
block means editing its `|||` / `~~` grammar as text. A structured grid editor
is phase 4.

---

## 9. What "reasoning" means on this screen

Shown: the findings (checks, the regulatory checker's citations, §6A issues),
the provenance (which agent, which instruction, which person, which amendments
were in force), the diffs, and the agents' own remarks captured outside the
section markers.

Not shown: model chain-of-thought. The pipeline strips conversational preamble
from drafts on purpose; it is unvalidated narrative *about* the text, not
evidence about it, and labelling it "the reasoning" would invite trust it has
not earned. What a reviewer should weigh is the checks and the citations.

---

## 10. Failure, restart, concurrency

- **A transient agent or Letta failure during a step** parks the job at
  `gate='step_failed'` with the error, offering Retry or Abandon. Completed
  sections are never discarded — the known gap in `run_workflow`'s docstring,
  closed for canvas jobs.
- **A worker killed mid-step:** the startup reaper parks canvas jobs at
  `gate='interrupted'` instead of failing them; Continue (a decision, so CAS
  applies) redoes only the unfinished step. It does not auto-resume at startup:
  a person should know a step was redone. Auto jobs are reaped exactly as today.
- **Two reviewers, or a double click:** the CAS on `jobs.rev` (§3).
- **Parked jobs are never reaped** (already guaranteed and tested); Abandon
  closes one explicitly.

---

## 11. Headless mode stays exactly as it is

`mode='auto'` keeps `run_workflow` untouched, so "generate without review" and
every API caller behave as today. Once canvas has run clean in production,
`run_workflow` can be re-implemented as `advance()` with an automatic policy —
approve when the deterministic gates pass, repair up to
`DOCENGINE_MAX_REPAIR_ROUNDS`, build without a signature — which would give
headless jobs checkpointing too. Later and separately: rewriting the path
production depends on is its own risk. Likewise `/revise` could later open a
canvas job seeded with the finished sections, so post-hoc edits get the same
review; today it has no accept/reject step by design.

---

## 12. Data integrity and security

- **Attribution:** `actor` is set by the backend from the session on every
  decision; DocEngine is internal and only the backend holds its key.
- **Tamper evidence:** revisions, checks and decisions are append-only by
  trigger; decisions are hash-chained per job and verifiable the way the
  backend's `audit_log` chain is.
- **Human text feeds the document and later prompts:** reject — never strip —
  the section sentinels (`<<<PP-SECTION`, `<<<PP-END`), a `<!--HEADERDATA` block
  and oversize content (60 000 characters per section); instructions and
  amendments ≤ 2 000 characters. Free text from an authenticated QA/QP author is
  the same accepted risk `meta` already carries.
- **No invented data:** an edit is the one place a value can be typed into the
  document, which is the point — a person supplies the fact, attributed to them.

---

## 13. Rollout

Each phase ships on its own.

0. **Prerequisite:** PR #55 (`job_events`, `/trace`) merged, or its `db.py`
   change carried onto this branch.
1. **DocEngine:** tables, `advance()`, gates, decisions, `build_readiness`,
   endpoints, reaper change, tests. `run_workflow` untouched.
2. **Backend:** proxy routes, actor injection, sign & build via `qc_signatures`.
3. **Frontend:** canvas step, rail / canvas / findings / actions, polling, open
   jobs list, e2e test against a fake engine.
4. **Later:** structured grid editor; `/revise` through the canvas; headless on
   `advance()`.

Deploy order docengine → backend → frontend, no downtime; the schema change is
additive. Rough size: phase 1 two to three days, phase 2 one, phase 3 two to
three.

---

## 14. Decisions for the owner

1. **A §6A FIX the reviewer believes is wrong.** Recommended: no waiver, as
   today — change the text or amend. Alternative: an attributed QA override with
   a stated reason, printed on the record.
2. **Regulatory findings at section review.** Recommended: approving a section
   whose check flagged something requires a one-line acknowledgement. That turns
   the advisory gap the pipeline documents into an attributed decision without
   making a checker of unknown false-positive rate a hard gate. Alternative: keep
   them informational only.
3. **Who may act on a canvas job.** Recommended: any authoring role, every act
   attributed. Alternative: only the requester, plus reviewers they invite.
4. **Where the signature lives.** Recommended: `qc_signatures` with
   `object_type='docengine_draft'`, meaning `AUTHORED`, object = the signed text
   (§5.4) — no migration, one re-authentication implementation, already in the
   audit chain. Alternative: a new `qms_signatures` table with a clearer name.
5. **Open NEEDS INPUT at sign & build.** Recommended: warn, do not block — the
   output is still a draft, as today. Alternative: block.
6. **Out of scope, to design separately:** document control for DocEngine output
   — second-person REVIEWED/APPROVED, effective date, supersession, training.

---

## 15. Tests for phase 1

With the fake Letta client the existing tests use:

- `advance()` drafts in order and parks at each section (`each_section`) or once
  (`all_at_end`).
- Approve is refused on a bilingual or structure failure and allowed once an edit
  fixes it.
- An edit or regenerate voids that section's approval and regulatory finding;
  other sections are untouched.
- An amendment: older approvals stop counting, the §6A PASS is voided, and later
  draft prompts contain the amendment.
- The §6A audit is never re-run on an unchanged assembled hash.
- A repair lands as unapproved revisions; approved text never changes without a
  new decision.
- `build_readiness` reports each missing condition on its own, and the build
  endpoint refuses a not-ready job when called directly.
- Two decisions on the same `rev`: one 200, one 409.
- Sign & build (backend): a wrong password writes nothing; the same person
  signing the same text twice gets 409; signing again after a change succeeds.
- The reaper parks running canvas jobs and still fails stale auto jobs.
- UPDATE or DELETE on revisions, checks or decisions raises; the decision chain
  verifies, and detects an altered row.
- Human input carrying a sentinel, a HEADERDATA block or oversize content → 422.
