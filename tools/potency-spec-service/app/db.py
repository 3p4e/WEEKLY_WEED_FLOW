"""Data-access layer for potency specs.

The public surface is the :class:`SpecStore` interface. Only a SQLite backend
(:class:`SQLiteSpecStore`) is implemented today; a Postgres backend can be added
later and selected via the ``DATABASE_URL`` env var without touching the routes
in ``app.main`` — they only ever talk to a ``SpecStore``.

Storage model (one table, ``specs``):
  * Columns are kept for the queryable / server-managed fields
    (id, name, custom, status, created_at, updated_at, finished_at).
  * The full Spec JSON body is kept verbatim in the ``data`` column.
  * On read the column values are merged *over* the stored body so the
    server-managed fields are always authoritative.

Concurrency: writes are last-write-wins (see the note in README.md about a
possible future optimistic-concurrency check on ``updated_at``). Thread safety
is achieved by opening a fresh short-lived connection per operation, so no
connection is ever shared across threads; WAL mode lets readers and the single
writer proceed without blocking each other.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Allowed lifecycle states for a spec.
VALID_STATUS = ("draft", "finished")


def now_iso() -> str:
    """Current UTC time as a tz-aware ISO-8601 string (microsecond precision).

    Microsecond precision keeps ``updated_at`` strictly increasing between
    successive writes, which also makes it a usable version token if optimistic
    concurrency is added later (see README).
    """
    return datetime.now(timezone.utc).isoformat()


class SpecStore:
    """Abstract data-access interface for specs.

    Implement this against another engine (e.g. Postgres) and return it from
    :func:`build_store` to swap backends; the HTTP layer is engine-agnostic.
    """

    def init(self) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def list(self, status: Optional[str] = None) -> List[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def get(self, spec_id: str) -> Optional[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def upsert(self, spec_id: str, body: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def finish(self, spec_id: str) -> Optional[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def reopen(self, spec_id: str) -> Optional[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def delete(self, spec_id: str) -> bool:  # pragma: no cover
        raise NotImplementedError


class SQLiteSpecStore(SpecStore):
    """SQLite-backed spec store (WAL mode, one connection per operation)."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_lock = threading.Lock()

    # -- connection helpers ------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Wait rather than fail immediately if another writer holds the lock.
        conn.execute("PRAGMA busy_timeout=30000;")
        return conn

    def init(self) -> None:
        """Create the parent dir, enable WAL, and create the table if needed."""
        parent = os.path.dirname(os.path.abspath(self.db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with self._init_lock:
            conn = self._connect()
            try:
                # WAL is a persistent property of the DB file; set once here.
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS specs (
                        id          TEXT PRIMARY KEY,
                        name        TEXT,
                        custom      INTEGER NOT NULL DEFAULT 0,
                        status      TEXT    NOT NULL DEFAULT 'draft',
                        created_at  TEXT,
                        updated_at  TEXT,
                        finished_at TEXT,
                        data        TEXT    NOT NULL
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_specs_status ON specs(status);")
                conn.commit()
            finally:
                conn.close()

    # -- serialization -----------------------------------------------------
    @staticmethod
    def _row_to_spec(row: sqlite3.Row) -> Dict[str, Any]:
        """Load the stored body and overlay the authoritative column values."""
        body: Dict[str, Any] = json.loads(row["data"])
        body["id"] = row["id"]
        body["name"] = row["name"]
        body["custom"] = bool(row["custom"])
        body["status"] = row["status"]
        body["created_at"] = row["created_at"]
        body["updated_at"] = row["updated_at"]
        body["finished_at"] = row["finished_at"]
        return body

    # -- reads -------------------------------------------------------------
    def get(self, spec_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM specs WHERE id = ?", (spec_id,)).fetchone()
            return self._row_to_spec(row) if row is not None else None
        finally:
            conn.close()

    def list(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if status is not None:
                rows = conn.execute(
                    "SELECT * FROM specs WHERE status = ? ORDER BY id", (status,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM specs ORDER BY id").fetchall()
            return [self._row_to_spec(r) for r in rows]
        finally:
            conn.close()

    # -- writes ------------------------------------------------------------
    def upsert(self, spec_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        status = body.get("status", "draft")
        if status not in VALID_STATUS:
            raise ValueError(f"invalid status: {status!r}")

        now = now_iso()
        conn = self._connect()
        try:
            prev = conn.execute(
                "SELECT created_at, finished_at FROM specs WHERE id = ?", (spec_id,)
            ).fetchone()

            created_at = prev["created_at"] if (prev and prev["created_at"]) else now
            updated_at = now
            # Invariant: finished_at is set iff status == "finished". Preserve an
            # existing finish time across an idempotent re-PUT of a finished spec.
            if status == "finished":
                finished_at = prev["finished_at"] if (prev and prev["finished_at"]) else now
            else:
                finished_at = None

            name = body.get("name")
            custom = 1 if body.get("custom") else 0

            # Store a clean, self-consistent copy of the body: caller-supplied
            # server fields (if any) are overwritten with the computed values.
            stored = dict(body)
            stored["id"] = spec_id
            stored["status"] = status
            stored["created_at"] = created_at
            stored["updated_at"] = updated_at
            stored["finished_at"] = finished_at

            conn.execute(
                """
                INSERT INTO specs (id, name, custom, status, created_at, updated_at, finished_at, data)
                VALUES (:id, :name, :custom, :status, :created_at, :updated_at, :finished_at, :data)
                ON CONFLICT(id) DO UPDATE SET
                    name        = excluded.name,
                    custom      = excluded.custom,
                    status      = excluded.status,
                    created_at  = excluded.created_at,
                    updated_at  = excluded.updated_at,
                    finished_at = excluded.finished_at,
                    data        = excluded.data
                """,
                {
                    "id": spec_id,
                    "name": name,
                    "custom": custom,
                    "status": status,
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "finished_at": finished_at,
                    "data": json.dumps(stored, ensure_ascii=False),
                },
            )
            conn.commit()
            row = conn.execute("SELECT * FROM specs WHERE id = ?", (spec_id,)).fetchone()
            return self._row_to_spec(row)
        finally:
            conn.close()

    def _set_status(self, spec_id: str, status: str) -> Optional[Dict[str, Any]]:
        now = now_iso()
        finished_at = now if status == "finished" else None
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM specs WHERE id = ?", (spec_id,)).fetchone()
            if row is None:
                return None
            body = json.loads(row["data"])
            body["status"] = status
            body["updated_at"] = now
            body["finished_at"] = finished_at
            conn.execute(
                "UPDATE specs SET status = ?, updated_at = ?, finished_at = ?, data = ? WHERE id = ?",
                (status, now, finished_at, json.dumps(body, ensure_ascii=False), spec_id),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM specs WHERE id = ?", (spec_id,)).fetchone()
            return self._row_to_spec(row)
        finally:
            conn.close()

    def finish(self, spec_id: str) -> Optional[Dict[str, Any]]:
        return self._set_status(spec_id, "finished")

    def reopen(self, spec_id: str) -> Optional[Dict[str, Any]]:
        return self._set_status(spec_id, "draft")

    def delete(self, spec_id: str) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM specs WHERE id = ?", (spec_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def build_store() -> SpecStore:
    """Select and initialize the storage backend from the environment.

    * ``DATABASE_URL`` unset or ``sqlite://...``  -> SQLite at ``DB_PATH``.
    * ``DATABASE_URL`` set to anything else       -> NotImplementedError
      (the seam is here; implement a Postgres ``SpecStore`` and return it).
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    db_path = os.getenv("DB_PATH", "/data/specs.db")

    if database_url and not database_url.startswith("sqlite"):
        raise NotImplementedError(
            f"Only the SQLite backend is implemented; DATABASE_URL={database_url!r} "
            "requests another engine. Implement a SpecStore for it and return it here."
        )
    if database_url.startswith("sqlite"):
        # Accept sqlite:///relative or sqlite:////absolute forms.
        parsed = database_url.split("sqlite://", 1)[-1].lstrip("/")
        if parsed:
            db_path = "/" + parsed if database_url.startswith("sqlite:////") else parsed

    store = SQLiteSpecStore(db_path)
    store.init()
    return store
