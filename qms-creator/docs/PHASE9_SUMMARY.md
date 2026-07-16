# Phase 9: Monitoring & Logging Implementation Summary

## Overview

Phase 9 implements comprehensive production-grade monitoring, logging, error tracking, and metrics collection for the Cannabis EU GMP QMS Creator.

## Completed Tasks

### 9.1: Structured Logging Configuration ✅

**File:** `CONTENT_CREATOR_FRAMEWORK/logging_config.py` (11KB, 350+ lines)

Complete structured logging system with:

**Features:**
- **Multiple Formats**:
  - JSON (production) - for log aggregation and analysis
  - Colored (development) - for human readability
  - Detailed - with request context

- **Context Tracking**:
  - Request ID correlation
  - User ID tracking
  - Correlation ID for distributed tracing
  - Environment information
  - Custom context data

- **Log Management**:
  - Rotating file handler (configurable max size)
  - Backup file rotation (configurable count)
  - Console and file output
  - Per-module log level configuration

- **Classes Implemented**:
  - `ContextFilter` - Adds contextual information to all logs
  - `JSONFormatter` - Custom JSON formatter with extra fields
  - `ColoredFormatter` - Development-friendly colored output
  - `LoggerMixin` - Easy logging for any class

**Configuration via Environment Variables:**
```
LOG_FORMAT=json|colored|detailed
LOG_LEVEL=DEBUG|INFO|WARNING|ERROR|CRITICAL
LOG_FILE=logs/qms.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=10
ENVIRONMENT=development|production
```

**Example Usage:**
```python
from CONTENT_CREATOR_FRAMEWORK.logging_config import get_logger, ContextFilter

logger = get_logger(__name__)

# Set context for correlation
ContextFilter.set_context(
    request_id="req-12345",
    user_id="user-001",
    correlation_id="corr-xyz"
)

logger.info("Document generated successfully")
logger.error("Failed to generate document", exc_info=True)

ContextFilter.clear_context()
```

### 9.2: Sentry Integration for Error Tracking ✅

**File:** `CONTENT_CREATOR_FRAMEWORK/monitoring/sentry_integration.py` (7.7KB, 250+ lines)

Production-grade error tracking and monitoring:

**Features:**
- **Automatic Error Capture**:
  - Unhandled exceptions
  - HTTP errors
  - Database errors
  - External service failures

- **Performance Monitoring**:
  - Request tracing
  - Database query tracking
  - External service call monitoring
  - Transaction profiling

- **Context Management**:
  - User context tracking
  - Tag organization
  - Breadcrumb trails
  - Custom context data

- **Classes and Functions**:
  - `SentryConfig` - Configuration from environment
  - `init_sentry()` - Initialize Sentry SDK
  - `capture_exception()` - Manual exception capture
  - `capture_message()` - Manual message capture
  - `set_user_context()` - Track user information
  - `set_tag()` - Tag events for filtering
  - `set_context()` - Add custom context
  - `add_breadcrumb()` - Track event sequence
  - `start_transaction()` - Performance tracking
  - `SentryMiddleware` - FastAPI middleware for automatic tracking

**Configuration via Environment Variables:**
```
SENTRY_DSN=https://key@sentry.io/project
SENTRY_ENVIRONMENT=development|production
SENTRY_RELEASE=1.0.0
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1
SENTRY_SERVER_NAME=optional
```

**Example Usage:**
```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.sentry_integration import (
    init_sentry,
    capture_exception,
    set_user_context,
    set_tag,
    add_breadcrumb,
)

# Initialize
init_sentry()

# Track user
set_user_context("user-001", email="user@example.com")

# Add context
set_tag("document_type", "SOP")

# Track event sequence
add_breadcrumb("Started document generation", category="document")

# Capture error
try:
    generate_document()
except Exception as e:
    capture_exception(e)
```

### 9.3: Prometheus Metrics Collection ✅

**File:** `CONTENT_CREATOR_FRAMEWORK/monitoring/metrics.py` (9.7KB, 350+ lines)

Comprehensive metrics for performance monitoring:

**Custom Metrics Implemented:**

1. **Document Generation**:
   - `documents_generated_total` - Total documents generated (by status, type)
   - `document_generation_duration_seconds` - Generation time distribution

2. **Questionnaire**:
   - `questionnaire_submissions_total` - Total submissions (by status)

3. **Document Management**:
   - `document_uploads_total` - Total uploads (by file type, status)
   - `active_documents_count` - Current active document count

4. **API Performance**:
   - `api_request_duration_seconds` - Request duration (by method, endpoint)
   - `api_errors_total` - Total API errors (by endpoint, error type)
   - `rate_limit_exceeded_total` - Rate limit violations (by endpoint)
   - `authentication_failures_total` - Auth failures (by reason)

5. **Database Performance**:
   - `database_query_duration_seconds` - Query time (by operation, table)
   - `database_connections_active` - Active connection count

6. **External Services**:
   - `external_service_calls_total` - Service calls (by service, status)
   - `external_service_duration_seconds` - Service call duration

7. **Caching** (if implemented):
   - `cache_hits_total` - Cache hits (by type)
   - `cache_misses_total` - Cache misses (by type)

8. **Business Events**:
   - `business_events_total` - Custom business events (by type)

**Context Managers for Easy Metric Recording:**

```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.metrics import (
    DatabaseQueryContext,
    ExternalServiceContext,
    DocumentGenerationContext,
)

# Database queries
with DatabaseQueryContext('SELECT', 'documents') as ctx:
    docs = db.query(Document).all()

# External service calls
with ExternalServiceContext('openai') as ctx:
    response = openai_client.complete(prompt="...")
    ctx.mark_success()

# Document generation
with DocumentGenerationContext('SOP') as ctx:
    generate_document()
    ctx.mark_success()
```

**Manual Metric Recording:**

```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.metrics import (
    record_document_generated,
    record_questionnaire_submission,
    record_api_error,
)

record_document_generated('SOP', success=True, duration_seconds=5.2)
record_questionnaire_submission(success=True)
record_api_error('/documents', 'ValueError')
```

**Prometheus Endpoint:**
```bash
curl http://localhost:8000/metrics
```

### 9.4: Enhanced Health Checks ✅

**File:** `CONTENT_CREATOR_FRAMEWORK/monitoring/health_checks.py` (14KB, 400+ lines)

Comprehensive system health monitoring:

**Components Checked:**

1. **Application**:
   - Process running
   - Startup complete

2. **Database**:
   - Connection pool status
   - Query latency
   - Pool size and checked-out connections

3. **File System**:
   - Path accessibility
   - Write permissions
   - Directory creation

4. **Memory**:
   - Usage percentage
   - Available RAM
   - CPU usage

5. **Disk Space**:
   - Total/used/free space
   - Usage percentage

6. **External Services**:
   - Ollama availability
   - OpenAI configured
   - Anthropic configured

**Health Status Levels:**
- `healthy` - All checks passed
- `degraded` - Some components have issues
- `unhealthy` - Critical component failed

**Classes Implemented:**

- `HealthStatus` - Enum for status values
- `ComponentHealth` - Single component status
- `HealthChecker` - Orchestrates all health checks

**Endpoints:**

```bash
# Basic health check
curl http://localhost:8000/health

# Comprehensive health check
curl http://localhost:8000/api/health
```

**Response Format:**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-23T10:30:45.123Z",
  "components": [
    {
      "component": "application",
      "status": "healthy",
      "message": "Application is running",
      "details": {"pid": 12345}
    },
    {
      "component": "database",
      "status": "healthy",
      "message": "Database connection successful",
      "details": {
        "type": "PostgreSQL",
        "pool_size": 20,
        "checked_out": 3
      }
    }
  ],
  "summary": {
    "total": 6,
    "healthy": 6,
    "degraded": 0,
    "unhealthy": 0
  }
}
```

**Usage:**

```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.health_checks import check_health

health = await check_health(db_session=db, ollama_url=ollama_url)
print(health["status"])  # "healthy" or "degraded"
```

### 9.5: Comprehensive Monitoring Documentation ✅

**File:** `docs/MONITORING.md` (15KB, 400+ lines)

Complete guide covering:

**Sections:**
1. Structured Logging Configuration
   - Environment variables
   - Log format examples
   - Using logging in code
   - Log file management

2. Sentry Integration
   - Setup instructions
   - Error tracking examples
   - Breadcrumb trails
   - Monitoring dashboard

3. Prometheus Metrics
   - Metrics collection setup
   - Custom metrics usage
   - Prometheus installation
   - Grafana integration

4. Health Checks
   - Basic and enhanced endpoints
   - Component status indicators
   - Response format examples

5. Distributed Tracing
   - Request ID correlation
   - Trace request examples

6. Alerting
   - Alert rules configuration
   - Notification channels

7. Best Practices
   - Logging best practices
   - Metrics collection tips
   - Error tracking guidelines

8. Troubleshooting
   - High memory usage
   - Slow queries
   - High error rates
   - Service failures

## Supporting Files

**Package Initialization:**
- `CONTENT_CREATOR_FRAMEWORK/monitoring/__init__.py` - Exports all monitoring functions

**Dependencies Added to requirements.txt:**
- `sentry-sdk==1.40.1` - Error tracking
- `prometheus-fastapi-instrumentator==6.1.0` - Prometheus metrics
- `python-json-logger==2.0.7` - JSON structured logging
- `psutil` (already available) - System metrics

## Integration Points

### Application Initialization

```python
from fastapi import FastAPI
from CONTENT_CREATOR_FRAMEWORK.logging_config import setup_logging
from CONTENT_CREATOR_FRAMEWORK.monitoring.sentry_integration import init_sentry
from CONTENT_CREATOR_FRAMEWORK.monitoring.metrics import init_prometheus

# Initialize logging
setup_logging()

# Initialize Sentry
init_sentry()

# Initialize Prometheus
app = FastAPI()
init_prometheus(app)
```

### Middleware Setup

```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.sentry_integration import SentryMiddleware
from CONTENT_CREATOR_FRAMEWORK.logging_config import ContextFilter
from fastapi import Request
import uuid

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    correlation_id = request.headers.get("X-Correlation-ID", request_id)
    
    ContextFilter.set_context(
        request_id=request_id,
        correlation_id=correlation_id,
        user_id=request.query_params.get("user_id", "anonymous")
    )
    
    response = await call_next(request)
    
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Correlation-ID"] = correlation_id
    
    ContextFilter.clear_context()
    
    return response
```

### Health Check Endpoint

```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.health_checks import check_health

@app.get("/api/health")
async def health_check(db: Session = Depends(get_db_session)):
    return await check_health(db_session=db)
```

## Metrics Summary

| Component | Metrics | Count |
|-----------|---------|-------|
| Document Generation | 2 | 2 |
| Questionnaire | 1 | 1 |
| Document Management | 2 | 2 |
| API Performance | 4 | 4 |
| Database | 2 | 2 |
| External Services | 2 | 2 |
| Business Events | 1 | 1 |
| **TOTAL** | | **14** |

## Files Summary

| File | Size | Lines | Purpose |
|------|------|-------|---------|
| `logging_config.py` | 11KB | 350+ | Structured logging |
| `sentry_integration.py` | 7.7KB | 250+ | Error tracking |
| `metrics.py` | 9.7KB | 350+ | Prometheus metrics |
| `health_checks.py` | 14KB | 400+ | Health monitoring |
| `monitoring/__init__.py` | 1KB | 40 | Package exports |
| `MONITORING.md` | 15KB | 400+ | Documentation |
| **TOTAL** | **58.4KB** | **1,790+** | |

## Environment Configuration

```bash
# .env.production example
LOG_FORMAT=json
LOG_LEVEL=INFO
LOG_FILE=/var/log/qms/qms.log
LOG_MAX_BYTES=104857600
LOG_BACKUP_COUNT=20

SENTRY_DSN=https://key@sentry.io/project
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1

ENVIRONMENT=production
```

## Benefits

✅ **Comprehensive Logging**
- Structured JSON logs for production
- Context correlation across requests
- Easy log aggregation and analysis

✅ **Real-time Error Tracking**
- Automatic exception capture
- Performance monitoring
- User impact analysis
- Breadcrumb trails for debugging

✅ **Performance Metrics**
- Custom business metrics
- Database performance tracking
- External service monitoring
- API endpoint metrics

✅ **System Health Monitoring**
- Multi-component health checks
- Resource utilization tracking
- Service dependency monitoring
- Alerting capability

✅ **Production Ready**
- Distributed tracing support
- Alert integration ready
- Grafana dashboard compatible
- Slack/PagerDuty integration ready

## Testing

### Manual Testing

```bash
# Test logging
python -c "
from CONTENT_CREATOR_FRAMEWORK.logging_config import get_logger
logger = get_logger(__name__)
logger.info('Test message')
logger.warning('Test warning')
logger.error('Test error')
"

# Test Sentry (if configured)
curl -X POST http://localhost:8000/test-sentry

# Test metrics endpoint
curl http://localhost:8000/metrics | head -20

# Test health check
curl http://localhost:8000/api/health | jq '.'
```

## Next Steps

1. **Deploy with Monitoring**:
   - Set up Sentry account
   - Install Prometheus + Grafana
   - Configure alerts

2. **Create Dashboards**:
   - Document generation metrics
   - API performance dashboard
   - System health dashboard

3. **Set Up Alerts**:
   - High error rates
   - Slow queries
   - Service failures
   - Resource exhaustion

4. **Integrate with Slack/PagerDuty**:
   - Real-time notifications
   - On-call integration
   - Incident tracking

## References

- [Sentry Documentation](https://docs.sentry.io/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Python Logging](https://docs.python.org/3/library/logging.html)
- [FastAPI Monitoring](https://fastapi.tiangolo.com/advanced/monitoring/)
