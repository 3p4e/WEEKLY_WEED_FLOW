# GrowFlow DocEngine — internal-only service container (no published ports).
FROM python:3.12-slim

WORKDIR /srv/docengine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY agents ./agents
COPY engine ./engine

RUN useradd -u 1000 -m docengine \
    && mkdir -p /data/docengine-out \
    && chown -R docengine:docengine /data/docengine-out
USER docengine

# state lives in Postgres; 2 workers are safe
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
