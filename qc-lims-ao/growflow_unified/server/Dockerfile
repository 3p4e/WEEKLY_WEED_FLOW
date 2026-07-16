# GrowFlow Unified API — FastAPI backend (applies SQL migrations, then uvicorn).
# Build context = growflow_unified/  (so the db/ migrations are available).
FROM python:3.12-slim
WORKDIR /app

# postgresql-client provides pg_isready (startup wait) + psql (migrations).
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY server/pyproject.toml ./
COPY server/planner_api ./planner_api
COPY db ./db
RUN pip install --no-cache-dir .

COPY server/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8765
ENTRYPOINT ["docker-entrypoint.sh"]
