# FastAPI backend image for the QC LIMS API.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for asyncpg / bcrypt builds.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Default command is overridden by docker-compose (seed + uvicorn), but this
# keeps the image runnable on its own.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
