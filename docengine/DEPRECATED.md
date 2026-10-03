# About the "frozen mirror" note that used to live here

Until 2026-09-27 this file said that `docengine/` was a frozen mirror of
`3p4e/letta-stack`'s `apps/wwf-docengine/`, received no engine edits, and that
WWF only *consumed* a DocEngine developed elsewhere (owner decision of
2026-08-09).

That is not what happened, and the note misled the 2026-09-27 review. Every
production DocEngine image since then — `growflow-docengine:v22` (2026-08-29)
through `v26` (2026-09-07), see `docs/DEPLOY-2026-09-*-docengine-v*.md` — was
built from **this** tree, and the service code here (`app/`, `agents/`,
`tests/`) has been developed and reviewed here continuously. This directory is
the source of the deployed service, not a mirror of it.

What is still true:

- `engine/` is the vendored formatting core. Its provenance and the merge it
  represents are recorded in `engine/PROVENANCE.md` and
  `docs/DOCENGINE-CANON-2026-07.md`; edit it only with that record updated.
- The second copy of the engine that used to sit at `pp-document-suite/` was
  never in the image and never imported; all six of its scripts had drifted from
  `engine/scripts/`, which is the confusion `docs/DEPLOY-2026-08-31-docengine-v23.md`
  (R3) ran into. It was removed on 2026-09-27. `engine/` is the only copy.
- Whether `3p4e/letta-stack` still carries a copy of this app, and whether
  anything there should flow back here, is a question for the owner; nothing
  in this repository depends on it.
