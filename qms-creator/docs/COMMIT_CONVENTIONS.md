# Commit Message Conventions - Cannabis EU GMP QMS Creator

This document outlines the commit message conventions for the Cannabis EU GMP QMS Creator project, following the Conventional Commits specification.

## Overview

Commit messages should be written in a clear, structured format that:
- Communicates intent clearly
- Makes git history readable
- Enables automated changelog generation
- Facilitates bisecting and searching

## Format

### Basic Structure

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Example

```
feat(api): Add SOP generation endpoint

Add new POST /generate endpoint that accepts SOP request parameters
and returns generated SOP document and audit report.

Implements RAG-based content retrieval and LLM-based writing.

Closes #123
```

## Components

### Type

The type indicates the kind of change being made:

| Type | Description | Example |
|------|-------------|---------|
| **feat** | New feature | `feat(ui): Add dark mode toggle` |
| **fix** | Bug fix | `fix(api): Correct document ordering` |
| **docs** | Documentation changes | `docs: Update API documentation` |
| **style** | Code style changes (formatting, missing semicolons, etc.) | `style: Format code with Black` |
| **refactor** | Code refactoring without feature/bug changes | `refactor(core): Simplify SOP generator` |
| **perf** | Performance improvements | `perf(db): Add index to documents table` |
| **test** | Adding or updating tests | `test(api): Add health check tests` |
| **ci** | CI/CD configuration changes | `ci: Update GitHub Actions workflow` |
| **chore** | Maintenance tasks, dependencies | `chore: Update dependencies` |
| **build** | Build system changes | `build: Update Docker configuration` |
| **revert** | Reverting a previous commit | `revert: Revert "fix: incorrect validation"` |

### Scope

The scope specifies which part of the codebase is affected:

**Backend Scopes**:
- `api` - API endpoints
- `db` - Database models and queries
- `auth` - Authentication and authorization
- `error` - Error handling
- `validation` - Input validation
- `security` - Security features
- `logging` - Logging configuration
- `monitoring` - Monitoring and metrics
- `rag` - RAG document classifier
- `search` - Vector search engine
- `audit` - Regulatory auditor
- `sop-gen` - SOP generator workflow
- `core` - Core framework

**Frontend Scopes**:
- `ui` - User interface components
- `hooks` - React hooks
- `types` - TypeScript interfaces
- `styles` - CSS/styling
- `form` - Form components
- `dashboard` - Dashboard components

**General Scopes**:
- `config` - Configuration files
- `deps` - Dependencies
- `docs` - Documentation
- `ci` - CI/CD
- `docker` - Docker configuration

### Subject

The subject line should:
- Use imperative mood ("add" not "added" or "adds")
- Not capitalize the first letter (unless proper noun)
- Not include a period at the end
- Be concise (50 characters or less is preferred)
- Describe what the code does, not why

**Good Examples**:
- `fix: correct document validation error`
- `feat: implement questionnaire persistence`
- `refactor: simplify PDF generation logic`

**Bad Examples**:
- `Fixed bug in document upload` (past tense)
- `Updated the API endpoint to handle new response format` (too long)
- `WIP: work in progress` (incomplete)

### Body

The body should:
- Explain **what** and **why**, not **how**
- Be wrapped at 72 characters
- Be separated from the subject by a blank line
- Use bullet points for multiple changes
- Include relevant context

**Good Example**:
```
Add caching to document retrieval to improve performance.

Previously, every document request queried the database,
causing slow response times on large document sets.

Implements Redis-based caching with 1-hour TTL. Cache is
invalidated on document updates.

Benefits:
- 80% reduction in API response time
- Reduced database load
- Better user experience for large facilities
```

### Footer

The footer should contain:
- References to issues: `Fixes #123`, `Closes #456`
- Breaking changes: `BREAKING CHANGE: description`
- Co-authored contributors: `Co-authored-by: Name <email@example.com>`

**Examples**:
```
Closes #123
Fixes #456, #789

BREAKING CHANGE: API endpoint /sop-draft has been removed.
Use /questionnaire-schema instead.

Co-authored-by: Jane Doe <jane@example.com>
```

## Examples by Type

### Feature

```
feat(api): Add document bulk upload endpoint

Implement POST /documents/bulk endpoint that accepts multiple
documents and processes them in parallel.

Features:
- Support for up to 100 documents per request
- Progress tracking via WebSocket
- Automatic retry on failure
- Detailed error reporting

Closes #234
```

### Bug Fix

```
fix(validation): Correct SOP name length validation

SOP names can now be up to 200 characters as per requirements.
Previous limit was incorrectly set to 100 characters.

Updated:
- Pydantic model validation
- Database schema constraints
- Frontend input validation

Fixes #512
```

### Documentation

```
docs: Add section on database indexing strategy

Document the rationale behind current index design and provide
guidelines for adding new indexes.

Includes examples of query performance before/after indexing.
```

### Refactoring

```
refactor(sop-gen): Extract content generation into separate module

Move content generation logic from integrated_sop_generator_workflow.py
into new content_generator.py module for better separation of concerns.

No functional changes. All tests passing.
```

### Performance Improvement

```
perf(db): Add indexes to frequently queried columns

Add composite index on (department, status) columns
and single index on created_at for document queries.

Impact:
- Document list query: 250ms → 50ms
- Department filter: 180ms → 30ms
```

### Tests

```
test(api): Add comprehensive endpoint tests

Add 15 new test cases covering:
- Valid request handling
- Invalid input validation
- Authentication failures
- Error responses
- Rate limiting

Coverage increased from 65% to 78%.
```

### Dependencies

```
chore(deps): Update FastAPI to 0.104.0

Update FastAPI and dependencies to latest stable version.
Includes security patches and performance improvements.

Breaking changes: None
Requires: Python 3.12+
```

### Breaking Changes

```
feat(api)!: Redesign document metadata endpoint

BREAKING CHANGE: Response format for /api/documents/{code} has changed.

Old format:
{
  "document": { ... }
}

New format:
{
  "id": "...",
  "code": "...",
  "metadata": { ... }
}

Migration guide: See docs/API_MIGRATION_v2.md
```

## Commit Workflow

### Single Feature

```bash
# Work on feature
git checkout -b feature/new-endpoint
# ... make changes ...
git add .
git commit -m "feat(api): Add document export endpoint"
git push origin feature/new-endpoint
```

### Multiple Related Changes

```bash
# Backend change
git add CONTENT_CREATOR_FRAMEWORK/
git commit -m "feat(api): Add export functionality"

# Frontend change
git add qms-ui/
git commit -m "feat(ui): Add export button to document viewer"

# Tests
git add CONTENT_CREATOR_FRAMEWORK/tests/
git commit -m "test(api): Add export endpoint tests"
```

### Bug Fix Workflow

```bash
git checkout -b bugfix/validation-issue
# ... fix bug ...
git add .
git commit -m "fix(validation): Correct email validation regex"
git push origin bugfix/validation-issue
```

### Amending Commits

```bash
# Fix last commit message
git commit --amend -m "feat(api): Correct endpoint description"
git push --force-with-lease origin feature/branch

# Add forgotten changes to last commit
git add forgotten_file.py
git commit --amend --no-edit
git push --force-with-lease origin feature/branch
```

## Best Practices

### Do

✅ **Do write commits that are atomic** (one logical change per commit)
```bash
git commit -m "feat(db): Add document audit logging"  # ✓ Good
```

✅ **Do use imperative mood**
```bash
git commit -m "feat: Add caching to document retrieval"  # ✓ Good
```

✅ **Do provide context in the body**
```bash
git commit -m "fix: Handle missing API responses

Previously, missing API responses caused the application
to crash with undefined errors. Now returns graceful error message.

Fixes #456"  # ✓ Good
```

✅ **Do reference issues**
```bash
git commit -m "feat: Implement dark mode

Closes #789"  # ✓ Good
```

### Don't

❌ **Don't mix multiple unrelated changes**
```bash
git commit -m "feat: Add caching and fix validation"  # ✗ Bad
```

❌ **Don't use past tense**
```bash
git commit -m "feat: Added dark mode"  # ✗ Bad
```

❌ **Don't include issue numbers in subject**
```bash
git commit -m "feat: #234 Add dark mode"  # ✗ Bad
# Use footer instead: Closes #234
```

❌ **Don't write vague messages**
```bash
git commit -m "fix: stuff"  # ✗ Bad
git commit -m "update files"  # ✗ Bad
```

## Linting Commits

### Using commitlint

```bash
# Install commitlint
npm install --save-dev @commitlint/config-conventional @commitlint/cli

# Create commitlint.config.js
echo "module.exports = {extends: ['@commitlint/config-conventional']}" > commitlint.config.js

# Set up Git hook
npx husky install
npx husky add .husky/commit-msg 'npx --no -- commitlint --edit "$1"'
```

### Commit Message Checklist

Before committing, ask yourself:

- [ ] Does the type accurately describe the change?
- [ ] Is the scope specific and relevant?
- [ ] Does the subject use imperative mood?
- [ ] Is the subject line ≤ 50 characters?
- [ ] Is the change atomic (one logical unit)?
- [ ] Does the body explain why, not just what?
- [ ] Are related issues referenced?
- [ ] Are any breaking changes documented?

## Git Log Examples

### Viewing Commit History

```bash
# View commits with full details
git log --oneline

# View commits with graph
git log --graph --oneline --decorate

# View commits for specific file
git log --oneline -- path/to/file

# View commits since last tag
git log --oneline $(git describe --tags --abbrev=0)..HEAD

# View commits for specific type
git log --oneline --grep="^feat"
```

## Automation

### Generating Changelogs

Properly formatted commits enable automated changelog generation:

```bash
# Using conventional-changelog
npm install --save-dev conventional-changelog-cli
npx conventional-changelog -p angular -i CHANGELOG.md -s

# Using git-log
git log --oneline | grep "^feat\|^fix" > CHANGELOG.md
```

## References

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Angular Commit Guidelines](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#-commit-message-guidelines)
- [GitFlow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow)

---

**Last Updated**: January 2026
**Version**: 1.0.0
