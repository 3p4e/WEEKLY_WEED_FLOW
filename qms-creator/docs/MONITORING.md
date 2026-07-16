# Monitoring & Logging Guide

Comprehensive guide for monitoring, logging, error tracking, and metrics collection.

## Overview

The Cannabis EU GMP QMS Creator includes production-grade monitoring with:

- **Structured Logging**: JSON formatted logs with context tracking
- **Error Tracking**: Sentry integration for real-time error monitoring
- **Metrics Collection**: Prometheus for performance metrics
- **Health Checks**: Comprehensive system health monitoring
- **Distributed Tracing**: Request correlation across services

## Structured Logging

### Configuration

Logging is configured via environment variables:

```bash
# Log format: colored (development), json (production), or detailed
LOG_FORMAT=json

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Log file path
LOG_FILE=logs/qms.log

# Max log file size (bytes)
LOG_MAX_BYTES=10485760  # 10MB

# Number of backup log files to keep
LOG_BACKUP_COUNT=10

# Environment
ENVIRONMENT=production
```

### Log Output Formats

#### Development (Colored)
```
2024-01-23 10:30:45,123 - CONTENT_CREATOR_FRAMEWORK.main_api - INFO - [req-12345] - Documents loaded successfully
```

#### Production (JSON)
```json
{
  "timestamp": "2024-01-23T10:30:45.123Z",
  "level": "INFO",
  "name": "CONTENT_CREATOR_FRAMEWORK.main_api",
  "message": "Documents loaded successfully",
  "request_id": "req-12345",
  "user_id": "user-001",
  "correlation_id": "corr-xyz",
  "environment": "production"
}
```

### Using Logging in Code

```python
import logging
from CONTENT_CREATOR_FRAMEWORK.logging_config import get_logger, ContextFilter

logger = get_logger(__name__)

# Set request context for correlation
ContextFilter.set_context(
    request_id="req-12345",
    user_id="user-001",
    correlation_id="corr-xyz"
)

# Log with context
logger.info("Document generated successfully")
logger.warning("Document generation took longer than expected")
logger.error("Failed to generate document", exc_info=True)

# Clear context when done
ContextFilter.clear_context()
```

### Log File Management

```bash
# View live logs
tail -f logs/qms.log

# View JSON logs with jq (pretty print)
tail -f logs/qms.log | jq '.'

# Search for errors
grep '"level":"ERROR"' logs/qms.log | jq '.'

# Search by request ID
grep 'req-12345' logs/qms.log | jq '.'

# Count log levels
grep -o '"level":"[^"]*"' logs/qms.log | sort | uniq -c
```

## Sentry Integration

### Setup

1. **Create Sentry Account**: https://sentry.io/signup/

2. **Configure Environment**:
```bash
# .env.production
SENTRY_DSN=https://key@sentry.io/project
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=1.0.0
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1
```

3. **Initialize in Application**:
```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.sentry_integration import init_sentry

init_sentry()
```

### Error Tracking

#### Automatic Tracking
Sentry automatically captures:
- Unhandled exceptions
- HTTP errors (4xx, 5xx)
- Database errors
- External service failures

#### Manual Error Tracking
```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.sentry_integration import (
    capture_exception,
    capture_message,
    set_user_context,
    set_tag,
    add_breadcrumb,
)

# Capture exception with context
try:
    generate_document()
except Exception as e:
    set_user_context("user-001", email="user@example.com")
    set_tag("document_type", "SOP")
    add_breadcrumb("About to generate document")
    capture_exception(e)

# Capture message
capture_message("Document generation started", level="info")

# Clear context when done
from CONTENT_CREATOR_FRAMEWORK.monitoring.sentry_integration import clear_user_context
clear_user_context()
```

### Breadcrumbs

Breadcrumbs track the sequence of events leading to an error:

```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.sentry_integration import add_breadcrumb

# Add breadcrumbs for important events
add_breadcrumb(
    message="User submitted questionnaire",
    category="user_action",
    level="info",
    data={"submission_id": "sub-123"}
)

add_breadcrumb(
    message="Started document generation",
    category="document",
    level="info",
    data={"doc_type": "SOP", "facility": "Farm A"}
)

add_breadcrumb(
    message="OpenAI API call started",
    category="external_service",
    level="debug",
    data={"service": "openai", "model": "gpt-4"}
)
```

### Monitoring Sentry

1. **Go to Sentry Dashboard**: https://sentry.io/organizations/your-org/

2. **View Issues**:
   - Click Issues tab
   - See error frequency and affected users
   - Get stack traces and context

3. **Set up Alerts**:
   - Alert when error rate exceeds threshold
   - Alert on new error types
   - Custom alert rules

4. **Integrate with Slack**:
   - Settings → Integrations → Slack
   - Create notification rules
   - Get alerts in Slack channel

## Prometheus Metrics

### Metrics Collection

Application automatically collects metrics via `prometheus-fastapi-instrumentator`:

```bash
# View metrics
curl http://localhost:8000/metrics

# Custom metrics
curl http://localhost:8000/metrics | grep documents_generated
curl http://localhost:8000/metrics | grep document_generation_duration
curl http://localhost:8000/metrics | grep questionnaire_submissions
```

### Custom Metrics

#### Document Generation
```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.metrics import (
    DocumentGenerationContext,
    record_document_generated,
)

# Using context manager
with DocumentGenerationContext('SOP') as ctx:
    result = generate_sop()
    ctx.mark_success()

# Or manually
start_time = time.time()
try:
    generate_document()
    duration = time.time() - start_time
    record_document_generated('SOP', success=True, duration_seconds=duration)
except Exception as e:
    duration = time.time() - start_time
    record_document_generated('SOP', success=False, duration_seconds=duration)
```

#### Database Queries
```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.metrics import DatabaseQueryContext

with DatabaseQueryContext('SELECT', 'documents') as ctx:
    docs = db.query(Document).all()
```

#### External Service Calls
```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.metrics import ExternalServiceContext

with ExternalServiceContext('openai') as ctx:
    response = openai_client.complete(prompt="...")
    ctx.mark_success()
```

#### Questionnaire Submissions
```python
from CONTENT_CREATOR_FRAMEWORK.monitoring.metrics import record_questionnaire_submission

try:
    process_questionnaire(data)
    record_questionnaire_submission(success=True)
except Exception as e:
    record_questionnaire_submission(success=False)
```

### Prometheus Setup

1. **Install Prometheus**:
```bash
# Docker
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

# Or local installation
brew install prometheus  # macOS
sudo apt-get install prometheus  # Ubuntu
```

2. **Configure Prometheus** (`prometheus.yml`):
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'qms'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

3. **View Metrics Dashboard**: http://localhost:9090

### Grafana Integration

1. **Install Grafana**:
```bash
# Docker
docker run -d \
  --name grafana \
  -p 3000:3000 \
  grafana/grafana

# Local
brew install grafana  # macOS
sudo apt-get install grafana-server  # Ubuntu
```

2. **Add Prometheus Data Source**:
   - Open http://localhost:3000
   - Login (admin/admin)
   - Configuration → Data Sources
   - Add Prometheus: `http://localhost:9090`

3. **Create Dashboards**:
   - Import community dashboards
   - Create custom dashboards for your metrics
   - Set up alerts

### Key Metrics to Monitor

```
# Document Generation
rate(documents_generated_total[5m])           # Generation rate
histogram_quantile(0.95, document_generation_duration_seconds)  # 95th percentile

# Questionnaire Submissions
rate(questionnaire_submissions_total[5m])     # Submission rate
questionnaire_submissions_total{status="failure"} / questionnaire_submissions_total  # Failure rate

# Database Performance
histogram_quantile(0.95, database_query_duration_seconds)       # Slow queries
rate(database_query_duration_seconds_sum[5m]) / rate(database_query_duration_seconds_count[5m])  # Avg query time

# External Services
rate(external_service_calls_total[5m])        # Service call rate
rate(external_service_calls_total{status="failure"}[5m])  # Service failures

# API Errors
rate(api_errors_total[5m])                    # Error rate
api_errors_total{endpoint="/documents"}       # Errors by endpoint

# System Health
process_resident_memory_bytes                 # Memory usage
rate(process_cpu_seconds_total[5m])          # CPU usage
```

## Health Checks

### Basic Health Check

```bash
# Simple health check
curl http://localhost:8000/health

# Response
{
  "status": "healthy",
  "timestamp": "2024-01-23T10:30:45.123Z"
}
```

### Enhanced Health Check

```bash
# Comprehensive health check
curl http://localhost:8000/api/health

# Response
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
    },
    {
      "component": "file_system",
      "status": "healthy",
      "message": "File system check passed",
      "details": {
        "paths": {
          "data": {"exists": true, "writable": true},
          "output": {"exists": true, "writable": true}
        }
      }
    },
    {
      "component": "memory",
      "status": "healthy",
      "message": "Memory usage: 45%",
      "details": {
        "total_gb": 16.0,
        "used_gb": 7.2,
        "available_gb": 8.8,
        "percent": 45.0,
        "cpu_percent": 12.5
      }
    },
    {
      "component": "disk_space",
      "status": "healthy",
      "message": "Disk usage: 65%",
      "details": {
        "total_gb": 500.0,
        "used_gb": 325.0,
        "free_gb": 175.0,
        "percent": 65.0
      }
    },
    {
      "component": "external_services",
      "status": "healthy",
      "message": "External services check completed",
      "details": {
        "openai": {"status": "configured", "available": true},
        "ollama": {"status": "available", "status_code": 200}
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

### Health Check Indicators

- **Application**: Process running, startup complete
- **Database**: Connection pool, query latency
- **File System**: Path accessibility, write permissions
- **Memory**: Usage percentage, available RAM
- **Disk Space**: Storage usage, free space
- **External Services**: API availability, connectivity

## Distributed Tracing

### Request ID Correlation

```python
import uuid
from fastapi import Request
from CONTENT_CREATOR_FRAMEWORK.logging_config import ContextFilter

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

### Tracing Requests

```bash
# Make request with trace ID
curl -H "X-Request-ID: req-123" \
     -H "X-Correlation-ID: corr-xyz" \
     http://localhost:8000/documents

# All logs for this request will include the request_id
grep 'req-123' logs/qms.log | jq '.'
```

## Alerting

### Alert Rules

Set up alerts for critical events:

```yaml
# Prometheus alert rules (alerting.yml)
groups:
  - name: qms_alerts
    interval: 30s
    rules:
      - alert: HighDocumentGenerationFailureRate
        expr: rate(documents_generated_total{status="failure"}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High document generation failure rate"
          
      - alert: DatabaseConnectionPoolExhausted
        expr: database_connections_active > 18
        for: 2m
        annotations:
          summary: "Database connection pool nearly exhausted"
          
      - alert: HighErrorRate
        expr: rate(api_errors_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High API error rate"
          
      - alert: SlowDatabaseQueries
        expr: histogram_quantile(0.95, database_query_duration_seconds) > 1
        for: 5m
        annotations:
          summary: "Database queries are slow"
```

### Notification Channels

Configure alerts to notify:
- Email
- Slack
- PagerDuty
- Webhook

## Best Practices

### Logging

✅ **DO**:
- Log at appropriate levels (DEBUG, INFO, WARNING, ERROR)
- Include context (user_id, request_id, document_id)
- Log at entry and exit points
- Log errors with exception info
- Use structured logging (JSON in production)

❌ **DON'T**:
- Log sensitive data (passwords, API keys)
- Spam logs with excessive DEBUG statements
- Log the same information multiple times
- Use print() instead of logger

### Metrics

✅ **DO**:
- Track business metrics (documents generated, submissions)
- Track performance metrics (query time, generation time)
- Use appropriate histogram buckets
- Tag metrics with relevant dimensions

❌ **DON'T**:
- Create too many unique metric values (cardinality explosion)
- Change metric definitions frequently
- Forget to clean up old metrics

### Error Tracking

✅ **DO**:
- Capture context with errors
- Use breadcrumbs to track sequence
- Set user context for errors
- Use tags for categorization

❌ **DON'T**:
- Capture every exception as critical
- Report the same error multiple times
- Include sensitive data in error context

## Troubleshooting

### High Memory Usage
1. Check memory metric: `process_resident_memory_bytes`
2. Review logs for memory warnings
3. Check for memory leaks in connection pools
4. Reduce connection pool size if needed

### Slow Database Queries
1. Check `database_query_duration_seconds` metric
2. Review slow query logs
3. Check database indexes
4. Consider query optimization

### High Error Rate
1. Check `api_errors_total` metric
2. Review error logs and Sentry dashboard
3. Check external service status
4. Review rate limiting

### External Service Failures
1. Check `external_service_calls_total` metric
2. Check service availability
3. Review network connectivity
4. Check authentication (API keys)

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Sentry Documentation](https://docs.sentry.io/)
- [Python Logging](https://docs.python.org/3/library/logging.html)
- [FastAPI Monitoring](https://fastapi.tiangolo.com/)
