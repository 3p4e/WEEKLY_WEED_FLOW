# WEEKLY_WEED_FLOW

Standalone weekly task-coordination app for Purely Plant — GACP cultivation + EU-GMP
production. Department hierarchy (Admin → Dept Head → Team Leader → User) plus a
cross-departmental Project Lead role. Adopts the ISO17verSUMA authentication / audit /
provisioning **methodology** (custom auth, OTP provisioning, no self-signup, Postgres RLS,
hash-chained audit) on a FastAPI + Postgres + React stack — **no Supabase**.

Inherits design tokens, bilingual EN/МК UI, and deploy infrastructure from QC_LIMS_Ao;
contains **no QC/LIMS modules**.

- **Design-of-record:** [`docs/WEEKLY_WEED_FLOW_ADAPTATION_SPEC.md`](docs/WEEKLY_WEED_FLOW_ADAPTATION_SPEC.md)
- **Deploy target:** `wwf.srv1231216.hstgr.cloud` (Traefik HTTPS), compose project `weekly_weed_flow`, sibling to QC_LIMS_Ao1 on KVM4.

Status: specification complete; code generation pending open-question sign-off (see spec §15).
