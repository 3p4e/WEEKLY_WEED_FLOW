"""
Prometheus metrics collection for Cannabis EU GMP QMS Creator.

Provides metrics for request tracking, document generation, database operations,
and application health.
"""

import logging
from datetime import datetime
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram, Summary
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import DEFAULT_METRICS

logger = logging.getLogger(__name__)


# Custom metrics
DOCUMENTS_GENERATED = Counter(
    "documents_generated_total",
    "Total number of documents generated",
    ["status", "document_type"],
)

DOCUMENT_GENERATION_TIME = Histogram(
    "document_generation_duration_seconds",
    "Time spent generating documents",
    ["document_type"],
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0),
)

QUESTIONNAIRE_SUBMISSIONS = Counter(
    "questionnaire_submissions_total",
    "Total number of questionnaire submissions",
    ["status"],
)

DOCUMENT_UPLOADS = Counter(
    "document_uploads_total",
    "Total number of documents uploaded",
    ["file_type", "status"],
)

API_ERRORS = Counter(
    "api_errors_total", "Total number of API errors", ["endpoint", "error_type"]
)

ACTIVE_DOCUMENTS = Gauge("active_documents_count", "Current number of active documents")

DATABASE_QUERY_TIME = Histogram(
    "database_query_duration_seconds",
    "Time spent in database queries",
    ["operation", "table"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1),
)

DATABASE_CONNECTIONS = Gauge(
    "database_connections_active", "Number of active database connections"
)

CACHE_HITS = Counter("cache_hits_total", "Total number of cache hits", ["cache_type"])

CACHE_MISSES = Counter(
    "cache_misses_total", "Total number of cache misses", ["cache_type"]
)

API_REQUEST_DURATION = Summary(
    "api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
)

EXTERNAL_SERVICE_CALLS = Counter(
    "external_service_calls_total",
    "Total calls to external services",
    ["service", "status"],
)

EXTERNAL_SERVICE_DURATION = Histogram(
    "external_service_duration_seconds",
    "Duration of external service calls",
    ["service"],
    buckets=(1.0, 2.5, 5.0, 10.0, 30.0),
)

RATE_LIMIT_EXCEEDED = Counter(
    "rate_limit_exceeded_total", "Total times rate limit was exceeded", ["endpoint"]
)

AUTHENTICATION_FAILURES = Counter(
    "authentication_failures_total", "Total authentication failures", ["reason"]
)

BUSINESS_EVENTS = Counter(
    "business_events_total", "Total business events", ["event_type"]
)


def init_prometheus(app) -> None:
    """
    Initialize Prometheus metrics collection.

    Args:
        app: FastAPI application instance
    """
    logger.info("Initializing Prometheus metrics")

    Instrumentator().add(DEFAULT_METRICS).instrument(app).expose(app)

    logger.info("Prometheus metrics initialized")


def record_document_generated(
    doc_type: str, success: bool, duration_seconds: float
) -> None:
    """
    Record document generation event.

    Args:
        doc_type: Type of document generated
        success: Whether generation was successful
        duration_seconds: Time taken to generate
    """
    status = "success" if success else "failure"
    DOCUMENTS_GENERATED.labels(status=status, document_type=doc_type).inc()
    DOCUMENT_GENERATION_TIME.labels(document_type=doc_type).observe(duration_seconds)


def record_questionnaire_submission(success: bool) -> None:
    """
    Record questionnaire submission.

    Args:
        success: Whether submission was successful
    """
    status = "success" if success else "failure"
    QUESTIONNAIRE_SUBMISSIONS.labels(status=status).inc()


def record_document_upload(file_type: str, success: bool) -> None:
    """
    Record document upload.

    Args:
        file_type: Type of file uploaded
        success: Whether upload was successful
    """
    status = "success" if success else "failure"
    DOCUMENT_UPLOADS.labels(file_type=file_type, status=status).inc()


def record_api_error(endpoint: str, error_type: str) -> None:
    """
    Record API error.

    Args:
        endpoint: API endpoint that had error
        error_type: Type of error
    """
    API_ERRORS.labels(endpoint=endpoint, error_type=error_type).inc()


def update_active_documents(count: int) -> None:
    """
    Update active documents count.

    Args:
        count: Current number of active documents
    """
    ACTIVE_DOCUMENTS.set(count)


def record_database_query(operation: str, table: str, duration_seconds: float) -> None:
    """
    Record database query.

    Args:
        operation: Database operation (SELECT, INSERT, UPDATE, DELETE)
        table: Table name
        duration_seconds: Query duration
    """
    DATABASE_QUERY_TIME.labels(operation=operation, table=table).observe(
        duration_seconds
    )


def update_database_connections(count: int) -> None:
    """
    Update active database connections count.

    Args:
        count: Current number of active connections
    """
    DATABASE_CONNECTIONS.set(count)


def record_cache_hit(cache_type: str) -> None:
    """
    Record cache hit.

    Args:
        cache_type: Type of cache (redis, memory, etc.)
    """
    CACHE_HITS.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str) -> None:
    """
    Record cache miss.

    Args:
        cache_type: Type of cache
    """
    CACHE_MISSES.labels(cache_type=cache_type).inc()


def record_api_request(method: str, endpoint: str, duration_seconds: float) -> None:
    """
    Record API request.

    Args:
        method: HTTP method
        endpoint: API endpoint
        duration_seconds: Request duration
    """
    API_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(
        duration_seconds
    )


def record_external_service_call(
    service: str, success: bool, duration_seconds: float
) -> None:
    """
    Record external service call.

    Args:
        service: Service name (openai, anthropic, ollama, etc.)
        success: Whether call was successful
        duration_seconds: Call duration
    """
    status = "success" if success else "failure"
    EXTERNAL_SERVICE_CALLS.labels(service=service, status=status).inc()
    EXTERNAL_SERVICE_DURATION.labels(service=service).observe(duration_seconds)


def record_rate_limit_exceeded(endpoint: str) -> None:
    """
    Record rate limit exceeded event.

    Args:
        endpoint: API endpoint that exceeded rate limit
    """
    RATE_LIMIT_EXCEEDED.labels(endpoint=endpoint).inc()


def record_authentication_failure(reason: str) -> None:
    """
    Record authentication failure.

    Args:
        reason: Reason for failure (invalid_key, expired_token, missing_header, etc.)
    """
    AUTHENTICATION_FAILURES.labels(reason=reason).inc()


def record_business_event(event_type: str) -> None:
    """
    Record business event.

    Args:
        event_type: Type of business event (sop_created, document_published, etc.)
    """
    BUSINESS_EVENTS.labels(event_type=event_type).inc()


# Metrics context managers for convenience
class DatabaseQueryContext:
    """Context manager for recording database queries."""

    def __init__(self, operation: str, table: str):
        """Initialize context."""
        self.operation = operation
        self.table = table
        self.start_time = None

    def __enter__(self):
        """Start timing."""
        self.start_time = datetime.utcnow()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Record query duration."""
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds()
            record_database_query(self.operation, self.table, duration)


class ExternalServiceContext:
    """Context manager for recording external service calls."""

    def __init__(self, service: str):
        """Initialize context."""
        self.service = service
        self.start_time = None
        self.success = False

    def __enter__(self):
        """Start timing."""
        self.start_time = datetime.utcnow()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Record call duration."""
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds()
            record_external_service_call(self.service, self.success, duration)

    def mark_success(self):
        """Mark call as successful."""
        self.success = True


class DocumentGenerationContext:
    """Context manager for recording document generation."""

    def __init__(self, doc_type: str):
        """Initialize context."""
        self.doc_type = doc_type
        self.start_time = None
        self.success = False

    def __enter__(self):
        """Start timing."""
        self.start_time = datetime.utcnow()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Record generation duration."""
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds()
            record_document_generated(self.doc_type, self.success, duration)

    def mark_success(self):
        """Mark generation as successful."""
        self.success = True


# Usage examples in docstrings
"""
Example usage:

# Recording database queries
with DatabaseQueryContext('SELECT', 'documents') as ctx:
    db.query(Document).all()

# Recording external service calls
with ExternalServiceContext('openai') as ctx:
    response = openai_client.complete()
    ctx.mark_success()

# Recording document generation
with DocumentGenerationContext('SOP') as ctx:
    generate_document()
    ctx.mark_success()

# Recording other metrics
record_questionnaire_submission(success=True)
record_api_error('/documents', 'ValueError')
update_active_documents(77)
"""
