# Deployment Scripts for Cannabis EU GMP QMS Creator

This directory contains production deployment scripts for the Cannabis EU GMP QMS Creator platform. These scripts help you deploy, verify, and maintain the production instance of the platform.

## Overview

The platform consists of:
- **Backend**: FastAPI application with RAG document analysis and SOP generation
- **Frontend**: React-based web interface (pre-built in `qms-ui/dist`)
- **Database**: PostgreSQL (containerized or external)
- **Reverse Proxy**: Nginx for serving frontend and proxying API requests

## Available Scripts

### 1. `setup_production.sh` - Production Setup Script
Interactive script that guides you through the entire deployment process.

### 2. `verify_deployment.sh` - Deployment Verification Script
Comprehensive verification tool to check all components after deployment.

### 3. `DEPLOYMENT_GUIDE.md` - Complete Deployment Guide
Detailed manual deployment instructions and best practices.

## Prerequisites

Before using these scripts, ensure your system has:

### Minimum Requirements:
- Linux/Unix system (Ubuntu 20.04+, RHEL 8+, or similar)
- Python 3.12+ with pip
- Git (for cloning/updating)
- curl or wget (for verification)

### For Docker Deployment:
- Docker Engine 20.10+
- Docker Compose 2.0+
- User added to docker group (or sudo access)

### For Manual Deployment:
- PostgreSQL 13+ (running and accessible)
- Nginx or alternative web server (recommended for production)

## Quick Start

### Option A: Complete Setup with Docker (Recommended)
```bash
# Make script executable
chmod +x setup_production.sh

# Run interactive setup
./setup_production.sh

# Follow the prompts to:
# 1. Select Docker deployment
# 2. Configure environment variables
# 3. Start the application
```

### Option B: Manual Setup
```bash
# Run setup with manual deployment
./setup_production.sh

# Select "Manual deployment" when prompted
# Configure PostgreSQL connection
# Install Python dependencies
# Start backend manually
```

### Option C: Verification Only
```bash
# Make verification script executable
chmod +x verify_deployment.sh

# Run verification (adjust parameters as needed)
./verify_deployment.sh --use-docker --env-file .env.production
```

## Script Details

### `setup_production.sh`

#### Features:
- Interactive command-line interface with color-coded output
- Automatic prerequisite checking (Python, Docker, PostgreSQL)
- Secure random generation of API keys and passwords
- Support for both Docker and manual deployment methods
- Automatic database migrations for manual deployment
- Comprehensive logging to timestamped log files

#### Usage:
```bash
./setup_production.sh
```

#### Options:
The script is interactive - all options are selected during runtime.

#### Output:
- Creates `.env.production` with secure credentials
- Creates log file: `setup_production_YYYYMMDD_HHMMSS.log`
- Starts services based on selected deployment method
- Provides verification steps after completion

### `verify_deployment.sh`

#### Features:
- 11 comprehensive verification tests
- Docker container status checking
- API endpoint testing with authentication
- Database connectivity verification
- Document generation testing
- External service availability checking
- Detailed pass/fail/warning reporting

#### Usage:
```bash
./verify_deployment.sh [OPTIONS]
```

#### Options:
```
--backend-url URL     Backend API URL (default: http://localhost:8000)
--frontend-url URL    Frontend URL (default: http://localhost)
--api-key KEY         API key for authentication
--env-file FILE       Environment file (default: .env.production)
--use-docker          Check Docker containers (default: false)
--help                Show help message
```

#### Examples:
```bash
# Basic verification
./verify_deployment.sh

# Verify Docker deployment
./verify_deployment.sh --use-docker

# Verify custom deployment
./verify_deployment.sh --backend-url http://api.example.com --api-key my-secret-key

# Verify with custom environment file
./verify_deployment.sh --env-file .env.staging --use-docker
```

#### Test Categories:
1. **Prerequisites** - System requirements check
2. **Docker Containers** - Container status (if using Docker)
3. **Backend Health** - API health endpoint
4. **API Documentation** - OpenAPI/Swagger UI
5. **API Authentication** - API key validation
6. **Frontend** - Web interface accessibility
7. **Database** - PostgreSQL connectivity
8. **Document Generation** - SOP creation test
9. **RAG System** - Vector search index check
10. **Output Directories** - File system permissions
11. **External Services** - Optional AI services (Ollama, OpenAI, Anthropic)

## Environment Configuration

### Required Environment Variables:
Create `.env.production` (template available in `.env.example`):

```bash
# Backend Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
API_KEY=generate-a-strong-random-key-here

# Database (for Docker)
DB_NAME=qms
DB_USER=qmsuser
DB_PASSWORD=strong-password-here

# OR direct DATABASE_URL (for manual)
# DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Security
CORS_ORIGINS=http://localhost:3000,http://localhost:80

# Features
USE_POSTGRESQL=true
LOG_LEVEL=INFO
```

### Generating Secure Credentials:
```bash
# Generate secure API key
openssl rand -base64 32

# Generate secure database password
openssl rand -base64 16
```

## Deployment Methods

### Method 1: Docker Compose (Recommended)
- Uses containers for isolation
- Automatic service orchestration
- Easy scaling and maintenance
- Production-ready configuration

```bash
# Start with Docker Compose
docker-compose up --build -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Stop services
docker-compose down
```

### Method 2: Manual Deployment
- Direct control over services
- No Docker dependency
- Customizable configuration
- Suitable for existing infrastructure

```bash
# Start backend
python -m uvicorn CONTENT_CREATOR_FRAMEWORK.main_api:app \
  --host 0.0.0.0 --port 8000 --workers 4

# Serve frontend (pre-built)
python3 -m http.server 3000 --directory qms-ui/dist

# Or use Nginx (production)
sudo cp nginx/nginx.conf /etc/nginx/sites-available/qms
sudo systemctl restart nginx
```

## Verification Results Interpretation

### Success Indicators:
- ✅ **All tests passed**: Deployment is fully operational
- ✅ **Core functionality verified**: Essential services working
- ⚠️ **Warnings present**: Optional features not available

### Common Issues and Solutions:

#### Issue: Docker permission denied
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Log out and log back in
```

#### Issue: PostgreSQL connection failed
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Create database and user
sudo -u postgres psql -c "CREATE DATABASE qms;"
sudo -u postgres psql -c "CREATE USER qmsuser WITH PASSWORD 'password';"
```

#### Issue: API authentication failed
```bash
# Check API key in .env.production
grep API_KEY .env.production

# Verify key matches request
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/health
```

#### Issue: Frontend not loading
```bash
# Check Nginx configuration
sudo nginx -t
sudo systemctl restart nginx

# Or test with Python server
python3 -m http.server 3000 --directory qms-ui/dist
```

## Maintenance

### Updating the Application:
```bash
# Pull latest code
git pull origin main

# Rebuild Docker containers
docker-compose build --no-cache
docker-compose up -d

# Or update manual deployment
pip install -r requirements.txt --upgrade
alembic upgrade head
```

### Monitoring:
```bash
# View real-time logs
docker-compose logs -f

# Check container health
docker-compose ps

# Monitor resource usage
docker stats

# Verify deployment periodically
./verify_deployment.sh --use-docker
```

### Backup and Restore:
```bash
# Database backup
docker exec qms-db pg_dump -U qmsuser qms > backup_$(date +%Y%m%d).sql

# Configuration backup
cp .env.production .env.production.backup_$(date +%Y%m%d)

# Restore database
cat backup.sql | docker exec -i qms-db psql -U qmsuser qms
```

## Troubleshooting

### Common Problems:

1. **Port conflicts**: Check if ports 8000 (backend) and 80 (frontend) are available
2. **Missing dependencies**: Run `python check_deps.py` to verify Python packages
3. **Database schema issues**: Run `alembic upgrade head` to apply migrations
4. **File permissions**: Ensure output directories are writable
5. **CORS errors**: Verify CORS_ORIGINS includes your frontend URL

### Debug Mode:
```bash
# Increase log level
export LOG_LEVEL=DEBUG

# Restart services
docker-compose restart backend

# View detailed logs
docker-compose logs --tail=100 backend
```

### Getting Help:
- Check log files: `setup_production_*.log` and `verify_deployment_*.log`
- Review Docker logs: `docker-compose logs`
- Consult `DEPLOYMENT_GUIDE.md` for detailed instructions
- Check API documentation: http://localhost:8000/docs when running

## Security Considerations

### Production Best Practices:
1. **Always use HTTPS** in production
2. **Rotate API keys** periodically
3. **Use strong passwords** for database and API
4. **Restrict network access** to essential ports only
5. **Regularly update** dependencies and security patches
6. **Monitor logs** for suspicious activity
7. **Implement backup strategy** for database and configuration
8. **Use firewall** to restrict access to services

### SSL/TLS Configuration:
```bash
# Use Let's Encrypt for free SSL certificates
sudo certbot --nginx -d yourdomain.com

# Update CORS_ORIGINS to HTTPS
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

## Support and Resources

### Documentation:
- `DEPLOYMENT_GUIDE.md` - Complete deployment manual
- `docs/` directory - Additional documentation
- API documentation - http://localhost:8000/docs (when running)

### Script Output:
- Timestamped log files for debugging
- Color-coded console output for easy reading
- Detailed verification reports

### Next Steps After Deployment:
1. Test document generation with sample requests
2. Configure monitoring and alerting
3. Set up automated backups
4. Document custom configurations
5. Train users on platform usage
6. Plan scaling strategy for growth

---

**Note**: These scripts are designed for production deployments. For development setup, see `docs/DEVELOPMENT_WORKFLOW.md`.

For issues or contributions, please refer to the project repository.