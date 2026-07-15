# Security & Hardening Guide

Comprehensive security guide for the Cannabis EU GMP QMS Creator application.

## Overview

The application implements multiple layers of security:

1. **Input Validation** - Prevent malformed or malicious data
2. **Error Handling** - Prevent information disclosure
3. **Request Limits** - Protect against resource exhaustion
4. **Security Headers** - Protect against common web attacks
5. **Authentication** - Protect sensitive endpoints
6. **Authorization** - Enforce access control
7. **Rate Limiting** - Prevent abuse and DoS

## Input Validation & Sanitization

### Built-in Validators

The `InputValidator` class provides validation for common patterns:

```python
from CONTENT_CREATOR_FRAMEWORK.validators import InputValidator

# Email validation
if InputValidator.validate_email(user_email):
    process_email(user_email)

# File name validation (prevents path traversal)
if InputValidator.validate_file_name(filename):
    save_file(filename)

# File path validation
if InputValidator.validate_file_path(user_path, allowed_dir="/uploads"):
    process_file(user_path)

# URL validation (prevents SSRF)
if InputValidator.validate_url(user_url):
    fetch_url(user_url)

# Identifier validation
if InputValidator.validate_identifier(doc_id):
    get_document(doc_id)
```

**Available Validators:**
- `validate_email()` - Email format
- `validate_slug()` - URL-safe slug
- `validate_identifier()` - Alphanumeric identifier
- `validate_file_name()` - Safe file name
- `validate_file_path()` - Safe file path (prevents traversal)
- `validate_url()` - URL with SSRF prevention
- `validate_uuid()` - UUID format
- `validate_length()` - String length bounds
- `validate_enum()` - Allowed values

### Input Sanitization

The `InputSanitizer` class removes dangerous characters:

```python
from CONTENT_CREATOR_FRAMEWORK.validators import InputSanitizer

# Sanitize general string input
safe_title = InputSanitizer.sanitize_string(user_input, max_length=500)

# Sanitize identifier
safe_id = InputSanitizer.sanitize_identifier(user_id)

# Sanitize file name (removes path components)
safe_filename = InputSanitizer.sanitize_file_name(uploaded_filename)

# Sanitize file path (prevents traversal)
safe_path = InputSanitizer.sanitize_path(user_provided_path)
```

### Pydantic Models with Validation

Use provided Pydantic models for automatic validation:

```python
from CONTENT_CREATOR_FRAMEWORK.validators import (
    DocumentRequest,
    FileUploadRequest,
    QuestionnaireRequest
)

# Automatically validates and sanitizes
@app.post("/documents")
async def create_document(doc: DocumentRequest):
    # doc.title, doc.code, etc. are already validated
    return save_document(doc)

# File upload with validation
@app.post("/upload")
async def upload_file(file: FileUploadRequest):
    # filename is sanitized, file_type is validated
    return process_upload(file)

# Questionnaire with validation
@app.post("/questionnaire")
async def submit_questionnaire(questionnaire: QuestionnaireRequest):
    # All fields validated and sanitized
    return process_questionnaire(questionnaire)
```

## Error Handling

### Custom Exception Classes

Use custom exceptions that don't expose sensitive information:

```python
from CONTENT_CREATOR_FRAMEWORK.error_handlers import (
    ValidationException,
    ResourceNotFoundException,
    UnauthorizedException,
    ExternalServiceException,
    RateLimitException,
)

# Validation error
if not valid_input:
    raise ValidationException("Invalid email format", field="email")

# Not found
if not document:
    raise ResourceNotFoundException("Document", doc_id)

# Unauthorized
if not api_key:
    raise UnauthorizedException("Missing API key")

# External service failure
try:
    response = call_external_service()
except Exception as e:
    raise ExternalServiceException("OpenAI", str(e))

# Rate limit
if requests_exceeded:
    raise RateLimitException(retry_after=60)
```

### Error Response Format

All errors return consistent format:

```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "Human-readable message",
  "details": {
    "additional": "information"
  },
  "timestamp": "2024-01-23T10:30:45.123Z",
  "request_id": "req-12345"
}
```

**Error Codes:**
- `VALIDATION_ERROR` - Input validation failed
- `RESOURCE_NOT_FOUND` - Resource doesn't exist
- `UNAUTHORIZED` - Missing/invalid authentication
- `FORBIDDEN` - Insufficient permissions
- `CONFLICT` - Resource conflict
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `EXTERNAL_SERVICE_ERROR` - External service failure
- `INTERNAL_ERROR` - Server error (no details exposed)

## Security Middleware

### Security Headers

Automatically added to all responses:

```
X-Content-Type-Options: nosniff           # Prevent MIME type sniffing
X-Frame-Options: DENY                     # Prevent clickjacking
X-XSS-Protection: 1; mode=block          # XSS protection
Strict-Transport-Security: ...             # HTTPS enforcement
Content-Security-Policy: ...               # Prevent XSS, clickjacking
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=()
```

### Request Size Limits

Enforce per-endpoint request size limits:

```
/documents:    50MB (file uploads)
/generate:     1MB (SOP generation)
/api/files:    100MB (large files)
others:        10MB (default)
```

**Configuration:**

```python
from CONTENT_CREATOR_FRAMEWORK.security_middleware import RequestLimitMiddleware

# Customize limits
ENDPOINT_LIMITS = {
    "/documents": {"max_size": 52428800, "timeout": 300},
    "/custom": {"max_size": 5242880, "timeout": 60},
}
```

### Request Timeout

Prevent slow-client attacks:

```
/documents:    300 seconds (5 minutes)
/generate:     600 seconds (10 minutes)
/api/files:    600 seconds (10 minutes)
others:        300 seconds (5 minutes)
```

### IP Whitelist (Optional)

If configured, restrict access to allowed IPs:

```bash
# .env
IP_WHITELIST=192.168.1.1,192.168.1.2,10.0.0.0/8
```

```python
from CONTENT_CREATOR_FRAMEWORK.security_middleware import IPWhitelistMiddleware

# Enable whitelist
app.add_middleware(IPWhitelistMiddleware, whitelist=whitelist)
```

### Injection Prevention

Detect and block injection attempts:

- SQL injection patterns
- NoSQL injection patterns ($where, $or, etc.)
- Command injection attempts

```bash
# Dangerous request will be blocked
curl "http://localhost:8000/documents?id='; DROP TABLE--"
# Returns 400 Bad Request
```

## Authentication & Authorization

### API Key Authentication

All sensitive endpoints require API key:

```bash
# Provide API key
curl -H "X-API-Key: your-key" http://localhost:8000/generate

# Missing key returns 401
curl http://localhost:8000/generate
# {"status": "error", "code": "UNAUTHORIZED", ...}
```

**Protected Endpoints:**
- `POST /documents` - Upload documents
- `POST /generate` - Generate SOPs
- `POST /submit-questionnaire` - Submit questionnaire
- Custom endpoints with `dependencies=[Depends(verify_api_key)]`

### API Key Management

```bash
# .env
API_KEY=your-secure-api-key-change-this

# Production
API_KEY=$(openssl rand -hex 32)  # Generate strong key
```

**Best Practices:**
- Change default key immediately
- Use strong random keys (32+ characters)
- Rotate keys regularly
- Never commit keys to version control
- Use environment variables or secrets manager

## Rate Limiting

### FastAPI Rate Limiting

Configured per endpoint:

```
/generate:              5 requests/minute
/submit-questionnaire:  5 requests/minute
/documents POST:        5 requests/minute
/analyze:               20 requests/minute
others:                 100 requests/minute
```

**Configuration:**

```bash
# .env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_GLOBAL=100/minute
RATE_LIMIT_GENERATE=5/minute
```

### Response Headers

Rate limit information in response:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1234567890
```

### Exceeding Rate Limit

```json
{
  "status": "error",
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Please try again later.",
  "details": {"retry_after": 60}
}
```

## File Upload Security

### File Validation

```python
from CONTENT_CREATOR_FRAMEWORK.validators import FileUploadRequest

@app.post("/upload")
async def upload_file(file: FileUploadRequest):
    # Filename is sanitized (removes path components)
    # File type is validated (pdf, docx, xlsx, pptx only)
    # Size is limited (checked by middleware)
    return process_file(file)
```

**Security Measures:**
- Validate file names (prevents path traversal)
- Limit file types (whitelist allowed types)
- Limit file size (per-endpoint configuration)
- Store in secure location (outside web root)
- Don't execute uploaded files

### Safe File Handling

```python
from CONTENT_CREATOR_FRAMEWORK.validators import InputValidator, InputSanitizer

# Validate path is safe
file_path = user_input["path"]
if not InputValidator.validate_file_path(file_path, allowed_dir="/uploads"):
    raise ValidationException("Invalid file path")

# Sanitize filename
filename = user_input["filename"]
safe_filename = InputSanitizer.sanitize_file_name(filename)

# Use safe path
final_path = "/uploads/" + safe_filename
```

## Database Security

### SQL Injection Prevention

Using SQLAlchemy ORM prevents SQL injection:

```python
# Safe - parameterized query
doc = db.query(Document).filter(Document.id == doc_id).first()

# NOT SAFE - string concatenation (don't do this)
# doc = db.execute(f"SELECT * FROM documents WHERE id = '{doc_id}'")
```

### Connection Security

Configured in database URL:

```bash
# .env
# PostgreSQL with SSL
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
```

## Authentication Headers

Always use secure headers for sensitive operations:

```python
@app.post("/sensitive-operation")
async def sensitive_op(request: Request):
    # Check authentication
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise UnauthorizedException()
    
    # Verify key
    if not verify_api_key(api_key):
        raise UnauthorizedException()
    
    # Process request
    return process()
```

## HTTPS/TLS Configuration

### Enable HTTPS

```bash
# Production .env
SSL_CERT_PATH=/etc/ssl/certs/qms.crt
SSL_KEY_PATH=/etc/ssl/private/qms.key

# Using Nginx (recommended)
# Configure SSL in nginx.conf
```

### HTTPS Redirect

```python
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Redirect HTTP to HTTPS in production
if os.getenv("ENVIRONMENT") == "production":
    app.add_middleware(HTTPSRedirectMiddleware)
```

## CORS Configuration

Restrict cross-origin requests:

```bash
# .env
CORS_ORIGINS=https://qms.example.com,https://admin.qms.example.com
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_ALLOW_HEADERS=Content-Type,Authorization,X-API-Key
```

**Never use:**
```
CORS_ORIGINS=*  # Opens to all origins
```

## Sensitive Data Handling

### Logging Best Practices

Never log sensitive data:

```python
# Good - log safe information
logger.info("User login attempt", extra={"user_id": user_id})

# Bad - logs password
# logger.info(f"User login: {username}:{password}")

# Bad - logs API key
# logger.info(f"API key: {api_key}")
```

### Error Message Guidelines

```python
# Good - generic message
except Exception as e:
    logger.error("Database error occurred")
    return {"status": "error", "message": "An error occurred"}

# Bad - exposes details
except Exception as e:
    logger.error(str(e))
    return {"status": "error", "message": str(e)}
```

### Environment Variables

Never hardcode secrets:

```python
# Good - use environment variables
api_key = os.getenv("API_KEY")
db_password = os.getenv("DATABASE_PASSWORD")

# Bad - hardcoded
api_key = "abc123def456"
db_password = "mypassword123"
```

## Security Headers Details

### Content-Security-Policy

Prevents XSS attacks:

```
default-src 'self'                    # Only same-origin by default
script-src 'self'                     # Only same-origin scripts
style-src 'self' 'unsafe-inline'     # Styles (inline needed for some UIs)
img-src 'self' data: https:           # Images from self, data URIs, HTTPS
font-src 'self'                       # Fonts from self only
```

### HSTS (HTTP Strict Transport Security)

Forces HTTPS in production:

```
max-age=31536000              # 1 year
includeSubDomains             # Apply to subdomains
preload                       # Allow browser preload
```

## Security Checklist

### Before Production

- [ ] Change default API key
- [ ] Enable HTTPS/TLS
- [ ] Configure CORS origins (not wildcard)
- [ ] Set strong database password
- [ ] Enable rate limiting
- [ ] Configure logging levels
- [ ] Set up error tracking (Sentry)
- [ ] Review error messages (no leaks)
- [ ] Test file upload validation
- [ ] Test input sanitization
- [ ] Configure backups
- [ ] Set up monitoring/alerts
- [ ] Review database indexes
- [ ] Enable SQL query logging
- [ ] Test rate limiting

### Ongoing Security

- [ ] Regular dependency updates
- [ ] Monthly security audits
- [ ] Rotate API keys quarterly
- [ ] Review access logs weekly
- [ ] Monitor error rates
- [ ] Check for failed authentication attempts
- [ ] Review application logs
- [ ] Update security headers as needed
- [ ] Patch critical vulnerabilities immediately
- [ ] Conduct security training for team

## Common Vulnerabilities Prevention

### OWASP Top 10

| Vulnerability | Prevention |
|---|---|
| **A1: Injection** | Input validation, parameterized queries, ORM usage |
| **A2: Broken Authentication** | API key validation, secure storage, HTTPS |
| **A3: Sensitive Data Exposure** | HTTPS/TLS, encryption at rest, secure headers |
| **A4: XML External Entities (XXE)** | Disable XML external entities in parsers |
| **A5: Broken Access Control** | Authentication checks, API key validation |
| **A6: Security Misconfiguration** | Security headers, CORS limits, no debug mode |
| **A7: XSS** | Input validation, output encoding, CSP |
| **A8: Insecure Deserialization** | Avoid unsafe deserialization, validate data |
| **A9: Using Components with Known Vulnerabilities** | Regular updates, dependency scanning |
| **A10: Insufficient Logging & Monitoring** | Comprehensive logging, error tracking, alerts |

## Troubleshooting

### Request Rejected (400 Bad Request)

Check if request contains:
- Path traversal attempts (../)
- SQL injection patterns
- NoSQL injection patterns
- Oversized content

### Rate Limited (429 Too Many Requests)

Wait before retrying. Check headers:
```
X-RateLimit-Remaining: 0
Retry-After: 60
```

### Authentication Failed (401 Unauthorized)

- Verify API key in header
- Check key hasn't expired
- Verify header name is exactly "X-API-Key"

### File Upload Blocked

- Check file size (view Content-Length header)
- Validate file name (no path components)
- Check file type (must be whitelisted)

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Pydantic Validation](https://docs.pydantic.dev/latest/concepts/validators/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CWE - Common Weakness Enumeration](https://cwe.mitre.org/)
- [SANS Top 25](https://www.sans.org/top25-software-errors/)
