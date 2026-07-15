# Cannabis EU GMP QMS Creator - API Documentation

Complete REST API reference for the Cannabis EU GMP QMS Creator.

## Base URL

```
Development:  http://localhost:8000
Production:   https://api.qms.example.com
```

## Authentication

All protected endpoints require authentication via the `X-API-Key` header.

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/documents
```

### Protected Endpoints

The following endpoints require authentication:
- `POST /documents` - Upload documents
- `POST /generate` - Generate SOPs
- `POST /submit-questionnaire` - Submit questionnaire responses

## Rate Limiting

API requests are rate limited per endpoint:

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/generate` | 5 | per minute |
| `/submit-questionnaire` | 5 | per minute |
| `/documents` (POST) | 5 | per minute |
| `/analyze` | 20 | per minute |
| Others | 100 | per minute |

Rate limit information is returned in response headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1234567890
```

When rate limited, the API returns a `429 Too Many Requests` status.

## Data Types

### Common Responses

All successful responses follow this structure:

```json
{
  "status": "success",
  "data": {},
  "timestamp": "2024-01-23T10:30:00Z"
}
```

Error responses:

```json
{
  "status": "error",
  "message": "Human-readable error message",
  "code": "ERROR_CODE",
  "timestamp": "2024-01-23T10:30:00Z"
}
```

## API Endpoints

### System Endpoints

#### Health Check

```http
GET /health
```

Returns the current health status of the application.

**Response (200 OK)**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-23T10:30:00Z",
  "version": "1.0.0"
}
```

#### API Health

```http
GET /api/health
```

Returns health status including database connectivity.

**Response (200 OK)**
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-01-23T10:30:00Z"
}
```

### Document Management Endpoints

#### List Documents

```http
GET /documents
```

Retrieves all available documents.

**Query Parameters**
- `skip` (integer) - Number of documents to skip (default: 0)
- `limit` (integer) - Maximum documents to return (default: 100)
- `department` (string) - Filter by department

**Response (200 OK)**
```json
{
  "status": "success",
  "data": {
    "documents": [
      {
        "id": "QMS-DOC-001",
        "code": "QMS-DOC",
        "title": "Quality Management System Documentation",
        "version": "1.0",
        "department": "Quality Assurance",
        "pdfPath": "/documents/QMS-DOC-001.pdf",
        "docxPath": "/documents/QMS-DOC-001.docx"
      }
    ],
    "total": 77,
    "skip": 0,
    "limit": 100
  }
}
```

#### Get Document Details

```http
GET /documents/{document_id}
```

Retrieves details of a specific document.

**Path Parameters**
- `document_id` (string) - Document identifier

**Response (200 OK)**
```json
{
  "status": "success",
  "data": {
    "id": "QMS-DOC-001",
    "code": "QMS-DOC",
    "title": "Quality Management System Documentation",
    "version": "1.0",
    "department": "Quality Assurance",
    "description": "Comprehensive QMS documentation",
    "pdfPath": "/documents/QMS-DOC-001.pdf",
    "docxPath": "/documents/QMS-DOC-001.docx",
    "createdAt": "2024-01-15T10:00:00Z",
    "updatedAt": "2024-01-23T10:30:00Z"
  }
}
```

#### Get Document Hierarchy

```http
GET /documents/{document_id}/hierarchy
```

Retrieves the hierarchical structure of a document (chapters, sections, etc.).

**Response (200 OK)**
```json
{
  "status": "success",
  "data": {
    "chapters": [
      {
        "id": "CH001",
        "title": "1. Introduction",
        "level": 1,
        "children": [
          {
            "id": "SEC001",
            "title": "1.1 Purpose",
            "level": 2
          }
        ]
      }
    ],
    "stats": {
      "totalDocuments": 77,
      "totalAnnexes": 45,
      "totalFiles": 150,
      "pdfFiles": 77,
      "docxFiles": 73,
      "chapters": 450,
      "lastUpdated": "2024-01-23T10:30:00Z"
    }
  }
}
```

#### Upload Document

```http
POST /documents
Content-Type: multipart/form-data
X-API-Key: your-api-key
```

Uploads a new document or annex to the system.

**Request Body**
- `file` (file, required) - PDF or DOCX file to upload
- `title` (string, required) - Document title
- `department` (string, optional) - Department name

**Response (201 Created)**
```json
{
  "status": "success",
  "data": {
    "id": "NEW-DOC-001",
    "title": "New Document",
    "path": "/documents/NEW-DOC-001.pdf",
    "size": 1024000,
    "uploadedAt": "2024-01-23T10:30:00Z"
  }
}
```

**Errors**
- `400 Bad Request` - Missing required fields
- `413 Payload Too Large` - File exceeds maximum size
- `415 Unsupported Media Type` - Invalid file type
- `401 Unauthorized` - Missing or invalid API key

### SOP Generation Endpoints

#### Generate SOP

```http
POST /generate
Content-Type: application/json
X-API-Key: your-api-key
```

Generates a new Standard Operating Procedure based on template and customization data.

**Request Body**
```json
{
  "sop_id": "SOP-001",
  "sop_title": "Sample Collection Procedure",
  "department": "Harvest",
  "customization": {
    "facility_name": "Cannabis Facility ABC",
    "location": "Netherlands",
    "responsible_person": "John Doe",
    "additional_requirements": "EU GMP Annex 15 compliant"
  },
  "ai_provider": "openai",
  "ai_model": "gpt-4"
}
```

**Response (200 OK)**
```json
{
  "status": "success",
  "data": {
    "request_id": "REQ-12345",
    "sop_id": "SOP-001",
    "title": "Sample Collection Procedure - Cannabis Facility ABC",
    "content": "1. Objective\n2. Scope\n3. Procedure\n...",
    "format": "docx",
    "file_path": "/output/SOP-001-generated.docx",
    "generated_at": "2024-01-23T10:30:00Z",
    "generation_time_ms": 5234
  }
}
```

**Errors**
- `400 Bad Request` - Invalid SOP ID or missing required fields
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Generation failed
- `503 Service Unavailable` - AI provider unavailable

#### Get Generation Status

```http
GET /generate/{request_id}
```

Retrieves the status of a document generation request.

**Response (200 OK)**
```json
{
  "status": "success",
  "data": {
    "request_id": "REQ-12345",
    "status": "completed",
    "progress": 100,
    "file_path": "/output/SOP-001-generated.docx",
    "started_at": "2024-01-23T10:25:00Z",
    "completed_at": "2024-01-23T10:30:00Z",
    "duration_ms": 5000
  }
}
```

### Questionnaire Endpoints

#### Initialize Questionnaire

```http
GET /initialize-questionnaire
```

Retrieves the questionnaire schema and questions for business analysis.

**Query Parameters**
- `department` (string, optional) - Filter questions by department

**Response (200 OK)**
```json
{
  "status": "success",
  "data": {
    "questionnaire_id": "Q-2024-001",
    "title": "Cannabis Facility Business Analysis",
    "version": "1.0",
    "questions": [
      {
        "id": "Q1",
        "question": "What is the primary cultivation method?",
        "type": "multiple_choice",
        "required": true,
        "options": [
          "Indoor",
          "Outdoor",
          "Hybrid"
        ]
      },
      {
        "id": "Q2",
        "question": "Annual production capacity (kg)?",
        "type": "text",
        "required": true
      }
    ],
    "estimated_time_minutes": 30
  }
}
```

#### Submit Questionnaire

```http
POST /submit-questionnaire
Content-Type: application/json
X-API-Key: your-api-key
```

Submits questionnaire responses and triggers document generation workflow.

**Request Body**
```json
{
  "questionnaire_id": "Q-2024-001",
  "facility_name": "Cannabis Facility XYZ",
  "location": "Belgium",
  "answers": {
    "Q1": "Indoor",
    "Q2": "5000",
    "Q3": "GMP Compliant",
    "Q4": "Yes"
  },
  "additional_notes": "Priority: Fast processing"
}
```

**Response (200 OK)**
```json
{
  "status": "success",
  "data": {
    "submission_id": "SUB-12345",
    "questionnaire_id": "Q-2024-001",
    "facility_name": "Cannabis Facility XYZ",
    "status": "processing",
    "generated_sops": [
      "SOP-001",
      "SOP-002",
      "SOP-003"
    ],
    "estimated_completion": "2024-01-23T11:30:00Z",
    "submitted_at": "2024-01-23T10:30:00Z"
  }
}
```

### Statistics Endpoints

#### Get System Statistics

```http
GET /stats
```

Retrieves system-wide statistics and metrics.

**Response (200 OK)**
```json
{
  "status": "success",
  "data": {
    "total_documents": 77,
    "total_annexes": 45,
    "total_files": 150,
    "pdf_files": 77,
    "docx_files": 73,
    "total_chapters": 450,
    "total_departments": 9,
    "last_updated": "2024-01-23T10:30:00Z",
    "storage_used_mb": 2048,
    "storage_total_mb": 10240,
    "active_sessions": 5,
    "total_generations": 234,
    "failed_generations": 3
  }
}
```

## Error Handling

### Standard Error Response

```json
{
  "status": "error",
  "message": "Human-readable error description",
  "code": "ERROR_CODE",
  "details": {
    "field": "error details"
  },
  "timestamp": "2024-01-23T10:30:00Z"
}
```

### HTTP Status Codes

| Code | Meaning | Response |
|------|---------|----------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid API key |
| 403 | Forbidden | Access denied |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists |
| 413 | Payload Too Large | Request body or file too large |
| 415 | Unsupported Media Type | Invalid file type |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily unavailable |

### Common Error Codes

- `INVALID_API_KEY` - API key is missing or invalid
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `DOCUMENT_NOT_FOUND` - Document ID not found
- `INVALID_FILE_FORMAT` - Uploaded file format not supported
- `GENERATION_FAILED` - SOP generation failed
- `DATABASE_ERROR` - Database connection or query error
- `EXTERNAL_SERVICE_ERROR` - Third-party service (AI provider) failed

## Request/Response Examples

### Example 1: Generate SOP with cURL

```bash
curl -X POST http://localhost:8000/generate \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "sop_id": "SOP-001",
    "sop_title": "Sample Collection",
    "department": "Harvest",
    "customization": {
      "facility_name": "My Cannabis Facility",
      "location": "Netherlands"
    },
    "ai_provider": "openai",
    "ai_model": "gpt-4"
  }'
```

### Example 2: Upload Document with Python

```python
import requests

url = "http://localhost:8000/documents"
headers = {"X-API-Key": "your-api-key"}
files = {"file": open("procedure.pdf", "rb")}
data = {
    "title": "New SOP",
    "department": "Quality Assurance"
}

response = requests.post(url, headers=headers, files=files, data=data)
print(response.json())
```

### Example 3: Get Documents with JavaScript

```javascript
const response = await fetch('http://localhost:8000/documents', {
  method: 'GET',
  headers: {
    'X-API-Key': 'your-api-key',
    'Content-Type': 'application/json'
  }
});

const data = await response.json();
console.log(data);
```

## Webhooks (Future)

Webhook support for asynchronous notifications about document generation completion is planned for future releases.

## API Versioning

Current API version: `v1`

Future API versions will be supported with explicit version selection via URL prefix or header:

```
/api/v1/documents
/api/v2/documents
```

## Pagination

Endpoints that return collections support pagination:

```http
GET /documents?skip=0&limit=50
```

- `skip` - Number of items to skip (default: 0)
- `limit` - Maximum items to return (default: 100, max: 1000)

## Filtering

Supported filter parameters:

```http
GET /documents?department=Quality&status=active
```

## Sorting

Supported sort parameters:

```http
GET /documents?sort=title:asc
GET /documents?sort=created_at:desc
```

## Search

Full-text search across documents:

```http
GET /documents/search?query=sample%20collection
```

## SDK and Client Libraries

### Python

```python
from qms_client import QMSClient

client = QMSClient(
    base_url="http://localhost:8000",
    api_key="your-api-key"
)

# List documents
documents = client.documents.list()

# Generate SOP
sop = client.sops.generate(
    sop_id="SOP-001",
    sop_title="Sample Collection",
    department="Harvest"
)
```

### JavaScript/TypeScript

```typescript
import { QMSClient } from 'qms-client-js';

const client = new QMSClient({
  baseUrl: 'http://localhost:8000',
  apiKey: 'your-api-key'
});

// List documents
const documents = await client.documents.list();

// Generate SOP
const sop = await client.sops.generate({
  sopId: 'SOP-001',
  sopTitle: 'Sample Collection',
  department: 'Harvest'
});
```

## Rate Limiting Best Practices

1. **Implement exponential backoff** for retries
2. **Cache responses** to reduce API calls
3. **Batch requests** when possible
4. **Monitor rate limit headers** to adjust request frequency
5. **Use webhooks** for asynchronous operations

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use HTTPS** in production
3. **Rotate API keys** regularly
4. **Restrict CORS origins** to known domains
5. **Validate all inputs** before sending
6. **Use request timeouts** to prevent hanging requests
7. **Implement request signing** for additional security

## Support

For API support:
- Check API documentation at `/docs`
- Review error codes and messages
- Check GitHub issues: https://github.com/yourusername/cannabis-qms-creator/issues
- Contact: support@qms.example.com
