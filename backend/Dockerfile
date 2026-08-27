# WEEKLY_WEED_FLOW API — FastAPI (async, asyncpg) served by uvicorn.
# Built and run on KVM4 as `weekly_weed_flow-backend:latest`; the GrowFlow
# nginx frontend reverse-proxies /auth /departments /weeks /tasks /ai /audit
# /reports /health to it over the internal Docker network. The HEALTHCHECK is
# declared in docker-compose.yml, not here, because this same image also runs
# as the scheduler (a loop with no HTTP surface) and the two need different
# probes. The "Traefik won't route unhealthy containers" rationale that used to
# sit here was copied from the frontend and never applied: this service carries
# no Traefik labels, so nothing was watching it at all (H12).
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# WeasyPrint (weekly document PDF export) needs Pango/Harfbuzz at runtime and
# a Cyrillic-capable font — DejaVu covers Macedonian (МК) document content.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
# alembic.ini + alembic/ ship in the same image so migrations run via
# `docker exec <container> alembic -n users|tasks upgrade head` with the
# per-database *_MIGRATION_DATABASE_URL set — see backend/README.md's "Migrations" section. Not used by the
# running app itself (uvicorn only ever imports app/).
COPY alembic.ini .
COPY alembic_users ./alembic_users
COPY alembic_tasks ./alembic_tasks
# scripts/ ships too: the weekly-snapshot job + scheduler run from this same
# image as a separate container (`python scripts/scheduler.py`) and via
# `docker exec ... python scripts/weekly_snapshot.py --once`. Not imported by
# the uvicorn app.
COPY scripts ./scripts
EXPOSE 8000
# --proxy-headers makes uvicorn honour X-Forwarded-For, but ONLY from peers
# listed in FORWARDED_ALLOW_IPS (set in compose to the frontend nginx's
# static IP — see docker-compose.yml). We deliberately do NOT bake
# --forwarded-allow-ips=* here: '*' would trust a forged X-Forwarded-For from
# ANY container on the shared docker network — including capture-mcp, which
# is itself internet-exposed — letting a compromised sibling spoof its source
# IP and defeat the login rate-limiter. Trusting only the frontend's IP means
# every other peer's request.client.host is its real address. If the env var
# is unset, uvicorn falls back to trusting 127.0.0.1 only (fail-safe: the
# per-IP limiter degrades to one shared bucket, never becomes spoofable).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
