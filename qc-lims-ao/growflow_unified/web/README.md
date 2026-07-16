# GrowFlow Unified — Web (P4)

The converged SPA: **T_PLAN's React+Vite+TypeScript** planner (navy/gold design
tokens, bilingual EN/МК, JWT session) extended with the converged screens.

## What was grafted

| Area | File(s) |
|---|---|
| **Adaptive Task Tree** (task→annex→Draft/Review/Approve, expand/collapse, SOP + kind chips) | `views/TreeView.tsx` |
| **Governance** (change_proposal list, approve/reject for approvers, field registry) | `views/GovernanceView.tsx` |
| **AI Assistant drawer** (invokes bound agents, graceful degradation) | `views/AiDrawer.tsx` |
| **Settings** (AI provider toggle, compliance badges, OTP user provisioning) | `views/SettingsView.tsx` |
| **Forced first-login change** gate | `views/ChangePassword.tsx` |
| Shell nav + AI button + new routes | `PlannerShell.tsx`, `App.tsx` |
| Typed API + models | `api/planner.ts`, `types/models.ts` |
| Bilingual strings (EN/МК) | `i18n.ts` |

## Flows

- **Login → forced change.** If `must_change_password`, the app renders
  `ChangePassword` until the temp password is replaced (mirrors the backend guard).
- **This Week** (`MyWeek`) is the command dashboard; **Board** is the weekly grid;
  **Task Tree** is the adaptive hierarchy; **Governance** is the change-control queue;
  **Executive** (exec/admin) is analytics; **Settings** holds AI + provisioning.
- **AI Assistant** opens from the header on any screen, lists active capabilities
  from `/ai/functions`, and shows `available:false` reasons when Letta is offline.

## Config / build

- API base via `VITE_PLANNER_API` (defaults to `http://127.0.0.1:8765`).
- `npm install && npm run build` → `dist/` (served by nginx in the image).
- **Verified:** `tsc && vite build` passes clean (strict, noUnusedLocals/Parameters)
  — 1596 modules, 0 type errors.
