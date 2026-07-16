# Import provenance — qc-lims-ao/

Imported VERBATIM from the owner's private repository:

- **Source:** https://github.com/3p4e/QC_LIMS_Ao.git
- **Branch:** `main`
- **Commit:** `765818f4e083055df518d7d62f898f5b6800a3f4` (2026-06-29 12:58:31 +0200)
- **Imported:** 2026-07-16, on owner's directive: *"assimilate the QC_LIMS_Ao
  repo app completely into our unified app, intelligently"*.
- **Files:** 328 tracked files (~20 MB), `.git` removed.

## What this is

"GrowFlow Unified" prototype (React + Vite SPA / FastAPI + async SQLAlchemy /
single `qc_lims` Postgres) with two modes: a Production task board and a deep
**QC LIMS** workspace — samples, specifications, CoA, OOS, CAPA, stability,
transport, water-system QC, sampling requests, Annex-11 audit trail, plus
lifecycle/validation/numbering services and a comprehensive vision/ADR doc
(`QC_LIMS_Comprehensive_Vision_and_Architecture.md`, 2026-05-24).

## Assimilation decision (owner, 2026-07-16)

THIS repo (WWF/GrowFlow, the live app on wwf_app/wwf_mass) remains the one
unified application. QC_LIMS_Ao is **assimilated into it natively** — its QC
domain model, workflows, services and vision are the source of truth for the
GrowFlow **QC LIMS module**, rebuilt on WWF's foundations (FastAPI two-DB +
RLS + hash-chained audit, vanilla-JS bilingual PWA, DocEngine for controlled
forms/CoA output, same containers/URLs). It is NOT deployed as a second app
and its stack is NOT adopted wholesale.

## Notes

- `weekly_weed_flow/` and `growflow_unified/` inside this import are **stale
  snapshots of earlier WWF/GrowFlow lines** absorbed by that repo — they are
  superseded by this repository itself; kept only for provenance.
- Its task-management lifecycle work (assignment accept/decline, outcome,
  weekly snapshot → Letta) is harvest material for the priority-#1 TMS.
- Approved QC-department SOPs (Drive folder `1oPEIlNTWMutZIineO6Pb_DC3HZ9ue1WM`,
  QCSOP 001–024) are the regulatory workflow authority the assimilated module
  must follow where the prototype and the SOPs disagree.
