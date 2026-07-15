# Contributing to Cannabis EU GMP QMS Creator

Thank you for your interest in contributing to the Cannabis EU GMP QMS Creator! This document provides guidelines and procedures for contributing to the project.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and professional in all interactions.

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/yourusername/Cannabis-EU-GMP-QMS-Creator.git
cd "Cannabis EU GMP QMS Creator"
```

### 2. Setup Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Frontend setup
cd qms-ui
npm install
cd ..
```

### 3. Run Tests Locally

```bash
# Backend tests
pytest CONTENT_CREATOR_FRAMEWORK/tests/

# Frontend tests
cd qms-ui
npm test
npm run build
cd ..
```

## Development Workflow

### Branch Strategy

- `main` - Production-ready code
- `develop` - Development branch (base for feature branches)
- `feature/*` - Feature branches (e.g., `feature/add-user-auth`)
- `bugfix/*` - Bug fix branches (e.g., `bugfix/fix-pdf-rendering`)
- `docs/*` - Documentation updates

### Creating a Feature Branch

```bash
# Update develop branch
git fetch origin
git checkout develop
git pull origin develop

# Create feature branch
git checkout -b feature/your-feature-name
```

### Commit Message Conventions

Follow conventional commits format:

```
type(scope): subject

body

footer
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation changes
- `style` - Code style (formatting, missing semicolons, etc.)
- `refactor` - Code refactoring
- `perf` - Performance improvements
- `test` - Test additions/updates
- `ci` - CI/CD changes
- `chore` - Build, dependencies, etc.

**Examples:**
```
feat(pdf): add Cyrillic font support for Macedonian text

fix(questionnaire): handle empty sections gracefully

docs(api): update endpoint documentation

test(frontend): add DocumentBrowser component tests
```

## Code Standards

### Python Code

**Style Guide:** PEP 8 with Black formatter

```bash
# Format code
black CONTENT_CREATOR_FRAMEWORK/ scripts/

# Check style
flake8 CONTENT_CREATOR_FRAMEWORK/ scripts/

# Type checking
mypy CONTENT_CREATOR_FRAMEWORK/
```

**Naming Conventions:**
- Functions/variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

**Documentation:**
- Module docstrings required
- Function docstrings with type hints
- Complex logic needs comments

**Example:**
```python
"""Module for document processing and PDF generation."""

from typing import Optional, Dict, Any

def generate_pdf(
    content: str,
    metadata: Dict[str, Any],
    output_path: Optional[str] = None
) -> bytes:
    """
    Generate a PDF from markdown content.
    
    Args:
        content: Markdown content to convert
        metadata: Document metadata (title, author, etc.)
        output_path: Optional path to save PDF file
        
    Returns:
        PDF file as bytes
        
    Raises:
        ValueError: If content is empty
        IOError: If output path is not writable
    """
    if not content:
        raise ValueError("Content cannot be empty")
    
    # Implementation...
```

### TypeScript/React Code

**Style Guide:** ESLint + Prettier configuration included

```bash
# Format code
cd qms-ui
npm run format

# Lint code
npm run lint

# Type check
npm run type-check
```

**Naming Conventions:**
- Functions/variables: `camelCase`
- Components: `PascalCase`
- Types/Interfaces: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Unused variables: prefix with `_`

**Component Example:**
```typescript
import React from 'react';
import type { QMSDocument } from '../types/document';

interface DocumentListProps {
  documents: QMSDocument[];
  onSelect: (doc: QMSDocument) => void;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  onSelect,
}) => {
  return (
    <div className="document-list">
      {documents.map((doc) => (
        <button key={doc.id} onClick={() => onSelect(doc)}>
          {doc.title}
        </button>
      ))}
    </div>
  );
};
```

## Testing Requirements

### Backend Testing

- Minimum 80% code coverage
- All public functions tested
- Error cases tested
- Integration tests for API endpoints

```bash
# Run with coverage
pytest --cov=CONTENT_CREATOR_FRAMEWORK CONTENT_CREATOR_FRAMEWORK/tests/

# Generate HTML report
pytest --cov=CONTENT_CREATOR_FRAMEWORK --cov-report=html
```

### Frontend Testing

- Minimum 70% component coverage
- Critical user flows tested
- User interactions tested
- Mock external dependencies

```bash
# Run tests
cd qms-ui
npm test

# Coverage report
npm run test:coverage
```

### Test File Naming

- Python: `test_*.py` or `*_test.py`
- TypeScript: `*.test.ts` or `*.test.tsx`
- Location: `__tests__` directory or alongside source

### Example Tests

**Python:**
```python
import pytest
from CONTENT_CREATOR_FRAMEWORK.models import Document

def test_document_creation():
    """Test Document model creation."""
    doc = Document(
        id="test-1",
        code="DOC-001",
        title="Test Document",
        department="QA",
        status="draft",
        version="1.0"
    )
    
    assert doc.id == "test-1"
    assert doc.title == "Test Document"
    assert doc.status == "draft"

def test_document_invalid_status():
    """Test invalid status raises error."""
    with pytest.raises(ValueError):
        Document(
            id="test-2",
            code="DOC-002",
            title="Invalid",
            department="QA",
            status="invalid",  # Invalid status
            version="1.0"
        )
```

**TypeScript:**
```typescript
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DocumentList } from '../DocumentList';

describe('DocumentList', () => {
  it('renders document list', () => {
    const docs = [
      { id: '1', code: 'DOC-001', title: 'Test' }
    ];
    
    render(<DocumentList documents={docs} onSelect={vi.fn()} />);
    
    expect(screen.getByText('Test')).toBeInTheDocument();
  });
});
```

## Pull Request Process

### 1. Before Submitting

- [ ] Code follows style guidelines
- [ ] All tests pass locally
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] No console warnings/errors
- [ ] Commits follow convention

### 2. Create Pull Request

**Title Format:** `type(scope): description`

**Description Template:**
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe testing performed

## Checklist
- [ ] Tests pass
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No breaking changes
- [ ] Self-reviewed changes

## Screenshots (if applicable)
Add screenshots for UI changes
```

### 3. Code Review

- Expect feedback from maintainers
- Be open to suggestions
- Request changes and push updates
- CI/CD pipeline must pass

### 4. Merge

Once approved:
- Squash commits (for feature branches)
- Merge to develop, not main
- Delete branch after merge

## Documentation

### When to Document

- New API endpoints
- New public functions
- Changed behavior
- New features
- Configuration options

### Documentation Locations

- **API:** `docs/API.md` or inline with code
- **Features:** `docs/` directory
- **Setup:** `README.md` or relevant guide
- **Code:** Docstrings in code

### Documentation Example

```markdown
## Feature: Questionnaire System

### Overview
Users can fill out a questionnaire to generate SOPs.

### Usage

```python
from questionnaire import QuestionnaireGenerator

gen = QuestionnaireGenerator()
schema = gen.get_schema()
answers = gen.process_answers(user_input)
```

### API Endpoint

```
POST /questionnaire/schema
GET /questionnaire/schema
```

See [API.md](docs/API.md) for full reference.
```

## Issue Reporting

### Bug Reports

Provide:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (OS, Python version, etc.)
- Screenshots/logs if applicable

### Feature Requests

Provide:
- Use case/motivation
- Proposed solution
- Alternative approaches
- Any additional context

### Issue Template

```markdown
## Description
[Clear, concise description]

## Steps to Reproduce
1. [First step]
2. [Second step]
3. [...]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Environment
- OS: [Windows/macOS/Linux]
- Python: [3.12]
- Node: [18.x]

## Logs/Screenshots
[Attach relevant logs or screenshots]
```

## Development Tips

### Hot Reload

**Backend:**
```bash
python -m uvicorn CONTENT_CREATOR_FRAMEWORK.main_api:app --reload
```

**Frontend:**
```bash
cd qms-ui
npm run dev
```

### Database Testing

For testing without PostgreSQL:
```python
# Use in-memory SQLite
from CONTENT_CREATOR_FRAMEWORK.database.session import DatabaseConfig

config = DatabaseConfig(database_url="sqlite:///:memory:")
```

### Debugging

**Python:**
```python
import pdb
pdb.set_trace()  # Breakpoint

# Or use debugger
python -m pdb CONTENT_CREATOR_FRAMEWORK/main_api.py
```

**TypeScript/React:**
```typescript
console.log(variable);  // Quick log
debugger;  // Breakpoint in browser DevTools
```

### Common Tasks

```bash
# Format all code
black CONTENT_CREATOR_FRAMEWORK/ scripts/
cd qms-ui && npm run format && cd ..

# Run all tests
pytest CONTENT_CREATOR_FRAMEWORK/tests/
cd qms-ui && npm test && cd ..

# Build frontend
cd qms-ui && npm run build && cd ..

# Start full stack
docker-compose up -d

# View logs
docker-compose logs -f
```

## Performance Considerations

- Frontend bundles should be < 500KB
- API responses should complete in < 500ms
- Database queries should use indexes
- Avoid N+1 query problems

## Security Considerations

- Never commit secrets (.env files, API keys)
- Validate all user input
- Use parameterized queries (SQLAlchemy handles this)
- Sanitize output to prevent XSS
- Use security headers
- Keep dependencies updated

## Release Process

1. Create release branch from `develop`
2. Update version numbers
3. Update CHANGELOG
4. Merge to `main` with version tag
5. Create GitHub release
6. Deploy to production

## Getting Help

- **Issues:** Check existing issues first
- **Discussions:** GitHub Discussions for questions
- **Documentation:** Check `docs/` folder
- **Code:** Read related source files and comments

## Community

We appreciate all contributions! Whether it's:
- Code improvements
- Bug reports
- Documentation updates
- Feature suggestions
- Testing and feedback

All help is welcome. Thank you for contributing to making the Cannabis EU GMP QMS Creator better!

---

**Happy Contributing! 🎉**
