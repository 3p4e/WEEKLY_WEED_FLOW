# WWF end-to-end tests (Playwright)

Drives a real Chromium browser against the real backend + a local nginx
proxy — the closest thing to production reachable without Docker. Uses the
same test database as the pytest suite (`backend/tests/`); each spec seeds
its own organization via `backend/scripts/seed_e2e_org.py` (this app has no
self-signup, so e2e tests need a real bootstrap account to log in as).

## One-time setup

1. Backend test database — see `backend/README.md`'s "Tests" section (same
   `weekly_weed_flow_test` database, same `app_user`/`app_admin` roles).
2. `nginx` installed locally (`apt install nginx-light` or equivalent) —
   `start-nginx.sh` renders `nginx.local.conf` (production's routing rules,
   pointed at `127.0.0.1` instead of a Docker hostname) and runs it on
   `127.0.0.1:8091`.
3. `npm install` in this directory.

## Run

```bash
npx playwright test
```

`playwright.config.js`'s `webServer` array starts the backend
(`../../backend/scripts/run_e2e_backend.sh`, port 8000) and nginx
(`start-nginx.sh`, port 8091) automatically and waits for both to be
healthy before running specs; `reuseExistingServer` is on outside CI, so
you can leave both running locally across repeated `npx playwright test`
invocations while iterating.

If the installed `@playwright/test` version doesn't match the Chromium
build already on disk in your environment, point at the existing binary
directly instead of downloading a new one:

```bash
PLAYWRIGHT_CHROMIUM_PATH=/path/to/chromium npx playwright test
```

## What this suite is (and isn't) for

One real end-to-end path per meaningfully different user flow — proving the
seams actually connect (auth → API → RLS → rendering → the next API call),
not exhaustive UI coverage. `backend/tests/` (pytest) is where behavior at
the API/RLS layer belongs; reach for a new e2e spec only when the thing
you're pinning genuinely can't be observed without a real browser.

`tests/core-flow.spec.js` (login → create a task → cycle its status →
assign a teammate → logout) is exactly how a previously-undetected bug
surfaced during Phase 2 of this project's test-suite work: every task's
`progress_notes` column was jsonb, no jsonb codec was registered on the
asyncpg pools, so it round-tripped as the raw string `"[]"` instead of an
empty list — and `GF.WWF.transform`'s `(t.progress_notes || []).map(...)`
throws on a string. Every pytest test up to that point asserted on specific
fields and never happened to check that one's *type*, so nothing caught it
at the API layer; the e2e test caught it because the real frontend code ran
against the real response shape. Fixed in `backend/app/db.py` (a
`set_type_codec` on jsonb) — see `backend/tests/test_tasks.py`'s
`test_progress_notes_is_a_real_list_not_a_json_string` for the pytest-level
regression pin now that the shape is known.
