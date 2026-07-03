#!/usr/bin/env python3
"""Seed a fresh org + ADMIN profile for one e2e run; prints JSON credentials
to stdout. This app has no self-signup, so e2e tests need a real bootstrap
account to log in as before they can drive the UI — same approach as
tests/conftest.py's `org` fixture, just callable from outside pytest.

Usage: DATABASE_URL=... ADMIN_DATABASE_URL=... python3 seed_e2e_org.py
"""
import asyncio
import datetime
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg  # noqa: E402

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "local-e2e-secret-not-for-production")
from app.security import hash_password  # noqa: E402


async def main():
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    teammate_id = uuid.uuid4()
    suffix = uuid.uuid4().hex[:8]
    username = f"e2e_admin_{suffix}"
    password = "E2ETestPassword123456"
    teammate_name = f"E2E Teammate {suffix[:4]}"

    conn = await asyncpg.connect(os.environ["ADMIN_DATABASE_URL"])
    try:
        await conn.execute("INSERT INTO organizations(id, name, slug) VALUES ($1,$2,$3)",
                            org_id, f"E2E Org {suffix}", f"e2e-{suffix}")
        await conn.execute(
            "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role, must_change_password)"
            " VALUES ($1,$2,$3,$4,$5,'ADMIN',false)",
            admin_id, org_id, username, hash_password(password), "E2E Admin")
        # A second, non-admin org member — the assign step needs someone real
        # to assign the created task to.
        await conn.execute(
            "INSERT INTO profiles(id, org_id, username, password_hash, full_name, role, must_change_password)"
            " VALUES ($1,$2,$3,$4,$5,'USER',false)",
            teammate_id, org_id, f"e2e_teammate_{suffix}", hash_password(password), teammate_name)
        await conn.execute(
            "INSERT INTO departments(org_id, code, name) VALUES ($1,'cultivation','Cultivation')",
            org_id)
        today = datetime.date.today()
        starts_on = today - datetime.timedelta(days=today.weekday())  # Monday of the current week
        ends_on = starts_on + datetime.timedelta(days=6)
        iso_year, iso_week, _ = today.isocalendar()
        await conn.execute(
            "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on) VALUES ($1,$2,$3,$4,$5)",
            org_id, iso_year, iso_week, starts_on, ends_on)
        # A second, following week — needed for the roll-over-to-next-week
        # e2e flow (there is no POST /weeks endpoint to create one on demand).
        next_starts_on = starts_on + datetime.timedelta(days=7)
        next_ends_on = next_starts_on + datetime.timedelta(days=6)
        next_iso_year, next_iso_week, _ = next_starts_on.isocalendar()
        await conn.execute(
            "INSERT INTO calendar_weeks(org_id, iso_year, iso_week, starts_on, ends_on) VALUES ($1,$2,$3,$4,$5)",
            org_id, next_iso_year, next_iso_week, next_starts_on, next_ends_on)
    finally:
        await conn.close()

    print(json.dumps({
        "org_id": str(org_id), "username": username, "password": password,
        "teammate_name": teammate_name,
    }))


if __name__ == "__main__":
    asyncio.run(main())
