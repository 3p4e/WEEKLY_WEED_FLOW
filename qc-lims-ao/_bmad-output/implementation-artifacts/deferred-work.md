# Deferred Work — Phase P0 Foundation

Collected during step-04 review. These are pre-existing issues surfaced but not caused by P0.

## Defer Items

| # | Finding | Source | Priority |
|---|---------|--------|----------|
| D1 | CORS wildcard origin + credentials is a latent security issue | Edge Case Hunter | Medium |
| D2 | `Base.metadata.create_all` races in multi-worker deployments | Edge Case Hunter | Medium |
| D3 | `session_id` regenerated per HTTP request, not per user session | Edge Case Hunter | Low |
| D4 | `updated_at` on audit entries can mutate on accidental UPDATE (inherited from BaseModel) | Edge Case Hunter | Medium |
| D5 | No unit tests for `parse_xlsx`, `health_check`, schema validation | Acceptance Auditor | Medium |
| D6 | `create_access_token` does not guard against non-positive expiry | Edge Case Hunter | Low |
| D7 | `TestResult.__repr__` may trigger `DetachedInstanceError` | Edge Case Hunter | Low |
| D8 | `file_size` Integer column overflows for files > 2 GB | Edge Case Hunter | Low |
| D9 | `page_count` accepts zero without validation | Edge Case Hunter | Low |
| D10 | Alembic autogenerate may miss models if `__init__.py` incomplete | Edge Case Hunter | Low |
| D11 | Inconsistent import style (`Optional` vs `\| None`) across files | Blind Hunter | Low |
| D12 | No `__all__` in package `__init__.py` files | Blind Hunter | Low |
| D13 | `google_client_id` empty string vs None ambiguity | Blind Hunter | Low |

## Rejected Items (noise / false positive)

| # | Finding | Reason |
|---|---------|--------|
| R1 | Placeholder routers expose empty endpoints | Intentional scaffolding — will be filled in P1-P6 |
| R2 | `import_service` reimplemented instead of direct copy | Functional equivalent, better stdlib approach |
| R3 | `min_limit`/`max_limit` denormalization | Required for GMP snapshot compliance (frozen at test time) |
