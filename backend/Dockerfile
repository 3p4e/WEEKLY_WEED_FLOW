# WEEKLY_WEED_FLOW API — FastAPI (async, asyncpg) served by uvicorn.
# Built and run on KVM4 as `weekly_weed_flow-backend:latest`; the GrowFlow
# nginx frontend reverse-proxies /auth /departments /weeks /tasks /ai /audit
# to it over the internal Docker network. Intentionally no HEALTHCHECK —
# Traefik (host network mode) won't route containers marked "unhealthy".
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
