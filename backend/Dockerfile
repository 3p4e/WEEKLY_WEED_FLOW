# WEEKLY_WEED_FLOW API — FastAPI (async, asyncpg) served by uvicorn.
# Built and run on KVM4 as `weekly_weed_flow-backend:latest`; the GrowFlow
# nginx frontend reverse-proxies /auth /departments /weeks /tasks /ai /audit
# /reports /health to it over the internal Docker network. Intentionally no
# HEALTHCHECK — Traefik (host network mode) won't route containers marked
# "unhealthy".
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
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
