# Scope: WWF is a non-GMP planning tool

This is a deliberate, explicit decision, not an oversight: **Weekly Weed Flow
(WWF) is an internal operational planning and task-tracking tool. It is not a
validated GxP / 21 CFR Part 11 computerized system, and it is not part of the
Quality Management System (QMS).** For now, it will not be.

## What this means in practice

- **Authoritative CAPA, SOP, validation, and qualification records live in
  the QMS** — not here. A WWF task that references a CAPA or an SOP is a
  *pointer* to that record for planning purposes; it is not the record
  itself, and its status in WWF is not evidence of the underlying record's
  state.
- **AI-generated content (weekly reports, next-week plans) is informational
  only** — a planning aid, not an official record. It is labeled as such
  in-app (see the report view's "AI-generated — informational draft, not an
  official record" note next to every AI pin) and is never auto-approved or
  presented as validated output.
- **Older reference mockups under `docs/`** (e.g. `GrowFlow Unified.html`,
  which shows compliance-badge UI elements as part of an early, unused
  design mockup — see `docs/PROVENANCE.md`) predate this decision and do not
  reflect WWF's current scope.
- The facility itself operating under GMP licensing is a true, unrelated
  fact about the business — it does not make WWF itself a regulated
  computerized system. AI prompts and other content that describe "a GMP
  cannabis facility" are describing that real-world context, not making a
  claim about WWF's own validation status.

## Why this resolves cleanly

WWF's own 2026-07 architecture review (`docs/ARCHITECTURE-REVIEW-2026-07.md`,
§7) laid out the Annex 11 / Part 11 gap: no validation lifecycle, no
electronic-signature workflow, no MFA, no tested backups (now addressed —
see `docs/BACKUP.md`), AI output with no human-approval gate. Closing that
entire gap (§7's "Option B") is only worth doing if WWF is meant to *replace*
part of the paper/QMS process. Scoping it instead as a non-GMP planning aid
(§7's "Option A", adopted here) means most of that gap simply stops applying
— the tool is not claiming to be something it would need to be validated to
actually be.

If that changes in the future — if WWF is ever meant to hold or evidence a
GMP-relevant record directly — this document is the place to update, and the
§7 gap analysis in the architecture review is the checklist for what full
validation would require.
