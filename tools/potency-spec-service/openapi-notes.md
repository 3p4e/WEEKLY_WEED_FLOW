# Potency Spec API — notes for the frontend

Concise restatement of the contract you're building the SPA against. The service
is **same-origin** with the SPA, so call everything with **relative** URLs
(`/api/specs`, not an absolute host). No auth headers — Traefik handles TLS/host.

Content type for writes: `application/json`. All responses are JSON.

## Identifiers

`id` = strain abbreviation, **uppercased**, matching `^[A-Z0-9_]{1,12}$`
(letters A–Z, digits, underscore; 1–12 chars). Anything else → **422**. The
server does not auto-uppercase; send it uppercased. On `PUT`, the URL's `id` wins
over any `id` in the body.

## Endpoints

| Method & path                 | Success | Notes |
|-------------------------------|---------|-------|
| `GET /health`                 | 200     | `{"ok": true}` — liveness only. |
| `GET /api/specs`              | 200     | `{"specs": [Spec, ...]}`, sorted by id. `?status=draft` / `?status=finished` to filter; other `status` → 422. |
| `GET /api/specs/{id}`         | 200     | a `Spec`. Missing → **404**. Bad id → 422. |
| `PUT /api/specs/{id}`         | 200     | upsert; returns the stored `Spec`. |
| `POST /api/specs/{id}/finish` | 200     | sets `status="finished"`, `finished_at=now`. Missing → **404**. |
| `POST /api/specs/{id}/reopen` | 200     | sets `status="draft"`, `finished_at=null`. Missing → **404**. |
| `DELETE /api/specs/{id}`      | 200     | `{"deleted": true}`, **idempotent** (200 even if it never existed). |

Errors come back as `{"detail": "<message>"}` with the status code above.

## The Spec object

```jsonc
{
  "id": "GP",                 // uppercased, ^[A-Z0-9_]{1,12}$
  "name": "Grape Pie",        // app-owned
  "custom": false,            // true if user-created, false if from the seed catalogue
  "status": "draft",          // "draft" | "finished"
  "tol":    {"16": 1.6, "18": 1.8, "24": 2.4},   // nominal (int as string) -> tolerance (float)
  "ranges": [                 // one per nominal
    {"nominal": 16, "tol": 1.6, "lo": 14.4, "hi": 17.59}
  ],
  "results_entered":  [13.8, 14.2],   // values the user typed
  "results_excluded": [21.29],        // source values the user hid
  "created_at": "2026-09-11T14:47:47.401884+00:00",  // server-managed, ISO-8601 UTC
  "updated_at": "2026-09-11T14:48:09.837790+00:00",  // server-managed
  "finished_at": null                 // server-managed; ISO when finished, else null
}
```

**Server-managed fields** — `created_at`, `updated_at`, `finished_at` (and
`status` via finish/reopen) — are owned by the server. You may send them on a
`PUT`; they are ignored and recomputed. Everything else round-trips untouched, so
you can stash extra keys in the object if you need to and they'll come back.

Invariant: `finished_at` is non-null **iff** `status == "finished"`.

## Writing (PUT is the workhorse)

`PUT` is a full upsert. Send the whole Spec **without** the server timestamps
(sending them is harmless — they're overwritten). First write stamps
`created_at`; every write stamps `updated_at`. **Last-write-wins** — there is no
version check yet, so two tabs saving the same id will clobber each other's body.

### Example — create/update

Request:
```
PUT /api/specs/GP
Content-Type: application/json

{
  "id": "GP",
  "name": "Grape Pie",
  "custom": false,
  "status": "draft",
  "tol": {"16": 1.6, "18": 1.8},
  "ranges": [
    {"nominal": 16, "tol": 1.6, "lo": 14.4, "hi": 17.59},
    {"nominal": 18, "tol": 1.8, "lo": 16.2, "hi": 19.79}
  ],
  "results_entered": [13.8, 14.2],
  "results_excluded": [21.29]
}
```

Response `200`:
```json
{
  "id": "GP",
  "name": "Grape Pie",
  "custom": false,
  "status": "draft",
  "tol": {"16": 1.6, "18": 1.8},
  "ranges": [
    {"nominal": 16, "tol": 1.6, "lo": 14.4, "hi": 17.59},
    {"nominal": 18, "tol": 1.8, "lo": 16.2, "hi": 19.79}
  ],
  "results_entered": [13.8, 14.2],
  "results_excluded": [21.29],
  "created_at": "2026-09-11T14:46:31.000000+00:00",
  "updated_at": "2026-09-11T14:46:31.000000+00:00",
  "finished_at": null
}
```

### Example — list, filtered

Request: `GET /api/specs?status=finished`

Response `200`:
```json
{
  "specs": [
    {
      "id": "GP",
      "name": "Grape Pie",
      "custom": false,
      "status": "finished",
      "tol": {"16": 1.6},
      "ranges": [{"nominal": 16, "tol": 1.6, "lo": 14.4, "hi": 17.59}],
      "results_entered": [13.8, 14.2],
      "results_excluded": [],
      "created_at": "2026-09-11T14:46:31.000000+00:00",
      "updated_at": "2026-09-11T14:47:02.500000+00:00",
      "finished_at": "2026-09-11T14:47:02.500000+00:00"
    }
  ]
}
```

### Example — finish, then 404 on a missing id

Request: `POST /api/specs/GP/finish` → `200`
```json
{ "id": "GP", "status": "finished", "finished_at": "2026-09-11T14:47:02.500000+00:00", "...": "rest of Spec" }
```

Request: `GET /api/specs/ZZZ` (valid id, not stored) → `404`
```json
{ "detail": "spec 'ZZZ' not found" }
```

### Example — validation failure

Request: `PUT /api/specs/bad-id` → `422`
```json
{ "detail": "invalid spec id 'bad-id': must match ^[A-Z0-9_]{1,12}$" }
```

## Suggested client flow

- On load: `GET /api/specs` (or `?status=draft`) to populate the list.
- On save: `PUT /api/specs/{id}` with the full working object.
- Finish/reopen: `POST .../finish` and `.../reopen` — don't try to toggle
  `status` through `PUT` and expect `finished_at` bookkeeping to differ; the two
  POST endpoints exist precisely so the client doesn't manage `finished_at`.
  (A `PUT` with `status:"finished"` *will* set `finished_at`, but the POSTs are
  the intended path.)
- Delete: `DELETE /api/specs/{id}` — safe to call blindly; it's idempotent.
