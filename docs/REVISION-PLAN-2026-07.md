# WWF / GrowFlow — Revision Plan (2026-07-14)

A ground-up re-analysis triggered by the owner's assessment that the app is a
"patchwork": subtasks can't be completed, the COO's input is invisible, nobody
is notified of anything, the "Mass Weed" design was only skinned, and many
requested changes (dropdowns → popups) were never built. This document records
what is **actually** true in the code (four parallel audits + live-data
reproduction), what leading comparable apps do, and a concrete phased plan.

Every finding below was verified against the running production database or the
source — not assumed.

---

## 1. Confirmed diagnosis (evidence-backed)

### 1.1 Subtasks cannot be started or completed — CONFIRMED, CRITICAL
The start/complete lifecycle (clickable status pill + checkbox → `cycleStatus`/
`toggleDone` → PATCH) was built **only** for top-level cards (`render.js:220,231`).
On a subtask row the pill was rendered inert (`render.js:310`,
`style="pointer-events:none"`), there was no checkbox, and the edit modal has no
status field. So from the UI there was **no way at all** to move a subtask off
"Not started."

Worse, effort and progress are fully decoupled from status: logging a work
session (`worklog.js`→`add_session`, a pure INSERT, `tasks.py:580`) and adding a
progress note (`add_progress`, `tasks.py:530`) never touch `status`, and nothing
auto-advances it. **Live proof:** task `3e7c9971` has subtask `6e5e320c` with a
real 1-hour work session logged, yet its status is still `pending` ("Not
started"). → **Fixed in Phase 0 (this change set).**

### 1.2 The COO's input is invisible to the team — CONFIRMED
`tasks_read` RLS (`schema.tasks.sql:967`) shows a task to: its owner, any
elevated role, or an explicit assignee. An exec/COO is org-wide and NOT
dept-scoped, so `create_task` does not auto-fill a department
(`tasks.py:313-318` only fires for dept-scoped roles). Result: a COO-created
task typically has **no department and no assignee** → visible only to *other*
org-wide roles, invisible to the managers and operators it's meant for. It
didn't disappear; it fell into a visibility gap.

### 1.3 There is no notification system — CONFIRMED
No notifications table, no endpoints, no email (OTP email is a stubbed
"added later" TODO, `auth.py:269`), no inbox, no unread badge, no activity feed.
Every "notification" is a 3-second client-side `GF.toast` (`core.js:426`).
Assignment (`collab.py:101`) and comments produce no durable signal. "Nobody
gets notified of anything" is literally true.

### 1.4 Six real accounts are locked out — CONFIRMED
`coo.fros` (Frosina, COO), `mam.rez`, `sem.andr`, `whm.log`, `qca.hris`,
`qca.mar` all have `password_set_at = NULL` → their create-time OTP was never
used, and because OTPs are only shown once on the creator's screen (no email),
their passwords are lost. They cannot log in. Recovery = an ADMIN re-issues a
fresh OTP per account (`POST /auth/users/{id}/reset-password`) and hands it over.

### 1.5 "Mass Weed" is a skin, not the redesign — CONFIRMED
`mass-weed.css` is a pure color-palette + HUD-chrome overlay (chamfered corners,
cyan glow) on the *existing* generic `.btn`/`.modal`. It is the default theme and
was not reverted — but there is no bespoke new-task popup and no new screens.
The repeatedly-requested conversion of **~19 `<select>` dropdowns → popup
choosers** was never built (not added-then-reverted — simply never built),
despite reusable chooser scaffolding already present (`GF.openThemePicker`,
`cmdk.js` ⌘K palette, `GF.openModal`).

---

## 2. What comparable apps do (research, cited)

Closest open-source references to study: **Leantime** (roles + time logged
directly on the task; built for non-PM staff), **Plane** (sub-issues as
first-class children with their own work logs; Cycles ≈ weekly plans with
burn-down; shared Views/analytics), **Vikunja** (clean task attributes +
relations + inline quick-add). **OpenTHC** is the credible open cannabis stack
but is compliance/traceability, not ops/tasks — domain reference only.
(Open-source GMP/EBR systems effectively don't exist; moot since WWF is
non-GMP.)

Patterns worth adopting:

- **Row-level status, keyboard-first** (Linear): every task *and subtask* row
  carries its own status control; a single click on a leaf completes it; status
  is never buried in a modal. `linear.app/docs/configuring-workflows`,
  `linear.app/docs/parent-and-sub-issues`.
- **Parent auto-completes when all children are done**, and a **progress ring =
  done children / total** on the parent (Linear default). Sub-issues inherit
  parent context (team/priority) but not labels.
- **Keep time / progress / status independent** (Leantime): time is the effort
  ledger for reporting, status is the human's explicit signal, progress % is
  derived from children. Don't flip status from hours; don't compute % from
  hours. This is what lets an exec see planned-vs-actual effort without
  corrupting completion state.
- **Inbox + unread + optional email/digest, separate from a shared activity
  feed** (Asana): the inbox is per-user, actionable, dismissible, with filters
  (Assigned to me / @Mentioned / Assigned by me) and quiet hours; the activity
  feed is shared, append-only history. WWF needs both — they are different
  surfaces. `asana.com/features/project-management/inbox`.
- **Bilingual done right:** store activity as **structured events**
  (verb + object + actor + timestamp) and render the sentence in EN or МК at
  display time — never store pre-composed English strings, or the Macedonian
  feed drifts.
- **Command-palette / popup choosers** (`cmdk`) are a good replacement for heavy
  searchable dropdowns (assignee, department, status, task picker) **as an
  accelerator over visible tap targets** — not a replacement that hides
  everything behind ⌘K (which is unreachable on the phones used on the grow
  floor). If adopted, follow the ARIA combobox pattern for accessibility.

## 3. Tech direction — modernize, do NOT rewrite

The vanilla-JS PWA works, is offline-capable and installable — real assets a
rewrite would risk. "Patchwork" is a structure-inside-the-files problem (global
state, hand-rolled `innerHTML`, copy-pasted rendering), not a wrong-language
problem; a framework doesn't fix that, discipline does. Highest-ROI path,
incremental, app shippable throughout:

1. **Vite build + ES modules** — kills script-ordering/global-leak pain.
2. **Incremental TypeScript** on the data model (Task, Subtask, WeeklyPlan,
   User/Role, TimeLog, ActivityEvent) — catches the bug class patchwork apps are
   riddled with.
3. **One state store** (nanostores / Preact Signals) replacing scattered globals.
4. **Componentized rows** (Preact islands if components are wanted) — subtask
   rows, inbox items, activity-feed items become reusable components.
5. **Keep the PWA shell** (service worker, offline, install) — a real edge over
   the SaaS comparables.

Do NOT jump to Next.js/SSR (wrong paradigm for an internal ops PWA) or rewrite
from scratch (re-loses bilingual coverage, offline behavior, battle-tested
edge cases for zero user-visible gain).

---

## 4. Phased plan

### Phase 0 — Immediate, no-regret (in this change set)
- **Subtask lifecycle fix**: real completion checkbox + clickable status pill on
  every subtask row (mirrors cards); logging a work session auto-advances a
  still-"Not started" task to "Working on it". (`render.js`, `worklog.js`,
  `data.js`, SW bump.)
- **Unlock the 6 accounts**: re-issue OTPs (owner-relayed) — *pending owner
  go-ahead; credential handling is the owner's call.*

### Phase 1 — Awareness (biggest missing capability)
- Backend: `notifications` table (org-isolated: user_id, type, task_id,
  read_at) written at assign / comment / ack / status-change; `GET
  /notifications` + unread count + mark-read.
- Shared, append-only, **bilingual activity feed** from structured events — the
  "COO sees what the team did" surface, roll-up by person/department per week.
- Frontend: nav inbox badge + inbox view (Asana-style filters) + activity feed
  view. Reuse toast for live display. Email/digest later (needs SMTP).

### Phase 2 — Visibility & onboarding
- Make **department and/or assignee required** on task creation (or block
  orphan top-level tasks) so exec-created work reaches its audience.
- Persistent **"pending activations + OTPs" admin view** so OTPs aren't lost
  after the creation response scrolls away; optionally wire the stubbed OTP
  email delivery.

### Phase 3 — Interaction redesign (the Mass Weed intent + choosers)
- One reusable `GF.choose()` popup chooser (generalize `openThemePicker` +
  `cmdk`); convert the heavy/searchable `<select>`s (assignee, department,
  status, priority, type, language) — as an accelerator over visible touch
  targets, ARIA-combobox accessible.
- A bespoke new-task popup matching the Mass Weed HUD intent (not just chamfer
  on the generic modal).
- Parent auto-complete-when-children-done + progress ring (Linear pattern).

### Phase 4 — Foundational modernization (optional, high-ROI)
- Vite + incremental TypeScript + one state store + componentized rows
  (Section 3). No rewrite; ship continuously.

---

## 5. Sources
Leantime `github.com/Leantime/leantime` · Plane `github.com/makeplane/plane` ·
Vikunja `github.com/go-vikunja/vikunja` · OpenTHC `openthc.com` ·
Linear workflows & parent/sub-issues `linear.app/docs` · Asana inbox
`asana.com/features/project-management/inbox` · command-palette pattern
`uxpatterns.dev/patterns/advanced/command-palette` · cmdk
`github.com/pacocoursey/cmdk`.
