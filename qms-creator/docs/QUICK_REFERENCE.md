# Quick Reference Card - Cannabis EU GMP QMS Creator

A one-page quick reference for common development tasks and commands.

---

## 🚀 Getting Started (5 minutes)

```bash
# Clone & Setup
git clone https://github.com/yourusername/cannabis-qms-creator.git
cd cannabis-qms-creator

# Backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python CONTENT_CREATOR_FRAMEWORK/main_api.py

# Frontend (new terminal)
cd qms-ui
npm install
npm start

# Open in browser
http://localhost:3000          # Frontend
http://localhost:8000          # Backend
http://localhost:8000/docs     # API Docs
```

---

## 🔧 Development Commands

### Python Backend

```bash
# Activate environment
source .venv/bin/activate

# Run API server
python CONTENT_CREATOR_FRAMEWORK/main_api.py

# Or with auto-reload
uvicorn CONTENT_CREATOR_FRAMEWORK.main_api:app --reload

# Run tests
pytest CONTENT_CREATOR_FRAMEWORK/tests/ -v
pytest CONTENT_CREATOR_FRAMEWORK/tests/test_api.py::TestHealthEndpoints -v

# Run with coverage
pytest --cov=CONTENT_CREATOR_FRAMEWORK --cov-report=html

# Format code
black CONTENT_CREATOR_FRAMEWORK/
isort CONTENT_CREATOR_FRAMEWORK/

# Lint code
flake8 CONTENT_CREATOR_FRAMEWORK/
mypy CONTENT_CREATOR_FRAMEWORK/
```

### JavaScript/React Frontend

```bash
cd qms-ui

# Development
npm start                    # Start dev server
npm run dev                 # Vite dev mode

# Testing
npm test                    # Run tests
npm test -- --coverage      # With coverage
npm test -- --watch         # Watch mode

# Building
npm run build               # Build for production
npm run preview             # Preview build

# Linting
npm run lint                # Check ESLint
npm run lint -- --fix       # Fix issues
npm run format              # Format with Prettier
```

---

## 🐳 Docker Commands

```bash
# Development
docker-compose -f docker-compose.dev.yml up --build

# Production
docker-compose up --build

# Specific service
docker-compose up backend
docker-compose up frontend

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres

# Execute command
docker-compose exec backend bash
docker-compose exec frontend bash
docker-compose exec postgres psql -U postgres

# Cleanup
docker-compose down
docker-compose down -v  # Include volumes
```

---

## 📊 API Endpoints (Quick List)

```bash
# Health & Status
GET  /health                        # Basic health check
GET  /api/health                    # Detailed health check
GET  /metrics                       # Prometheus metrics

# Documents
GET  /documents                     # List all documents
POST /documents                     # Create/update (auth required)
GET  /api/hierarchy                 # Document hierarchy
GET  /api/stats                     # Statistics
GET  /api/documents/{code}          # Get document by code

# Questionnaire
GET  /questionnaire-schema          # Get SOP schema
POST /initialize-questionnaire      # Initialize
POST /submit-questionnaire          # Submit & generate (auth required)

# SOP Generation
POST /generate                      # Generate SOP (auth required)
POST /analyze                       # Analyze request

# Test with cURL
curl http://localhost:8000/health
curl -H "X-API-Key: test-api-key-12345" http://localhost:8000/documents
```

---

## 🔐 Authentication

```bash
# API Key (in .env)
API_KEY=your-secure-key-here

# Use in requests
curl -H "X-API-Key: your-secure-key-here" http://localhost:8000/documents

# Protected endpoints
/documents (POST)           # Create/update
/generate                   # Generate SOP
/submit-questionnaire       # Submit answers
```

---

## 📝 Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes
git add .
git commit -m "feat: description of changes"

# Push to remote
git push origin feature/your-feature-name

# Create pull request on GitHub
# Get review
# Merge when approved

# Clean up
git branch -D feature/your-feature-name
git push origin --delete feature/your-feature-name
```

**Commit Types**: feat, fix, docs, style, refactor, perf, test, ci, chore, revert

---

## 🧪 Testing Quick Guide

```bash
# Backend Tests

# Run all tests
pytest CONTENT_CREATOR_FRAMEWORK/tests/ -v

# Run specific file
pytest CONTENT_CREATOR_FRAMEWORK/tests/test_api.py -v

# Run specific test
pytest CONTENT_CREATOR_FRAMEWORK/tests/test_api.py::TestHealthEndpoints::test_health_check -v

# With coverage
pytest --cov=CONTENT_CREATOR_FRAMEWORK --cov-report=term-missing --cov-report=html

# Frontend Tests

# Run all tests
npm test

# Run in watch mode
npm test -- --watch

# With coverage
npm test -- --coverage

# Run specific test
npm test -- DocumentBrowser.test.tsx
```

---

## 🗂️ File Structure Essentials

```
CONTENT_CREATOR_FRAMEWORK/
├── main_api.py                  # FastAPI app
├── auth.py                      # Authentication
├── database/models.py           # Database schemas
├── tests/
│   ├── conftest.py             # Test fixtures
│   ├── test_api.py             # API tests (23)
│   └── test_database.py        # DB tests (12)
└── monitoring/                  # Monitoring

qms-ui/
├── src/
│   ├── components/             # React components
│   ├── hooks/                  # Custom hooks
│   └── types/                  # TypeScript types
└── tests/                      # Component tests

docs/
├── QUICK_START.md              # Getting started
├── ARCHITECTURE.md             # System design
├── TROUBLESHOOTING.md          # Problem solving
└── ... (12+ more guides)

.github/
├── ISSUE_TEMPLATE/
│   ├── bug_report.md
│   └── feature_request.md
├── pull_request_template.md
└── workflows/                  # CI/CD pipelines
```

---

## 🐛 Debugging Tips

```bash
# Backend Debugging

# Enable debug logging
export LOG_LEVEL=DEBUG
python CONTENT_CREATOR_FRAMEWORK/main_api.py

# Check running services
ps aux | grep python
ps aux | grep node

# View live logs
docker-compose logs -f
docker-compose logs -f backend | grep ERROR

# Database debugging
psql -U postgres -d qms_db
SELECT * FROM documents LIMIT 5;
SELECT COUNT(*) FROM audit_logs;

# Frontend Debugging

# Browser DevTools (F12)
# Network tab - check API calls
# Console tab - see errors
# Application tab - check storage

# View network requests
curl -v http://localhost:8000/health
```

---

## 📦 Key Dependencies

### Backend (Python)
```
FastAPI==0.104.0         # Web framework
SQLAlchemy==2.0.20       # ORM
Pydantic==2.0.0          # Data validation
psycopg2-binary==2.9.9   # PostgreSQL
python-dotenv==1.0.0     # Environment variables
slowapi==0.1.9           # Rate limiting
sentry-sdk==1.35.0       # Error tracking
prometheus-client==0.19.0 # Metrics
```

### Frontend (JavaScript)
```
react@19.0.0             # UI library
typescript@5.3.0         # Type checking
vite@5.0.0               # Build tool
react-router@6.0.0       # Routing
vitest@1.0.0             # Testing
@testing-library/react   # Component testing
```

---

## 🔗 Important URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:3000 | Main UI |
| Backend API | http://localhost:8000 | REST API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Prometheus | http://localhost:9090 | Metrics |
| Grafana | http://localhost:3000 | Dashboards |
| PgAdmin | http://localhost:5050 | Database UI |

---

## 📚 Documentation Links

| Document | Location | Purpose |
|----------|----------|---------|
| Quick Start | `docs/QUICK_START.md` | Get started |
| Architecture | `docs/ARCHITECTURE.md` | System design |
| API Reference | `docs/API.md` | Endpoints |
| Troubleshooting | `docs/TROUBLESHOOTING.md` | Fix issues |
| Deployment | `docs/DEPLOYMENT.md` | Production |
| Development | `docs/DEVELOPMENT_WORKFLOW.md` | Workflow |
| Commits | `docs/COMMIT_CONVENTIONS.md` | Git standards |

---

## ⚡ Common Tasks

### Add New Endpoint

```python
# CONTENT_CREATOR_FRAMEWORK/main_api.py
@app.get("/api/new-endpoint")
async def new_endpoint(request: Request):
    """Endpoint description"""
    return {"result": "data"}

# Add test
# CONTENT_CREATOR_FRAMEWORK/tests/test_api.py
def test_new_endpoint(test_client):
    response = test_client.get("/api/new-endpoint")
    assert response.status_code == 200
    assert "result" in response.json()
```

### Add New Component

```typescript
// qms-ui/src/components/NewComponent.tsx
import React from 'react'

export const NewComponent: React.FC = () => {
  return <div>Component content</div>
}

// Add test
// qms-ui/src/components/__tests__/NewComponent.test.tsx
import { render, screen } from '@testing-library/react'
import { NewComponent } from '../NewComponent'

describe('NewComponent', () => {
  it('renders', () => {
    render(<NewComponent />)
    expect(screen.getByText('Component content')).toBeInTheDocument()
  })
})
```

### Create Database Migration

```bash
# Auto-generate migration from changes
alembic revision --autogenerate -m "Add new field"

# Review generated file
cat alembic/versions/001_add_new_field.py

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

---

## 🚨 Emergency Commands

```bash
# Reset everything
docker-compose down -v
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Kill process on port
lsof -i :8000                   # Find process
kill -9 <PID>                   # Kill it

# Clear Docker
docker system prune -a
docker-compose build --no-cache

# Database reset
psql -U postgres -d qms_db -c "DROP TABLE IF EXISTS documents CASCADE;"
alembic upgrade head
python scripts/seed_database.py
```

---

## 📞 Getting Help

```
Documentation: See docs/ folder
API Docs: http://localhost:8000/docs
Issues: GitHub Issues
Chat: GitHub Discussions
Email: dev@example.com
```

---

## ✅ Checklist Before Commit

- [ ] Tests passing: `pytest` + `npm test`
- [ ] Linting clean: `npm run lint`
- [ ] Code formatted: `npm run format`
- [ ] Commit message follows convention
- [ ] No debug code left (console.log, print, etc.)
- [ ] No secrets in code
- [ ] Documentation updated if needed

---

## 🎯 Performance Tips

```bash
# Check what's slow
time pytest CONTENT_CREATOR_FRAMEWORK/tests/

# Frontend bundle size
npm run build
# Check dist/ folder size

# Database query time
EXPLAIN ANALYZE SELECT * FROM documents;

# API response time
curl -w "@curl-format.txt" http://localhost:8000/documents
```

---

**Last Updated**: January 2026  
**Version**: 1.0.0

Save this page as a bookmark for quick reference! 🔖
