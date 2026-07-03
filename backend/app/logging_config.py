"""Structured (JSON) logging for request/response and error paths.

Modest scope on purpose: one JSON-lines formatter for the whole process,
applied at startup, plus the request-logging middleware in main.py. Not a
full observability stack — just enough for KVM4's `docker logs` to be
grep/jq-able instead of free-text.
"""
import json
import logging
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "message": record.getMessage()}
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # Our own request middleware logs a structured line per request already;
    # uvicorn's default access line would just duplicate it unstructured.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
