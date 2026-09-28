# WWF capture connector — remote MCP server for claude.ai/Cowork custom
# connectors. One tool (submit_capture) forwarding to the backend's
# /capture/import with a server-side token. See connector/server.py.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
# Unprivileged, like docengine (uid 1000). This is the only internet-facing
# Python service in the stack and it ran as root beside both databases
# (review 2026-09-27, DI-22). It needs no write access anywhere.
RUN useradd -u 1000 -m -r connector
USER connector
EXPOSE 8000
CMD ["python", "server.py"]
