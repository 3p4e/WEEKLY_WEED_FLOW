# Changelog

All notable changes to the Cannabis EU GMP QMS Creator project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Code Quality & Type Safety
- Created comprehensive TypeScript type definitions in `src/types/questionnaire.ts`
- Fixed all 15 ESLint errors across frontend codebase
- Added proper type annotations replacing all `any` types with strict interfaces
- Implemented proper React Hook dependencies with `useCallback` wrapper

#### Frontend Testing Infrastructure
- Added Vitest test runner with jsdom environment
- Integrated React Testing Library for component testing
- Created 5 comprehensive test suites covering critical user flows:
  - `App.test.tsx` - Main app routing and UI interactions
  - `Dashboard.test.tsx` - Dashboard statistics and navigation
  - `Questionnaire.test.tsx` - Form submission and validation
  - `DocumentBrowser.test.tsx` - Document hierarchy navigation
  - `useDocuments.test.ts` - API hooks for document management
- Configured test coverage reporting with 70% target threshold
- Added test scripts to `package.json`
- Added 6 testing dependencies to frontend

#### API Documentation & Security
- Enhanced OpenAPI/Swagger documentation with:
  - FastAPI app metadata (title, description, version, contact info)
  - 10 comprehensive Pydantic response models
  - Detailed endpoint summaries and descriptions
  - Endpoint grouping with tags for better organization
- Implemented API Key authentication using X-API-Key header
- Added rate limiting middleware with slowapi:
  - `/generate` endpoint: 5 requests/minute
  - `/submit-questionnaire` endpoint: 5 requests/minute
  - `/documents` POST: 5 requests/minute
  - `/analyze`, `/initialize-questionnaire`: 20 requests/minute
- Protected sensitive endpoints with authentication dependencies
- Added API key validation middleware to `auth.py`

#### Containerization & Orchestration
- Created `Dockerfile.backend` with:
  - Multi-stage build for optimized image size
  - Python 3.12-slim base image
  - Gunicorn + Uvicorn production server
  - Non-root user (qmsapi) for security
  - Health check configuration
  - Proper layer caching strategy

- Created `Dockerfile.frontend` with:
  - Multi-stage build (builder → production)
  - Node 22 Alpine for lightweight build stage
  - Nginx Alpine for static file serving
  - Security headers and SPA routing
  - Non-root user (nginx-user) for security
  - Health check configuration

- Created `docker-compose.yml` (production) with:
  - 3 services: backend (FastAPI), frontend (Nginx), postgres (PostgreSQL 16)
  - Named volumes for data persistence
  - Health checks for all services
  - Environment variable configuration
  - Network isolation with custom bridge network
  - Logging configuration with json-file driver

- Created `docker-compose.dev.yml` (development overrides) with:
  - Hot reload configuration for both services
  - Development database credentials
  - Optional PgAdmin service on port 5050
  - stdin_open and tty for development

- Created `.dockerignore` with 30+ exclusion patterns for optimized builds

- Created `nginx/nginx.conf` with:
  - 230+ lines of comprehensive configuration
  - SPA routing with fallback to index.html
  - API reverse proxy to backend service
  - Security headers (X-Content-Type-Options, X-Frame-Options, HSTS, CSP)
  - Gzip compression for text/javascript/json
  - Rate limiting zones for general and API traffic
  - Static asset caching (1 year for versioned files)
  - Buffer pooling and connection optimization
  - Non-root user execution

#### CI/CD Pipeline
- Created GitHub Actions CI workflow (`.github/workflows/ci.yml`) with:
  - **Backend Tests Job**: Python 3.12, pytest with coverage reporting
  - **Frontend Linting Job**: ESLint and Prettier checks
  - **Frontend Tests Job**: Vitest with coverage reporting
  - **Build Docker Images Job**: Multi-arch Docker image building
  - **Security Scanning Job**: Trivy, npm audit, safety checks
  - **Commit Linting Job**: Conventional Commits validation
  - Automatic code coverage upload to Codecov

- Created GitHub Actions Deploy workflow (`.github/workflows/deploy.yml`) with:
  - **Staging Deployment**: Auto-deploy on develop branch
  - **Production Deployment**: Manual approval required for main branch
  - Docker image building and tagging
  - SSH-based remote deployment
  - Smoke tests for health verification
  - Database migration execution (alembic)
  - Slack notifications on successful deployment

- Created `.pre-commit-config.yaml` with:
  - Python linting (Black, Flake8, MyPy, isort, pydocstyle)
  - TypeScript/JavaScript linting (ESLint, Prettier)
  - Dockerfile linting (Hadolint)
  - Markdown linting
  - Secret detection (detect-secrets)
  - YAML/JSON validation
  - Large file detection
  - Git hooks for pytest and vitest

#### Environment Configuration
- Created `.env.example` with 60+ documented environment variables
- Created `.env.development` with development-specific defaults
- Created `.env.production` with production-ready configuration template
- Enhanced `config/secure_manager.py` with:
  - `.env` file loading via python-dotenv
  - Environment-specific configuration support
  - Multi-file loading priority system
  - Environment variable auto-discovery

#### Documentation
- Created comprehensive `README.md` with:
  - Project overview and feature list
  - Technology stack documentation
  - Quick start guide (Docker and local)
  - Local development setup instructions
  - Configuration guide
  - API documentation link
  - Testing guide
  - Deployment overview
  - Troubleshooting section
  - Security information
  - Contributing guidelines
  - Performance optimization tips
  - ~1400 lines of detailed documentation

- Created `docs/API.md` (14KB) with:
  - Complete REST API reference
  - Authentication details
  - Rate limiting information
  - All endpoint documentation with examples
  - Request/response examples in multiple languages (cURL, Python, JavaScript)
  - Error handling and HTTP status codes
  - Data type documentation
  - Pagination and filtering examples
  - SDK documentation
  - Best practices for rate limiting and security

- Created `docs/DEPLOYMENT.md` (16KB) with:
  - Local development deployment guide
  - Docker deployment instructions
  - AWS deployment options (EC2, ECS, Lambda)
  - Google Cloud Platform (Cloud Run, GKE)
  - Azure deployment (Container Instances, App Service, AKS)
  - DigitalOcean deployment (App Platform, Droplets)
  - SSL/TLS configuration with Let's Encrypt
  - Database setup and migration procedures
  - Monitoring and logging configuration
  - Backup and recovery procedures
  - Production deployment checklist

- Created `CONTRIBUTING.md` (12KB) with:
  - Code of conduct
  - Development environment setup
  - Git workflow and branch naming conventions
  - Conventional Commits format specification
  - Code style guidelines (Python, TypeScript)
  - Testing requirements and examples
  - Pre-commit hooks setup
  - Security guidelines
  - Pull request process
  - Documentation standards
  - Performance considerations
  - Accessibility guidelines

#### Infrastructure Files
- Updated `requirements.txt` with:
  - Added `slowapi==0.1.8` for rate limiting
  - Added `python-dotenv==1.0.0` for environment management

- Updated `qms-ui/package.json` with:
  - Added vitest, @testing-library/react, @testing-library/jest-dom
  - Added @testing-library/user-event, @vitest/ui, jsdom
  - Added test scripts: test, test:ui, test:coverage

### Fixed

- Fixed unused variable warnings in error handlers
- Fixed React Hook dependency warnings with useCallback
- Fixed all TypeScript strict mode issues
- Fixed API rate limiting on sensitive endpoints

### Changed

- Restructured API endpoints with descriptive tags and summaries
- Improved error response consistency with status codes
- Enhanced logging with structured format support
- Updated Docker configuration for production-ready deployments

### Security

- Implemented API key authentication on all sensitive endpoints
- Added rate limiting to prevent abuse
- Configured comprehensive security headers in Nginx
- Added secret detection in pre-commit hooks
- Restricted CORS to specific origins in production configuration

## [1.0.0] - 2024-01-15

### Initial Release

- 77 pre-configured SOPs organized across 9 departments
- AI-powered document generation with multiple provider support
- Interactive questionnaire system for business requirement capture
- Multi-format document export (PDF, DOCX)
- Document hierarchy browser
- REST API with OpenAPI documentation
- React 19 frontend with TypeScript
- FastAPI backend with Python 3.12
- 100% backend test coverage (14/14 tests passing)
- Docker support for containerized deployment
- Development and production configurations

---

## Version History

### Upcoming Features (Roadmap)

- [ ] PostgreSQL full migration (currently JSON fallback available)
- [ ] Enhanced AI models integration with streaming responses
- [ ] Advanced analytics dashboard with metrics
- [ ] Multi-language support (i18n)
- [ ] Mobile application
- [ ] API rate limiting dashboard
- [ ] Audit trail and compliance reporting
- [ ] WebSocket support for real-time updates
- [ ] GraphQL endpoint alongside REST API
- [ ] Machine learning for document recommendations

### Known Issues

- JSON database backend used as fallback (PostgreSQL migration planned)
- Document generation time varies based on AI provider

### Deprecations

- Legacy JSON-only database support will be deprecated in v2.0
- Python < 3.12 no longer supported

---

## How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines.

---

## Links

- [README](README.md) - Main documentation
- [API Documentation](docs/API.md) - Complete API reference
- [Deployment Guide](docs/DEPLOYMENT.md) - Deployment instructions
- [Contributing Guide](CONTRIBUTING.md) - Contribution guidelines
- [GitHub Repository](https://github.com/yourusername/cannabis-qms-creator)

---

## Release Notes

For detailed information about each release, see the [GitHub Releases](https://github.com/yourusername/cannabis-qms-creator/releases) page.
