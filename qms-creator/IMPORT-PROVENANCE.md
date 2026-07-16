# Import provenance

This directory is a verbatim monorepo import of another project, brought in
at the owner's request ("include in this project all of
claude/purely-plant-task-recorder-bbwkl2").

- **Source repository:** `3p4e/Cannabis-EU-GMP-QMS-Creator` (private)
- **Source branch:** `claude/purely-plant-task-recorder-bbwkl2`
- **Source commit:** `581906fb14299aa64bce0c530c993e1fa2682db7`
  ("Fix embedding model + client pin, verified against live kvm4 Letta")
- **Imported:** 2026-07-15
- **Method:** exact copy of the branch's 994 git-tracked files (verified by
  `git ls-files` count parity); history stays in the source repo.

## What this project is

**Cannabis EU GMP QMS Creator** — a standalone application that generates
EU-GMP QMS documentation (SOPs, forms, training matrices) for the Purely
Plant facility: FastAPI backend (`CONTENT_CREATOR_FRAMEWORK/`), React 19 +
TypeScript frontend (`qms-ui-v2/`), Letta AI integration (RAG over the
facility document base, agent-driven SOP drafting), 77 pre-configured SOPs
across 9 departments, and its own Docker stack.

## Relationship to WWF/GrowFlow

The two apps are SEPARATE deployables sharing this repository. Nothing under
`qms-creator/` is imported by `backend/` or `web/`, and the repository's CI
only exercises `backend/` and `web/` — the nested `.github/` here is inert
(GitHub only runs workflows from the repository root). The QMS Creator's own
compose files (`docker-compose.yml`) still work from inside this directory.

Scope note: WWF/GrowFlow itself remains informational-only (no GMP/QMS
records — see docs/SCOPE.md). The QMS Creator is the document-authoring tool;
importing its source here does not change WWF's scope.
