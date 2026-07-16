# Architecture Documentation - Cannabis EU GMP QMS Creator

## Overview

The Cannabis EU GMP QMS Creator is a full-stack web application designed to generate and manage Standard Operating Procedures (SOPs) and Quality Management System (QMS) documents for cannabis facilities operating under EU GMP regulations.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Layer (Browser)                   │
│                  React 19 + TypeScript + Vite               │
│                    Responsive Web UI                         │
└────────────────┬──────────────────────────────────┬──────────┘
                 │                                  │
                 │ HTTP/HTTPS REST API             │
                 │                                  │
┌────────────────▼──────────────────────────────────▼──────────┐
│                    API Gateway Layer                          │
│              Nginx Reverse Proxy + Load Balancer             │
│          Security Headers + Rate Limiting + CORS            │
└────────────────┬──────────────────────────────────┬──────────┘
                 │                                  │
                 │ Internal APIs                    │
                 │                                  │
┌────────────────▼──────────────────────────────────▼──────────┐
│                  Application Server                           │
│                    FastAPI (Python 3.12)                     │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  API Endpoints                                      │   │
│  │  • Document Management  • SOP Generation           │   │
│  │  • Questionnaire Workflow                          │   │
│  │  • Statistics & Reporting                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Core Modules                                       │   │
│  │  • Integrated SOP Generator Workflow               │   │
│  │  • RAG Document Classifier                         │   │
│  │  • Vector Search Engine                            │   │
│  │  • Regulatory Auditor                              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Infrastructure                                    │   │
│  │  • Authentication (API Keys)                       │   │
│  │  • Error Handling & Validation                     │   │
│  │  • Security Middleware                             │   │
│  │  • Structured Logging                              │   │
│  │  • Monitoring (Sentry, Prometheus)                 │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────┬──────────────────────────────────┬──────────┘
                 │                                  │
                 │ Database Operations              │
                 │ File I/O                         │
                 │ External Service Calls           │
                 │                                  │
┌────────────────▼──────────────────────────────────▼──────────┐
│                    Data Layer                                │
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │  PostgreSQL      │    │  File System     │              │
│  │  SQLAlchemy ORM  │    │  Documents/PDFs  │              │
│  │  Alembic         │    │  Generated SOPs  │              │
│  └──────────────────┘    └──────────────────┘              │
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐              │
│  │  JSON Fallback   │    │  Vector DB       │              │
│  │  (Legacy)        │    │  (Search Index)  │              │
│  └──────────────────┘    └──────────────────┘              │
└────────────────┬──────────────────────────────────┬──────────┘
                 │                                  │
                 │ External Services                │
                 │                                  │
┌────────────────▼──────────────────────────────────▼──────────┐
│               External Integrations                           │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ OpenAI API   │  │ Anthropic    │  │ Ollama Local │     │
│  │ GPT Models   │  │ Claude       │  │ LLMs         │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                        │
│  │ Sentry       │  │ GitHub       │                        │
│  │ Error Tracking│ │ CI/CD        │                        │
│  └──────────────┘  └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

## System Components

### 1. Frontend Application (`qms-ui/`)

**Technology Stack**:
- React 19 with TypeScript
- Vite (build tool)
- React Router (navigation)
- CSS/SCSS (styling)
- Vitest (unit testing)

**Key Features**:
- Single Page Application (SPA)
- Responsive design
- Real-time document updates
- Questionnaire workflow with validation
- Document browser with hierarchy view
- Statistics dashboard

**Directory Structure**:
```
qms-ui/
├── src/
│   ├── components/          # React components
│   │   ├── Dashboard.tsx
│   │   ├── Questionnaire.tsx
│   │   ├── DocumentBrowser.tsx
│   │   ├── Sidebar.tsx
│   │   └── DOCXViewer.tsx
│   ├── hooks/              # Custom React hooks
│   │   └── useDocuments.ts
│   ├── types/              # TypeScript types
│   │   └── questionnaire.ts
│   ├── App.tsx
│   └── main.tsx
├── public/                 # Static assets
└── vite.config.ts         # Vite configuration
```

**API Integration**:
- REST API communication with backend
- Axios/Fetch for HTTP requests
- Error handling and retry logic
- Authentication via API key headers

---

### 2. Backend Application

**Technology Stack**:
- Python 3.12
- FastAPI (web framework)
- SQLAlchemy (ORM)
- Alembic (migrations)
- Pydantic (data validation)

**Core Modules**:

#### 2.1 API Layer (`main_api.py`)
- RESTful endpoints for document management
- Questionnaire initialization and submission
- SOP generation workflow
- Statistics and reporting endpoints
- Health check and monitoring endpoints

**Key Endpoints**:
```
GET  /                          # Root
GET  /health                    # Health check
GET  /documents                 # List documents
POST /documents                 # Create/update document (auth required)
GET  /questionnaire-schema      # Get SOP questionnaire schema
POST /initialize-questionnaire  # Initialize questionnaire
POST /submit-questionnaire      # Submit answers & generate SOP (auth required)
POST /generate                  # Direct SOP generation (auth required)
POST /analyze                   # Analyze SOP request
GET  /api/hierarchy             # Get document hierarchy
GET  /api/stats                 # Get statistics
GET  /api/documents/{code}      # Get document metadata
```

#### 2.2 Integrated SOP Generator (`integrated_sop_generator_workflow.py`)
Multi-stage workflow for SOP generation:

1. **Analysis Stage**: 
   - RAG-based document retrieval
   - Relevant content identification
   - Gap analysis

2. **Content Generation Stage**:
   - LLM-based SOP writing
   - Questionnaire enrichment
   - Facility-specific customization

3. **Review Stage**:
   - Regulatory compliance audit
   - Quality assurance checks
   - Audit report generation

4. **Export Stage**:
   - DOCX document generation
   - PDF conversion
   - Archive creation

#### 2.3 RAG Document Classifier (`rag_document_classifier.py`)
- Semantic document search using vector embeddings
- Retrieval augmented generation for context
- Document similarity matching
- Content relevance ranking

#### 2.4 Vector Search Engine (`vector_search_engine.py`)
- Vector embeddings for documents
- Similarity search functionality
- Efficient indexing for large document sets
- Integration with Ollama for local embeddings

#### 2.5 Regulatory Auditor (`regulatory_auditor.py`)
- EU GMP compliance checking
- SOP requirement validation
- Quality assurance rules
- Audit report generation

#### 2.6 Document Service (`document_service.py`)
- Document file handling
- PDF/DOCX scanning
- Document metadata extraction
- Hierarchy building

---

### 3. Database Layer

**Primary Database**: PostgreSQL with SQLAlchemy ORM

**Models** (`database/models.py`):

```python
Document
├── id: String (Primary Key)
├── code: String (Unique)
├── title: String
├── department: String
├── version: String
├── status: Enum (pending, in_progress, completed, archived)
├── description: Text
├── created_at: DateTime
├── updated_at: DateTime
├── pdf_path: String
├── docx_path: String
├── is_template: Boolean
├── is_archived: Boolean
├── is_public: Boolean
└── Relationships
    ├── annexes: List[Annex]
    ├── chapters: List[DocumentChapter]
    └── audit_logs: List[AuditLog]

Annex
├── id: String (Primary Key)
├── document_id: String (Foreign Key)
├── code: String
├── title: String
├── file_path: String
├── file_type: String
├── file_size: Integer
├── created_at: DateTime
└── document: Document

DocumentChapter
├── id: String (Primary Key)
├── document_id: String (Foreign Key)
├── chapter_number: Integer
├── number: String
├── title: String
├── section: String
├── content: Text
├── level: Integer
├── order: Integer
└── document: Document

AuditLog
├── id: String (Primary Key)
├── document_id: String (Foreign Key)
├── action: String (CREATE, UPDATE, DELETE, etc.)
├── user_id: String
├── created_at: DateTime
├── details: Text (JSON)
├── ip_address: String
└── user_agent: String
```

**Database Indexes**:
- Document: code, title, department, status, created_at
- Annex: document_id, file_type
- DocumentChapter: document_id, order, level
- AuditLog: document_id, action, user_id, created_at

**Migrations**: Alembic for schema versioning and migrations

**Fallback**: JSON file storage when PostgreSQL unavailable

---

### 4. Security Layer

#### Authentication
- **API Key Authentication**: X-API-Key header validation
- **Status Codes**: 401 for missing/invalid, 403 for forbidden

#### Middleware
1. **Security Headers Middleware**:
   - X-Content-Type-Options
   - X-Frame-Options
   - Strict-Transport-Security
   - Content-Security-Policy

2. **Request Limit Middleware**:
   - Per-endpoint size limits
   - Request timeout enforcement

3. **Rate Limiting Middleware**:
   - Per-IP rate limiting
   - Endpoint-specific limits
   - Using slowapi library

4. **Input Validation Middleware**:
   - SQL/NoSQL injection detection
   - Request validation
   - Response sanitization

#### Error Handling
- Standardized error responses
- No sensitive information leakage
- Sentry integration for tracking
- Structured error logging

---

### 5. Monitoring & Logging

#### Structured Logging
- JSON format logging
- Context correlation with request IDs
- User tracking and correlation
- Automatic log rotation

#### Metrics (Prometheus)
- Request count and duration
- Document generation metrics
- Database query performance
- Error rates and types
- External service calls

#### Error Tracking (Sentry)
- Real-time error notifications
- Breadcrumb tracking
- Release tracking
- Performance monitoring

#### Health Monitoring
- Application health status
- Database connectivity
- File system availability
- Memory and disk usage
- External service status

---

### 6. Testing Infrastructure

#### Backend Tests
- **Unit Tests**: Module-level functionality
- **Integration Tests**: API endpoint testing
- **Database Tests**: Model CRUD operations
- **Test Coverage**: 70%+ target

**Test Files**:
- `test_api.py`: 23 API endpoint tests
- `test_database.py`: 12 database operation tests

#### Frontend Tests
- **Component Tests**: React component rendering
- **Hook Tests**: Custom hook functionality
- **Integration Tests**: Component interaction

---

## Data Flow

### SOP Generation Workflow

```
User Input (Questionnaire)
        ↓
[1] Analysis Stage
    ├── RAG retrieval of related documents
    ├── Identify relevant content
    ├── Analyze facility context
    └── Generate enriched schema
        ↓
[2] Content Generation Stage
    ├── Query LLM (OpenAI/Anthropic/Ollama)
    ├── Generate SOP sections
    ├── Integrate with existing documents
    ├── Apply facility-specific customization
    └── Compile full document
        ↓
[3] Review Stage
    ├── Regulatory compliance audit
    ├── Quality assurance checks
    ├── Generate audit report
    └── Flag non-compliant sections
        ↓
[4] Export Stage
    ├── Convert to DOCX format
    ├── Generate PDF (if configured)
    ├── Create archive with related documents
    └── Store in file system/database
        ↓
Generated SOP Documents + Audit Report
```

### Document Management Workflow

```
Upload Document
        ↓
File Validation
├── Size check
├── Format validation
└── Virus scanning (if configured)
        ↓
Metadata Extraction
├── Title/Author/Date
├── Content analysis
└── Keyword extraction
        ↓
Storage & Indexing
├── Save to file system
├── Store metadata in database
├── Index for search
└── Create audit log entry
        ↓
Available in Document Browser
        ↓
Users can:
├── View document details
├── Download document
├── Update metadata
└── Track changes in audit logs
```

---

## Technology Decisions

### Why FastAPI?
- Modern, fast, with automatic OpenAPI documentation
- Type hints support with Pydantic validation
- Excellent async/await support
- Built-in security utilities
- Active community and excellent documentation

### Why React?
- Component-based UI architecture
- Large ecosystem and community
- Excellent developer experience with TypeScript
- Performance optimizations (virtual DOM)
- Mature testing frameworks

### Why PostgreSQL?
- ACID compliance for data integrity
- Advanced query capabilities
- Excellent JSON support
- Proven reliability for production use
- Strong security features

### Why SQLAlchemy?
- Database-agnostic ORM
- Type-safe query building
- Built-in relationship management
- Excellent performance with query optimization
- Wide adoption and community support

---

## Deployment Architecture

### Development
- Local services: Backend (8000), Frontend (3000)
- JSON file storage for documents
- SQLite for testing

### Production
- Docker containerization
- Nginx reverse proxy with load balancing
- PostgreSQL with connection pooling
- Separate database server
- Redis for caching (optional)
- CDN for static assets (optional)
- SSL/TLS encryption
- Regular backups and recovery procedures

---

## Scalability Considerations

### Horizontal Scaling
- Stateless API design allows multiple backend instances
- Load balancer distributes traffic
- Shared PostgreSQL database
- Shared file storage (S3 or similar)

### Vertical Scaling
- Database connection pooling
- Caching strategies
- Query optimization with indexes
- Asynchronous task processing for long-running operations

### Performance Optimizations
- Database query caching
- API response compression
- Frontend asset minification
- Image optimization
- Lazy loading of components

---

## Security Architecture

### Defense in Depth
1. **Network Level**: Firewall, VPC isolation
2. **Application Level**: Authentication, authorization
3. **Data Level**: Encryption at rest and in transit
4. **Infrastructure Level**: Regular patching, monitoring

### Data Protection
- Sensitive data encryption in database
- TLS/SSL for data in transit
- HTTPS only for API communication
- API key rotation policies

### Access Control
- Role-based access control (future enhancement)
- Audit logging of all actions
- IP whitelisting (optional)
- Rate limiting per user/IP

---

## Integration Points

### LLM Integration
- OpenAI GPT models (production)
- Anthropic Claude (alternative)
- Ollama for local models (development)
- Configurable provider selection

### Document Processing
- PDF generation (reportlab)
- DOCX manipulation (python-docx)
- Document parsing (custom)

### External Services
- GitHub for CI/CD
- Sentry for error tracking
- Email for notifications (future)

---

## Configuration Management

### Environment Variables
- Development: `.env.development`
- Production: `.env.production`
- Testing: Set in `conftest.py`

### Configuration Hierarchy
1. Environment variables
2. `.env` file
3. Code defaults
4. System defaults

---

## Monitoring & Alerting

### Metrics to Monitor
- API response times
- Error rates
- Database query performance
- Memory usage
- Disk space
- External service availability

### Alerting Thresholds
- 5xx errors: Alert immediately
- 4xx errors: Alert on spike
- Response time > 5s: Alert
- Error rate > 1%: Alert
- Disk usage > 80%: Alert

---

## Future Architecture Enhancements

1. **Microservices**: Separate SOP generation into dedicated service
2. **Message Queue**: RabbitMQ/Redis for async processing
3. **Cache Layer**: Redis for session and query caching
4. **Search Engine**: Elasticsearch for full-text search
5. **Real-time Updates**: WebSockets for live notifications
6. **Machine Learning**: Custom models for compliance checking
7. **Multi-tenancy**: Support multiple organizations
8. **API Gateway**: Kong or similar for advanced routing

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [React Documentation](https://react.dev)
- [PostgreSQL Documentation](https://www.postgresql.org/docs)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org)
- [Docker Documentation](https://docs.docker.com)

---

**Last Updated**: January 2026
**Version**: 1.0.0
