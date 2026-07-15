# Cannabis EU GMP QMS Creator - Production Deployment Guide

## Overview

This guide will help you deploy the Cannabis EU GMP QMS Creator platform in a production environment. The system consists of:

- **Backend**: FastAPI application with RAG document analysis
- **Frontend**: React-based web interface (pre-built in `qms-ui/dist`)
- **Database**: PostgreSQL (containerized or external)
- **Reverse Proxy**: Nginx for serving frontend and proxying API

## Prerequisites

- Linux/Unix system (Ubuntu 20.04+, RHEL 8+, or similar)
- Python 3.12+
- Node.js 18+ (for frontend build, optional as pre-built exists)
- PostgreSQL 13+ (or use containerized version)
- Docker and Docker Compose (optional, for containerized deployment)

## Quick Start

### Option 1: Docker Compose (Recommended for Production)

```bash
# 1. Clone or navigate to project directory
cd "Cannabis EU GMP QMS Creator"

# 2. Create production environment file
cp .env.example .env.production

# 3. Edit environment variables
nano .env.production  # or use your preferred editor

# 4. Start the stack
docker-compose up --build -d

# 5. Check logs
docker-compose logs -f

# 6. Verify deployment
curl http://localhost:8000/health  # Backend health
curl http://localhost/health       # Frontend health (via Nginx)
```

### Option 2: Manual Deployment (No Docker)

```bash
# 1. Set up environment
cd "Cannabis EU GMP QMS Creator"
cp .env.example .env.production
nano .env.production  # Configure variables

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Start PostgreSQL (if not already running)
sudo systemctl start postgresql

# 4. Initialize database
# Edit DATABASE_URL in .env.production to point to your PostgreSQL instance
# Run migrations:
alembic upgrade head

# 5. Start backend
python -m uvicorn CONTENT_CREATOR_FRAMEWORK.main_api:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4

# 6. Serve frontend (separate terminal)
# Using Python's HTTP server for testing:
python3 -m http.server 3000 --directory qms-ui/dist

# Or using Nginx (production):
# Copy nginx/nginx.conf to /etc/nginx/sites-available/qms
# Configure SSL and enable site
```

## Environment Variables Template

Create `.env.production` with the following variables:

```bash
# ============================================
# BACKEND CONFIGURATION
# ============================================

# API Settings
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
ENVIRONMENT=production

# Security
API_KEY=generate-a-strong-random-key-here-using-openssl-rand-base64-32
SECRET_KEY=generate-another-strong-random-key-here

# CORS Configuration (allow frontend access)
CORS_ORIGINS=http://localhost:3000,http://localhost:80,https://yourdomain.com

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# ============================================
# DATABASE CONFIGURATION
# ============================================

# PostgreSQL Connection (for Docker Compose)
DB_NAME=qms
DB_USER=qmsuser
DB_PASSWORD=change-me-to-strong-password

# Alternative: Direct DATABASE_URL (overrides above)
# DATABASE_URL=postgresql://username:password@hostname:5432/database

# Connection Pool Settings
DB_POOL_SIZE=20
DB_POOL_RECYCLE=3600

# ============================================
# EXTERNAL SERVICES (OPTIONAL)
# ============================================

# AI/LLM Services (required for full AI features)
OLLAMA_URL=http://localhost:11434  # Local Ollama instance
OPENAI_API_KEY=sk-...               # OpenAI API key
ANTHROPIC_API_KEY=sk-ant-...        # Anthropic Claude API key

# ============================================
# FEATURE FLAGS
# ============================================

ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=3600

USE_POSTGRESQL=true  # Set to false for JSON backend (testing only)
```

**Important**: Replace all placeholder values (especially API_KEY, DB_PASSWORD) with secure, randomly generated strings.

## Database Setup

### With Docker Compose:
The PostgreSQL container is automatically initialized with the database schema.

### Manual PostgreSQL Setup:
```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE qms;
CREATE USER qmsuser WITH PASSWORD 'your-strong-password';
GRANT ALL PRIVILEGES ON DATABASE qms TO qmsuser;

# Exit psql
\q

# Run migrations
export DATABASE_URL="postgresql://qmsuser:your-strong-password@localhost:5432/qms"
alembic upgrade head
```

## Docker Permission Troubleshooting

If you get "permission denied" errors with Docker:

### Solution 1: Add user to docker group
```bash
sudo usermod -aG docker $USER
# Log out and log back in for changes to take effect
```

### Solution 2: Use sudo (not recommended for production)
```bash
sudo docker-compose up --build -d
```

### Solution 3: Fix socket permissions (temporary)
```bash
sudo chmod 666 /var/run/docker.sock
# Warning: This reduces security!
```

## Verification Checklist

After deployment, verify all components are working:

### 1. Backend API
```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status": "healthy"}

# API documentation
curl http://localhost:8000/docs  # OpenAPI/Swagger UI
```

### 2. Frontend
```bash
# If using Docker Compose:
curl http://localhost/

# If using manual deployment:
curl http://localhost:3000/
```

### 3. Database Connectivity
```bash
# Test database connection
python3 -c "
import os
from sqlalchemy import create_engine
engine = create_engine(os.getenv('DATABASE_URL', 'postgresql://qmsuser:password@localhost:5432/qms'))
conn = engine.connect()
print('Database connection successful')
conn.close()
"
```

### 4. Document Generation Test
```bash
# Generate a test SOP
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-from-env" \
  -d '{
    "sop_name": "Equipment Qualification",
    "sop_type": "Quality Assurance",
    "keywords": ["equipment", "validation", "GMP"],
    "department": "Quality"
  }'

# Check for generated file
ls -la output/generated_sops/
```

## Production Considerations

### 1. SSL/TLS
For production, always use HTTPS:
- Use Let's Encrypt with certbot
- Configure Nginx with SSL
- Update CORS_ORIGINS to use HTTPS URLs

### 2. Database Backups
```bash
# Daily backup script
pg_dump -U qmsuser -h localhost qms > /backups/qms-$(date +%Y%m%d).sql
# Keep 30 days of backups
```

### 3. Monitoring
- Monitor Docker container health: `docker-compose ps`
- Check application logs: `docker-compose logs -f backend`
- Set up log aggregation (ELK stack, Loki, etc.)

### 4. Scaling
- Increase backend workers in Dockerfile.backend (gunicorn workers)
- Add PostgreSQL connection pooling (PgBouncer)
- Consider Redis for caching and rate limiting

## Troubleshooting Common Issues

### Issue: "Connection refused" to PostgreSQL
**Solution**: Check if PostgreSQL is running and credentials are correct.
```bash
# Test connection
psql -h localhost -U qmsuser -d qms
```

### Issue: API Key authentication failures
**Solution**: Verify API_KEY in .env.production matches the header.
```bash
# Test with correct API key
curl -H "X-API-Key: your-actual-key" http://localhost:8000/health
```

### Issue: Frontend not loading
**Solution**: Check Nginx configuration and file permissions.
```bash
# Verify Nginx is serving files
sudo nginx -t
sudo systemctl restart nginx
```

### Issue: Missing dependencies
**Solution**: Run dependency check script.
```bash
python check_deps.py
```

## Maintenance

### Updating the Application
```bash
# Pull latest code
git pull origin main

# Rebuild containers
docker-compose build --no-cache
docker-compose up -d

# Or for manual deployment
pip install -r requirements.txt --upgrade
alembic upgrade head
```

### Viewing Logs
```bash
# Docker Compose
docker-compose logs -f
docker-compose logs backend --tail=100
docker-compose logs frontend --tail=100

# Manual deployment
# Backend logs: check stdout or log files
# Nginx logs: /var/log/nginx/access.log, /var/log/nginx/error.log
```

### Stopping the Application
```bash
# Docker Compose
docker-compose down

# Manual deployment
# Kill backend process and Nginx
pkill -f "uvicorn.*main_api"
sudo systemctl stop nginx
```

## Support and Resources

- Project documentation: `docs/` directory
- API documentation: http://localhost:8000/docs when running
- Issue tracker: Check project repository
- Log files: Container logs or application log files

---

**Note**: This is a production deployment guide. For development setup, see `docs/DEVELOPMENT_WORKFLOW.md`.
```

## Next Steps

1. **Complete the deployment** using one of the methods above
2. **Test thoroughly** using the verification checklist
3. **Configure monitoring** for production reliability
4. **Set up backups** for database and configuration
5. **Document any customizations** for future maintenance

For additional help, refer to the comprehensive documentation in the `docs/` directory or check the project repository for updates.