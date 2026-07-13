# Test-account matrix (`tt.*`)

A full-role test cast provisioned **on the live deployment** for validating
the per-department UI and the executive report with real accounts, then
removed before production use. Provisioning is **API-only** (never direct
SQL) so the hash-chained audit trail records every action.

## The matrix (~25 accounts)

| Username | Role | Department |
|---|---|---|
| `tt.owner` / `tt.ceo` / `tt.coo` | OWNER / CEO / COO | — |
| `tt.qp` | QP | — |
| `tt.cu.mgr`, `tt.cu.op1`, `tt.cu.op2` | CU_MGR, USER, USER | cultivation |
| `tt.pr.*` | PR_MGR + 2×USER | production |
| `tt.qc.*` | QC_MGR + 2×USER | qc |
| `tt.qa.*` | QA_MGR + 2×USER | quality_assurance |
| `tt.wh.*` | WH_MGR + 2×USER | logistics |
| `tt.se.*` | SE_MGR + 2×USER | security |
| `tt.mu.*` | MU_MGR + 2×USER | tooling |

Full names are prefixed `[TEST]` so they are unmistakable in rosters,
reports, and the audit trail. The 7 department codes are canonical
(`web/gf/demo.js`); `backend/tests/test_provision_matrix.py` pins the matrix
shape offline.

## Prerequisite — deploy order

`POST /departments` (ADMIN-only, idempotent) ships with this cycle's backend.
**The backend must be deployed before the script can run** — older backends
404 the department-creation step.

## Running

From any machine that can reach the deployment (workstation or the KVM4 host;
needs Python 3.11+ and `httpx`):

```bash
cd backend/scripts
WWF_ADMIN_PASSWORD=... python provision_test_accounts.py \
    --admin-user <admin> --set-passwords
```

- The admin password comes from the env var or an interactive prompt — never
  argv.
- **Safety abort:** the script compares live `/departments` codes against the
  canonical 7 and refuses to run if any unknown code exists (prevents
  semantic duplicates like a live `warehouse` next to `logistics`). Missing
  departments are created; existing ones are never modified.
- Reruns are idempotent: existing `tt.*` accounts are skipped.
- `--set-passwords` completes each account's forced first login with a random
  per-user password (OTP → change-password → verify), so the cast is
  immediately usable.

Credentials land in `test_accounts.local.json` (mode 0600, gitignored) in the
working directory. Treat it like any secret; delete it after validation.

## Cleanup (before production use)

```bash
python provision_test_accounts.py --admin-user <admin> --cleanup
```

Soft-deletes every `tt.*` account after a confirmation prompt
(`DELETE /auth/users/{id}` → `is_deleted=true, is_active=false`). The rows —
and everything they did — **intentionally persist in the audit trail**; their
usernames are freed for reuse. The hard `DELETE /auth/users/{id}/purge`
(ADMIN-only) remains a deliberate manual step per account, via the app's
"Removed accounts" modal or the API, once nothing references the test data
anymore.

## Known quirk — landing views

The role-aware landing default (executives → Executive overview, department
members → Department home) applies only to a **fresh browser profile**: an
existing browser keeps its persisted `gf_view` choice until the user
navigates. When validating landing behaviour, use a private window per
account.
