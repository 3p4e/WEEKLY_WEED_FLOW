# WWF capture connector — remote MCP server for claude.ai/Cowork custom
# connectors. One tool (submit_capture) forwarding to the backend's
# /capture/import with a server-side token. See connector/server.py.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
EXPOSE 8000
CMD ["python", "server.py"]
