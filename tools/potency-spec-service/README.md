# Potency Spec Service

A tiny, self-contained web service that backs the single-page **Potency Spec
Builder** with a **shared** database of specifications. Multiple users hit one
instance and share the same data — the database is the source of truth, not the
browser.

A "spec" is one cannabis strain's potency-range specification: a set of nominal
Total-THC % values each with a tolerance, the measured results behind it, and a
draft/finished status.

- **Backend:** FastAPI (Python 3.12), served by uvicorn.
- **Storage:** SQLite (WAL mode) on a mounted volume — one file, survives
  restarts. The data-access layer sits behind a small `SpecStore` interface so a
  Postgres backend can be swapped in later via `DATABASE_URL` (not implemented
  yet — the seam is `build_store()` in `app/db.py`).
- **Frontend:** the app serves a static SPA from `web/` at `/`, same-origin with
  the API. `web/index.html` here is a placeholder that fetches `/api/specs` and
  renders the count so the wiring is testable end-to-end; the real SPA replaces it.
- **Auth:** none in the app. TLS + host routing are Traefik's job on the host.

## Layout

```
potency-spec-service/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app: routes, /health, static SPA mount
│   └── db.py            # SpecStore interface + SQLite backend (WAL, thread-safe)
├── web/
│   └── index.html       # placeholder SPA (GET /api/specs -> count)
├── seed.py              # parse the strain catalogue -> PUT one draft Spec each
├── requirements.txt     # fastapi + uvicorn[standard], pinned
├── Dockerfile           # python:3.12-slim, non-root, uvicorn on :8000
├── docker-compose.yml   # one service + Traefik labels + named /data volume
├── openapi-notes.md     # contract restated for the frontend author
└── README.md
```

## API contract

Base path for data is `/api`. `id` is the strain abbreviation, uppercased, and
must match `^[A-Z0-9_]{1,12}$` (else **422**).

| Method & path                    | Behaviour                                                                                     |
|----------------------------------|-----------------------------------------------------------------------------------------------|
| `GET /health`                    | `{"ok": true}`                                                                                |
| `GET /api/specs`                 | `{"specs": [Spec, ...]}` — all. Filter with `?status=draft` or `?status=finished`.            |
| `GET /api/specs/{id}`            | `Spec` (**404** if missing)                                                                   |
| `PUT /api/specs/{id}`            | Upsert. Body is a Spec without server timestamps. Returns the stored Spec.                    |
| `POST /api/specs/{id}/finish`    | `status="finished"`, `finished_at=now`; returns Spec (**404** if missing)                     |
| `POST /api/specs/{id}/reopen`    | `status="draft"`, `finished_at=null`; returns Spec (**404** if missing)                       |
| `DELETE /api/specs/{id}`         | `{"deleted": true}` — idempotent, **200** even if it was absent                               |

`PUT` sets `created_at` on the first write and `updated_at` on every write. The
path `{id}` is authoritative — it overrides any `id` in the body. `status` must
be `draft` or `finished` (else 422). `finished_at` is kept non-null **iff**
`status == "finished"`.

### Spec JSON shape

```json
{
  "id": "GP",
  "name": "Grape Pie",
  "custom": false,
  "status": "draft",
  "tol": {"16": 1.6, "18": 1.8, "24": 2.4, "26": 2.6, "28": 2.8},
  "ranges": [{"nominal": 16, "tol": 1.6, "lo": 14.4, "hi": 17.59}],
  "results_entered": [13.8, 14.2],
  "results_excluded": [21.29],
  "created_at": "2026-09-11T14:47:47.401884+00:00",
  "updated_at": "2026-09-11T14:48:09.837790+00:00",
  "finished_at": null
}
```

Columns are persisted for the queryable/server-managed fields (`id` PK, `name`,
`custom`, `status`, `created_at`, `updated_at`, `finished_at`); the whole JSON
body is kept in a `data` column. On read the columns are merged **over** the
stored body, so server-managed fields are always authoritative. The app owns the
rest of the shape (`tol`, `ranges`, `results_entered`, `results_excluded`, …) and
they round-trip untouched.

### Concurrency

`PUT` is **last-write-wins** for now. Optimistic concurrency (rejecting a write
whose `updated_at`/version does not match the currently-stored one) is a possible
future addition — `updated_at` already has microsecond precision so it can serve
as the version token — but it is **not implemented**.

## Configuration (env vars)

| Var            | Default            | Meaning                                                    |
|----------------|--------------------|------------------------------------------------------------|
| `DB_PATH`      | `/data/specs.db`   | SQLite file path.                                          |
| `STATIC_DIR`   | `web`              | Directory of static files served at `/`.                  |
| `DATABASE_URL` | *(unset)*          | Optional. `sqlite://…` uses SQLite; any other engine → `NotImplementedError`. |

## Run locally

### With uvicorn

```bash
cd potency-spec-service
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
DB_PATH=./specs.db STATIC_DIR=web uvicorn app.main:app --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000/  and  http://127.0.0.1:8000/health
```

### With Docker Compose

```bash
cd potency-spec-service
docker compose up --build       # add -d to detach
```

The SQLite file lives on the named volume `specs_data` mounted at `/data`.

## Seed the catalogue

`seed.py` parses the `const DATA = [...]` array out of the repo file
`docs/tools/potency-range-builder.html`, builds one **draft** Spec per strain
(`custom=false`, `results_entered`/`results_excluded` empty, tolerances at the
"10% max": `tol = round(n*0.10, 2)`, ranges `lo = round(n-tol, 2)`,
`hi = round(n+tol-0.01, 2)`), and PUTs each to a running instance.

```bash
# instance running on localhost:8000, catalogue auto-discovered by walking up
# from the CWD / this script looking for docs/tools/potency-range-builder.html
python seed.py

# or be explicit: python seed.py BASE_URL CATALOGUE_HTML
CATALOGUE_HTML=/path/to/docs/tools/potency-range-builder.html \
  python seed.py https://specs.srv1231216.hstgr.cloud

# re-seed a live DB without clobbering user edits (skips ids that already exist)
python seed.py http://localhost:8000 --skip-existing
```

Idempotent: `PUT` is an upsert keyed by `id`, so repeated runs converge to the
same catalogue state.

## Deploy behind Traefik on the host

> The KVM4 host was **just rebuilt** — the placeholders in `docker-compose.yml`
> must be reconciled against the live host first (there is a full reconcile
> comment block at the top of that file).

1. **DNS.** Add an `A` (and `AAAA` if the box is dual-stack) record for the
   subdomain — placeholder `specs.srv1231216.hstgr.cloud` — pointing at KVM4, so
   letsencrypt can issue a cert and Traefik can match the `Host()` rule.
2. **Reconcile the network.** `docker network ls` on the host and set **both**
   the external network `name:` and the `traefik.docker.network=` label to the
   real Traefik network (the pre-rebuild WWF stack used `traefik_network`; the
   compose file ships the placeholder `shared`). Traefik only routes to
   containers that share its own docker network.
3. **Reconcile entrypoint / certresolver names.** The labels use `websecure` and
   `letsencrypt` (the WWF names). If the rebuilt Traefik's static config names
   them differently, update the two labels.
4. **Bring it up:**
   ```bash
   docker compose up -d --build
   docker compose logs -f specs
   ```
5. **Seed** (see above) against `https://<subdomain>`.

## Database location & backup

The DB is a single SQLite file on the `specs_data` volume at `/data/specs.db`
(plus its `-wal`/`-shm` sidecars while running). To back it up, prefer the
online-safe backup that respects WAL:

```bash
# consistent hot copy (recommended)
docker compose exec specs sqlite3 /data/specs.db ".backup '/data/specs.backup.db'"
docker compose cp specs:/data/specs.backup.db ./specs-$(date +%F).db

# or, with the container stopped, just copy the file
docker compose cp specs:/data/specs.db ./specs-$(date +%F).db
```

Restore by copying a backup file back to `/data/specs.db` on the volume with the
service stopped.

## Same-origin note

The service is designed to be **same-origin** with the SPA: Traefik serves both
the static app and the API under one host, so the SPA calls the API with
**relative** URLs (`/api/specs`, `/api/specs/GP`, …). There is no CORS config and
none is needed in that arrangement. If the SPA is ever hosted on a different
origin, CORS middleware would have to be added.

## Verified

Built here, then run for real: created a venv, `pip install -r requirements.txt`
(fastapi 0.141.1, uvicorn 0.52.4), launched `uvicorn app.main:app` on port 8137
with a scratch `DB_PATH`, and exercised every endpoint with `curl`. All passed;
the DB came up in WAL mode with the expected schema.

```console
$ curl -s $B/health
{"ok":true}                                                    <- HTTP 200

$ curl -s $B/api/specs                          # empty DB
{"specs":[]}                                                   <- HTTP 200

$ curl -s -X PUT $B/api/specs/GP -H 'Content-Type: application/json' \
    -d '{"id":"GP","name":"Grape Pie","custom":false,"status":"draft",
         "tol":{"16":1.6,"18":1.8},
         "ranges":[{"nominal":16,"tol":1.6,"lo":14.4,"hi":17.59},
                   {"nominal":18,"tol":1.8,"lo":16.2,"hi":19.79}],
         "results_entered":[13.8,14.2],"results_excluded":[21.29]}'
{"id":"GP","name":"Grape Pie","custom":false,"status":"draft", ... ,
 "created_at":"2026-09-11T14:46:31+00:00",
 "updated_at":"2026-09-11T14:46:31+00:00","finished_at":null}  <- HTTP 200

$ curl -s $B/api/specs          | jq '{count:(.specs|length),ids:[.specs[].id]}'
{"count":1,"ids":["GP"]}                                       <- HTTP 200

$ curl -s $B/api/specs/GP       | jq '{id,status,created_at,updated_at,finished_at}'
{"id":"GP","status":"draft", ... ,"finished_at":null}          <- HTTP 200

$ curl -s "$B/api/specs?status=draft"    | jq '{draft:(.specs|length)}'
{"draft":1}
$ curl -s "$B/api/specs?status=finished" | jq '{finished:(.specs|length)}'
{"finished":0}

$ curl -s -X POST $B/api/specs/GP/finish | jq '{status,finished_at}'
{"status":"finished","finished_at":"2026-09-11T14:46:31+00:00"} <- HTTP 200

$ curl -s -X POST $B/api/specs/GP/reopen | jq '{status,finished_at}'
{"status":"draft","finished_at":null}                          <- HTTP 200

$ curl -s -X DELETE $B/api/specs/GP
{"deleted":true}                                               <- HTTP 200
$ curl -s -X DELETE $B/api/specs/GP     # idempotent — 200 even when absent
{"deleted":true}                                               <- HTTP 200

$ curl -s $B/api/specs/GP               # after delete
{"detail":"spec 'GP' not found"}                               <- HTTP 404

# --- validation (422) ---
$ curl -s -X PUT $B/api/specs/bad-id -d '{"name":"x"}'
{"detail":"invalid spec id 'bad-id': must match ^[A-Z0-9_]{1,12}$"}  <- HTTP 422
$ curl -s $B/api/specs/TOOLONGABCDEF    # 13 chars
{"detail":"invalid spec id 'TOOLONGABCDEF': must match ^[A-Z0-9_]{1,12}$"} <- HTTP 422
$ curl -s "$B/api/specs?status=weird"
{"detail":"invalid status filter 'weird': must be one of ['draft', 'finished']"} <- HTTP 422
$ curl -s -X PUT $B/api/specs/AB -d '{"name":"x","status":"nope"}'
{"detail":"invalid status 'nope': must be one of ['draft', 'finished']"}     <- HTTP 422

# --- finish/reopen on a missing spec -> 404 ---
$ curl -s -X POST $B/api/specs/NOPE/finish   -> HTTP 404
$ curl -s -X POST $B/api/specs/NOPE/reopen   -> HTTP 404

# --- upsert keeps created_at, bumps updated_at (server fields authoritative) ---
{"created_at":"2026-09-11T14:47:47.401884+00:00",
 "updated_at":"2026-09-11T14:48:09.837790+00:00","bumped":true}

# --- static SPA served same-origin ---
$ curl -s $B/                            -> HTTP 200, 1695 bytes, title present

# --- seed against the running instance ---
$ CATALOGUE_HTML=.../docs/tools/potency-range-builder.html python seed.py http://127.0.0.1:8137
strains : 23
  ... put GP Grape Pie (5 nominal(s)) -> 200 ...
done: 23 put, 0 skipped, 0 failed
# GP seeded ranges match the contract example exactly:
#   nominal 16 -> tol 1.6, lo 14.4, hi 17.59 ; 18 -> 1.8/16.2/19.79 ; ...
$ python seed.py http://127.0.0.1:8137 --skip-existing
done: 0 put, 23 skipped, 0 failed

# --- storage ---
sqlite> PRAGMA journal_mode;  ->  wal
sqlite> SELECT count(*) FROM specs;  ->  23
```

### Note on the catalogue size

The contract mentioned "22 strains"; the current
`docs/tools/potency-range-builder.html` actually holds **23** entries (`ACC, AB,
BG, BSS, CJ, CC, CF, CLE, FB, GG, GP, GRC, HPA, JD, J31, KC, MB, OPM, PM, PUM,
SCR, SJ, WC`). `seed.py` parses whatever the file contains rather than hard-coding
a count, so it seeded all 23. No action needed; flagged for awareness.
