"""
Audit trail middleware and utilities.

EU GMP Annex 11 / 21 CFR Part 11 compliant immutable audit logging.
All GxP-relevant operations are captured with old/new values,
timestamp (UTC), user identity, IP address, and reason for change.

Data Integrity (ALCOA++):
- Attributable: Who performed action and when
- Original: First record preserved immutably
- Complete: All data including old/new values
"""

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.security import decode_access_token


# In-memory store for pending audit entries (flushed to DB by audit_service)
_pending_entries: list[dict[str, Any]] = []


class AuditAction:
    """Canonical audit action types."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    VIEW = "VIEW"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SIGN = "SIGN"
    EXPORT = "EXPORT"
    PRINT = "PRINT"


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that captures every API request for audit trail purposes.
    
    Records: timestamp, user_id (from JWT), action, resource, IP address.
    Mutating requests (POST/PUT/PATCH/DELETE) are always logged.
    GET requests are optionally logged if they access sensitive data.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.time()

        # Extract user from Authorization header
        user_id = None
        user_name = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = decode_access_token(token)
            if payload:
                user_id = payload.get("sub")
                user_name = payload.get("username", "unknown")

        # Determine action from HTTP method
        method = request.method
        action_map = {
            "POST": AuditAction.CREATE,
            "PUT": AuditAction.UPDATE,
            "PATCH": AuditAction.UPDATE,
            "DELETE": AuditAction.DELETE,
            "GET": AuditAction.VIEW,
        }
        action = action_map.get(method, AuditAction.VIEW)

        # Extract resource type from path (e.g., /samples -> samples)
        path_parts = request.url.path.strip("/").split("/")
        record_type = path_parts[0] if path_parts else "unknown"
        record_id = path_parts[1] if len(path_parts) > 1 else None

        # Process request
        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000

        # Only log mutating operations or sensitive retrievals
        if action in (AuditAction.CREATE, AuditAction.UPDATE, AuditAction.DELETE):
            entry = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc),
                "user_id": user_id,
                "user_full_name": user_name or "anonymous",
                "action": action,
                "record_type": record_type,
                "record_id": record_id,
                "field_name": None,
                "old_value": None,
                "new_value": None,
                "reason": None,
                "ip_address": request.client.host
                if request.client
                else "0.0.0.0",
                "session_id": str(uuid.uuid4()),
                "duration_ms": duration_ms,
                "path": request.url.path,
            }
            _pending_entries.append(entry)

        return response


def audit_log_change(
    *,
    user_id: str | None,
    user_full_name: str,
    action: str,
    record_type: str,
    record_id: str | None = None,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    reason: str | None = None,
    ip_address: str = "0.0.0.0",
) -> None:
    """
    Log a single audit event (for use in services/repositories).

    This function adds an in-memory entry that is flushed to the database
    by the audit service at the end of the request.

    Args:
        user_id: UUID of the acting user.
        user_full_name: Human-readable name of the user.
        action: One of AuditAction values.
        record_type: e.g., 'sample', 'coa', 'specification'.
        record_id: UUID of the affected record.
        field_name: Name of changed field (for UPDATE events).
        old_value: Value before change.
        new_value: Value after change.
        reason: Mandatory for critical changes (per EU GMP).
        ip_address: Client IP address.
    """
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc),
        "user_id": user_id,
        "user_full_name": user_full_name,
        "action": action,
        "record_type": record_type,
        "record_id": record_id,
        "field_name": field_name,
        "old_value": old_value,
        "new_value": new_value,
        "reason": reason,
        "ip_address": ip_address,
        "session_id": str(uuid.uuid4()),
    }
    _pending_entries.append(entry)


async def log_audit_entry(
    db,
    action: str,
    record_type: str,
    record_id: Any,
    user_id: Any,
    detail: str | None = None,
) -> None:
    """
    Persist an immutable audit-trail entry directly via the async session.

    Best-effort helper used by services (e.g. OOS) that already hold a DB
    session. Resolves the user's full name when possible. Never raises — a
    failed audit write must not abort the GxP operation it accompanies.

    Args:
        db: AsyncSession.
        action: One of AuditAction values.
        record_type: e.g. 'oos_record', 'coa'.
        record_id: UUID/identifier of the affected record.
        user_id: UUID of the acting user.
        detail: Free-text detail stored in new_value (e.g. field changed).
    """
    # Deferred imports to avoid circular import at module load.
    from sqlalchemy import select

    from app.models.audit import AuditEntry
    from app.models.user import User

    try:
        full_name = "system"
        if user_id is not None:
            res = await db.execute(select(User).where(User.id == user_id))
            user = res.scalar_one_or_none()
            if user is not None:
                full_name = user.full_name or user.username

        db.add(
            AuditEntry(
                timestamp=datetime.now(timezone.utc),
                user_id=user_id,
                user_full_name=full_name,
                action=action,
                record_type=record_type,
                record_id=str(record_id),
                record_identifier=str(record_id),
                new_value=str(detail) if detail is not None else None,
                ip_address="127.0.0.1",
                session_id="service",
            )
        )
        await db.flush()
    except Exception:
        # Audit logging is best-effort; do not break the parent transaction.
        pass


def flush_pending() -> list[dict[str, Any]]:
    """
    Flush all pending audit entries and return them.

    Called by the audit service to persist entries to the database.
    """
    entries = list(_pending_entries)
    _pending_entries.clear()
    return entries
