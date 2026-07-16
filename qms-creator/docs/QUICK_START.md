# Quick Start Guide - Cannabis EU GMP QMS Creator

Welcome! This guide will get you up and running with the Cannabis EU GMP QMS Creator in just a few minutes.

## Table of Contents
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Running Locally](#running-locally)
- [Using Docker](#using-docker)
- [First Steps](#first-steps)
- [Common Tasks](#common-tasks)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Local Development
- **Python**: 3.12 or higher
- **Node.js**: 18 or higher (for frontend)
- **npm**: 8 or higher
- **PostgreSQL**: 13 or higher (optional, uses JSON fallback)
- **Git**: 2.25 or higher
- **4GB RAM** minimum, **8GB** recommended
- **2GB** free disk space

### Docker
- **Docker**: 20.10 or higher
- **Docker Compose**: 2.0 or higher
- **4GB RAM** minimum for Docker
- **2GB** free disk space

### Supported Operating Systems
- Linux (Ubuntu 20.04+, CentOS 8+)
- macOS (10.15+, Intel or Apple Silicon)
- Windows 10/11 (with WSL2 recommended)

---

## Installation

### Option 1: Local Development Setup

#### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/cannabis-qms-creator.git
cd cannabis-qms-creator
```

#### 2. Set Up Python Backend

```bash
# Create virtual environment
python3.12 -m venv .venv

# Activate virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Create .env file for configuration
cp .env.example .env

# Edit .env with your settings (optional)
# nano .env  # or open in your editor
```

#### 3. Set Up React Frontend

```bash
# Navigate to frontend directory
cd qms-ui

# Install Node dependencies
npm install

# Return to project root
cd ..
```

#### 4. Initialize Database (Optional)

```bash
# If using PostgreSQL instead of JSON:
alembic upgrade head
```

---

### Option 2: Docker Compose Setup (Recommended for New Users)

#### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/cannabis-qms-creator.git
cd cannabis-qms-creator
```

#### 2. Create Environment File
```bash
cp .env.example .env

# Edit .env if needed (optional for basic usage)
# nano .env
```

#### 3. Start Services
```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

## Running Locally

### Starting the Backend

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Start FastAPI server
python CONTENT_CREATOR_FRAMEWORK/main_api.py

# Or with uvicorn directly
uvicorn CONTENT_CREATOR_FRAMEWORK.main_api:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at: **http://localhost:8000**

API Documentation: **http://localhost:8000/docs**

### Starting the Frontend

In a new terminal:

```bash
# Navigate to frontend directory
cd qms-ui

# Start development server
npm start

# Or use the run script
npm run dev
```

Frontend will be available at: **http://localhost:3000**

---

## Using Docker

### Start All Services

```bash
# Build and start in foreground (shows logs)
docker-compose up --build

# Or start in background
docker-compose up -d --build
```

### Access Services
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PgAdmin** (if enabled): http://localhost:5050

### Useful Docker Commands

```bash
# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Execute commands in container
docker-compose exec backend python -m pytest

# Access container shell
docker-compose exec backend /bin/bash

# Rebuild services
docker-compose build --no-cache

# Remove all containers and volumes
docker-compose down -v
```

---

## First Steps

### 1. Access the Application

Open your browser and navigate to:
- **http://localhost:3000** (Frontend)

### 2. Explore the Dashboard

The main dashboard shows:
- **Document Statistics**: Total documents, annexes, files
- **Document Hierarchy**: Organized by chapters and sections
- **Recent Activity**: Latest document changes

### 3. Generate Your First SOP

#### Step 1: Navigate to SOP Generator
Click "Generate SOP" in the main navigation

#### Step 2: Fill in Basic Information
- **SOP Name**: e.g., "Cultivation Standard Operating Procedure"
- **SOP Type**: Select from predefined types
- **Facility Context**: Information about your facility

#### Step 3: Complete Questionnaire
Answer questions about your specific operation:
- Facility characteristics
- Equipment and resources
- Personnel and training
- Specific requirements

#### Step 4: Generate Documents
Click "Generate" to create:
- Detailed SOP document (DOCX format)
- Audit report with recommendations
- Integration with existing documents

#### Step 5: Download Results
Download generated files from the results panel

### 4. Manage Documents

#### Viewing Documents
- Navigate to "Document Browser"
- Browse documents by chapter and department
- View detailed metadata and statistics

#### Creating Documents
- Click "Upload Document" in the browser
- Provide document details (title, department, version)
- Upload PDF or DOCX file
- Document automatically indexed and available

#### Updating Documents
- Select document from browser
- Click "Update" button
- Modify document information
- Changes are tracked in audit logs

---

## Common Tasks

### Task 1: Generate Multiple SOPs

```bash
# Option A: Using Web Interface (Easiest)
1. Open http://localhost:3000
2. Click "Generate SOP"
3. Complete the form
4. Click "Generate"
5. Download results

# Option B: Using API (For Automation)
curl -X POST http://localhost:8000/generate \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "sop_name": "My SOP",
    "sop_type": "Process",
    "facility_context": {"name": "My Facility"}
  }'
```

### Task 2: Upload Company Documents

1. Navigate to "Document Browser"
2. Click "Upload Document"
3. Fill in document details:
   - Title
   - Department
   - Version
   - Description
4. Select file to upload
5. Click "Upload"

### Task 3: Configure API Access

```bash
# Edit .env file
API_KEY=your-custom-api-key

# Use API with authentication
curl -X GET http://localhost:8000/documents \
  -H "X-API-Key: your-custom-api-key"
```

### Task 4: Run Tests

```bash
# Run all tests
pytest CONTENT_CREATOR_FRAMEWORK/tests/ -v

# Run API tests only
pytest CONTENT_CREATOR_FRAMEWORK/tests/test_api.py -v

# Run database tests only
pytest CONTENT_CREATOR_FRAMEWORK/tests/test_database.py -v

# Frontend tests
cd qms-ui && npm test
```

### Task 5: Seed Database with Sample Data

```bash
# Run seeding script
python scripts/seed_database.py

# Choose to clear existing data and reseed when prompted
```

### Task 6: Export Data

```bash
# Documents are automatically exportable from the UI
# API endpoint for exporting document data
curl -X GET http://localhost:8000/documents \
  -H "X-API-Key: your-api-key" > documents.json
```

---

## Environment Configuration

### Key Environment Variables

Create a `.env` file in the project root with these variables:

```env
# Backend Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
API_KEY=default-dev-key-change-in-production

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/qms_db

# Logging
LOG_LEVEL=INFO

# CORS
CORS_ORIGINS=http://localhost:3000

# LLM Configuration (Optional)
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
OLLAMA_URL=http://localhost:11434

# Frontend
REACT_APP_API_URL=http://localhost:8000
```

### Using Different Environments

```bash
# Development
export ENVIRONMENT=development
docker-compose -f docker-compose.dev.yml up

# Production
export ENVIRONMENT=production
docker-compose up -d
```

---

## Troubleshooting

### Issue: Port Already in Use

**Problem**: `Address already in use` error when starting services

**Solution**:
```bash
# Find process using port 8000 (backend)
lsof -i :8000

# Find process using port 3000 (frontend)
lsof -i :3000

# Kill the process
kill -9 <PID>

# Or use different ports
python main_api.py --port 8001
```

### Issue: Module Not Found Error

**Problem**: `ModuleNotFoundError: No module named 'CONTENT_CREATOR_FRAMEWORK'`

**Solution**:
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Set Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Issue: API Connection Refused

**Problem**: Frontend can't connect to backend

**Solution**:
```bash
# Check if backend is running
curl http://localhost:8000/health

# If not running, start it
python CONTENT_CREATOR_FRAMEWORK/main_api.py

# Check CORS_ORIGINS in .env
# Ensure frontend URL is included
CORS_ORIGINS=http://localhost:3000
```

### Issue: Database Connection Error

**Problem**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
```bash
# Check if using PostgreSQL or JSON fallback
# For JSON fallback (default), remove DATABASE_URL from .env

# For PostgreSQL, verify connection:
psql -U postgres -h localhost -d qms_db

# Or use Docker PostgreSQL:
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:13
```

### Issue: Permission Denied Error

**Problem**: `Permission denied` when executing scripts

**Solution**:
```bash
# Make scripts executable
chmod +x scripts/*.py
chmod +x *.sh

# Or run with python
python scripts/seed_database.py
```

### Issue: Docker Build Fails

**Problem**: `docker-compose up --build` fails

**Solution**:
```bash
# Clear Docker cache and rebuild
docker-compose down --volumes
docker system prune -a
docker-compose up --build

# Or check Docker logs
docker-compose logs

# Ensure Docker daemon is running
docker ps
```

### Issue: Tests Failing

**Problem**: Tests pass locally but fail in CI/CD

**Solution**:
```bash
# Ensure test dependencies are installed
pip install pytest pytest-cov

# Run tests with verbose output
pytest CONTENT_CREATOR_FRAMEWORK/tests/ -v -s

# Check for environment variables
echo $API_KEY
echo $DATABASE_URL

# Run individual test for debugging
pytest CONTENT_CREATOR_FRAMEWORK/tests/test_api.py::TestHealthEndpoints::test_health_check -v
```

---

## Next Steps

1. **Explore the Dashboard**: Get familiar with the UI
2. **Generate Your First SOP**: Follow the SOP Generator workflow
3. **Read Architecture Docs**: Understand the system design
4. **Configure for Production**: Follow deployment guide
5. **Integrate with Your Systems**: Use the API for automation

---

## Getting Help

### Documentation
- **API Documentation**: http://localhost:8000/docs
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Deployment**: See `docs/DEPLOYMENT.md`
- **Security**: See `docs/SECURITY.md`

### Common Resources
- **Issue Tracker**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Contributing**: See `CONTRIBUTING.md`

### Support
For issues and questions:
1. Check troubleshooting section above
2. Review existing GitHub issues
3. Create a new issue with details
4. Include error logs and environment info

---

## Quick Reference

### Useful Commands

```bash
# Start everything locally
source .venv/bin/activate && python CONTENT_CREATOR_FRAMEWORK/main_api.py &
cd qms-ui && npm start

# Start with Docker
docker-compose up --build

# Run tests
pytest CONTENT_CREATOR_FRAMEWORK/tests/ -v

# Access API
curl http://localhost:8000/docs

# Check health
curl http://localhost:8000/health

# Generate SOP via API
curl -X POST http://localhost:8000/generate \
  -H "X-API-Key: test-api-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"sop_name":"Test","sop_type":"Process","facility_context":{}}'
```

### Port Reference
| Service | Port | URL |
|---------|------|-----|
| Frontend | 3000 | http://localhost:3000 |
| Backend API | 8000 | http://localhost:8000 |
| API Docs | 8000 | http://localhost:8000/docs |
| PostgreSQL | 5432 | localhost:5432 |
| PgAdmin | 5050 | http://localhost:5050 |

---

**Last Updated**: January 2026
**Version**: 1.0.0

For the latest version, visit: [GitHub Repository](https://github.com/yourusername/cannabis-qms-creator)
