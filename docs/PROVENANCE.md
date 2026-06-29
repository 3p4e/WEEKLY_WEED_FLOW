# Provenance & Isolation Notes

This repository is the **task‑tracking application** isolated from the larger
**GrowFlow** "Cloud Design" source — an all‑encompassing cannabis‑factory
**QMS + production task‑tracking + QC‑LIMS** suite designed for Purely Plant.

## What was isolated

The original design shipped a *unified* app (`GrowFlow Unified.html`) that loaded
two independent module sets behind a mode switch:

- **Production (task tracking)** — the `gf/*` modules.  ← **included here**
- **QC Lab (LIMS)** — the `qc/*` modules (CoA, OOS, stability, sampling, specs,
  equipment qualification, registers, login/RBAC, …).  ← **excluded**

This build takes **only the production task‑tracking surface** and packages it as
a clean standalone app.

## Mapping (design source → this repo)

| Design source                          | Here                         |
|----------------------------------------|------------------------------|
| `gf/*.js`, `gf/*.css`                   | `web/gf/`                    |
| `assets/pp-*.png`                       | `web/assets/`                |
| `GrowFlow App.html` / `Unified.html`    | basis for `web/index.html` (+ kept in `docs/` for reference) |
| `backend/` (FastAPI + Letta)            | `backend/` (QC endpoints removed) |
| `deploy/` (Docker + nginx)              | `deploy/`                    |

## Decoupling changes

- **`qc/boot-guard.js` → `web/gf/boot-guard.js`** — the original schema‑guard
  lived in the QC folder and cleared both `gf_*` and `qc_*` localStorage keys.
  The standalone copy only touches `gf_*` keys, removing the `qc/` dependency.
- **Unified `APP` controller dropped** — `web/index.html` wires the UI directly
  to the `GF.*` API (the app self‑boots via `gf/main.js` on `DOMContentLoaded`),
  instead of the QC‑coupled `window.APP` mode‑switch controller.
- **Backend QC endpoints removed** — `/ai/lab-search` and `/ai/anomaly-check`
  (and their request models) were dropped from `backend/main.py`; the
  task‑relevant endpoints remain.
- The single remaining optional QC reference (`window.QC && QC.lang` in
  `gf/leaf-fx.js`) is a guarded fallback and is harmless without the QC module.

## Not included (by design)

The QC‑laboratory / QMS modules — CoA generation, OOS/OOT investigations,
stability studies, sampling plans, spec limits, equipment qualification,
certificate registers and the LIMS login/RBAC — are **not** part of this
task‑tracking application. "QC" remains only as one of the eleven **departments**
that own production tasks.
