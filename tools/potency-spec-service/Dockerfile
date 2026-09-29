# Potency Spec Service — single-container FastAPI + SQLite.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DB_PATH=/data/specs.db \
    STATIC_DIR=web

WORKDIR /app

# Non-root runtime user.
RUN groupadd --system app && useradd --system --gid app --home-dir /app app

# Install deps first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App code + static SPA + the (re-)seed helper.
COPY app ./app
COPY web ./web
COPY seed.py ./

# The SQLite DB lives on a mounted volume at /data (declared below). Create it
# and hand /data + /app to the non-root user so the app can write the DB file.
RUN mkdir -p /data && chown -R app:app /data /app
VOLUME ["/data"]

USER app
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
