# GrowFlow DocEngine — internal-only service container (no published ports).
FROM python:3.12-slim

WORKDIR /srv/docengine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -u 1000 -m docengine \
    && mkdir -p /data/docengine-out \
    && chown -R docengine:docengine /data/docengine-out

# --chown: the runner uploads the build context as root with whatever modes
# the source tarball carried, and the service runs unprivileged — without
# this the docengine user can't even read its own module files (import
# fails with EACCES at container start, not at build time).
COPY --chown=docengine:docengine app ./app
COPY --chown=docengine:docengine agents ./agents
COPY --chown=docengine:docengine engine ./engine

USER docengine

# Workflow/document state lives in Postgres, so any worker can serve any
# poll. Build OUTPUT is what used to be worker-unsafe (a shared filename
# per document code); builder.build now writes a per-build unique path and
# publishes it with os.replace, so 2 workers are safe for that too (H13).
#
# One worker anyway, deliberately (2026-09-07). With --workers N uvicorn runs
# a multiprocess supervisor that pings each spawned child and SIGKILLs any
# that fails to answer within 5 s (uvicorn.supervisors.multiprocess,
# Process.is_alive → ping(5)). On the 4-core production box a freshly
# spawned child cannot reach its pong thread inside that window when the
# host is busy, so after the 07:15 reboot the service crash-looped for
# 3.5 h — "Child process [N] died" every few seconds, no traceback (it is a
# kill, not an exception), serving nothing and burning a core, which kept
# the host busy enough to guarantee the next child missed the window too.
# Run in-process, with no supervisor, the same app boots in seconds. Two
# workers were never buying parallelism on an oversubscribed 4-core host.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
