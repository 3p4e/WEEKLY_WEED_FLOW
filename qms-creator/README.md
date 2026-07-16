# Cannabis EU GMP QMS Creator

A comprehensive Quality Management System (QMS) document creator for the cannabis industry, specifically designed to comply with EU Good Manufacturing Practice (GMP) requirements. This application automates the generation of SOPs (Standard Operating Procedures), documentation, and quality-related documents.

## 📊 Project Status & Tracking

**Current Status:** ✅ **PRODUCTION READY** (Software Platform) | 🟡 **15% COMPLETE** (QMS Content)


## Features

- **77 Pre-configured SOPs** organized across 9 departments
- **AI-Powered Document Generation** using OpenAI, Anthropic, or Ollama
- **Interactive Questionnaire System** for capturing business requirements
- **Multi-format Export** (PDF, DOCX, Excel)
- **Document Hierarchy Browser** for easy navigation
- **REST API** with OpenAPI/Swagger documentation
- **Authentication & Rate Limiting** for API security
- **Docker Support** for easy deployment
- **Comprehensive Testing** with 100% backend coverage, 70%+ frontend coverage

## Technology Stack

### Backend
- **Python 3.12** with FastAPI
- **Uvicorn** (async server) + **Gunicorn** (production WSGI)
- **Pydantic** for request/response validation
- **OpenAPI/Swagger** auto-documentation
- **pytest** for testing (14/14 tests passing)

### Frontend
- **React 19** with TypeScript
- **Vite** (build tool)
- **TailwindCSS** for styling
- **Axios** for API communication
- **Vitest** + **React Testing Library** for testing

### Infrastructure
- **Docker & Docker Compose** for containerization
- **Nginx** as reverse proxy and static file server
- **PostgreSQL** for data persistence
- **GitHub Actions** for CI/CD

## Project Structure

```
Cannabis EU GMP QMS Creator/
├── CONTENT_CREATOR_FRAMEWORK/          # Backend application
│   ├── main_api.py                    # FastAPI application entry point
│   ├── qms_database.py                # Database management
│   ├── auth.py                        # API authentication
│   ├── tests/                         # Backend unit tests (100% coverage)
│   └── requirements.txt               # Python dependencies
├── qms-ui-v2/                            # Frontend application
│   ├── src/
│   │   ├── components/                # React components
│   │   ├── hooks/                     # Custom React hooks
│   │   ├── types/                     # TypeScript type definitions
│   │   └── App.tsx                    # Main app component
│   ├── package.json                   # Node dependencies
│   └── vitest.config.ts              # Frontend test configuration
├── nginx/
│   └── nginx.conf                     # Nginx reverse proxy config
├── .github/
│   └── workflows/                     # GitHub Actions CI/CD pipelines
│   ├── ci.yml                         # Test, lint, build jobs
│   └── deploy.yml                     # Staging/production deployment
├── Dockerfile.backend                 # Backend container image
├── Dockerfile.frontend                # Frontend container image
├── docker-compose.yml                 # Production orchestration
├── docker-compose.dev.yml            # Development orchestration
├── .env.example                       # Environment variables template
├── .env.development                   # Development-specific config
├── .env.production                    # Production-specific config
├── .pre-commit-config.yaml           # Pre-commit hooks for code quality
└── README.md                          # This file
```

## Quick Start

### Prerequisites

- Docker and Docker Compose (recommended)
- OR: Python 3.12, Node.js 22, PostgreSQL 16

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/cannabis-qms-creator.git
   cd cannabis-qms-creator
   ```

2. **Start with Docker Compose**
   ```bash
   # Development
   docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
   
   # Production
   docker-compose up --build
   ```

3. **Access the application**
   - Frontend: http://localhost:3000 (dev) or http://localhost (production)
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Local Development Setup

#### Backend

1. **Set up Python environment**
   ```bash
   cd CONTENT_CREATOR_FRAMEWORK
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp ../.env.example ../.env.development
   # Edit .env.development with your settings
   ```

4. **Run the application**
   ```bash
   python main_api.py
   ```

5. **Run tests**
   ```bash
   pytest tests/ -v --cov=.
   ```

#### Frontend

1. **Install dependencies**
   ```bash
   cd qms-ui-v2
   npm install
   ```

2. **Configure API URL**
   ```bash
   cp .env.example .env.development
   # Edit VITE_API_URL to point to your backend
   ```

3. **Start development server**
   ```bash
   npm run dev
   ```

4. **Run tests**
   ```bash
   npm run test
   npm run test:ui      # Interactive test UI
   npm run test:coverage # Coverage report
   ```

## Configuration

### Environment Variables

Configuration is managed through `.env` files with the following priority:

1. `.env.{ENVIRONMENT}` (e.g., `.env.production`)
2. `.env` (local overrides)
3. `.env.example` (defaults)

Key variables:

```bash
# API Configuration
BACKEND_HOST=localhost
BACKEND_PORT=8000
API_KEY=your-secure-api-key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/qms

# External Services
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
OLLAMA_URL=http://localhost:11434

# Security
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
RATE_LIMIT_ENABLED=true
```

See `.env.example` for complete list of available configurations.

## API Documentation

The API automatically generates OpenAPI/Swagger documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Authentication

Protected endpoints require an API key in the `X-API-Key` header:

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"sop_id": "SOP-001"}'
```

### Main Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Application health check |
| GET | `/documents` | List all documents |
| GET | `/documents/{id}` | Get document details |
| GET | `/documents/{id}/hierarchy` | Get document structure |
| POST | `/documents` | Upload new document |
| POST | `/generate` | Generate SOP from template |
| POST | `/submit-questionnaire` | Submit questionnaire responses |
| GET | `/stats` | Get system statistics |

## Testing

### Backend Tests

```bash
cd CONTENT_CREATOR_FRAMEWORK
pytest tests/ -v                    # Run all tests
pytest tests/ --cov=.              # With coverage
pytest tests/test_api.py -v        # Specific test file
```

**Coverage**: 100% (14/14 tests passing)

### Frontend Tests

```bash
cd qms-ui-v2
npm run test                        # Run all tests
npm run test:watch                 # Watch mode
npm run test:ui                    # Interactive UI
npm run test:coverage              # Coverage report
```

**Coverage Target**: >70%

### Pre-commit Hooks

Install pre-commit hooks for automatic code quality checks:

```bash
pip install pre-commit
pre-commit install

# Run hooks on all files
pre-commit run --all-files

# Skip hooks for a commit
git commit --no-verify
```

Hooks include:
- Black (Python formatting)
- Flake8 (Python linting)
- MyPy (Python type checking)
- ESLint (JavaScript/TypeScript linting)
- Prettier (JavaScript/TypeScript formatting)
- Secret detection

## Deployment

### Docker Deployment

1. **Build images**
   ```bash
   docker build -f Dockerfile.backend -t qms-api:latest .
   docker build -f Dockerfile.frontend -t qms-ui:latest .
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose -f docker-compose.yml up -d
   ```

3. **Verify deployment**
   ```bash
   docker-compose ps
   docker-compose logs -f
   ```

### Production Configuration

1. **Update environment**
   ```bash
   cp .env.production /path/to/deployment/
   # Edit with production values
   ```

2. **Configure database**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

3. **Enable HTTPS**
   - Update `nginx/nginx.conf` with SSL certificates
   - Set `SSL_CERT_PATH` and `SSL_KEY_PATH` in `.env.production`

4. **Setup monitoring**
   - Configure Sentry for error tracking: `SENTRY_DSN`
   - Enable structured logging: `LOG_FORMAT=json`

### Cloud Deployment

See `docs/DEPLOYMENT.md` for detailed guides for:
- AWS (EC2, ECS, Lambda)
- Google Cloud Platform (Cloud Run, GKE)
- Azure (App Service, Container Instances)
- Digital Ocean (App Platform)

## CI/CD Pipeline

GitHub Actions workflows automatically:

1. **Run tests** on pull requests
2. **Check code quality** (linting, formatting, security)
3. **Build Docker images** for verified commits
4. **Deploy to staging** on develop branch
5. **Deploy to production** on main branch (with approval)

Workflows are defined in `.github/workflows/`:
- `ci.yml` - Continuous Integration pipeline
- `deploy.yml` - Deployment pipeline

## Development Workflow

1. **Create feature branch**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Make changes and test**
   ```bash
   # Backend changes
   cd CONTENT_CREATOR_FRAMEWORK
   pytest tests/ -v
   
   # Frontend changes
   cd qms-ui-v2
   npm run test
   npm run lint
   ```

3. **Commit with conventional commits**
   ```bash
   git commit -m "feat: add new questionnaire question"
   ```

4. **Push and create pull request**
   ```bash
   git push origin feature/my-feature
   ```

5. **CI pipeline runs automatically**
   - All checks must pass before merge

See `CONTRIBUTING.md` for detailed guidelines.

## Troubleshooting

### Backend Issues

**Port 8000 already in use**
```bash
lsof -i :8000
kill -9 <PID>
```

**Database connection error**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection string in .env
grep DATABASE_URL .env
```

**Tests failing**
```bash
# Clear pytest cache
rm -rf .pytest_cache __pycache__

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Frontend Issues

**Port 3000 already in use**
```bash
lsof -i :3000
kill -9 <PID>
```

**Module not found errors**
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

**Tests not running**
```bash
# Ensure vitest is installed
npm install --save-dev vitest

# Clear vitest cache
rm -rf node_modules/.vitest
npm run test -- --no-cache
```

### Docker Issues

**Container won't start**
```bash
# Check logs
docker-compose logs backend
docker-compose logs frontend

# Restart containers
docker-compose restart

# Full rebuild
docker-compose down
docker-compose up --build
```

## Performance Optimization

### Backend Optimization
- Database connection pooling (configured in `.env`)
- Request caching with Redis (optional)
- Async request handling with Uvicorn
- Rate limiting on expensive endpoints

### Frontend Optimization
- Code splitting with Vite
- Lazy loading of components
- Image optimization
- Gzip compression enabled in Nginx

### Database Optimization
- Indexed queries for fast lookups
- Connection pooling
- Query optimization in SQLAlchemy
- Prepared statements to prevent SQL injection

## Security

### Built-in Security Features

1. **API Authentication** - X-API-Key header required
2. **Rate Limiting** - Prevents brute force attacks
3. **CORS Configuration** - Restricts cross-origin requests
4. **Security Headers** - Set by Nginx
   - X-Content-Type-Options: nosniff
   - X-Frame-Options: DENY
   - Strict-Transport-Security
   - Content-Security-Policy
5. **Input Validation** - Pydantic validation on all endpoints
6. **Secret Detection** - Pre-commit hooks detect hardcoded secrets
7. **Dependency Scanning** - GitHub Actions security checks

### Security Checklist

- [ ] Update API_KEY in production `.env`
- [ ] Update all database passwords
- [ ] Enable SSL/TLS certificates
- [ ] Configure CORS_ORIGINS for production domains
- [ ] Enable Sentry for error tracking
- [ ] Set up backup strategy
- [ ] Configure firewall rules
- [ ] Review and rotate API keys regularly

## Monitoring & Logging

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General application events
- **WARNING**: Warning messages for potential issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical errors requiring immediate attention

### Viewing Logs

```bash
# Docker logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Application logs
tail -f logs/qms.log

# Structured JSON logs
grep "ERROR" logs/qms.log | jq '.'
```

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Database connection
curl http://localhost:8000/api/health

# Full system status
docker-compose ps
```

## Contributing

We welcome contributions! Please see `CONTRIBUTING.md` for guidelines on:
- Code style and standards
- Commit message format
- Testing requirements
- Pull request process

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Support

For issues, questions, or suggestions:

1. Check existing GitHub issues
2. Create a new issue with detailed information
3. Contact the development team

## Changelog

See `CHANGELOG.md` for version history and updates.

## Roadmap

Planned features:
- [ ] PostgreSQL full migration (currently JSON fallback available)
- [ ] Enhanced AI models integration
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Mobile application
- [ ] API rate limiting dashboard
- [ ] Audit trail and compliance reports

## Authors

Cannabis EU GMP QMS Creator Development Team

## Acknowledgments

- Inspired by pharmaceutical industry QMS best practices
- Built with FastAPI, React, and Docker
- Uses AI for intelligent document generation
