# Development Workflow Guide - Cannabis EU GMP QMS Creator

This guide describes the recommended workflow for developing, testing, and contributing to the Cannabis EU GMP QMS Creator project.

## Table of Contents
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Feature Development](#feature-development)
- [Testing Workflow](#testing-workflow)
- [Code Review Process](#code-review-process)
- [Deployment Workflow](#deployment-workflow)
- [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites
- Git 2.25+
- Python 3.12+
- Node.js 18+
- PostgreSQL 13+ (optional)
- Docker & Docker Compose (optional)

### Initial Setup

1. **Clone Repository**
   ```bash
   git clone https://github.com/yourusername/cannabis-qms-creator.git
   cd cannabis-qms-creator
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Set Up Development Environment**
   ```bash
   # Backend setup
   python3.12 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   
   # Frontend setup
   cd qms-ui
   npm install
   cd ..
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your development settings
   ```

---

## Development Setup

### Backend Development

#### Starting the Development Server

```bash
# Activate virtual environment
source .venv/bin/activate

# Start FastAPI with auto-reload
python CONTENT_CREATOR_FRAMEWORK/main_api.py

# Or use uvicorn directly
uvicorn CONTENT_CREATOR_FRAMEWORK.main_api:app --reload
```

Backend available at: **http://localhost:8000**
API Docs: **http://localhost:8000/docs**

#### Code Structure

```
CONTENT_CREATOR_FRAMEWORK/
├── main_api.py                      # FastAPI application
├── auth.py                          # Authentication logic
├── error_handlers.py                # Error handling
├── validators.py                    # Input validation
├── security_middleware.py           # Security middleware
├── logging_config.py               # Logging configuration
├── document_service.py             # Document operations
├── integrated_sop_generator_workflow.py  # SOP generation
├── rag_document_classifier.py      # RAG functionality
├── vector_search_engine.py         # Search functionality
├── regulatory_auditor.py           # Compliance checking
├── qms_database.py                 # Database management
├── database/                       # Database models and session
├── monitoring/                     # Sentry and metrics
└── tests/                          # Test suite
```

#### Making Backend Changes

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/new-api-endpoint
   ```

2. **Make Code Changes**
   - Edit relevant files in CONTENT_CREATOR_FRAMEWORK/
   - Follow PEP 8 style guidelines
   - Add type hints to functions
   - Write docstrings for complex logic

3. **Test Changes Locally**
   ```bash
   # Run specific endpoint
   curl http://localhost:8000/health
   
   # Run unit tests
   pytest CONTENT_CREATOR_FRAMEWORK/tests/test_api.py -v
   ```

4. **Commit Changes**
   ```bash
   git add CONTENT_CREATOR_FRAMEWORK/
   git commit -m "feat: Add new SOP generation endpoint"
   ```

### Frontend Development

#### Starting the Development Server

```bash
cd qms-ui

# Start Vite dev server
npm start

# Or use npm run dev
npm run dev
```

Frontend available at: **http://localhost:3000**

#### Code Structure

```
qms-ui/
├── src/
│   ├── components/                 # React components
│   │   ├── Dashboard.tsx
│   │   ├── Questionnaire.tsx
│   │   ├── DocumentBrowser.tsx
│   │   └── Sidebar.tsx
│   ├── hooks/                      # Custom React hooks
│   ├── types/                      # TypeScript interfaces
│   ├── App.tsx                     # Root component
│   └── main.tsx                    # Entry point
├── public/                         # Static assets
└── vite.config.ts                 # Build configuration
```

#### Making Frontend Changes

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/improve-questionnaire-ui
   ```

2. **Make Code Changes**
   - Edit components in src/components/
   - Update types in src/types/
   - Follow React best practices
   - Use TypeScript for type safety
   - Add JSDoc comments

3. **Test Changes Locally**
   ```bash
   # Linting
   npm run lint
   
   # Unit tests
   npm test
   
   # Manual testing in browser
   # http://localhost:3000
   ```

4. **Commit Changes**
   ```bash
   git add qms-ui/src/
   git commit -m "feat: Improve questionnaire form validation"
   ```

---

## Testing Workflow

### Running Tests

#### Backend Tests

```bash
# Run all backend tests
pytest CONTENT_CREATOR_FRAMEWORK/tests/ -v

# Run specific test file
pytest CONTENT_CREATOR_FRAMEWORK/tests/test_api.py -v

# Run specific test
pytest CONTENT_CREATOR_FRAMEWORK/tests/test_api.py::TestHealthEndpoints::test_health_check -v

# Run with coverage
pytest CONTENT_CREATOR_FRAMEWORK/tests/ --cov=CONTENT_CREATOR_FRAMEWORK --cov-report=html
```

#### Frontend Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm test -- --watch

# Run with coverage
npm test -- --coverage
```

### Writing Tests

#### Backend Test Example

```python
# CONTENT_CREATOR_FRAMEWORK/tests/test_api.py

def test_new_endpoint(test_client, auth_headers):
    """Test new endpoint functionality."""
    response = test_client.get(
        "/new-endpoint",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "result" in data
```

#### Frontend Test Example

```typescript
// qms-ui/src/components/__tests__/NewComponent.test.tsx

import { render, screen } from '@testing-library/react'
import { NewComponent } from '../NewComponent'

describe('NewComponent', () => {
  it('renders correctly', () => {
    render(<NewComponent />)
    expect(screen.getByText('Expected Text')).toBeInTheDocument()
  })
})
```

### Test Coverage Goals

- **Backend**: 70%+ coverage for new code
- **Frontend**: 70%+ coverage for new components
- **Critical Paths**: 100% coverage for auth, payments, core logic

### Pre-Commit Testing

```bash
# Run all tests before committing
npm test && pytest CONTENT_CREATOR_FRAMEWORK/tests/ -q

# Or use pre-commit hooks (configured in .pre-commit-config.yaml)
pre-commit run --all-files
```

---

## Code Review Process

### Creating a Pull Request

1. **Push Your Branch**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create PR on GitHub**
   - Use PR template from `.github/pull_request_template.md`
   - Provide clear description
   - Link related issues
   - List all changes made

3. **PR Checklist**
   - [ ] Code follows style guidelines
   - [ ] Tests written and passing
   - [ ] Documentation updated
   - [ ] No breaking changes
   - [ ] All conversations resolved

### Code Review Guidelines

#### For Authors

1. **Before Requesting Review**
   - Run all tests: `npm test && pytest`
   - Run linter: `npm run lint`
   - Format code: `npm run format`
   - Self-review your changes
   - Keep PRs reasonably sized (< 400 lines)

2. **Respond to Feedback**
   - Address all comments
   - Explain decisions respectfully
   - Request re-review after changes
   - Thank reviewers

#### For Reviewers

1. **Review Checklist**
   - [ ] Code is readable and maintainable
   - [ ] Tests adequately cover changes
   - [ ] No security vulnerabilities introduced
   - [ ] Documentation is accurate
   - [ ] No breaking changes
   - [ ] Performance implications considered

2. **Provide Constructive Feedback**
   - Be respectful and professional
   - Ask questions rather than demand
   - Suggest improvements
   - Acknowledge good work

3. **Approval Process**
   - Require 2 approvals for main branch
   - 1 approval for develop branch
   - All CI checks must pass
   - No unresolved conversations

### Merging Process

```bash
# Once approved, merge using GitHub interface
# Use "Squash and merge" for cleaner history
# Delete branch after merging
git branch -D feature/your-feature-name
git push origin --delete feature/your-feature-name
```

---

## Deployment Workflow

### Development Deployment

```bash
# Using Docker Compose
docker-compose -f docker-compose.dev.yml up --build

# Using Docker
docker-compose up --build

# Local deployment
npm start &  # Frontend
python CONTENT_CREATOR_FRAMEWORK/main_api.py &  # Backend
```

### Staging Deployment

```bash
# Automated via GitHub Actions when merging to develop branch
# Check workflow status in Actions tab

# Or manual deployment
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

### Production Deployment

```bash
# Automated via GitHub Actions when merging to main branch
# Requires manual approval in GitHub

# Or manual deployment (if needed)
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Deployment Checklist

Before deploying to production:
- [ ] All tests passing
- [ ] Code reviewed and approved
- [ ] Documentation updated
- [ ] Database migrations tested
- [ ] Secrets configured
- [ ] Backups created
- [ ] Rollback plan ready

---

## Branch Strategy

### Branch Naming

```
feature/description-of-feature     # New features
bugfix/description-of-bug          # Bug fixes
hotfix/description-of-issue        # Critical production fixes
refactor/description-of-changes    # Code refactoring
docs/description-of-documentation  # Documentation updates
test/description-of-tests          # Test additions
perf/description-of-optimization   # Performance improvements
```

### Branch Workflow

```
main (Production)
  ↑
  ├─ hotfix/critical-issue
  │
develop (Staging)
  ↑
  ├─ feature/new-feature
  ├─ bugfix/issue-fix
  ├─ docs/update-readme
  └─ test/add-coverage
```

### Creating Branches

```bash
# Update main branch
git checkout main
git pull origin main

# Create feature branch
git checkout -b feature/new-sop-generator

# Push to remote
git push -u origin feature/new-sop-generator
```

---

## Development Best Practices

### Code Style

#### Python
```bash
# Format code with Black
black CONTENT_CREATOR_FRAMEWORK/

# Check style with Flake8
flake8 CONTENT_CREATOR_FRAMEWORK/

# Type checking with MyPy
mypy CONTENT_CREATOR_FRAMEWORK/
```

#### TypeScript/JavaScript
```bash
# Format code with Prettier
npm run format

# Lint with ESLint
npm run lint

# Fix linting issues automatically
npm run lint -- --fix
```

### Type Safety

**Backend (Python)**:
- Add type hints to all functions
- Use Pydantic for data validation
- Leverage IDE type checking

**Frontend (TypeScript)**:
- Use strict TypeScript mode
- Define interfaces for all data
- Avoid `any` type unless necessary

### Documentation

**Backend**:
```python
def calculate_sop_sections(facility_data: Dict[str, Any]) -> List[str]:
    """
    Calculate required SOP sections based on facility data.
    
    Args:
        facility_data: Dictionary containing facility information
        
    Returns:
        List of required section titles
        
    Raises:
        ValueError: If facility_data is invalid
    """
    pass
```

**Frontend**:
```typescript
/**
 * Calculate required SOP sections based on facility data.
 * @param facilityData - Dictionary containing facility information
 * @returns List of required section titles
 * @throws {Error} If facilityData is invalid
 */
function calculateSopSections(facilityData: FacilityData): string[] {
  // Implementation
}
```

### Performance Considerations

- **Database**: Use indexes on frequently queried columns
- **API**: Implement caching for read-heavy endpoints
- **Frontend**: Use React.memo and lazy loading for large lists
- **Images**: Optimize and compress before committing

### Security Best Practices

- Never commit secrets or API keys
- Use environment variables for configuration
- Validate all user input
- Use parameterized queries
- Follow OWASP guidelines

---

## Continuous Integration

### GitHub Actions Workflows

#### On Pull Request
```yaml
- Run ESLint
- Run TypeScript check
- Run pytest
- Run coverage check
- Build Docker images
- Security scanning
```

#### On Merge to main
```yaml
- Run all tests
- Build production Docker images
- Push to Docker registry
- Deploy to staging
```

#### Scheduled Tasks
```yaml
# Daily security scan
- Dependency updates
- Security audit
```

### Monitoring CI

```bash
# Check workflow status
gh run list

# View specific run
gh run view <run-id>

# Download artifacts
gh run download <run-id>
```

---

## Troubleshooting

### Virtual Environment Issues

```bash
# Recreate virtual environment
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Port Conflicts

```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>

# Use different port
python CONTENT_CREATOR_FRAMEWORK/main_api.py --port 8001
```

### Node Modules Issues

```bash
# Clear npm cache
npm cache clean --force

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

### Git Issues

```bash
# Undo last commit
git reset HEAD~1

# Stash uncommitted changes
git stash

# Clean up branches
git branch -d feature/old-branch
```

---

## Useful Commands

### Development

```bash
# Start all services
make dev  # If Makefile available

# Backend
python CONTENT_CREATOR_FRAMEWORK/main_api.py

# Frontend
cd qms-ui && npm start

# Docker
docker-compose up --build
```

### Testing

```bash
# All tests
npm test && pytest

# Coverage
npm test -- --coverage
pytest --cov

# Specific test
pytest test_api.py::TestHealthEndpoints::test_health_check
```

### Linting & Formatting

```bash
# Python
black CONTENT_CREATOR_FRAMEWORK/
flake8 CONTENT_CREATOR_FRAMEWORK/

# JavaScript
npm run lint
npm run format
```

### Database

```bash
# Run migrations
alembic upgrade head

# Create migration
alembic revision --autogenerate -m "description"

# Seed data
python scripts/seed_database.py
```

---

## Getting Help

### Documentation
- Architecture: `docs/ARCHITECTURE.md`
- API: `docs/API.md`
- Deployment: `docs/DEPLOYMENT.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`

### Communication
- Issues: GitHub Issues
- Discussions: GitHub Discussions
- Code Review: Pull Requests

### Contact
- Email: dev@example.com
- Slack: #development channel

---

**Last Updated**: January 2026
**Version**: 1.0.0
