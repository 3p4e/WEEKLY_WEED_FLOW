# Production deploy: growflow-docengine v22 (2026-08-29)

Deployed from `596d6f2` — the merge commit of PR #41, the fleet-training and
DocEngine-pipeline work. Single service, no migrations, no schema change.

## What shipped

**The `gf_*` Letta fleet, trained and wired to a corpus that exists.** Five of
eight agents had been pointed at RAGflow datasets deleted in the 2026-08-26
re-ingest; `ensure_fleet` had only ever reconciled one memory block, so no
instruction edit had reached a live agent since they were created. Both fixed,
plus mission/corpus/persona blocks, read-only governance blocks, and a dataset
scope that is now an enforced control (`RAGFLOW_ALLOWED_DATASETS`) rather than
an instruction the model could talk itself out of.

**The pipeline defects that only appear when you run it.** Six document jobs
were driven through the REST API during this work; the first five failed, each
differently, and none of it was visible from the agent side:

| job | outcome | cause |
| --- | --- | --- |
| `VERIFY-ANNEX-001` | failed `qa-audit` | 78k-token buffer → 300 s `ReadTimeout` |
| `-002` | failed `qa-repair 1` | auditor surfaced issues one per round, 1-round budget |
| `-003` | failed `format` | §5A fidelity short by one word — a `[[FORM]]` row losing its 4th cell |
| `-005` | failed `generate` | 300 s timeout again, mid-turn |
| `-006` | **done** | green, but structurally wrong (see below) |
| `-007` | **done** | correct |

**`gf_doc_orchestrator` disarmed.** It carried `kvm4_runner_exec` — unrestricted
shell on this host — with live `KVM4_RUNNER_URL`/`KVM4_RUNNER_TOKEN` secrets,
attached out-of-band (never by `fleet.py`). It is a router: it resolves
TYPE/MODE and hands off, and the automated pipeline never calls it. Tool
detached, both secrets cleared, verified by re-reading the agent. The tool
remains registered server-side for deliberate re-attachment; a future host-ops
agent should get an allowlisted, audited runner instead — the current one
accepts any command.

## The one worth reading twice: `-006` went green and was still wrong

`emit_form` reads exactly three cells per `[[FORM]]` row — MK label, EN label,
value — and never looks at a fourth. `-006` passed every gate while its grid
rows carried four cells, which renders the *next field's label* as the current
field's pre-filled value and destroys the write-in blank. A GMP form with no
blanks to fill, that no gate objected to.

The first fix for this was **wrong in both directions**. It was inferred from a
single experiment ("a row wider than its siblings loses content") and a code
review challenged it. Settled by building each shape and diffing the tokens in
the produced `.docx`:

| shape | first gate | engine |
| --- | --- | --- |
| `A \|\|\| B` beside `C \|\|\| D \|\|\| E` | flagged | loses nothing |
| uniform 5-cell rows | passed | loses cells 4-5 of **every** row |
| SOP row wider than its first | passed | `IndexError`, crashes the build |

The second is the dangerous one: a tidy-looking block that drops a field from
every row, structurally invisible to a sibling comparison. `_grid_overflow` is
now per doctype and derived from `emit_form`/`build_sop` directly.

**The instruction was worse than the gate.** `fleet.yaml` told the annex author
that rows must share a column count and that short rows should be *padded* to
match — advice which manufactures precisely the uniform-wide block the old gate
could not see. It now teaches the real grammar: one field per row, three cells.

## Configuration changed with this deploy

`/opt/stacks/wwf_app/docengine.env` (backup: `docengine.env.bak-pre-v22`):

| key | value | why |
| --- | --- | --- |
| `LETTA_READ_TIMEOUT` | `900` | 300 s was ending turns the model would have finished; killed two jobs mid-turn |
| `DOCENGINE_MAX_REPAIR_ROUNDS` | `2` | one round means any second §6A finding fails the document |

`docs/DEPLOY.md`'s compose snippet still advertised `LETTA_READ_TIMEOUT: "300"`
and has been corrected — the live compose never set it, so this was a trap for
the next reader rather than an active fault.

## Sequence

1. Merged PR #41 → `596d6f2` (all 9 CI checks green on `f11ddd3`).
2. Built `growflow-docengine:v22` from `596d6f2` via the `gh-runner-wwf`
   checkout — **no PAT staged on the host**, same route as capture-mcp v2 and
   frontend v131.
3. Asserted the image really carries that commit: `app/fleet.py`,
   `app/letta.py`, `app/pipeline.py` and `agents/fleet.yaml` all checksum-equal
   to the repo at `596d6f2`, plus commit-unique markers (`_grid_overflow`,
   `status=r.status_code`, `ONE FIELD PER ROW`, `autoclear`).
4. Backed up `compose.yaml`, flipped line 151 `v21` → `v22`, diffed against the
   backup (exactly one line), `docker compose up -d --no-deps docengine`.

## Verification

- `/health` → `{"ok":true,"db":true,"letta":true,"engine":"pp-document-suite (canon 2026-07)"}`
- Running container env carries both overrides; no errors in the logs since start.
- The four source checksums inside the running container match the repo at the
  merge commit.
- **A real document job on production**: `PROD-ANNEX-001` reached `status=done`
  — a 58,044-byte `.docx`, `RESULT: PASS`, `FIDELITY … [OK]`, §6A `Verdict: PASS`.

  It needed **two repair rounds**. On the previous configuration (`1`) this job
  would have failed at `qa-repair 1` — so the env bump is not cosmetic, it is
  load-bearing, and this run is the evidence.

  The auditor's closing verdict, unprompted: *"the form uses the correct inline
  full-page layout with a consistent three-cell [[FORM:grid]] metadata block…
  All write-in fields are blank, no personnel names are hard-coded (roles only),
  and no data or citations appear fabricated."*

## Rollback

`growflow-docengine:v21` is retained on the host and
`/opt/wwf-deploy/snapshots/compose.yaml.pre-docengine-v22` restores the previous
tag. No migrations ran, so a rollback is a tag flip and a recreate — but note
that v21's `ensure_fleet` would rewrite the live agents' `ragflow_scope` blocks
back to the **deleted** dataset names on its next document job, and since the
tool-level allowlist would stay correct, retrieval would then fail closed. A
rollback therefore needs `ensure_fleet` re-run from a v22 image afterwards.

## Evidence retained deliberately

The six `verification*` job rows in `docengine.jobs` are kept, not cleaned up.
They carry the persisted diagnostics (`markdown`, `qa_audit_history`, `verify`)
for every failure above, and the `-006`/`-007` pair is the record of the grid
defect and its fix. `docengine.documents` holds `VERIFY-ANNEX-006`,
`VERIFY-ANNEX-007` and `PROD-ANNEX-001`.

## Still open

- **Three corpora are not in RAGflow** — `DB3_PP_CURRENT_unified`,
  `DB1_REGULATORY`, `GrowFlow_Weekly_Snapshots`. Four agents draft without
  grounding until they exist, and their scope blocks say exactly that. Waiting
  on the owner to point at the source knowledge base.
- **Two PATs still need rotating** (`ghp_r43p…`, `ghp_AadT…`), per the
  credential-hygiene note in `DEPLOY-2026-08-26-v90.md`.
