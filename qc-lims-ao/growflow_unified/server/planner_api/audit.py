"""Append-only, hash-chained audit trail (ALCOA+ backbone).

Each event links to the previous one: payload_hash = sha256(prev_hash || canonical_json(payload)),
matching db/schema.sql §6 and the smoke-test convention. A transaction-scoped advisory lock
serialises concurrent writers so the chain stays gap-free and tamper-evident.
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Arbitrary constant key for the audit-chain advisory lock (held until commit/rollback).
_AUDIT_LOCK_KEY = 74010


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


async def record_event(
    session: AsyncSession,
    *,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    payload: dict,
) -> None:
    """Append one audit event within the caller's transaction (caller commits)."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _AUDIT_LOCK_KEY})
    prev = (
        await session.execute(text("SELECT payload_hash FROM audit_event ORDER BY id DESC LIMIT 1"))
    ).scalar_one_or_none()
    digest = hashlib.sha256((bytes(prev) if prev is not None else b"") + _canonical(payload)).digest()
    await session.execute(
        text(
            "INSERT INTO audit_event "
            "(actor_id, action, entity_type, entity_id, payload, prev_hash, payload_hash) "
            "VALUES (:actor, :action, :etype, :eid, CAST(:payload AS JSONB), :prev, :hash)"
        ),
        {
            "actor": actor_id,
            "action": action,
            "etype": entity_type,
            "eid": entity_id,
            "payload": json.dumps(payload, default=str),
            "prev": prev,
            "hash": digest,
        },
    )
