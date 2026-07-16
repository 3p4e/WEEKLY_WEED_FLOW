# WEEKLY_WEED_FLOW — Adaptation Specification

> **Status:** Design-of-Record · **Date:** 2026-06-28 · **Owner:** Purely Plant GmbH
> **Target deployment:** KVM4 VPS (sibling to QC_LIMS_Ao1) · **Project:** `weekly_weed_flow` · **Repo:** `3p4e/WEEKLY_WEED_FLOW` (private)

This document is the complete adaptation specification for **WEEKLY_WEED_FLOW** ("Weekly Weed Flow" — internal name "GrowFlow Weekly"), a weekly task-board and cross-departmental coordination system for Purely Plant's GACP cultivation and EU-GMP production teams. It inherits the visual language, design tokens, bilingual UI, and deploy infrastructure of QC_LIMS_Ao, while adopting a substantially stricter authentication, authorization, and audit model derived from the ISO17verSUMA principles (full SUMA checklist mapped in §14).

The spec is the design-of-record: code generation in subsequent turns is derived **directly** from this document. Where alternatives are conceivable, the decision is locked in §0 and not re-opened downstream.

---

## 0. Decision Log

Every architectural decision, why we picked it, and what we rejected.

| # | Decision | Why | Rejected alternative |
|---|---|---|---|
| D1 | **No Supabase, no GoTrue, no Edge Functions** | The SUMA reference stack is Supabase-shaped; QC_LIMS_Ao is a hand-rolled FastAPI app with bcrypt + python-jose JWT. WEEKLY_WEED_FLOW must be deployable on the same KVM4 sibling pattern with zero new managed services. We extract the *principles* from SUMA (RLS, hash-chained audit, OTP provisioning, forced password change) and reimplement them on plain Postgres 16. | Adopting Supabase Self-Hosted — pulls in GoTrue/PostgREST/Realtime/Storage/Studio, conflicts with sibling deploy pattern, doubles attack surface, and re-introduces the "anon key reaches anything without RLS" footgun. |
| D2 | **Custom auth: bcrypt + python-jose HS256 JWT** | Matches QC_LIMS_Ao exactly. `backend/app/core/security.py` is reusable as-is for hashing and token mint/verify. Single login endpoint, single signing key, no parallel provider to disable. | Auth0/Clerk/Keycloak — adds external dependency and per-seat cost; we already have the primitives. |
| D3 | **Two Postgres roles: `app_user` (NOBYPASSRLS) and `app_admin` (BYPASSRLS)** | Provisioning paths must touch rows the caller cannot legitimately see (creating a new user, writing audit attribution). A separate BYPASSRLS role makes the bypass decision grep-able in the code rather than buried in `SET row_security = off` calls. | Single role with conditional bypass — moves the decision into app code where audit/reviewers cannot easily inspect it. |
| D4 | **Two SQLAlchemy engines, two env vars (`DATABASE_URL`, `BYPASS_DATABASE_URL`)** | Mirrors the two-role model at the Python layer. Importing the admin engine from a request handler becomes a visible, reviewable act. | Single engine with role switching — every per-request `SET ROLE` is one bug away from privilege escalation. |
| D5 | **Postgres RLS as the real boundary, app-layer checks as defence-in-depth** | Even if a service function forgets a `WHERE assignee_id = me` filter, the database refuses to leak the row. This is the GMP / 21 CFR Part 11 mindset. | App-layer-only checks — works in practice until it doesn't; one missed filter is a breach. |
| D6 | **Per-request `SET LOCAL app.user_id = …` inside an explicit transaction** | asyncpg pools connections; `SET` (session-scoped) would leak identity across requests on the same connection. `SET LOCAL` is transaction-scoped and pool-safe. Use `set_config(name, value, true)` (the function form) so the value can be bind-parameterized. | `SET app.user_id = …` (session) — catastrophic identity leak on pooled connections. Raw `SET LOCAL` with f-string interpolation — SQL-injection vector. |
| D7 | **JWT carries `sub, role, dept_id, org_id` but `get_current_user` re-reads role+dept from `profiles` on every request** | A stale claim cannot escalate privileges (per SUMA principle #34). Short JWT TTL (15 min) keeps propagation tight. | Trust JWT claims for role/dept — a deactivated user could keep acting until their token expires. |
| D8 | **OTP provisioning by ADMIN/DEPT_HEAD only (no self-signup)** | SUMA principle: self-signup is the most common abuse vector. All accounts created by privileged users; OTP is returned synchronously in the API response (Resend email is best-effort, never blocking). | Public registration — removes the chain-of-custody for account creation. |
| D9 | **Unambiguous OTP alphabet `ABCDEFGHJKMNPQRSTUVWXYZ23456789`, format `K7PM-4QWS-9TXR` (3×4 grouped)** | Excludes `0/O`, `1/I/l`. Phone-readable and email-readable. Single-use, forces password change on first login. | Numeric-only — too short for the entropy we want; collides with reset codes. |
| D10 | **Forced password change on first login via `must_change_password` flag** | Per SUMA principle #22. Gate lives in `get_current_user` (server enforcement) AND `App.jsx` (UX). The first-login change does NOT require the current password (user already authenticated with the OTP). | Hard-coded password expiry policies — heavy and irrelevant; we want a one-shot rotation. |
| D11 | **Self-service password reset via 6-digit email code** | Per SUMA principle #17. Hashed-and-stored, 15-min TTL, single-use, rate-limited, same-shape response for unknown emails (no enumeration). | Magic-link reset — requires hosted redirect endpoint; OTP-style is simpler and works in plain-text email. |
| D12 | **Email via Resend (`RESEND_API_KEY` env var already present)** | Lightweight HTTP API, bilingual templates trivial, no SMTP infrastructure. Email is OPTIONAL — every OTP/reset code is also returned to the creator's screen. | SMTP relay — adds a moving part; Resend free tier covers our volume. |
| D13 | **Hash-chained audit via Postgres `AFTER INSERT/UPDATE/DELETE` trigger** | Cannot be bypassed by direct SQL or by a forgetful service function. Hash uses `encode(digest(convert_to(payload, 'UTF8'), 'sha256'), 'hex')` to avoid the `text::bytea` gotcha (SUMA principle #45 / #60). | App-layer-only audit (current QC_LIMS_Ao pattern) — `AuditMiddleware` can be bypassed by background jobs and by direct DB access. We KEEP the middleware as a *context enricher* (sets request-id GUC) and add the trigger as the system-of-record. |
| D14 | **`audit_log` table: INSERT-only for app roles; UPDATE/DELETE/TRUNCATE revoked from both `app_user` and `app_admin`** | Append-only is the GMP requirement. Only `postgres` superuser (Alembic migrations) can ever touch existing rows. | Single grant-all-then-policy-deny — relies on policy correctness; revoking the privilege belts-and-braces. |
| D15 | **4-tier role hierarchy: ADMIN → DEPT_HEAD → TEAM_LEADER → USER, plus PROJECT_LEAD (orthogonal)** | Matches the user's stated org chart. PROJECT_LEAD is cross-departmental and scoped by project membership rather than department. QA_AUDITOR is added as a read-everywhere/write-nothing role for compliance review. | Flat role list — fails to express the dept-scoped management chain SUMA's `canManage` matrix relies on. |
| D16 | **Cross-departmental handoffs are a first-class entity (`handoffs` table)** | The QC_LIMS_Ao Production board models handoff as a UI button that fires a toast. WEEKLY_WEED_FLOW requires persisted, accept/reject workflow with audit trail (a Cultivation→Production handoff is GMP-relevant). | Encode handoff in `task.notes` — un-queryable, unauditable. |
| D17 | **Soft-delete via `is_deleted` flag; never hard-delete GMP data** | Inherited from QC_LIMS_Ao + 10-year retention requirement. Hard-DELETE allowed only for `task_dependencies` join rows (relation changes, not data). | Hard-delete with archive table — doubles the schema. |
| D18 | **Async SQLAlchemy 2.0 + asyncpg throughout** | Inherited from QC_LIMS_Ao. All service-layer code is `async def`. | Sync mode — backwards step. |
| D19 | **Frontend uses controlled inputs everywhere** | QC_LIMS_Ao uses uncontrolled `defaultValue` + `getElementById` (App.jsx:172-179). For OTP / password forms this is brittle. WWF mandates `useState`-driven inputs. | Inherit the uncontrolled pattern — risks subtle reset bugs in auth flows. |
| D20 | **`shared/` module for ui.jsx, icons.jsx, i18n.js, app.css, brand.css, http.js** | The QC LIMS shell and WWF shell consume the same primitives without one importing the other. | Copy-paste — divergence within weeks. |
| D21 | **Mode toggle (QC/Prod) does not transfer — WWF has roles, not modes** | App.jsx mode pills become role-based landing dispatch. Each role gets one console. | Three-mode shell — confuses the model. |
| D22 | **Sibling Compose deploy on KVM4, project name `weekly_weed_flow`** | Containers: `weekly_weed_flow-{db,backend,frontend}-1`. Traefik host `weekly.srv1231216.hstgr.cloud` (default; flagged in §15). Own Postgres database (NOT shared with QC_LIMS_Ao). | Shared DB with QC_LIMS_Ao — conflicts with the "two-roles per app" model and complicates RLS reasoning. |
| D23 | **Alembic from day one (not `Base.metadata.create_all`)** | QC_LIMS_Ao's create_all bootstrap is flagged as tech-debt; we don't inherit that debt. Migration `000_init_extensions.sql` enables pgcrypto immediately. | Defer Alembic — every spec needs a versioned schema. |
| D24 | **Seed bootstraps only `admin22` (ADMIN role, must_change_password=TRUE) on first deploy** | The human admin then provisions everyone else via the normal OTP flow. Demo-data gate (`SEED_DEMO_DATA`) inherited from QC_LIMS_Ao. | Pre-seed depts and users — bypasses the very provisioning audit trail we're building. |
| D25 | **`admin22` re-seeded fresh in WWF (separate DB from QC_LIMS_Ao)** | Each app owns its own user table; sharing accounts across LIMS and Flow couples release cycles. | Federate to QC_LIMS_Ao's users — operational coupling. |
| D26 | **GitHub Actions runner-based deploy channel, same SSH pattern as QC_LIMS_Ao** | `bash deploy/kvm4.sh` works locally and from Actions. | Container registry push — overkill for two-app KVM4. |

---

## 1. Executive Summary

WEEKLY_WEED_FLOW is a bilingual EN/МК weekly task board for Purely Plant's cultivation (GACP) and production (EU-GMP) teams. It models *who is doing what this week*, who they hand it off to next, and produces a tamper-evident audit trail of every state change. The system is a sibling deployment to QC_LIMS_Ao on the same KVM4 host, runs in its own Docker Compose project, and uses its own Postgres database. It inherits QC_LIMS_Ao's design tokens, bilingual i18n, JWT auth primitives, and deployment scripts; it diverges on its authorization model (4-tier roles + PROJECT_LEAD), its persistence model (server-backed instead of localStorage), and its audit model (Postgres-trigger hash chain rather than middleware-only).

The authorization model is three-layered: a React `RoleGuard` for UX gating, a FastAPI `Depends(get_current_user)` for API enforcement, and Postgres Row-Level Security as the actual boundary. Every authenticated request runs inside an explicit transaction whose first statement is `SELECT set_config('app.user_id', :uid, true)` — a pool-safe pattern that surfaces JWT claims to RLS policies. Account provisioning is admin-only: ADMIN and DEPT_HEAD users create accounts via `POST /api/admin/users`, receive a single-use OTP returned synchronously in the response, and the recipient is forced through `<ForceChangePassword/>` on first login. Audit rows are written by a Postgres trigger that hashes `prev_hash || canonical_payload` with `sha256(convert_to(text, 'UTF8'))` — never `text::bytea` — and the `audit_log` table has zero UPDATE/DELETE policies plus explicit `REVOKE` on those privileges.

```
                       ┌──────────────────────────────────────┐
                       │     KVM4 (Hetzner, 72.60.35.12)      │
                       │                                      │
   weekly.srv1231216.  │   ┌───────────┐                      │
   hstgr.cloud         │   │  Traefik  │  ◀── shared network  │
   ───────────────────▶│   └────┬──────┘                      │
   (HTTPS, Let's       │        │                             │
    Encrypt)           │  ┌─────▼──────────────────────────┐  │
                       │  │ project: weekly_weed_flow      │  │
                       │  │                                │  │
                       │  │  frontend (nginx, static SPA)  │  │
                       │  │     ▲                          │  │
                       │  │     │ /api proxy               │  │
                       │  │  backend (FastAPI uvicorn)     │  │
                       │  │     ▲      ▲                   │  │
                       │  │     │      │                   │  │
                       │  │     │ app_user (NOBYPASSRLS)   │  │
                       │  │     │ app_admin (BYPASSRLS)    │  │
                       │  │     ▼      ▼                   │  │
                       │  │  db (Postgres 16 + pgcrypto)   │  │
                       │  │     - RLS on every table       │  │
                       │  │     - hash-chained audit_log   │  │
                       │  └────────────────────────────────┘  │
                       │                                      │
                       │  (sibling: QC_LIMS_Ao1, untouched)   │
                       └──────────────────────────────────────┘

       outbound: Resend HTTPS  (OTP + reset-code email, optional)
```

---

## 2. Repository Layout

```
WEEKLY_WEED_FLOW/
├── README.md                          # Setup, env vars, troubleshooting
├── CLAUDE.md                          # Project instructions for AI agents
├── LICENSE                            # MIT (private repo, marker only)
├── .env.example                       # All env keys with placeholder values
├── .gitignore
├── docker-compose.yml                 # db + backend + frontend (local + base for prod)
├── docker-compose.kvm4.yml            # Traefik labels overlay (prod-only)
├── nginx.conf                         # SPA + /api proxy
│
├── deploy/
│   ├── kvm4.sh                        # One-shot deploy to KVM4
│   ├── kvm4.env.template              # Production env template
│   └── traefik-check.sh               # Sanity-check Traefik routing
│
├── .github/
│   └── workflows/
│       ├── deploy-kvm4.yml            # On push to main → SSH deploy
│       └── ci.yml                     # pytest + npm build on PR
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml                 # deps pinned
│   ├── requirements.txt               # frozen lock
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       ├── 000_init_extensions.py        # pgcrypto, citext, uuid-ossp
│   │       ├── 010_roles_and_grants.py       # app_user, app_admin
│   │       ├── 020_core_tables.py            # departments, profiles
│   │       ├── 030_tasks_and_relations.py    # tasks, subtasks, notes, deps
│   │       ├── 040_handoffs.py
│   │       ├── 050_password_reset.py         # password_reset_codes, otp_audit
│   │       ├── 060_audit_log.py              # audit_log + indexes
│   │       ├── 070_rls_helpers.py            # SECURITY DEFINER functions
│   │       ├── 080_rls_policies.py           # ENABLE RLS + CREATE POLICY
│   │       └── 090_audit_trigger.py          # fn_audit_row + attachments
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app, lifespan, router includes
│   │   ├── seed.py                    # Idempotent admin22 bootstrap (gated)
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic Settings
│   │   │   ├── database.py            # SessionLocal (app_user) + AdminSessionLocal (app_admin)
│   │   │   ├── security.py            # bcrypt, JWT, OTP generator, password policy
│   │   │   ├── audit_context.py       # Middleware: stamps app.request_id / app.client_ip GUCs
│   │   │   └── deps.py                # FastAPI deps: get_session, get_current_user, require_role, can_manage
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # BaseModel, TimestampMixin, SoftDeleteMixin (verbatim from QC_LIMS_Ao)
│   │   │   ├── department.py
│   │   │   ├── profile.py             # 'profiles' table — name aligns with SUMA convention
│   │   │   ├── task.py
│   │   │   ├── task_subtask.py
│   │   │   ├── task_note.py
│   │   │   ├── task_dependency.py
│   │   │   ├── task_assignee.py       # m2m for helpers (task owner is single FK on tasks)
│   │   │   ├── handoff.py
│   │   │   ├── audit_log.py
│   │   │   ├── password_reset_code.py
│   │   │   └── otp_audit.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # LoginRequest, LoginResponse, ChangePasswordRequest...
│   │   │   ├── admin.py               # CreateUserRequest, CreateUserResponse (incl. otp)
│   │   │   ├── profile.py
│   │   │   ├── department.py
│   │   │   ├── task.py
│   │   │   ├── handoff.py
│   │   │   └── audit.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py        # verify_password, mint_jwt, lockout counter
│   │   │   ├── provisioning_service.py # OTP gen, create_user_atomic, reset_password
│   │   │   ├── password_reset_service.py # request + confirm flows
│   │   │   ├── authorization.py       # can_manage matrix
│   │   │   ├── task_service.py        # CRUD on tasks (RLS does the gate)
│   │   │   ├── handoff_service.py     # propose/accept/reject/withdraw
│   │   │   ├── audit_service.py       # app-level audit events (intent capture)
│   │   │   ├── email_service.py       # Resend HTTP wrapper, bilingual templates
│   │   │   └── department_service.py
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── audit_context.py       # request_id + client_ip → Postgres GUCs
│   │   │   └── error_handler.py
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── auth.py                # /api/auth/* (login, change-password, password-reset)
│   │       ├── admin.py               # /api/admin/users (provisioning)
│   │       ├── departments.py
│   │       ├── tasks.py
│   │       ├── handoffs.py
│   │       ├── profile.py             # /api/me
│   │       └── audit.py               # /api/audit (read-only, elevated roles)
│   └── tests/
│       ├── conftest.py                # async fixtures, ephemeral DB, identity-switch helper
│       ├── test_auth_flow.py
│       ├── test_provisioning.py
│       ├── test_rls_tasks.py
│       ├── test_rls_handoffs.py
│       ├── test_audit_chain.py
│       └── test_can_manage.py
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx                     # Shell, auth gate, role-based dispatch
        ├── shared/                     # COPIED (not symlinked) from QC_LIMS_Ao
        │   ├── ui.jsx                  # Modal, Avatar, AvatarStack, ToastProvider, Spinner + new Field/Button/Select/EmptyState
        │   ├── icons.jsx               # SVG icon dict + new entries: key, eye, eye-off, copy
        │   ├── i18n.js                 # tr(), useLang(), setGlobalLang()
        │   ├── style.js                # css() helper
        │   ├── http.js                 # bare request() function (extracted from QC client.js)
        │   └── styles/
        │       ├── app.css             # Design tokens + component classes
        │       └── brand.css           # Wordmark, splash animations
        ├── api/
        │   └── client.js               # WWF endpoints: auth, admin, tasks, handoffs, departments, audit, me
        ├── auth/
        │   ├── LoginPage.jsx           # Single-component state machine: splash → menu → login → forgot → reset
        │   ├── ForceChangePassword.jsx # Modal-style gate, full-screen
        │   ├── RoleGuard.jsx           # <RoleGuard allow={['ADMIN','DEPT_HEAD']}>...</RoleGuard>
        │   ├── SpeedDial.jsx           # localStorage chip rack (no secrets)
        │   └── AuthContext.jsx         # {user, login, logout, refresh, mustChange}
        ├── wwf/
        │   ├── data.js                 # WWF_I18N flat dict (EN/МК), no PEOPLE/DEPTS seed
        │   ├── labels.js               # makeLabels(lang)
        │   ├── useTasks.js             # Server-backed mutation hook (replaces useProduction)
        │   ├── useHandoffs.js
        │   ├── useUsers.js
        │   ├── screens/
        │   │   ├── UserDashboard.jsx          # USER role
        │   │   ├── TeamLeaderConsole.jsx      # TEAM_LEADER role
        │   │   ├── DeptConsole.jsx            # DEPT_HEAD role
        │   │   ├── ProjectLeadConsole.jsx     # PROJECT_LEAD role
        │   │   ├── AdminConsole.jsx           # ADMIN role
        │   │   └── AuditViewer.jsx            # elevated readers
        │   └── components/
        │       ├── TaskWorkspace.jsx          # Adapted from production/ProductionWorkspace.jsx
        │       ├── TaskCard.jsx               # Adapted from production/TaskCard.jsx
        │       ├── AddTaskModal.jsx
        │       ├── HandoffTray.jsx
        │       ├── CreateAccountForm.jsx      # Admin/HOD account-creation modal
        │       ├── OtpDisplayModal.jsx        # "Copy or send this OTP — it won't be shown again"
        │       ├── DepartmentManager.jsx
        │       └── Telemetry.jsx
        └── lib/
            └── (intentionally empty — everything is in shared/)
```

---

## 3. Data Model

All UUIDs are Postgres-native `uuid` with default `gen_random_uuid()` (from pgcrypto). All timestamps are `timestamptz` defaulting to `now()` (UTC). All governed tables inherit `created_at`, `updated_at`, `is_deleted` from `BaseModel` (mirrors QC_LIMS_Ao's pattern).

### 3.1 `departments`

Cultivation/Production org units. The HOD authority scope.

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `id` | uuid | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `code` | text | NOT NULL | — | UNIQUE, CHECK length 2-16, uppercase |
| `name_en` | text | NOT NULL | — | — |
| `name_mk` | text | NOT NULL | — | — |
| `parent_dept_id` | uuid | NULL | — | FK → departments(id) ON DELETE SET NULL |
| `head_user_id` | uuid | NULL | — | FK → profiles(id) ON DELETE SET NULL (set later) |
| `color` | text | NOT NULL | `'#6B7280'` | CHECK matches `^#[0-9A-Fa-f]{6}$` |
| `icon` | text | NULL | — | One of icon names from icons.jsx |
| `sort_order` | int | NOT NULL | `0` | — |
| `created_at` | timestamptz | NOT NULL | `now()` | — |
| `updated_at` | timestamptz | NOT NULL | `now()` | trigger-updated |
| `is_deleted` | boolean | NOT NULL | `false` | INDEX |

**Indexes:** `(code)` UNIQUE, `(parent_dept_id)`, `(is_deleted)`.
**Notes:** `parent_dept_id` lets us model Cultivation → {Clone, Veg, Flower} without a separate "team" table for the initial scope. `head_user_id` is the DEPT_HEAD per SUMA's authority-scoping principle (#30).

### 3.2 `profiles`

The user table. Named `profiles` (not `users`) to align with SUMA conventions and to keep room for future federated auth.

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `id` | uuid | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `email` | citext | NOT NULL | — | UNIQUE |
| `username` | text | NOT NULL | — | UNIQUE, CHECK length 2-64 |
| `display_name_en` | text | NOT NULL | — | — |
| `display_name_mk` | text | NULL | — | — |
| `password_hash` | text | NULL | — | bcrypt; NULL only during OTP-only pre-activation |
| `password_set_at` | timestamptz | NULL | — | Set when user completes ForceChangePassword |
| `must_change_password` | boolean | NOT NULL | `true` | Forced rotation gate |
| `role` | text | NOT NULL | `'USER'` | CHECK ∈ ('ADMIN','DEPT_HEAD','PROJECT_LEAD','TEAM_LEADER','USER','QA_AUDITOR') |
| `dept_id` | uuid | NULL | — | FK → departments(id) ON DELETE RESTRICT |
| `org_id` | uuid | NOT NULL | `'00000000-0000-0000-0000-000000000001'::uuid` | Single-tenant placeholder for future multi-tenancy |
| `avatar_bg` | text | NOT NULL | `'#6B7280'` | CHECK `^#[0-9A-Fa-f]{6}$` |
| `avatar_initials` | text | NOT NULL | — | CHECK length 1-3 |
| `locale` | text | NOT NULL | `'en'` | CHECK ∈ ('en','mk') |
| `is_active` | boolean | NOT NULL | `true` | INDEX |
| `failed_login_attempts` | int | NOT NULL | `0` | — |
| `locked_until` | timestamptz | NULL | — | When non-null and > now(), login blocked |
| `last_login_at` | timestamptz | NULL | — | — |
| `token_version` | int | NOT NULL | `0` | Bumped on deactivate; JWT carries this value, mismatch ⇒ 401 |
| `created_by` | uuid | NULL | — | FK → profiles(id) ON DELETE SET NULL; NULL only for the bootstrap admin22 |
| `created_at` | timestamptz | NOT NULL | `now()` | — |
| `updated_at` | timestamptz | NOT NULL | `now()` | trigger-updated |
| `is_deleted` | boolean | NOT NULL | `false` | INDEX |
| `last_seen_at` | timestamptz | NULL | — | App-set on each authenticated request (best-effort) |

**Indexes:** `(email)` UNIQUE, `(username)` UNIQUE, `(dept_id)`, `(role)`, `(is_active)`, `(is_deleted)`.
**Notes:**
- `must_change_password` defaults `true` so any user created without an explicit override is forced through the rotation gate.
- `token_version` deactivation pattern (SUMA #25): the JWT carries `tv`; `get_current_user` rejects when claim ≠ DB.
- `password_hash` is nullable so an OTP-provisioned account that has been e-mailed but not yet activated can exist without a sentinel string. The OTP itself is stored hashed in `otp_audit` (§3.10), not on the profile.
- `org_id` is a fixed placeholder UUID for Purely Plant; the column exists so RLS policies are forward-compatible with multi-tenancy without a future migration shockwave.

### 3.3 `tasks`

The weekly task — the workhorse table.

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `id` | uuid | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `code` | text | NOT NULL | — | UNIQUE, e.g. `T-A8K9P`; generated app-side from OTP-style alphabet |
| `title` | text | NOT NULL | — | CHECK length 1-200 |
| `description` | text | NOT NULL | `''` | — |
| `dept_id` | uuid | NOT NULL | — | FK → departments(id) ON DELETE RESTRICT |
| `assignee_id` | uuid | NULL | — | FK → profiles(id) ON DELETE SET NULL |
| `helpers` | uuid[] | NOT NULL | `'{}'::uuid[]` | Array of profile ids — RLS uses `= ANY(helpers)` |
| `created_by` | uuid | NOT NULL | — | FK → profiles(id) ON DELETE RESTRICT |
| `project_id` | uuid | NULL | — | NULL = department-scoped; non-null = cross-dept project task |
| `status` | text | NOT NULL | `'pending'` | CHECK ∈ ('pending','working','review','stuck','postponed','done') |
| `priority` | text | NOT NULL | `'medium'` | CHECK ∈ ('critical','high','medium','low') |
| `week_start` | date | NOT NULL | — | Monday of the task's week (UTC) |
| `days` | text[] | NOT NULL | `'{}'::text[]` | Subset of {'Mon','Tue','Wed','Thu','Fri','Sat','Sun'} |
| `room` | text | NOT NULL | `''` | Free-text e.g. "Flower 3" |
| `batch` | text | NOT NULL | `''` | Free-text batch id |
| `tags` | text[] | NOT NULL | `'{}'::text[]` | e.g. {'EU-GMP','sampling'} |
| `blocker` | text | NOT NULL | `''` | Rendered only when status='stuck' |
| `org_id` | uuid | NOT NULL | — | Mirror of creator's org for RLS |
| `created_at` | timestamptz | NOT NULL | `now()` | — |
| `updated_at` | timestamptz | NOT NULL | `now()` | trigger-updated |
| `is_deleted` | boolean | NOT NULL | `false` | INDEX |
| `due_date` | date | NULL | — | Optional hard deadline distinct from week_start |
| `completed_at` | timestamptz | NULL | — | Stamped when status transitions to 'done' |

**Indexes:** `(code)` UNIQUE, `(dept_id, week_start)`, `(assignee_id, week_start)`, `(created_by)`, `(project_id)`, `(status)`, `(is_deleted)`, GIN on `helpers`.
**Notes:**
- `helpers` is a Postgres array (not a join table) for fast `= ANY(...)` RLS checks. A separate `task_assignees` join table is also kept (§3.7) for cases where you need per-helper metadata (role on this task, accepted_at), but the array is the canonical source for visibility checks.
- `week_start` is stored as a date for trivial week-bucketing; the frontend's calendar builder converts.
- `org_id` is denormalized from the creator so RLS doesn't need to join to `profiles`.

### 3.4 `task_subtasks`

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `id` | uuid | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `task_id` | uuid | NOT NULL | — | FK → tasks(id) ON DELETE CASCADE |
| `text` | text | NOT NULL | — | CHECK length 1-500 |
| `done` | boolean | NOT NULL | `false` | — |
| `sort_order` | int | NOT NULL | `0` | — |
| `created_by` | uuid | NOT NULL | — | FK → profiles(id) |
| `created_at` | timestamptz | NOT NULL | `now()` | — |
| `updated_at` | timestamptz | NOT NULL | `now()` | trigger-updated |

**Indexes:** `(task_id, sort_order)`.
**Notes:** Cascade-delete with parent task is fine here — subtasks have no GMP-retention requirement of their own; the parent task's audit chain captures the relevant state. (If a regulator ever objects, we flip to `is_deleted`.)

### 3.5 `task_notes`

Append-only progress notes. Authors may NOT edit prior notes (SUMA #48 spirit).

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `id` | uuid | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `task_id` | uuid | NOT NULL | — | FK → tasks(id) ON DELETE CASCADE |
| `author_id` | uuid | NOT NULL | — | FK → profiles(id) |
| `day_label` | text | NOT NULL | — | e.g. 'Mon' — derived from now() but stored for stable display |
| `body` | text | NOT NULL | — | CHECK length 1-2000 |
| `created_at` | timestamptz | NOT NULL | `now()` | — |

**Indexes:** `(task_id, created_at)`.
**Notes:** No `updated_at`, no `is_deleted`. Notes are immutable; corrections are made by appending a new note that supersedes the prior one (GMP convention).

### 3.6 `task_dependencies`

Many-to-many self-link on tasks.

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `task_id` | uuid | NOT NULL | — | FK → tasks(id) ON DELETE CASCADE |
| `depends_on_task_id` | uuid | NOT NULL | — | FK → tasks(id) ON DELETE CASCADE |
| `created_at` | timestamptz | NOT NULL | `now()` | — |

**Primary key:** `(task_id, depends_on_task_id)`.
**Indexes:** `(depends_on_task_id)` for reverse lookups.
**Constraint:** `CHECK (task_id <> depends_on_task_id)` — no self-deps.

### 3.7 `task_assignees` (helpers, m2m)

Mirrors `tasks.helpers` (the array) for cases requiring per-helper metadata. **App-layer responsibility:** every write to `tasks.helpers` triggers a corresponding write to this table (and vice versa). The RLS check uses the array (fast); reports and "who accepted what when" use this table.

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `task_id` | uuid | NOT NULL | — | FK → tasks(id) ON DELETE CASCADE |
| `profile_id` | uuid | NOT NULL | — | FK → profiles(id) ON DELETE CASCADE |
| `role` | text | NOT NULL | `'helper'` | CHECK ∈ ('helper','reviewer','observer') |
| `assigned_by` | uuid | NOT NULL | — | FK → profiles(id) |
| `assigned_at` | timestamptz | NOT NULL | `now()` | — |
| `accepted_at` | timestamptz | NULL | — | Stamped when the helper opens the task |

**Primary key:** `(task_id, profile_id)`.
**Indexes:** `(profile_id)`.

### 3.8 `handoffs`

Cross-departmental transfer proposals. First-class workflow.

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `id` | uuid | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `task_id` | uuid | NOT NULL | — | FK → tasks(id) ON DELETE RESTRICT |
| `from_dept_id` | uuid | NOT NULL | — | FK → departments(id) |
| `to_dept_id` | uuid | NOT NULL | — | FK → departments(id), CHECK (to_dept_id <> from_dept_id) |
| `proposed_assignee_id` | uuid | NULL | — | FK → profiles(id) ON DELETE SET NULL |
| `created_by` | uuid | NOT NULL | — | FK → profiles(id) |
| `status` | text | NOT NULL | `'PENDING'` | CHECK ∈ ('PENDING','ACCEPTED','REJECTED','WITHDRAWN') |
| `note` | text | NOT NULL | `''` | — |
| `response_note` | text | NOT NULL | `''` | — |
| `responded_by` | uuid | NULL | — | FK → profiles(id) |
| `responded_at` | timestamptz | NULL | — | — |
| `org_id` | uuid | NOT NULL | — | — |
| `created_at` | timestamptz | NOT NULL | `now()` | — |
| `updated_at` | timestamptz | NOT NULL | `now()` | — |
| `is_deleted` | boolean | NOT NULL | `false` | — |

**Indexes:** `(task_id)`, `(from_dept_id, status)`, `(to_dept_id, status)`, `(status, created_at)`.

### 3.9 `audit_log`

Hash-chained, append-only audit trail. Written exclusively by the `fn_audit_row()` trigger (§7).

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `id` | bigserial | NOT NULL | seq | PRIMARY KEY |
| `created_at` | timestamptz | NOT NULL | `now()` | — |
| `user_id` | uuid | NULL | — | NULL only for system actions or unattributed admin scripts |
| `user_email` | text | NULL | — | Snapshot at audit time |
| `user_role` | text | NULL | — | Snapshot at audit time |
| `dept_id` | uuid | NULL | — | Snapshot at audit time — scopes DEPT_HEAD reads |
| `org_id` | uuid | NULL | — | Snapshot at audit time |
| `action` | text | NOT NULL | — | CHECK ∈ ('INSERT','UPDATE','DELETE') |
| `table_name` | text | NOT NULL | — | — |
| `record_id` | text | NOT NULL | — | Text to accommodate composite keys |
| `old_values` | jsonb | NULL | — | NULL on INSERT |
| `new_values` | jsonb | NULL | — | NULL on DELETE |
| `prev_hash` | text | NULL | — | NULL only on genesis row for a given (table, record) |
| `entry_hash` | text | NOT NULL | — | `encode(digest(convert_to(payload,'UTF8'),'sha256'),'hex')` |
| `client_ip` | inet | NULL | — | From `app.client_ip` GUC |
| `request_id` | text | NULL | — | From `app.request_id` GUC — correlates with FastAPI logs |

**Indexes:**
- `(table_name, record_id, created_at DESC)` — chain walks per record
- `(user_id, created_at DESC)` — per-user activity
- `(dept_id, created_at DESC)` — DEPT_HEAD scoped reads
- `(action, created_at DESC)` — filter by op

**Notes:** No `UPDATE`/`DELETE`/`TRUNCATE` grants for either app role. Even `app_admin` (BYPASSRLS) cannot mutate this table.

### 3.10 `password_reset_codes`

6-digit codes for self-service password reset (SUMA #17).

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `id` | uuid | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `profile_id` | uuid | NOT NULL | — | FK → profiles(id) ON DELETE CASCADE |
| `code_hash` | text | NOT NULL | — | bcrypt of the 6-digit code |
| `created_at` | timestamptz | NOT NULL | `now()` | — |
| `expires_at` | timestamptz | NOT NULL | — | created_at + 15 minutes |
| `used_at` | timestamptz | NULL | — | Single-use sentinel |
| `client_ip` | inet | NULL | — | Issuance IP, for audit |
| `request_id` | text | NULL | — | — |

**Indexes:** `(profile_id, created_at DESC)`, `(expires_at)` for cleanup cron.

### 3.11 `otp_audit`

One row per OTP issued. Captures *who issued it for whom* — the OTP itself is hashed and stored to detect later abuse-pattern analysis.

| Column | Type | NULL | Default | Constraint |
|---|---|---|---|---|
| `id` | uuid | NOT NULL | `gen_random_uuid()` | PRIMARY KEY |
| `profile_id` | uuid | NOT NULL | — | FK → profiles(id) — the OTP recipient |
| `issued_by` | uuid | NOT NULL | — | FK → profiles(id) — the admin/HOD who created the account |
| `code_hash` | text | NOT NULL | — | bcrypt of the OTP |
| `code_last4` | text | NOT NULL | — | Last 4 chars of OTP for support recovery ("did the user receive the one ending in TXR?") |
| `purpose` | text | NOT NULL | — | CHECK ∈ ('PROVISION','RESET') |
| `issued_at` | timestamptz | NOT NULL | `now()` | — |
| `expires_at` | timestamptz | NOT NULL | — | issued_at + 7 days for PROVISION; + 24h for RESET |
| `consumed_at` | timestamptz | NULL | — | Set when the user logs in with this OTP |
| `client_ip` | inet | NULL | — | Issuer's IP |

**Indexes:** `(profile_id, issued_at DESC)`, `(issued_by, issued_at DESC)`, `(expires_at)`.
**Decision:** Yes, we keep this table — the audit trail value (every OTP ever issued, by whom, for whom, consumed when) is high and the storage cost is trivial.

---

## 4. Role & Department Model

### 4.1 Role enum

```sql
-- Implemented as a CHECK constraint on profiles.role (per SUMA #29).
-- Postgres ENUM type avoided to keep migration of role additions cheap.

ALTER TABLE profiles
    ADD CONSTRAINT profiles_role_check
    CHECK (role IN (
        'ADMIN',         -- Platform admin; sees and manages everything
        'DEPT_HEAD',     -- Manages all users/tasks within one department
        'PROJECT_LEAD',  -- Orthogonal: cross-dept project coordinator
        'TEAM_LEADER',   -- Manages users/tasks within a team in a department
        'USER',          -- Standard worker; sees their own + dept-mates' tasks
        'QA_AUDITOR'     -- Read-everywhere, write-nothing compliance role
    ));
```

**Role meanings:**

| Role | Visibility | Mutation | Provisioning rights |
|---|---|---|---|
| `ADMIN` | Everything | Everything | Create any role in any dept |
| `DEPT_HEAD` | All in own dept; read all profiles+depts | Tasks in own dept; users in own dept | Create USER, TEAM_LEADER in own dept |
| `PROJECT_LEAD` | All tasks where `project_id` ∈ their projects; cross-dept | Tasks they own | Cannot create users |
| `TEAM_LEADER` | Own dept tasks; can reassign within team | Tasks in own dept; cannot create users | None |
| `USER` | Own tasks + dept-mates' tasks (read); own only (write) | Own tasks: status, notes, subtasks | None |
| `QA_AUDITOR` | Everything (read) | Nothing | None |

### 4.2 `canManage` authority matrix

Implemented in `services/authorization.py` as `can_manage(actor: Profile, target_role: str, target_dept_id: UUID | None) -> bool`. The matrix:

| Actor ↓ / Target → | ADMIN | DEPT_HEAD | PROJECT_LEAD | TEAM_LEADER | USER | QA_AUDITOR |
|---|---|---|---|---|---|---|
| **ADMIN** | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| **DEPT_HEAD (same dept)** | ✘ | ✘ | ✘ | ✔ | ✔ | ✘ |
| **DEPT_HEAD (different dept)** | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ |
| **PROJECT_LEAD** | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ |
| **TEAM_LEADER** | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ |
| **USER** | ✘ | ✘ | ✘ | ✘ | ✘ (except self) | ✘ |
| **QA_AUDITOR** | ✘ | ✘ | ✘ | ✘ | ✘ | ✘ |

Implementation:

```python
def can_manage(actor: Profile, target_role: str, target_dept_id: UUID | None) -> bool:
    if actor.role == 'ADMIN':
        return True
    if actor.role == 'DEPT_HEAD':
        if target_role not in ('TEAM_LEADER', 'USER'):
            return False
        return actor.dept_id is not None and actor.dept_id == target_dept_id
    return False
```

The `can_manage` check is applied uniformly at every privileged endpoint (create, reset password, change role, deactivate) — SUMA principle #27.

### 4.3 PROJECT_LEAD scope rules

PROJECT_LEAD is **orthogonal** to the hierarchy. A user with role=PROJECT_LEAD additionally has membership rows in a (future) `project_members` table; for the initial WWF scope we encode the relationship via `tasks.project_id` and rely on RLS to filter. PROJECT_LEAD:

- **Sees** all tasks where `task.project_id ∈ {projects where they are listed as lead}`. For initial scope: a profile with role=PROJECT_LEAD sees ALL `task.project_id IS NOT NULL` rows (we tighten this once `projects` table exists; tracked in §15).
- **Creates** tasks across any department (the `tasks_insert` policy's "role_at_least('PROJECT_LEAD')" arm).
- **Cannot create users.**
- **Can accept/reject handoffs** even when not in either department (the `handoffs_update` "role_at_least('PROJECT_LEAD')" arm).

---

## 5. SQL Migrations

Ordered, numbered `NNN_title.py` (Alembic Python files that issue raw SQL — Alembic from day one, no `metadata.create_all`).

| # | File | Summary |
|---|---|---|
| 000 | `000_init_extensions.py` | `CREATE EXTENSION IF NOT EXISTS pgcrypto, citext, "uuid-ossp"` |
| 010 | `010_roles_and_grants.py` | Create `app_user` (NOBYPASSRLS, 100 conn) and `app_admin` (BYPASSRLS, 10 conn), grant defaults on `public` schema |
| 020 | `020_core_tables.py` | `departments`, `profiles` with all columns, FKs, CHECK constraints, indexes |
| 030 | `030_tasks_and_relations.py` | `tasks`, `task_subtasks`, `task_notes`, `task_dependencies`, `task_assignees` |
| 040 | `040_handoffs.py` | `handoffs` |
| 050 | `050_password_reset.py` | `password_reset_codes`, `otp_audit` |
| 060 | `060_audit_log.py` | `audit_log` + indexes + REVOKE statements |
| 070 | `070_rls_helpers.py` | `current_user_id`, `current_user_role`, `current_user_dept`, `current_user_org`, `is_admin`, `is_elevated`, `role_rank`, `role_at_least`, `uid_can_read_task`, `uid_can_edit_task` |
| 080 | `080_rls_policies.py` | `ENABLE` + `FORCE` RLS on every governed table; all `CREATE POLICY` statements |
| 090 | `090_audit_trigger.py` | `fn_audit_row()` + `CREATE TRIGGER` on profiles, departments, tasks, handoffs |

### 5.1 Migration `010_roles_and_grants.py` (full SQL)

```sql
-- Run as the postgres superuser. Alembic runs as postgres in our setup.

CREATE ROLE app_user WITH
    LOGIN
    PASSWORD :'app_user_password'
    NOSUPERUSER
    NOBYPASSRLS
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    CONNECTION LIMIT 100;

GRANT USAGE ON SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO app_user;

CREATE ROLE app_admin WITH
    LOGIN
    PASSWORD :'app_admin_password'
    NOSUPERUSER
    BYPASSRLS
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    CONNECTION LIMIT 10;

GRANT USAGE ON SCHEMA public TO app_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO app_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO app_admin;
```

### 5.2 Migration `020_core_tables.py` — `departments` + `profiles` (full SQL)

```sql
CREATE TABLE public.departments (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code            text NOT NULL UNIQUE
                        CHECK (char_length(code) BETWEEN 2 AND 16
                               AND code = upper(code)),
    name_en         text NOT NULL,
    name_mk         text NOT NULL,
    parent_dept_id  uuid REFERENCES public.departments(id) ON DELETE SET NULL,
    head_user_id    uuid,
    color           text NOT NULL DEFAULT '#6B7280'
                        CHECK (color ~ '^#[0-9A-Fa-f]{6}$'),
    icon            text,
    sort_order      int  NOT NULL DEFAULT 0,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    is_deleted      boolean NOT NULL DEFAULT false
);
CREATE INDEX departments_parent_idx   ON public.departments(parent_dept_id);
CREATE INDEX departments_deleted_idx  ON public.departments(is_deleted);


CREATE TABLE public.profiles (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email                    citext NOT NULL UNIQUE,
    username                 text   NOT NULL UNIQUE
                                 CHECK (char_length(username) BETWEEN 2 AND 64),
    display_name_en          text   NOT NULL,
    display_name_mk          text,
    password_hash            text,
    password_set_at          timestamptz,
    must_change_password     boolean NOT NULL DEFAULT true,
    role                     text NOT NULL DEFAULT 'USER'
                                 CHECK (role IN ('ADMIN','DEPT_HEAD','PROJECT_LEAD',
                                                 'TEAM_LEADER','USER','QA_AUDITOR')),
    dept_id                  uuid REFERENCES public.departments(id) ON DELETE RESTRICT,
    org_id                   uuid NOT NULL
                                 DEFAULT '00000000-0000-0000-0000-000000000001'::uuid,
    avatar_bg                text NOT NULL DEFAULT '#6B7280'
                                 CHECK (avatar_bg ~ '^#[0-9A-Fa-f]{6}$'),
    avatar_initials          text NOT NULL
                                 CHECK (char_length(avatar_initials) BETWEEN 1 AND 3),
    locale                   text NOT NULL DEFAULT 'en'
                                 CHECK (locale IN ('en','mk')),
    is_active                boolean NOT NULL DEFAULT true,
    failed_login_attempts    int NOT NULL DEFAULT 0,
    locked_until             timestamptz,
    last_login_at            timestamptz,
    last_seen_at             timestamptz,
    token_version            int NOT NULL DEFAULT 0,
    created_by               uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now(),
    is_deleted               boolean NOT NULL DEFAULT false
);
CREATE INDEX profiles_dept_idx     ON public.profiles(dept_id);
CREATE INDEX profiles_role_idx     ON public.profiles(role);
CREATE INDEX profiles_active_idx   ON public.profiles(is_active);
CREATE INDEX profiles_deleted_idx  ON public.profiles(is_deleted);

-- Now that profiles exists, close the FK on departments.head_user_id:
ALTER TABLE public.departments
    ADD CONSTRAINT departments_head_user_fk
    FOREIGN KEY (head_user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;

-- updated_at triggers (one function, attached to both tables)
CREATE OR REPLACE FUNCTION public.fn_touch_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_touch_departments
    BEFORE UPDATE ON public.departments
    FOR EACH ROW EXECUTE FUNCTION public.fn_touch_updated_at();

CREATE TRIGGER trg_touch_profiles
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.fn_touch_updated_at();
```

### 5.3 Migration `030_tasks_and_relations.py` (full SQL for `tasks`)

```sql
CREATE TABLE public.tasks (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code          text NOT NULL UNIQUE,
    title         text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
    description   text NOT NULL DEFAULT '',
    dept_id       uuid NOT NULL REFERENCES public.departments(id) ON DELETE RESTRICT,
    assignee_id   uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
    helpers       uuid[] NOT NULL DEFAULT '{}'::uuid[],
    created_by    uuid NOT NULL REFERENCES public.profiles(id) ON DELETE RESTRICT,
    project_id    uuid,
    status        text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','working','review','stuck','postponed','done')),
    priority      text NOT NULL DEFAULT 'medium'
                      CHECK (priority IN ('critical','high','medium','low')),
    week_start    date NOT NULL,
    days          text[] NOT NULL DEFAULT '{}'::text[],
    room          text NOT NULL DEFAULT '',
    batch         text NOT NULL DEFAULT '',
    tags          text[] NOT NULL DEFAULT '{}'::text[],
    blocker       text NOT NULL DEFAULT '',
    org_id        uuid NOT NULL,
    due_date      date,
    completed_at  timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    is_deleted    boolean NOT NULL DEFAULT false
);

CREATE INDEX tasks_dept_week_idx     ON public.tasks(dept_id, week_start);
CREATE INDEX tasks_assignee_week_idx ON public.tasks(assignee_id, week_start);
CREATE INDEX tasks_created_by_idx    ON public.tasks(created_by);
CREATE INDEX tasks_project_idx       ON public.tasks(project_id);
CREATE INDEX tasks_status_idx        ON public.tasks(status);
CREATE INDEX tasks_deleted_idx       ON public.tasks(is_deleted);
CREATE INDEX tasks_helpers_gin       ON public.tasks USING GIN (helpers);

CREATE TRIGGER trg_touch_tasks
    BEFORE UPDATE ON public.tasks
    FOR EACH ROW EXECUTE FUNCTION public.fn_touch_updated_at();
```

(`task_subtasks`, `task_notes`, `task_dependencies`, `task_assignees` follow the column specs in §3 exactly — straightforward DDL, omitted here for brevity but included in the actual migration file.)

### 5.4 Migration `070_rls_helpers.py` (full SQL — the critical helpers)

```sql
-- ---------- current_user_id() ----------
CREATE OR REPLACE FUNCTION public.current_user_id()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT NULLIF(current_setting('app.user_id', true), '')::uuid;
$$;
REVOKE ALL ON FUNCTION public.current_user_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_user_id() TO app_user, app_admin;

-- ---------- current_user_role() ----------
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS text LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT NULLIF(current_setting('app.user_role', true), '');
$$;
REVOKE ALL ON FUNCTION public.current_user_role() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_user_role() TO app_user, app_admin;

-- ---------- current_user_dept() ----------
CREATE OR REPLACE FUNCTION public.current_user_dept()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT NULLIF(current_setting('app.user_dept', true), '')::uuid;
$$;
REVOKE ALL ON FUNCTION public.current_user_dept() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_user_dept() TO app_user, app_admin;

-- ---------- current_user_org() ----------
CREATE OR REPLACE FUNCTION public.current_user_org()
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT NULLIF(current_setting('app.user_org', true), '')::uuid;
$$;
REVOKE ALL ON FUNCTION public.current_user_org() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_user_org() TO app_user, app_admin;

-- ---------- is_admin() ----------
CREATE OR REPLACE FUNCTION public.is_admin()
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT public.current_user_role() = 'ADMIN';
$$;
REVOKE ALL ON FUNCTION public.is_admin() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_admin() TO app_user, app_admin;

-- ---------- is_elevated() ----------
CREATE OR REPLACE FUNCTION public.is_elevated()
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT public.current_user_role()
        IN ('ADMIN','DEPT_HEAD','PROJECT_LEAD','QA_AUDITOR');
$$;
REVOKE ALL ON FUNCTION public.is_elevated() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_elevated() TO app_user, app_admin;

-- ---------- role_rank / role_at_least ----------
CREATE OR REPLACE FUNCTION public.role_rank(p_role text)
RETURNS int LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE p_role
        WHEN 'USER'         THEN 10
        WHEN 'TEAM_LEADER'  THEN 20
        WHEN 'PROJECT_LEAD' THEN 30
        WHEN 'DEPT_HEAD'    THEN 40
        WHEN 'QA_AUDITOR'   THEN 45
        WHEN 'ADMIN'        THEN 99
        ELSE 0
    END;
$$;

CREATE OR REPLACE FUNCTION public.role_at_least(p_threshold text)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT public.role_rank(public.current_user_role())
         >= public.role_rank(p_threshold);
$$;
REVOKE ALL ON FUNCTION public.role_at_least(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.role_at_least(text) TO app_user, app_admin;

-- ---------- uid_can_read_task / uid_can_edit_task ----------
-- These break cross-table policy recursion (SUMA #59, fix for 42P17).

CREATE OR REPLACE FUNCTION public.uid_can_read_task(p_task_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.tasks t
        WHERE t.id = p_task_id
          AND (
                t.created_by  = public.current_user_id()
            OR  t.assignee_id = public.current_user_id()
            OR  public.current_user_id() = ANY(COALESCE(t.helpers, ARRAY[]::uuid[]))
            OR  (t.dept_id = public.current_user_dept()
                 AND public.role_at_least('USER'))
            OR  public.is_elevated()
          )
    );
$$;
REVOKE ALL ON FUNCTION public.uid_can_read_task(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.uid_can_read_task(uuid) TO app_user, app_admin;

CREATE OR REPLACE FUNCTION public.uid_can_edit_task(p_task_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.tasks t
        WHERE t.id = p_task_id
          AND (
                t.created_by  = public.current_user_id()
            OR  t.assignee_id = public.current_user_id()
            OR  (t.dept_id = public.current_user_dept()
                 AND public.role_at_least('TEAM_LEADER'))
            OR  public.role_at_least('PROJECT_LEAD')
          )
    );
$$;
REVOKE ALL ON FUNCTION public.uid_can_edit_task(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.uid_can_edit_task(uuid) TO app_user, app_admin;
```

---

## 6. RLS Policies

Every governed table:

```sql
ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <t> FORCE  ROW LEVEL SECURITY;   -- applies to owner too
```

`FORCE` is non-negotiable — without it, the table owner role silently bypasses RLS, masking bugs in dev.

### 6.1 `profiles`

```sql
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles FORCE  ROW LEVEL SECURITY;

-- SELECT: self, or elevated reader, or DEPT_HEAD within dept
CREATE POLICY profiles_select ON public.profiles
    FOR SELECT
    USING (
            id = public.current_user_id()
        OR  public.is_admin()
        OR  (public.current_user_role() = 'DEPT_HEAD'
             AND dept_id = public.current_user_dept())
        OR  (public.current_user_role() IN ('PROJECT_LEAD','QA_AUDITOR')
             AND org_id  = public.current_user_org())
    );

-- INSERT: explicit deny — provisioning goes through app_admin
CREATE POLICY profiles_insert_deny ON public.profiles
    FOR INSERT
    WITH CHECK (false);

-- UPDATE: self-update only, column-level restricted via GRANT
CREATE POLICY profiles_update_self ON public.profiles
    FOR UPDATE
    USING      (id = public.current_user_id())
    WITH CHECK (id = public.current_user_id());

-- DELETE: forbidden; soft-delete via UPDATE only (which is restricted further)
CREATE POLICY profiles_delete_deny ON public.profiles
    FOR DELETE
    USING (false);

-- Column-level grants prevent self-update from changing role/dept/is_active/etc.
REVOKE UPDATE ON public.profiles FROM app_user;
GRANT  UPDATE (display_name_en, display_name_mk, avatar_bg, avatar_initials,
               locale, last_seen_at)
       ON public.profiles TO app_user;
GRANT  SELECT, INSERT, DELETE ON public.profiles TO app_user;
```

### 6.2 `departments`

```sql
ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.departments FORCE  ROW LEVEL SECURITY;

CREATE POLICY departments_select ON public.departments
    FOR SELECT
    USING (public.current_user_id() IS NOT NULL);

CREATE POLICY departments_insert_deny ON public.departments
    FOR INSERT WITH CHECK (false);
CREATE POLICY departments_update_deny ON public.departments
    FOR UPDATE USING (false) WITH CHECK (false);
CREATE POLICY departments_delete_deny ON public.departments
    FOR DELETE USING (false);
```

### 6.3 `tasks`

```sql
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks FORCE  ROW LEVEL SECURITY;

CREATE POLICY tasks_select ON public.tasks
    FOR SELECT
    USING (
            created_by  = public.current_user_id()
        OR  assignee_id = public.current_user_id()
        OR  public.current_user_id() = ANY(COALESCE(helpers, ARRAY[]::uuid[]))
        OR  (dept_id = public.current_user_dept()
             AND public.role_at_least('USER'))
        OR  public.is_elevated()
    );

CREATE POLICY tasks_insert ON public.tasks
    FOR INSERT
    WITH CHECK (
            created_by = public.current_user_id()
        AND (
                dept_id = public.current_user_dept()
             OR public.role_at_least('PROJECT_LEAD')
            )
    );

CREATE POLICY tasks_update ON public.tasks
    FOR UPDATE
    USING (
            created_by  = public.current_user_id()
        OR  assignee_id = public.current_user_id()
        OR  (dept_id = public.current_user_dept()
             AND public.role_at_least('TEAM_LEADER'))
        OR  public.role_at_least('PROJECT_LEAD')
    )
    WITH CHECK (
            dept_id = public.current_user_dept()
        OR  public.role_at_least('PROJECT_LEAD')
    );

CREATE POLICY tasks_delete ON public.tasks
    FOR DELETE
    USING (
            (dept_id = public.current_user_dept()
             AND public.role_at_least('TEAM_LEADER'))
        OR  public.is_admin()
    );
```

### 6.4 `task_subtasks` / `task_notes` / `task_dependencies`

Using the helpers from §5.4 — no cross-table subselect, no 42P17 risk:

```sql
-- task_subtasks
ALTER TABLE public.task_subtasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_subtasks FORCE  ROW LEVEL SECURITY;

CREATE POLICY task_subtasks_select ON public.task_subtasks
    FOR SELECT USING (public.uid_can_read_task(task_id));
CREATE POLICY task_subtasks_insert ON public.task_subtasks
    FOR INSERT WITH CHECK (public.uid_can_edit_task(task_id));
CREATE POLICY task_subtasks_update ON public.task_subtasks
    FOR UPDATE USING (public.uid_can_edit_task(task_id))
               WITH CHECK (public.uid_can_edit_task(task_id));
CREATE POLICY task_subtasks_delete ON public.task_subtasks
    FOR DELETE USING (public.uid_can_edit_task(task_id));

-- task_notes (append-only)
ALTER TABLE public.task_notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_notes FORCE  ROW LEVEL SECURITY;

CREATE POLICY task_notes_select ON public.task_notes
    FOR SELECT USING (public.uid_can_read_task(task_id));
CREATE POLICY task_notes_insert ON public.task_notes
    FOR INSERT WITH CHECK (public.uid_can_read_task(task_id)
                       AND author_id = public.current_user_id());
CREATE POLICY task_notes_update_deny ON public.task_notes
    FOR UPDATE USING (false) WITH CHECK (false);
CREATE POLICY task_notes_delete_deny ON public.task_notes
    FOR DELETE USING (false);

-- task_dependencies
ALTER TABLE public.task_dependencies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_dependencies FORCE  ROW LEVEL SECURITY;

CREATE POLICY task_dependencies_select ON public.task_dependencies
    FOR SELECT USING (public.uid_can_read_task(task_id)
                  AND public.uid_can_read_task(depends_on_task_id));
CREATE POLICY task_dependencies_insert ON public.task_dependencies
    FOR INSERT WITH CHECK (public.uid_can_edit_task(task_id)
                       AND public.uid_can_read_task(depends_on_task_id));
CREATE POLICY task_dependencies_delete ON public.task_dependencies
    FOR DELETE USING (public.uid_can_edit_task(task_id));
CREATE POLICY task_dependencies_update_deny ON public.task_dependencies
    FOR UPDATE USING (false) WITH CHECK (false);

-- task_assignees (helpers m2m, RLS keyed off parent task)
ALTER TABLE public.task_assignees ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_assignees FORCE  ROW LEVEL SECURITY;

CREATE POLICY task_assignees_select ON public.task_assignees
    FOR SELECT USING (public.uid_can_read_task(task_id));
CREATE POLICY task_assignees_insert ON public.task_assignees
    FOR INSERT WITH CHECK (public.uid_can_edit_task(task_id)
                       AND assigned_by = public.current_user_id());
CREATE POLICY task_assignees_update ON public.task_assignees
    FOR UPDATE USING (public.uid_can_edit_task(task_id)
                  OR  profile_id = public.current_user_id())   -- self-accept
               WITH CHECK (public.uid_can_edit_task(task_id)
                       OR  profile_id = public.current_user_id());
CREATE POLICY task_assignees_delete ON public.task_assignees
    FOR DELETE USING (public.uid_can_edit_task(task_id));
```

### 6.5 `handoffs`

```sql
ALTER TABLE public.handoffs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.handoffs FORCE  ROW LEVEL SECURITY;

CREATE POLICY handoffs_select ON public.handoffs
    FOR SELECT USING (
            created_by               = public.current_user_id()
        OR  proposed_assignee_id     = public.current_user_id()
        OR  (from_dept_id = public.current_user_dept()
             AND public.role_at_least('TEAM_LEADER'))
        OR  (to_dept_id   = public.current_user_dept()
             AND public.role_at_least('TEAM_LEADER'))
        OR  public.is_elevated()
    );

CREATE POLICY handoffs_insert ON public.handoffs
    FOR INSERT WITH CHECK (
            created_by   = public.current_user_id()
        AND from_dept_id = public.current_user_dept()
        AND public.role_at_least('TEAM_LEADER')
        AND public.uid_can_read_task(task_id)
    );

CREATE POLICY handoffs_update ON public.handoffs
    FOR UPDATE
    USING (
            (to_dept_id = public.current_user_dept()
             AND public.role_at_least('TEAM_LEADER'))
        OR  (from_dept_id = public.current_user_dept()
             AND public.role_at_least('TEAM_LEADER')
             AND status = 'PENDING')
        OR  public.role_at_least('PROJECT_LEAD')
    )
    WITH CHECK (
        -- Cannot rewrite to_dept_id away from original target (anti-redirect)
            to_dept_id = (SELECT h.to_dept_id FROM public.handoffs h
                          WHERE h.id = handoffs.id)
        OR  public.role_at_least('PROJECT_LEAD')
    );

CREATE POLICY handoffs_delete ON public.handoffs
    FOR DELETE USING (
            (from_dept_id = public.current_user_dept()
             AND public.role_at_least('TEAM_LEADER')
             AND status = 'PENDING')
        OR  public.is_admin()
    );
```

### 6.6 `audit_log`

```sql
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log FORCE  ROW LEVEL SECURITY;

CREATE POLICY audit_log_select ON public.audit_log
    FOR SELECT USING (
            public.is_admin()
        OR  public.current_user_role() IN ('PROJECT_LEAD','QA_AUDITOR')
        OR  (public.current_user_role() = 'DEPT_HEAD'
             AND dept_id = public.current_user_dept())
    );

CREATE POLICY audit_log_insert ON public.audit_log
    FOR INSERT WITH CHECK (true);   -- The SECURITY DEFINER trigger writes here.

-- DELIBERATELY: no UPDATE policy, no DELETE policy, no TRUNCATE policy.
-- Additionally REVOKE so that even app_admin (BYPASSRLS) cannot mutate:
REVOKE UPDATE, DELETE, TRUNCATE ON public.audit_log FROM app_user, app_admin;
```

### 6.7 `password_reset_codes` / `otp_audit`

Both tables are accessed only via the app_admin engine (provisioning service). They have RLS enabled with deny-all policies so accidental access from a request handler with `app_user` returns nothing:

```sql
ALTER TABLE public.password_reset_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.password_reset_codes FORCE  ROW LEVEL SECURITY;
CREATE POLICY prc_deny_all ON public.password_reset_codes
    FOR ALL USING (false) WITH CHECK (false);

ALTER TABLE public.otp_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.otp_audit FORCE  ROW LEVEL SECURITY;
CREATE POLICY otp_deny_all_writes ON public.otp_audit
    FOR ALL USING (false) WITH CHECK (false);
-- Read access for elevated readers (debugging account-creation incidents):
CREATE POLICY otp_select_elevated ON public.otp_audit
    FOR SELECT USING (public.is_admin()
                  OR  public.current_user_role() = 'QA_AUDITOR');
```

### 6.8 Bypass-RLS service role setup

See migration `010_roles_and_grants.py` (§5.1). The `app_admin` role has `BYPASSRLS`. The corresponding `BYPASS_DATABASE_URL` env var is consumed by `app/core/database.py::admin_engine`. The only call sites for `admin_engine` are:

- `services/provisioning_service.py` — `create_user_atomic`, `reset_user_password`
- `services/password_reset_service.py` — internal reads of `password_reset_codes`
- `services/auth_service.py` — `verify_credentials` (must read `profiles` by email pre-login, when caller has no identity)
- `seed.py` — `admin22` bootstrap

A grep of `from app.core.database import admin_engine` MUST return only these four files; CI enforces.

---

## 7. Audit Trigger

The `fn_audit_row()` trigger is the single system-of-record for the audit chain. The middleware (§9.4) sets per-request GUCs (`app.request_id`, `app.client_ip`); the trigger reads them and folds them into each audit row alongside the JWT identity GUCs.

### 7.1 `fn_audit_row()` — full SQL

```sql
CREATE OR REPLACE FUNCTION public.fn_audit_row()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_user_id    uuid := public.current_user_id();
    v_user_role  text := public.current_user_role();
    v_user_dept  uuid := public.current_user_dept();
    v_user_org   uuid := public.current_user_org();
    v_user_email text;
    v_action     text := TG_OP;
    v_old        jsonb;
    v_new        jsonb;
    v_record_id  text;
    v_prev_hash  text;
    v_payload    text;
    v_entry_hash text;
    v_client_ip  inet;
    v_request_id text;
BEGIN
    -- Look up the actor's email for snapshot.
    IF v_user_id IS NOT NULL THEN
        SELECT email INTO v_user_email
        FROM public.profiles
        WHERE id = v_user_id;
    END IF;

    -- Marshal row state.
    IF TG_OP = 'INSERT' THEN
        v_old := NULL;
        v_new := to_jsonb(NEW);
        v_record_id := (NEW.id)::text;
    ELSIF TG_OP = 'UPDATE' THEN
        v_old := to_jsonb(OLD);
        v_new := to_jsonb(NEW);
        v_record_id := (NEW.id)::text;
    ELSIF TG_OP = 'DELETE' THEN
        v_old := to_jsonb(OLD);
        v_new := NULL;
        v_record_id := (OLD.id)::text;
    END IF;

    -- Request context.
    v_request_id := NULLIF(current_setting('app.request_id', true), '');
    BEGIN
        v_client_ip := NULLIF(current_setting('app.client_ip', true), '')::inet;
    EXCEPTION WHEN others THEN
        v_client_ip := NULL;
    END;

    -- Previous hash for (table, record).
    SELECT entry_hash INTO v_prev_hash
    FROM public.audit_log
    WHERE table_name = TG_TABLE_NAME
      AND record_id  = v_record_id
    ORDER BY created_at DESC, id DESC
    LIMIT 1;

    -- ----------------------------------------------------------------------
    -- Canonical payload. ORDER MATTERS. Locking this format forever:
    -- payload = user_id|user_email|action|table|record_id|old|new|prev_hash|ts
    -- ----------------------------------------------------------------------
    v_payload := COALESCE(v_user_id::text, '')  || '|' ||
                 COALESCE(v_user_email, '')     || '|' ||
                 v_action                       || '|' ||
                 TG_TABLE_NAME                  || '|' ||
                 v_record_id                    || '|' ||
                 COALESCE(v_old::text, '')      || '|' ||
                 COALESCE(v_new::text, '')      || '|' ||
                 COALESCE(v_prev_hash, '')      || '|' ||
                 (now() AT TIME ZONE 'UTC')::text;

    -- ----------------------------------------------------------------------
    -- HASHING — the critical SUMA gotcha.
    --
    -- BAD:  digest(v_payload::bytea, 'sha256')
    --       The ::bytea cast interprets v_payload as a bytea literal
    --       (looking for \x escape sequences) and either errors out on
    --       any string containing quotes/newlines/backslashes (very common
    --       in row_to_json output) or silently mangles bytes.
    --
    -- GOOD: digest(convert_to(v_payload, 'UTF8'), 'sha256')
    --       convert_to() is the explicit text→bytes encoder. The result
    --       is deterministic across hosts, encodings, and locales.
    --
    -- This single line is the difference between an audit chain you can
    -- replay on a fresh database and one you cannot.
    -- ----------------------------------------------------------------------
    v_entry_hash := encode(
        digest(convert_to(v_payload, 'UTF8'), 'sha256'),
        'hex'
    );

    INSERT INTO public.audit_log (
        user_id, user_email, user_role, dept_id, org_id,
        action, table_name, record_id,
        old_values, new_values,
        prev_hash, entry_hash,
        client_ip, request_id
    ) VALUES (
        v_user_id, v_user_email, v_user_role, v_user_dept, v_user_org,
        v_action, TG_TABLE_NAME, v_record_id,
        v_old, v_new,
        v_prev_hash, v_entry_hash,
        v_client_ip, v_request_id
    );

    RETURN COALESCE(NEW, OLD);
END;
$$;

REVOKE ALL ON FUNCTION public.fn_audit_row() FROM PUBLIC;
-- No GRANT EXECUTE; triggers invoke as owner.
```

### 7.2 Trigger attachments

```sql
CREATE TRIGGER trg_audit_profiles
    AFTER INSERT OR UPDATE OR DELETE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.fn_audit_row();

CREATE TRIGGER trg_audit_departments
    AFTER INSERT OR UPDATE OR DELETE ON public.departments
    FOR EACH ROW EXECUTE FUNCTION public.fn_audit_row();

CREATE TRIGGER trg_audit_tasks
    AFTER INSERT OR UPDATE OR DELETE ON public.tasks
    FOR EACH ROW EXECUTE FUNCTION public.fn_audit_row();

CREATE TRIGGER trg_audit_handoffs
    AFTER INSERT OR UPDATE OR DELETE ON public.handoffs
    FOR EACH ROW EXECUTE FUNCTION public.fn_audit_row();

CREATE TRIGGER trg_audit_task_assignees
    AFTER INSERT OR UPDATE OR DELETE ON public.task_assignees
    FOR EACH ROW EXECUTE FUNCTION public.fn_audit_row();

-- Deliberately NOT attached to task_subtasks and task_notes:
-- their visibility derives from the parent task's audit chain.
-- (If a regulator asks, we attach with one line each.)
```

### 7.3 Chain verification (operational)

A scheduled job (cron, or FastAPI background task) runs nightly:

```sql
WITH ordered AS (
    SELECT id, table_name, record_id, prev_hash, entry_hash, created_at,
           LAG(entry_hash) OVER (PARTITION BY table_name, record_id
                                 ORDER BY created_at, id) AS calc_prev
    FROM public.audit_log
)
SELECT count(*) AS broken_links
FROM ordered
WHERE prev_hash IS DISTINCT FROM calc_prev;
```

Non-zero → page on-call. The job runs via the admin engine and writes its result to a `system_health` table (not in this spec; tracked as follow-up).

---

## 8. Auth Flow

### 8.1 Login — `POST /api/auth/login`

```
Client                       FastAPI                      Postgres
  |                              |                             |
  | POST /api/auth/login         |                             |
  |  { email, password,          |                             |
  |    remember_device }         |                             |
  |----------------------------->|                             |
  |                              | get_anon_session()          |
  |                              | (no GUCs)                   |
  |                              |---------------------------->|
  |                              |                             |
  |                              | (uses admin_engine to read  |
  |                              |  profiles by email; the     |
  |                              |  app_user policies do not   |
  |                              |  permit anon read)          |
  |                              |---------------------------->|
  |                              |     SELECT * FROM profiles  |
  |                              |     WHERE email = $1        |
  |                              |       AND is_deleted=false  |
  |                              |<----------------------------|
  |                              |                             |
  |                              | If !user OR !is_active OR   |
  |                              |   locked_until > now():     |
  |                              |   constant-time-401         |
  |                              |                             |
  |                              | If !bcrypt.verify(pw, hash):|
  |                              |   inc failed_login_attempts |
  |                              |   if >= max_login_attempts: |
  |                              |     locked_until = now()+5m |
  |                              |   constant-time-401         |
  |                              |                             |
  |                              | reset failed_login_attempts |
  |                              | stamp last_login_at         |
  |                              | (UPDATE via admin_engine)   |
  |                              |                             |
  |                              | mint JWT:                   |
  |                              |   sub, role, dept_id,       |
  |                              |   org_id, tv (token_version)|
  |                              |   exp = now + (15m | 7d)    |
  |                              |     # 7d only if remember   |
  |                              |                             |
  | 200 { access_token,          |                             |
  |       must_change_password,  |                             |
  |       user: {id, role, ...}  |                             |
  |     }                        |                             |
  |<-----------------------------|                             |
  |                              |                             |
  | (store token in localStorage,|                             |
  |  attach to all subsequent    |                             |
  |  requests as Authorization)  |                             |
```

**Key contract:** the response always includes `must_change_password`. The client uses it to decide whether to render `<ForceChangePassword/>` or the role-based landing.

**Two-step or single-step?** Single-step. SUMA's two-step (verify → mint exchange code → swap for JWT) is a Supabase artifact (GoTrue's magic-link primitive); for FastAPI a single bcrypt-then-JWT is simpler and equally secure. The "fresh-token-after-change" wrinkle is handled by minting a *new* JWT inside the change-password handler.

### 8.2 Force change password — `POST /api/auth/change-password` (forced=true)

When `must_change_password=true`, the JWT issued at login is a "restricted" token whose only permitted route is `POST /api/auth/change-password`. This is enforced in `get_current_user`:

```python
if user.must_change_password and request.url.path != '/api/auth/change-password':
    raise HTTPException(403, 'PASSWORD_CHANGE_REQUIRED')
```

The forced-change handler:

```
Client                              FastAPI                  Postgres
  | POST /api/auth/change-password   |                          |
  |  Bearer <restricted token>       |                          |
  |  { new_password, confirm }       |                          |
  |--------------------------------->|                          |
  |                                  | validate policy:         |
  |                                  |   len >= 12, mixed-case, |
  |                                  |   digit, no-equal-to-old |
  |                                  |   (cannot verify "old"  |
  |                                  |    since OTP is one-shot)|
  |                                  |                          |
  |                                  | (admin_engine)           |
  |                                  | UPDATE profiles SET      |
  |                                  |   password_hash=$1,      |
  |                                  |   password_set_at=now(), |
  |                                  |   must_change_password=  |
  |                                  |     false,               |
  |                                  |   token_version =        |
  |                                  |     token_version + 1    |
  |                                  | WHERE id = :uid          |
  |                                  |                          |
  |                                  | mark consumed_at on the  |
  |                                  | OTP row in otp_audit     |
  |                                  |                          |
  |                                  | mint fresh JWT (new tv)  |
  |                                  |                          |
  | 200 { access_token, user: {...} }|                          |
  |<---------------------------------|                          |
```

### 8.3 Voluntary password change — `POST /api/auth/change-password` (forced=false)

Same endpoint, different branch. When `must_change_password=false`, the request body MUST include `current_password`:

```python
if not user.must_change_password:
    if not body.current_password:
        raise HTTPException(400, 'CURRENT_PASSWORD_REQUIRED')
    if not bcrypt_verify(body.current_password, user.password_hash):
        raise HTTPException(401, 'INVALID_CREDENTIALS')
```

Then proceed identically (update hash, bump token_version, mint fresh JWT).

### 8.4 Password reset request — `POST /api/auth/password-reset/request`

Public endpoint (no auth required).

```
Client                              FastAPI                Postgres        Resend
  | POST /api/auth/password-reset/   |                          |             |
  |   request { email }              |                          |             |
  |--------------------------------->|                          |             |
  |                                  | rate-limit by IP (Redis  |             |
  |                                  |  or in-memory; 5/15min)  |             |
  |                                  |                          |             |
  |                                  | (admin_engine)           |             |
  |                                  | SELECT id, email FROM    |             |
  |                                  |   profiles WHERE email=$1|             |
  |                                  | AND is_active AND        |             |
  |                                  |   NOT is_deleted         |             |
  |                                  |                          |             |
  |                                  | If found:                |             |
  |                                  |   code = secrets.randbelow(900000)+100000  |
  |                                  |   code_hash = bcrypt(code)              |
  |                                  |   INSERT INTO            |             |
  |                                  |     password_reset_codes |             |
  |                                  |   send_reset_email(      |             |
  |                                  |     email, code) -------------->|       |
  |                                  |   (Resend success or                    |
  |                                  |    failure does not block)              |
  |                                  |                          |             |
  | 200 { ok: true }                 |                          |             |
  | (always 200, regardless of       |                          |             |
  |  whether email exists — no       |                          |             |
  |  enumeration)                    |                          |             |
  |<---------------------------------|                          |             |
```

### 8.5 Password reset confirm — `POST /api/auth/password-reset/confirm`

```
Client                              FastAPI                Postgres
  | POST /api/auth/password-reset/   |                          |
  |   confirm { email, code,         |                          |
  |             new_password }       |                          |
  |--------------------------------->|                          |
  |                                  | (admin_engine)           |
  |                                  | SELECT prc.*, p.id, p.email  |
  |                                  | FROM password_reset_codes prc |
  |                                  | JOIN profiles p ON           |
  |                                  |   prc.profile_id = p.id      |
  |                                  | WHERE p.email = :email       |
  |                                  |   AND prc.used_at IS NULL    |
  |                                  |   AND prc.expires_at > now() |
  |                                  | ORDER BY prc.created_at DESC |
  |                                  | LIMIT 1                      |
  |                                  |                          |
  |                                  | If none → 401            |
  |                                  | If !bcrypt.verify(code,  |
  |                                  |   prc.code_hash) → 401   |
  |                                  |                          |
  |                                  | UPDATE prc SET used_at = now() |
  |                                  | UPDATE profiles SET      |
  |                                  |   password_hash = $1,    |
  |                                  |   password_set_at = now(),    |
  |                                  |   must_change_password = false, |
  |                                  |   failed_login_attempts = 0,    |
  |                                  |   locked_until = NULL,   |
  |                                  |   token_version = token_version + 1 |
  |                                  | WHERE id = prc.profile_id     |
  |                                  |                          |
  | 200 { ok: true }                 |                          |
  |<---------------------------------|                          |
```

### 8.6 OTP provisioning — `POST /api/admin/users`

ADMIN or DEPT_HEAD only (via `can_manage` check):

```
Client                              FastAPI                Postgres        Resend
  | POST /api/admin/users            |                          |             |
  |  Bearer <admin/HOD token>        |                          |             |
  |  { email, username,              |                          |             |
  |    display_name_en, display_name_mk, |                      |             |
  |    role, dept_id, avatar_bg }    |                          |             |
  |--------------------------------->|                          |             |
  |                                  | get_current_user → actor |             |
  |                                  | can_manage(actor, role,  |             |
  |                                  |   dept_id) → require true|             |
  |                                  |                          |             |
  |                                  | otp = generate_otp()     |             |
  |                                  |   alphabet = ABCDEFGHJK..|             |
  |                                  |   format K7PM-4QWS-9TXR  |             |
  |                                  |                          |             |
  |                                  | (admin_engine, txn)      |             |
  |                                  | SET LOCAL app.user_id =  |             |
  |                                  |   actor.id, role=ADMIN   |             |
  |                                  | INSERT INTO profiles (   |             |
  |                                  |   ..., password_hash =   |             |
  |                                  |     bcrypt(otp),         |             |
  |                                  |   must_change_password = |             |
  |                                  |     true,                |             |
  |                                  |   created_by = actor.id) |             |
  |                                  | INSERT INTO otp_audit (  |             |
  |                                  |   profile_id, issued_by, |             |
  |                                  |   code_hash, code_last4, |             |
  |                                  |   purpose='PROVISION')   |             |
  |                                  | send_otp_email(email,otp)|------------>|
  |                                  | (best-effort)            |             |
  |                                  | COMMIT                   |             |
  |                                  |                          |             |
  |                                  | If commit fails: rollback|             |
  |                                  | — no orphan auth row.    |             |
  |                                  |                          |             |
  | 201 { user: {id, email, ...},    |                          |             |
  |       otp: "K7PM-4QWS-9TXR",     |                          |             |
  |       email_sent: bool }         |                          |             |
  |<---------------------------------|                          |             |
  |                                  |                          |             |
  | (UI displays OTP in modal —      |                          |             |
  |  "copy or send now, will not be  |                          |             |
  |  shown again"; OTP NEVER logged) |                          |             |
```

---

## 9. FastAPI Module Layout

### 9.1 `backend/app/core/`

```
core/
├── config.py             # Pydantic Settings: env-driven, secret_key with NO default
├── database.py           # engine + SessionLocal (app_user) + admin_engine + AdminSessionLocal
├── security.py           # bcrypt, JWT, OTP gen, password policy validator
├── audit_context.py      # (re-export from middleware/) request-id GUC helper
└── deps.py               # FastAPI deps: get_session, get_anon_session, get_current_user,
                          # require_role, require_can_manage, get_admin_session (internal use)
```

**`core/config.py`** Pydantic Settings — `secret_key` raises if equal to `"change-me"`; `database_url`, `admin_database_url`, `resend_api_key`, `resend_from`, `app_host`, `cors_origins`, `access_token_expire_minutes=15`, `remember_device_expire_days=7`, `max_login_attempts=5`, `lockout_minutes=5`, `password_min_length=12`.

**`core/database.py`** Two engines:
```python
engine        = create_async_engine(settings.database_url,        pool_size=20, max_overflow=10, pool_pre_ping=True)
admin_engine  = create_async_engine(settings.admin_database_url,  pool_size=5,  max_overflow=2,  pool_pre_ping=True)
SessionLocal      = async_sessionmaker(engine,       expire_on_commit=False, class_=AsyncSession)
AdminSessionLocal = async_sessionmaker(admin_engine, expire_on_commit=False, class_=AsyncSession)
```

**`core/security.py`** All inherited from QC_LIMS_Ao (`pwd_context = CryptContext(['bcrypt'])`, `create_access_token`, `decode_access_token`) plus new:
```python
OTP_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # 31 chars; excludes 0,O,1,I,L
def generate_otp() -> str:
    g = lambda: ''.join(secrets.choice(OTP_ALPHABET) for _ in range(4))
    return f"{g()}-{g()}-{g()}"

def validate_password(pw: str) -> None:
    # raise HTTPException(400, ...) with structured codes:
    # PW_TOO_SHORT, PW_NO_UPPER, PW_NO_LOWER, PW_NO_DIGIT
    ...
```

**`core/deps.py`** — the dependency that applies the RLS context:
```python
async def get_session(claims: TokenClaims = Depends(decode_jwt)) -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(text(
                "SELECT set_config('app.user_id',:u,true),"
                "       set_config('app.user_role',:r,true),"
                "       set_config('app.user_dept',:d,true),"
                "       set_config('app.user_org',:o,true)"),
                {"u": str(claims.sub), "r": claims.role,
                 "d": str(claims.dept_id or ''), "o": str(claims.org_id or '')})
            yield session
```

`get_current_user` re-reads role+dept+token_version from `profiles` (SUMA #34); if `token_version` mismatch → 401; if `must_change_password=true` and path is not the change-password route → 403.

### 9.2 `backend/app/middleware/`

```
middleware/
├── audit_context.py   # ASGI middleware: per-request UUID → app.request_id GUC,
                       # client_ip → app.client_ip GUC. Reads from X-Forwarded-For.
└── error_handler.py   # Maps known service exceptions to FastAPI HTTPException
```

The audit_context middleware runs INSIDE the request lifecycle (after the session is acquired) by piggy-backing on `get_session`: the dependency, after `SET LOCAL app.user_id`, also runs `SET LOCAL app.request_id, app.client_ip`. (Implementation detail: the ASGI middleware stashes these on `request.state` and `get_session` reads them back.)

### 9.3 `backend/app/models/`

One SQLAlchemy file per table. All inherit `BaseModel` from QC_LIMS_Ao's `models/base.py` (verbatim). Notable shape for `profile.py`:

```python
class Profile(BaseModel):
    __tablename__ = 'profiles'
    email                 = Column(CITEXT, unique=True, nullable=False)
    username              = Column(String(64), unique=True, nullable=False)
    display_name_en       = Column(String, nullable=False)
    display_name_mk       = Column(String, nullable=True)
    password_hash         = Column(String, nullable=True)
    password_set_at       = Column(DateTime(timezone=True), nullable=True)
    must_change_password  = Column(Boolean, nullable=False, default=True)
    role                  = Column(String, nullable=False, default='USER')
    dept_id               = Column(UUID(as_uuid=True), ForeignKey('departments.id'))
    org_id                = Column(UUID(as_uuid=True), nullable=False,
                                   default=UUID('00000000-0000-0000-0000-000000000001'))
    avatar_bg             = Column(String(7), nullable=False, default='#6B7280')
    avatar_initials       = Column(String(3), nullable=False)
    locale                = Column(String(2), nullable=False, default='en')
    is_active             = Column(Boolean, nullable=False, default=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until          = Column(DateTime(timezone=True), nullable=True)
    last_login_at         = Column(DateTime(timezone=True), nullable=True)
    last_seen_at          = Column(DateTime(timezone=True), nullable=True)
    token_version         = Column(Integer, nullable=False, default=0)
    created_by            = Column(UUID(as_uuid=True), ForeignKey('profiles.id'))
```

### 9.4 `backend/app/schemas/`

Pydantic v2 models. Notable shapes:

```python
# schemas/auth.py
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)
    remember_device: bool = False

class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    display_name_en: str
    display_name_mk: str | None
    role: str
    dept_id: UUID | None
    avatar_bg: str
    avatar_initials: str
    locale: str
    must_change_password: bool

class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal['bearer'] = 'bearer'
    expires_in: int
    must_change_password: bool
    user: UserResponse

class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=12)
    confirm: str
    current_password: str | None = None   # required when must_change_password=false

# schemas/admin.py
class CreateUserRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=2, max_length=64)
    display_name_en: str
    display_name_mk: str | None = None
    role: Literal['USER','TEAM_LEADER','DEPT_HEAD','PROJECT_LEAD','QA_AUDITOR','ADMIN']
    dept_id: UUID | None
    avatar_bg: str = '#6B7280'
    avatar_initials: str

class CreateUserResponse(BaseModel):
    user: UserResponse
    otp: str                # K7PM-4QWS-9TXR — display once, never log
    email_sent: bool
```

### 9.5 `backend/app/services/`

| File | Responsibilities |
|---|---|
| `auth_service.py` | `verify_credentials(email, pw) → Profile | None` (constant-time), `mint_jwt(user, remember)`, `bump_failed_attempts(user)`, `clear_failed_attempts(user)` |
| `provisioning_service.py` | `create_user_atomic(actor, body) → (Profile, otp_plain, email_sent)`, `reset_user_password(actor, target_id) → otp_plain` |
| `password_reset_service.py` | `request_reset(email, ip, request_id) → None`, `confirm_reset(email, code, new_pw) → Profile` |
| `authorization.py` | `can_manage(actor, target_role, target_dept_id) → bool`, plus `assert_can_manage(...)` that raises 403 |
| `task_service.py` | CRUD wrappers (RLS enforces visibility; service-layer just packages SQLAlchemy queries) |
| `handoff_service.py` | `propose(actor, task_id, to_dept_id, proposed_assignee_id, note)`, `accept(actor, handoff_id)`, `reject(actor, handoff_id, note)`, `withdraw(actor, handoff_id)`; on `accept`, also flips `tasks.dept_id` and (optionally) `assignee_id` |
| `audit_service.py` | App-level intent capture: `log_intent(action, target, payload)` — writes to a separate `audit_intent` table (not strictly required for GMP; useful for "user clicked the Roll Over button" type events that the row-level trigger cannot capture) |
| `email_service.py` | Thin Resend HTTP wrapper, bilingual templates: `send_otp(email, otp, locale)`, `send_reset_code(email, code, locale)` |
| `department_service.py` | `list_departments()`, `create_department(actor, body)` (admin-only), `assign_head(actor, dept_id, user_id)` |

### 9.6 `backend/app/api/`

| File | Responsibilities |
|---|---|
| `auth.py` | `/api/auth/login`, `/api/auth/change-password`, `/api/auth/password-reset/request`, `/api/auth/password-reset/confirm`, `/api/auth/logout` (token revoke by bumping `token_version`) |
| `admin.py` | `/api/admin/users` (POST create, GET list, PATCH role, POST reset-password, POST deactivate, POST reactivate), `/api/admin/departments` (POST create, PATCH) |
| `departments.py` | `/api/departments` (GET list) |
| `tasks.py` | `/api/tasks` (GET list with filters, POST create), `/api/tasks/{id}` (GET, PATCH, DELETE), `/api/tasks/{id}/notes` (POST append), `/api/tasks/{id}/subtasks` (POST, PATCH, DELETE), `/api/tasks/{id}/dependencies` (POST, DELETE) |
| `handoffs.py` | `/api/handoffs` (GET list, POST propose), `/api/handoffs/{id}/accept`, `/api/handoffs/{id}/reject`, `/api/handoffs/{id}/withdraw` |
| `profile.py` | `/api/me` (GET — own profile, lightweight), `PATCH /api/me` (self-update of safe fields only) |
| `audit.py` | `/api/audit` (GET list, paginated, filterable; elevated readers only) |

### 9.7 `backend/app/seed.py`

```python
async def seed():
    if not settings.seed_demo_data:
        # Inherit QC_LIMS_Ao pattern but tightened — production never seeds demo.
        # However, the admin22 bootstrap ALWAYS runs (it's the only way in).
        pass
    await ensure_admin22()

async def ensure_admin22():
    async with AdminSessionLocal() as s:
        async with s.begin():
            exists = await s.scalar(select(Profile.id).where(Profile.username == 'admin22'))
            if exists:
                return
            s.add(Profile(
                email='admin22',
                username='admin22',
                display_name_en='Master Administrator',
                display_name_mk='Главен администратор',
                password_hash=hash_password('admin'),
                must_change_password=True,       # forced rotation on first login
                role='ADMIN',
                dept_id=None,
                avatar_bg='#1F2937',
                avatar_initials='A22',
                locale='en',
                is_active=True,
            ))
```

`seed.py` is invoked from `main.py::lifespan` only when `BOOTSTRAP_ADMIN=1`; production deploys set it once on first boot.

---

## 10. API Endpoints

All routes prefixed `/api`. `Auth` column: `none` (public), `bearer` (JWT required), `bearer-restricted` (JWT issued during forced-change flow; only `/api/auth/change-password` accepted).

### 10.1 Auth

| Method | Path | Auth | Role | Request | Response | Description |
|---|---|---|---|---|---|---|
| POST | `/api/auth/login` | none | — | `{email, password, remember_device}` | `LoginResponse` (incl. `must_change_password`) | Verify bcrypt, mint JWT |
| POST | `/api/auth/change-password` | bearer / bearer-restricted | any | `{new_password, confirm, current_password?}` | `LoginResponse` (fresh JWT) | Forced or voluntary; bumps token_version |
| POST | `/api/auth/password-reset/request` | none | — | `{email}` | `{ok: true}` | Always 200 (no enumeration); emails 6-digit code |
| POST | `/api/auth/password-reset/confirm` | none | — | `{email, code, new_password}` | `{ok: true}` | Verify code, set new password |
| POST | `/api/auth/logout` | bearer | any | `{}` | `{ok: true}` | Bumps `token_version` (invalidates all outstanding tokens) |

### 10.2 Admin (provisioning)

| Method | Path | Auth | Role | Request | Response | Description |
|---|---|---|---|---|---|---|
| GET | `/api/admin/users` | bearer | ADMIN, DEPT_HEAD | query: `dept_id?, role?, q?, page, page_size` | `{items: Profile[], total}` | List manageable users (HOD scoped) |
| POST | `/api/admin/users` | bearer | ADMIN, DEPT_HEAD | `CreateUserRequest` | `CreateUserResponse` (incl. OTP) | Create user; OTP returned synchronously |
| PATCH | `/api/admin/users/{id}/role` | bearer | ADMIN | `{role}` | `UserResponse` | Change role (admin only) |
| POST | `/api/admin/users/{id}/reset-password` | bearer | ADMIN, DEPT_HEAD | `{}` | `{otp: "..."}` | Generate fresh OTP, set `must_change_password=true` |
| POST | `/api/admin/users/{id}/deactivate` | bearer | ADMIN | `{}` | `UserResponse` | `is_active=false` + bump `token_version` |
| POST | `/api/admin/users/{id}/reactivate` | bearer | ADMIN | `{}` | `UserResponse` | `is_active=true` |
| POST | `/api/admin/departments` | bearer | ADMIN | `{code, name_en, name_mk, parent_dept_id?, color?, icon?, sort_order?}` | `Department` | Create dept |
| PATCH | `/api/admin/departments/{id}` | bearer | ADMIN | partial | `Department` | Edit dept |
| POST | `/api/admin/departments/{id}/head` | bearer | ADMIN | `{user_id}` | `Department` | Assign DEPT_HEAD |

### 10.3 Tasks

| Method | Path | Auth | Role | Request | Response | Description |
|---|---|---|---|---|---|---|
| GET | `/api/tasks` | bearer | any | query: `week_start?, dept_id?, assignee_id?, status?, q?, page, page_size` | `{items: Task[], total}` | List visible tasks (RLS filtered) |
| GET | `/api/tasks/{id}` | bearer | any | — | `Task` (expanded: subs, notes, deps) | One task |
| POST | `/api/tasks` | bearer | USER+ | `TaskCreate` | `Task` | Create task; `created_by` forced server-side |
| PATCH | `/api/tasks/{id}` | bearer | any | partial | `Task` | Update (RLS gates) |
| DELETE | `/api/tasks/{id}` | bearer | TEAM_LEADER+ | — | `{ok}` | Soft-delete (sets `is_deleted=true`) |
| POST | `/api/tasks/{id}/notes` | bearer | any (must be visible) | `{body, day_label?}` | `TaskNote` | Append note |
| POST | `/api/tasks/{id}/subtasks` | bearer | edit-rights | `{text, sort_order?}` | `TaskSubtask` | Add subtask |
| PATCH | `/api/tasks/{id}/subtasks/{sub_id}` | bearer | edit-rights | `{text?, done?, sort_order?}` | `TaskSubtask` | — |
| DELETE | `/api/tasks/{id}/subtasks/{sub_id}` | bearer | edit-rights | — | `{ok}` | — |
| POST | `/api/tasks/{id}/dependencies` | bearer | edit-rights | `{depends_on_task_id}` | `{ok}` | — |
| DELETE | `/api/tasks/{id}/dependencies/{dep_id}` | bearer | edit-rights | — | `{ok}` | — |

### 10.4 Handoffs

| Method | Path | Auth | Role | Request | Response | Description |
|---|---|---|---|---|---|---|
| GET | `/api/handoffs` | bearer | TEAM_LEADER+ | query: `status?, to_dept_id?, from_dept_id?` | `{items: Handoff[]}` | List visible handoffs |
| POST | `/api/handoffs` | bearer | TEAM_LEADER+ | `{task_id, to_dept_id, proposed_assignee_id?, note?}` | `Handoff` | Propose handoff |
| POST | `/api/handoffs/{id}/accept` | bearer | TEAM_LEADER+ (receiving dept) | `{response_note?}` | `Handoff` | Accept; flips `tasks.dept_id` |
| POST | `/api/handoffs/{id}/reject` | bearer | TEAM_LEADER+ (receiving dept) | `{response_note}` | `Handoff` | Reject |
| POST | `/api/handoffs/{id}/withdraw` | bearer | TEAM_LEADER+ (sending dept) | `{}` | `Handoff` | Withdraw (only while PENDING) |

### 10.5 Departments

| Method | Path | Auth | Role | Request | Response | Description |
|---|---|---|---|---|---|---|
| GET | `/api/departments` | bearer | any | — | `Department[]` | All depts (internal org chart) |

### 10.6 Profile (self)

| Method | Path | Auth | Role | Request | Response | Description |
|---|---|---|---|---|---|---|
| GET | `/api/me` | bearer | any | — | `UserResponse` | Own profile (fresh from DB on every call) |
| PATCH | `/api/me` | bearer | any | `{display_name_en?, display_name_mk?, avatar_bg?, avatar_initials?, locale?}` | `UserResponse` | Self-update of safe fields only (column GRANTs enforce server-side) |

### 10.7 Audit

| Method | Path | Auth | Role | Request | Response | Description |
|---|---|---|---|---|---|---|
| GET | `/api/audit` | bearer | ADMIN, DEPT_HEAD, PROJECT_LEAD, QA_AUDITOR | query: `from?, to?, user_id?, action?, table_name?, page, page_size` | `{items: AuditEntry[], total, chain_ok: bool}` | Read audit log (RLS scopes DEPT_HEAD to own dept) |
| GET | `/api/audit/{id}` | bearer | same | — | `AuditEntry` (full payload) | Single entry expanded |
| GET | `/api/audit/verify/{table}/{record_id}` | bearer | ADMIN, QA_AUDITOR | — | `{chain_ok: bool, broken_at?: id}` | Re-walk and verify hash chain |

---

## 11. Frontend Layout

### 11.1 File tree

```
frontend/src/
├── main.jsx
├── App.jsx                          # Shell + auth gate + role dispatch
├── shared/                          # Copied verbatim from QC_LIMS_Ao + enhanced
│   ├── ui.jsx                       # Modal, Avatar, AvatarStack, ToastProvider, Spinner,
│                                    # + new: Field, TextInput, PasswordInput, Button, Select,
│                                    #        Checkbox, Tabs, Pills, EmptyState, FormFooter
│   ├── icons.jsx                    # 46-entry SVG dict + new: key, eye, eye-off, copy, send
│   ├── i18n.js                      # tr(), useLang(), setGlobalLang(), makeT()
│   ├── style.js                     # css() helper
│   ├── http.js                      # bare request() — extracted from QC client.js
│   └── styles/
│       ├── app.css                  # Tokens + components
│       └── brand.css                # Wordmark + splash
├── api/
│   └── client.js                    # WWF endpoints, JWT injection, offline handling
├── auth/
│   ├── AuthContext.jsx              # {user, mustChange, login, logout, refresh}
│   ├── LoginPage.jsx                # State machine: splash → menu → login → forgot → reset
│   ├── ForceChangePassword.jsx      # Full-screen gate, cannot be dismissed
│   ├── RoleGuard.jsx                # <RoleGuard allow={[...]}>...</RoleGuard>
│   └── SpeedDial.jsx                # localStorage chip rack, no secrets
└── wwf/
    ├── data.js                      # WWF_I18N flat dict (EN/МК)
    ├── labels.js                    # makeLabels(lang)
    ├── useTasks.js                  # Server-backed mutation hook (replaces useProduction)
    ├── useHandoffs.js
    ├── useUsers.js
    ├── screens/
    │   ├── UserDashboard.jsx
    │   ├── TeamLeaderConsole.jsx
    │   ├── DeptConsole.jsx
    │   ├── ProjectLeadConsole.jsx
    │   ├── AdminConsole.jsx
    │   └── AuditViewer.jsx
    └── components/
        ├── TaskWorkspace.jsx        # Week strip + day pills + telemetry + panels
        ├── TaskCard.jsx             # Collapsed + expanded card
        ├── AddTaskModal.jsx
        ├── HandoffTray.jsx
        ├── CreateAccountForm.jsx
        ├── OtpDisplayModal.jsx      # Strong "copy now" warning
        ├── DepartmentManager.jsx
        └── Telemetry.jsx
```

### 11.2 `LoginPage.jsx` — state machine

Single component, single `view` state advances:

```
splash (3s auto)  →  menu (Speed Dial)  →  login         →  (success → AuthContext.login)
                                         →  forgot       →  reset    →  (back to login)
```

```jsx
export function LoginPage({ onSignedIn }) {
  const [view, setView] = useState('splash');
  const [resetEmail, setResetEmail] = useState('');
  const [error, setError] = useState(null);
  const lang = useLang();

  useEffect(() => {
    if (view === 'splash') {
      const t = setTimeout(() => setView('menu'), 2800);
      return () => clearTimeout(t);
    }
  }, [view]);

  return (
    <div className="auth-shell">
      {view === 'splash' && <Splash />}
      {view === 'menu'   && <SpeedDialMenu
                              onSignIn={() => setView('login')}
                              onForgot={() => setView('forgot')} />}
      {view === 'login'  && <SignInForm
                              onForgot={() => setView('forgot')}
                              onSignedIn={onSignedIn}
                              onBack={() => setView('menu')} />}
      {view === 'forgot' && <ForgotForm
                              onCodeSent={(email) => { setResetEmail(email); setView('reset'); }}
                              onBack={() => setView('menu')} />}
      {view === 'reset'  && <ResetForm
                              email={resetEmail}
                              onDone={() => setView('login')} />}
    </div>
  );
}
```

**SpeedDial:** `localStorage['wwf_speed_dial']` stores an array of `{email, display_name, avatar_bg, avatar_initials, role_label}`. NO passwords, NO tokens. Clicking a chip prefills the email in the SignInForm and focuses the password field.

### 11.3 `ForceChangePassword.jsx`

```jsx
export function ForceChangePassword({ onComplete }) {
  const { refresh } = useAuth();
  const [newPw, setNewPw] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  async function submit(e) {
    e.preventDefault();
    if (newPw !== confirm)      return setErr('PW_MISMATCH');
    if (newPw.length < 12)      return setErr('PW_TOO_SHORT');
    setBusy(true);
    try {
      const fresh = await api.changePassword({ new_password: newPw, confirm });
      setToken(fresh.access_token);
      await refresh();
      onComplete();
    } catch (e) { setErr(e.detail || 'CHANGE_FAILED'); }
    setBusy(false);
  }

  return (
    <div className="auth-shell auth-shell--gate">
      <form className="auth-card" onSubmit={submit}>
        <PpWordmark />
        <h1>{t('auth.force.title')}</h1>
        <p>{t('auth.force.subtitle')}</p>
        <PasswordInput value={newPw}   onChange={setNewPw}   label={t('auth.new_pw')}     autoFocus />
        <PasswordInput value={confirm} onChange={setConfirm} label={t('auth.confirm_pw')} />
        <PasswordStrength value={newPw} />
        {err && <Alert kind="error">{t(`auth.err.${err}`)}</Alert>}
        <Button kind="primary" type="submit" busy={busy}>{t('auth.force.submit')}</Button>
      </form>
    </div>
  );
}
```

Cannot be dismissed; no logout button (the user must rotate the password to proceed). Implementation: render this BEFORE any sidebar/header chrome mounts.

### 11.4 `App.jsx` shell logic

```jsx
function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </ToastProvider>
  );
}

function Shell() {
  const { user, mustChange, ready } = useAuth();

  if (!ready)        return <Spinner full />;
  if (!user)         return <LoginPage onSignedIn={() => {}} />;
  if (mustChange)    return <ForceChangePassword onComplete={() => location.reload()} />;

  return <RoleDispatcher user={user} />;
}

function RoleDispatcher({ user }) {
  switch (user.role) {
    case 'ADMIN':        return <AdminConsole user={user} />;
    case 'DEPT_HEAD':    return <DeptConsole user={user} />;
    case 'PROJECT_LEAD': return <ProjectLeadConsole user={user} />;
    case 'TEAM_LEADER':  return <TeamLeaderConsole user={user} />;
    case 'QA_AUDITOR':   return <AuditViewer user={user} />;
    case 'USER':
    default:             return <UserDashboard user={user} />;
  }
}
```

### 11.5 `RoleGuard.jsx`

UX-only gate (re-checked on the server by every endpoint). Used to hide buttons the user shouldn't see.

```jsx
export function RoleGuard({ allow, dept, children, fallback = null }) {
  const { user } = useAuth();
  if (!user) return fallback;
  if (allow && !allow.includes(user.role)) return fallback;
  if (dept  && user.dept_id !== dept && user.role !== 'ADMIN') return fallback;
  return children;
}
```

### 11.6 `TaskWorkspace.jsx` adaptation

Direct port of `production/ProductionWorkspace.jsx` with three changes:

1. **Replace `useProduction()` with `useTasks(scope)`** — a server-backed hook. `scope = { kind: 'mine' | 'team' | 'dept' | 'project' | 'all', id?: UUID }`.
2. **Optimistic mutations**: every `mutate(fn)` call applies locally, fires the API request, rolls back on failure with a toast.
3. **AvatarStack** populated from `useUsers({ dept_id })` (server) not the hardcoded list.

The week strip, day pills, panels, telemetry, and all CSS stay byte-identical.

### 11.7 `TaskCard.jsx` adaptation

Three role-aware behavioural changes:

| Section | USER | TEAM_LEADER | DEPT_HEAD / ADMIN / PROJECT_LEAD |
|---|---|---|---|
| Status pill cycle | pending → working → review (stops at review) | full cycle including → done | full cycle |
| Delete button | hidden | visible | visible |
| Reassign | hidden | visible (within team) | visible (within dept / cross-dept) |
| Handoff button | "Flag for help" → notifies TEAM_LEADER | "Request handoff" → opens HandoffTray | "Request handoff" |

Each is gated with `<RoleGuard allow={[...]}>`.

### 11.8 `CreateAccountForm.jsx`

Modal triggered from `AdminConsole` (Users tab) and `DeptConsole` (Teams tab). Submits to `POST /api/admin/users`. On success, replaces itself with `<OtpDisplayModal otp={response.otp} email={response.user.email} />`.

```jsx
function OtpDisplayModal({ otp, email, onClose }) {
  const { toast } = useToast();
  async function copy() {
    await navigator.clipboard.writeText(otp);
    toast(t('admin.otp.copied'), 'success');
  }
  return (
    <Modal open onClose={onClose} title={t('admin.otp.title')} titleColor="var(--orange)">
      <p>{t('admin.otp.warning')}</p>          {/* "This OTP will not be shown again..." */}
      <div className="otp-display">{otp}</div>
      <div className="otp-meta">{t('admin.otp.email')}: <code>{email}</code></div>
      <div className="otp-actions">
        <Button onClick={copy} icon="copy">{t('admin.otp.copy')}</Button>
        <Button onClick={onClose} kind="primary">{t('admin.otp.done')}</Button>
      </div>
    </Modal>
  );
}
```

### 11.9 i18n keys (sample)

Added to `wwf/data.js → WWF_I18N`:

```js
export const WWF_I18N = {
  en: {
    'auth.splash.tagline':        'Weekly Weed Flow',
    'auth.menu.signin':           'Sign in',
    'auth.menu.forgot':           'Forgot password',
    'auth.menu.no_register':      'Accounts are created by your administrator or department head.',
    'auth.login.email':           'Email',
    'auth.login.password':        'Password',
    'auth.login.remember':        'Remember on this device',
    'auth.login.submit':          'Sign in',
    'auth.force.title':           'Set a new password',
    'auth.force.subtitle':        'Your account was issued with a one-time password. Choose a permanent one to continue.',
    'auth.new_pw':                'New password',
    'auth.confirm_pw':            'Confirm new password',
    'auth.force.submit':          'Save and continue',
    'auth.err.PW_TOO_SHORT':      'Password must be at least 12 characters.',
    'auth.err.PW_MISMATCH':       'Passwords do not match.',
    'admin.otp.title':            'Account created — one-time password',
    'admin.otp.warning':          'This OTP will not be shown again. Copy or send it to the user now.',
    'admin.otp.copy':             'Copy OTP',
    'admin.otp.copied':           'OTP copied to clipboard',
    'admin.otp.done':             'Done',
    'handoff.request':            'Request handoff',
    'handoff.flag_help':          'Flag for help',
    'role.ADMIN':                 'Administrator',
    'role.DEPT_HEAD':             'Head of Department',
    'role.PROJECT_LEAD':          'Project Lead',
    'role.TEAM_LEADER':           'Team Leader',
    'role.USER':                  'Member',
    'role.QA_AUDITOR':            'QA Auditor',
  },
  mk: {
    'auth.splash.tagline':        'Неделен Канабис Тек',
    'auth.menu.signin':           'Најави се',
    'auth.menu.forgot':           'Заборавена лозинка',
    'auth.menu.no_register':      'Сметките ги креира администраторот или раководителот на одделот.',
    'auth.login.email':           'Е-пошта',
    'auth.login.password':        'Лозинка',
    'auth.login.remember':        'Запомни на овој уред',
    'auth.login.submit':          'Најави се',
    'auth.force.title':           'Постави нова лозинка',
    'auth.force.subtitle':        'Сметката беше издадена со еднократна лозинка. Изберете трајна за да продолжите.',
    'auth.new_pw':                'Нова лозинка',
    'auth.confirm_pw':            'Потврди нова лозинка',
    'auth.force.submit':          'Зачувај и продолжи',
    'auth.err.PW_TOO_SHORT':      'Лозинката мора да биде најмалку 12 знаци.',
    'auth.err.PW_MISMATCH':       'Лозинките не се совпаѓаат.',
    'admin.otp.title':            'Сметката е креирана — еднократна лозинка',
    'admin.otp.warning':          'Оваа OTP нема да биде прикажана повторно. Копирајте ја или испратете ја сега.',
    'admin.otp.copy':             'Копирај OTP',
    'admin.otp.copied':           'OTP е копиран',
    'admin.otp.done':             'Готово',
    'handoff.request':            'Побарај предавање',
    'handoff.flag_help':          'Побарај помош',
    'role.ADMIN':                 'Администратор',
    'role.DEPT_HEAD':             'Раководител на одделение',
    'role.PROJECT_LEAD':          'Лидер на проект',
    'role.TEAM_LEADER':           'Тимски лидер',
    'role.USER':                  'Член',
    'role.QA_AUDITOR':            'QA Ревизор',
  },
};
```

---

## 12. Compose + Deploy

### 12.1 `docker-compose.yml`

```yaml
name: weekly_weed_flow

services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?}
      POSTGRES_DB: weekly_weed_flow
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d weekly_weed_flow"]
      interval: 5s
      timeout: 3s
      retries: 12
    networks:
      - internal

  backend:
    build: ./backend
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      # postgres role wiring — two URLs, two pools
      DATABASE_URL:        postgresql+asyncpg://app_user:${APP_USER_PASSWORD:?}@db:5432/weekly_weed_flow
      BYPASS_DATABASE_URL: postgresql+asyncpg://app_admin:${APP_ADMIN_PASSWORD:?}@db:5432/weekly_weed_flow
      ALEMBIC_DATABASE_URL: postgresql+psycopg://postgres:${POSTGRES_PASSWORD:?}@db:5432/weekly_weed_flow

      # auth
      SECRET_KEY:          ${SECRET_KEY:?}
      ACCESS_TOKEN_EXPIRE_MINUTES: 15
      REMEMBER_DEVICE_EXPIRE_DAYS: 7
      MAX_LOGIN_ATTEMPTS:  5
      LOCKOUT_MINUTES:     5
      PASSWORD_MIN_LENGTH: 12

      # email (Resend)
      RESEND_API_KEY:      ${RESEND_API_KEY:?}
      RESEND_FROM:         ${RESEND_FROM:-noreply@purelyplant.eu}

      # bootstrap
      BOOTSTRAP_ADMIN:     ${BOOTSTRAP_ADMIN:-0}
      SEED_DEMO_DATA:      0

      # CORS / host
      CORS_ORIGINS:        ${CORS_ORIGINS:-http://localhost:8080}
      APP_HOST:            ${APP_HOST:-localhost}
    command: >
      sh -c "alembic upgrade head &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"
    networks:
      - internal

  frontend:
    build: ./frontend
    restart: unless-stopped
    depends_on:
      - backend
    ports:
      - "${HOST_PORT:-8080}:80"
    networks:
      - internal

networks:
  internal:

volumes:
  pgdata:
```

### 12.2 `docker-compose.kvm4.yml` (overlay)

```yaml
services:
  frontend:
    ports: []                          # Traefik handles ingress
    networks:
      - internal
      - shared                         # The Traefik-attached shared network on KVM4
    labels:
      traefik.enable: "true"
      traefik.docker.network: "shared"
      traefik.http.routers.wwf.rule: "Host(`${APP_HOST}`)"
      traefik.http.routers.wwf.entrypoints: "websecure"
      traefik.http.routers.wwf.tls.certresolver: "le"
      traefik.http.services.wwf.loadbalancer.server.port: "80"

  backend:
    networks:
      - internal                       # backend never exposed via Traefik;
                                       # frontend nginx proxies /api → backend:8000

networks:
  shared:
    external: true                     # Created by QC_LIMS_Ao deploy
```

### 12.3 `deploy/kvm4.sh`

Adapted from QC_LIMS_Ao's deploy script:

```bash
#!/usr/bin/env bash
# deploy/kvm4.sh — one-shot deploy of WEEKLY_WEED_FLOW to KVM4
set -euo pipefail

REMOTE="${REMOTE:-root@72.60.35.12}"
REMOTE_DIR="${REMOTE_DIR:-/opt/weekly_weed_flow}"
PROJECT="weekly_weed_flow"
APP_HOST="${APP_HOST:-weekly.srv1231216.hstgr.cloud}"

# ---- generate or read secrets ----------------------------------------------
ENV_FILE="deploy/kvm4.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Generating fresh secrets for first deploy..."
  cat > "$ENV_FILE" <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 32)
APP_USER_PASSWORD=$(openssl rand -hex 32)
APP_ADMIN_PASSWORD=$(openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 48)
RESEND_API_KEY=${RESEND_API_KEY:?env var RESEND_API_KEY required for first deploy}
RESEND_FROM=noreply@purelyplant.eu
APP_HOST=$APP_HOST
CORS_ORIGINS=https://$APP_HOST
BOOTSTRAP_ADMIN=1
HOST_PORT=8080
EOF
  echo "deploy/kvm4.env created — KEEP THIS FILE SAFE."
fi

# ---- rsync sources ---------------------------------------------------------
ssh "$REMOTE" "mkdir -p $REMOTE_DIR"
rsync -az --delete \
  --exclude '.git' --exclude 'node_modules' --exclude '__pycache__' \
  --exclude 'frontend/dist' --exclude '.venv' \
  ./ "$REMOTE:$REMOTE_DIR/"

scp "$ENV_FILE" "$REMOTE:$REMOTE_DIR/.env"

# ---- build + up ------------------------------------------------------------
ssh "$REMOTE" bash <<EOF
set -euo pipefail
cd $REMOTE_DIR
docker compose -p $PROJECT \
  -f docker-compose.yml -f docker-compose.kvm4.yml \
  --env-file .env \
  up -d --build

# After first successful boot, turn off BOOTSTRAP_ADMIN
if grep -q '^BOOTSTRAP_ADMIN=1' .env; then
  sed -i 's/^BOOTSTRAP_ADMIN=1/BOOTSTRAP_ADMIN=0/' .env
  echo "Bootstrap complete; BOOTSTRAP_ADMIN=0 for future deploys."
fi
EOF

echo "Deployed. Visit https://$APP_HOST"
```

### 12.4 `.env.example` (committed)

```bash
# --- Postgres roles ---------------------------------------------------------
POSTGRES_PASSWORD=replace_me
APP_USER_PASSWORD=replace_me            # role: app_user (NOBYPASSRLS)
APP_ADMIN_PASSWORD=replace_me           # role: app_admin (BYPASSRLS)

# --- Auth -------------------------------------------------------------------
SECRET_KEY=replace_with_openssl_rand_hex_48

# --- Email (Resend) ---------------------------------------------------------
RESEND_API_KEY=re_xxx
RESEND_FROM=noreply@purelyplant.eu

# --- Host / network ---------------------------------------------------------
APP_HOST=localhost
CORS_ORIGINS=http://localhost:8080
HOST_PORT=8080
KPM_NETWORK=shared                      # Name of the external Traefik network on KVM4

# --- Bootstrap --------------------------------------------------------------
BOOTSTRAP_ADMIN=0                       # Set to 1 only on first deploy
SEED_DEMO_DATA=0
```

---

## 13. Seed Strategy

**Behaviour:** on every boot, `main.py::lifespan` calls `seed()` which:

1. **Always** ensures `admin22` exists. The user has username `admin22`, email `admin22`, password `admin` (bcrypt-hashed), `role='ADMIN'`, `dept_id=NULL`, `must_change_password=true`, `is_active=true`. If the row exists, no-op (idempotent).
2. **Never** seeds departments, demo users, or sample tasks unless `SEED_DEMO_DATA=1`. Production deployments NEVER set this flag.
3. Logs a clear one-liner: `[seed] admin22 already present (skipping)` or `[seed] admin22 bootstrap row inserted`.

**Rationale:**
- The whole authentication model assumes a privileged user exists from `t=0`. Without `admin22`, nobody can log in to provision the first real users.
- The default password `admin` paired with `must_change_password=true` means the human admin's first action is to rotate it.
- The `admin22` account has `created_by=NULL` — the only profile in the system permitted to have a null creator (per the SUMA chain-of-custody principle).

**Onboarding flow on first deploy:**
1. Deploy WWF; `BOOTSTRAP_ADMIN=1` triggers `seed()`.
2. Human admin opens `https://weekly.srv1231216.hstgr.cloud`, signs in as `admin22 / admin`.
3. Forced password change UI appears; admin sets a strong personal password.
4. Admin opens `AdminConsole → Departments` and creates the dept tree (Cultivation, Production, Quality, etc.).
5. Admin creates the "head of QC" account via `AdminConsole → Users → Create` with `role=DEPT_HEAD, dept_id=<QC dept>`. The OTP is displayed in the modal; admin copies it and shares with the head of QC out-of-band (Slack/SMS) — Resend email is also fired as best-effort.
6. Head of QC signs in, rotates password, can now create USER and TEAM_LEADER accounts within the QC dept.

---

## 14. Security Checklist (SUMA → file/line mapping)

Every SUMA principle (#1 - #63 from the research input) mapped to its implementation in WEEKLY_WEED_FLOW. This proves no principle is dropped.

| SUMA # | Principle | Implemented in |
|---|---|---|
| 1 | Single-route auth shell state machine | `frontend/src/auth/LoginPage.jsx` |
| 2 | Splash entry screen | `LoginPage.jsx` view='splash' |
| 3 | "Accounts created by your administrator" copy | `wwf/data.js → auth.menu.no_register` |
| 4 | No Register path / no self-signup | No `/api/auth/register` route in `app/api/auth.py`; no signup view in `LoginPage.jsx` |
| 5 | Speed Dial quick sign-in (non-secret chips) | `frontend/src/auth/SpeedDial.jsx`, `localStorage['wwf_speed_dial']` |
| 6 | Per-device, removable Speed Dial | Chip delete affordance in `SpeedDial.jsx` |
| 7 | "Remember on this device" checkbox | `LoginRequest.remember_device` → JWT exp 7d vs 15min in `auth_service.py::mint_jwt` |
| 8 | "Forgot password?" link from login | `LoginPage.jsx` view='login' → setView('forgot') |
| 9 | Scoped style block | `shared/styles/app.css` token-scoped; `brand.css` for auth-specific |
| 10 | Login screen stateless about routing | `AuthContext.jsx` decides landing in `App.jsx::Shell` |
| 11 | Custom password flow | `api/auth.py::POST /login` — single endpoint, bcrypt-verified |
| 12 | Two-step session minting | Adapted to single-step bcrypt→JWT (rationale in §8.1) |
| 13 | bcrypt verification stays close to DB | `services/auth_service.py::verify_credentials` runs bcrypt in Python against `password_hash`; admin_engine reads the hash without exposing it |
| 14 | Service-role / privileged-key separation | `app_user` (request handlers) vs `app_admin` (provisioning only); `core/database.py` |
| 15 | Only the server can mint a session token | `core/security.py::create_access_token` server-side only |
| 16 | JWT in Authorization Bearer header | `api/client.js::request` injects; FastAPI `HTTPBearer` |
| 17 | 6-digit code email reset path | `api/auth.py::POST /password-reset/{request,confirm}`, `services/password_reset_service.py` |
| 18 | All accounts provisioned by privileged users | `api/admin.py::POST /admin/users` gated by `require_role(['ADMIN','DEPT_HEAD'])` + `can_manage` |
| 19 | CSPRNG OTP with unambiguous alphabet | `core/security.py::generate_otp` uses `secrets.choice` over `ABCDEFGHJKMNPQRSTUVWXYZ23456789` |
| 20 | Atomic create-account with rollback | `services/provisioning_service.py::create_user_atomic` wraps in `async with session.begin():` |
| 21 | OTP always returned to creator's screen | `CreateUserResponse.otp` field; UI `OtpDisplayModal.jsx` |
| 22 | `must_change_password` flag gates the whole app | `profiles.must_change_password` column; `core/deps.py::get_current_user` raises 403 unless path is change-password; `App.jsx::Shell` renders `<ForceChangePassword/>` |
| 23 | Voluntary change requires current pw; forced does not | `api/auth.py::change_password` branches on user.must_change_password |
| 24 | Min 8-char password (we enforce 12) | `core/security.py::validate_password`; Pydantic `Field(min_length=12)` on `ChangePasswordRequest` |
| 25 | Disable = is_active=false AND token revoke | `api/admin.py::POST /users/{id}/deactivate` bumps `token_version` |
| 26 | `canManage(actor, role, dept)` matrix | `services/authorization.py::can_manage` (§4.2) |
| 27 | Authority enforced on BOTH create and reset | `can_manage` called from `provisioning_service` for create, reset, role-change, deactivate |
| 28 | Privileged admin endpoints | `api/admin.py` (§10.2) |
| 29 | Role enum as CHECK constraint | `profiles.role CHECK (role IN (...))` (§5.2) |
| 30 | Departments table with FK from profiles | `departments` table + `profiles.dept_id FK` (§3.1, §3.2) |
| 31 | Role determines landing screen | `App.jsx::RoleDispatcher` (§11.4) |
| 32 | Defense-in-depth: three layers | `RoleGuard.jsx` (UX) + FastAPI `require_role`/`can_manage` (API) + Postgres RLS (DB) |
| 33 | Frontend RoleGuard is UX-only | Documented in `RoleGuard.jsx` header comment |
| 34 | API middleware reloads profile from DB on every request | `core/deps.py::get_current_user` re-reads role/dept/token_version from profiles |
| 35 | Source of truth = profiles, not JWT | Same as #34; JWT TTL 15min for fast propagation |
| 36 | RLS is the real boundary | Migrations 070+080; every governed table |
| 37 | SECURITY DEFINER helpers for current user | `current_user_*` functions (§5.4) |
| 38 | Org/ownership/sharing/elevated standard shapes | Embedded in policy `USING` clauses (§6) |
| 39 | Cross-table membership behind SECURITY DEFINER | `uid_can_read_task`, `uid_can_edit_task` (§5.4) |
| 40 | GMP / ALCOA+ guiding philosophy | `fn_audit_row()` triggers; `audit_log` schema |
| 41 | Two-level logging (trigger + app) | Trigger = system-of-record (§7); `services/audit_service.py` = app-level intent capture |
| 42 | SHA-256 entry_hash | `fn_audit_row()` (§7.1) |
| 43 | Hash-chain links each entry to predecessor | `v_prev_hash` lookup + folded into payload |
| 44 | Trigger is SECURITY DEFINER | `fn_audit_row()` declared `SECURITY DEFINER` |
| 45 | `convert_to(text,'UTF8')` — never `::bytea` | `fn_audit_row()` uses `digest(convert_to(v_payload,'UTF8'),'sha256')` with explicit comment |
| 46 | Log auth/account + governed data | Triggers on profiles, departments, tasks, handoffs, task_assignees |
| 47 | Standard captured fields | `audit_log` columns: user_id, user_email, action, table_name, record_id, old_values, new_values, entry_hash, timestamp |
| 48 | Append-only audit log | No UPDATE/DELETE policies; explicit REVOKE (§6.6) |
| 49 | Audit log readable only by elevated roles | `audit_log_select` policy + `/api/audit` `require_role` |
| 50 | Service-role key server-only | `BYPASS_DATABASE_URL` never exposed to frontend; only `VITE_API_BASE_URL` public |
| 51 | Built-in provider disabled (Supabase-specific) | N/A; single login endpoint by design |
| 52 | Staging/import tables must have RLS | Every new model creates a migration that includes `ENABLE/FORCE RLS` + policies — codified in `CLAUDE.md` for WWF |
| 53 | Custom login = built-in disabled | N/A; document in `CLAUDE.md` that no second login endpoint may be added |
| 54 | No orphan auth records | Atomic txn in `create_user_atomic`; rollback on email-fail-AND-commit-fail |
| 55 | created_by attribution on every account | `profiles.created_by NOT NULL` (with `admin22` carve-out) |
| 56 | CSPRNG everywhere | `secrets` module in `core/security.py`; no use of `random` |
| 57 | Single-use OTPs | `otp_audit.consumed_at`; `password_reset_codes.used_at` |
| 58 | Email delivery is optional, never blocking | `provisioning_service.py` returns OTP regardless of Resend success; `email_sent` boolean in response |
| 59 | RLS infinite recursion — SECURITY DEFINER helpers | `uid_can_read_task` / `uid_can_edit_task` (§5.4) |
| 60 | `text::bytea` cast breaks audit | Documented in `fn_audit_row()` comment block; regression test in `test_audit_chain.py` inserts row with `"` and `\n` |
| 61 | Tables without RLS = open (Supabase-specific) | N/A; FastAPI service-layer auth checks for every model — code-review checklist item |
| 62 | Built-in provider re-enable breaks custom flow | N/A; code-review rejects any second `/login` endpoint |
| 63 | Verify procedure after porting | `tests/test_provisioning.py` runs the full sequence: bootstrap admin22 → rotate pw → provision HOD → HOD provisions USER → HOD cannot provision in other dept → audit_log entries exist for each |

---

## 15. Open Questions

These small items need a yes/no or pick-one before code generation begins:

1. **Traefik subdomain.** Default in this spec is `weekly.srv1231216.hstgr.cloud`. Alternatives: `wwf.`, `flow.`, `weekly-weed-flow.`. **Recommendation:** keep `weekly.` — shortest, matches the project's internal nickname, no acronym collision.

2. **Department seed list.** Spec assumes a tree of:
   - **Cultivation** (parent) → Clone, Veg, Flower
   - **Production** (parent) → Drying, Trim, Pack
   - **Quality** (parent) → QC, QA, QP
   - **Warehouse** (parent) → Inbound, Outbound
   - **Maintenance** (flat)
   - **Compliance** (parent) → GACP, EU-GMP

   But per the seed strategy (§13), production deploys do NOT auto-seed depts; the human admin creates them via `AdminConsole`. **Question:** should we provide a one-click "Seed Purely Plant default departments" button in `AdminConsole` for convenience, or strictly manual creation only? **Recommendation:** provide the button (idempotent, logs to audit_log under the admin's identity), but never auto-run.

3. **Resend FROM address.** Default in spec: `noreply@purelyplant.eu`. Confirm this is the right inbox / DNS-verified sender domain. If `purelyplant.eu` is not DNS-verified with Resend, fall back to a Resend sandbox sender for initial dev. **Decision needed before email service goes live.**

4. **Re-seed admin22 in WWF?** Spec answer: **yes** (§13, decision D25). The WWF database is independent of QC_LIMS_Ao's database, so bootstrap is necessary. Confirm.

5. **Password reset for users without confirmed email.** A user provisioned via OTP whose recipient email bounces could be locked out if they never receive the email and the OTP expires. **Options:**
   (a) ADMIN/HOD can always re-issue the OTP via `POST /api/admin/users/{id}/reset-password` (current spec — sufficient).
   (b) Additionally support an "OTP-via-screen" fallback flow where the user calls support, support verifies identity, support re-issues OTP via the admin panel.

   Both are covered by (a) alone — the reset-password endpoint regenerates an OTP that the admin reads off-screen, same as initial provisioning. **Recommendation:** (a) only; no separate flow needed. Confirm.

6. **`audit_intent` table for app-level events.** Spec mentions a separate table for "user clicked Roll Over" type intent events that the row-level trigger cannot capture (these don't modify rows). **Question:** include in v1 or defer? **Recommendation:** include the table in v1 (cheap), wire up only the high-value events (login_success, login_failure, otp_issued_displayed, handoff_proposed_via_ui) and leave the rest for v1.1.

7. **PROJECT_LEAD scope tightening.** Spec currently has PROJECT_LEAD see all tasks where `project_id IS NOT NULL`. The full design needs a `projects` table with `project_members(project_id, profile_id, role)` so PROJECT_LEAD sees only their own projects. **Question:** ship the loose version in v1 and tighten in v1.1, or ship the projects table now? **Recommendation:** ship the loose version now (Purely Plant has 1-2 PROJECT_LEAD users initially); add `projects` table when the second project is created.

---

*End of specification.*