# Production Deployment Guide - Cannabis EU GMP QMS Creator

**Status**: ✅ PRODUCTION READY  
**Last Updated**: January 23, 2026  
**Version**: 1.0.0  

---

## Table of Contents

1. [Pre-Deployment Planning](#pre-deployment-planning)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Local Testing](#local-testing)
4. [Deployment Options](#deployment-options)
5. [Production Configuration](#production-configuration)
6. [Deployment Execution](#deployment-execution)
7. [Post-Deployment Verification](#post-deployment-verification)
8. [Monitoring Setup](#monitoring-setup)
9. [Disaster Recovery](#disaster-recovery)
10. [Frequently Asked Questions](#frequently-asked-questions)

---

## Pre-Deployment Planning

### Requirements Verification

**System Requirements:**
- Linux server (Ubuntu 20.04+, RHEL 8+, or equivalent)
- Minimum 2 CPU cores
- Minimum 4 GB RAM
- Minimum 20 GB free disk space
- Docker and Docker Compose installed
- PostgreSQL 13+ (can be containerized)
- Python 3.12 (in container)
- Node.js 18+ (in container)

**Network Requirements:**
- Outbound HTTPS (443) for external API calls
- Inbound HTTP (80) for health checks
- Inbound HTTPS (443) for users
- Inbound port 5432 for database (if not containerized)

**SSL/TLS:**
- Valid SSL certificate for domain
- Certificate renewal process documented
- HSTS headers configured

**DNS:**
- Domain configured to point to server
- SSL certificate matches domain name
- MX records set up if email needed

### Resource Planning

```
Component          CPU    Memory   Disk    Notes
─────────────────────────────────────────────
FastAPI Backend    0.5    512MB    5GB     Scales with load
React Frontend     0.2    256MB    1GB     Static files
PostgreSQL DB      0.5    1GB      8GB     Growth depends on usage
nginx Proxy        0.1    128MB    -       Reverse proxy
─────────────────────────────────────────────
TOTAL              1.3    1.9GB    14GB    Minimum recommended
```

### Timeline

- **Pre-deployment**: 1-2 weeks
- **Testing**: 3-5 days
- **Deployment**: 2-4 hours
- **Validation**: 4-8 hours
- **Full go-live**: 24 hours

---

## Infrastructure Setup

### Option 1: AWS Deployment

#### 1. EC2 Instance Setup

```bash
# Launch EC2 instance
# AMI: Ubuntu 20.04 LTS
# Instance type: t3.medium (minimum)
# Storage: 50GB SSD
# Security group: Open 80, 443, 22, 5432 (restricted)

# Connect to instance
ssh -i your-key.pem ubuntu@your-instance-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

#### 2. RDS Database Setup

```bash
# Create RDS PostgreSQL instance
# Engine: PostgreSQL 13.7
# Instance class: db.t3.micro (development) or db.t3.small (production)
# Storage: 100GB with auto-scaling
# Backup retention: 30 days
# Multi-AZ: Yes (for production)

# Get RDS endpoint
# Update DATABASE_URL in .env.production
DATABASE_URL=postgresql://admin:password@rds-endpoint:5432/qms_production
```

#### 3. S3 Bucket for Backups

```bash
# Create S3 bucket
aws s3 mb s3://qms-backups-prod-unique-name

# Set bucket policy for automated backups
# Enable versioning and lifecycle policies
```

#### 4. Load Balancer Setup

```bash
# Create Application Load Balancer
# - HTTP (80) → Target group
# - HTTPS (443) → Target group
# - Health check: /health on port 8000

# Create target groups
# - Backend: port 8000, /health check
# - Frontend: port 3000, /health check
```

### Option 2: DigitalOcean Deployment

```bash
# Create Droplet
# Image: Ubuntu 20.04
# Size: $12/month (2GB/50GB) - Basic
# Region: Choose closest to users

# Connect and install
ssh root@droplet-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose, PostgreSQL-client
# (Follow same steps as AWS above)

# Create managed database (optional)
# doctl databases create --engine postgresql
```

### Option 3: On-Premises Deployment

```bash
# Install on your own server
# Ubuntu 20.04 server with public IP

# Prerequisites
sudo apt install -y docker.io docker-compose postgresql postgresql-contrib

# Enable services
sudo systemctl enable docker postgresql
sudo systemctl start docker postgresql

# Configure PostgreSQL
sudo -u postgres createuser qms_admin
sudo -u postgres createdb -O qms_admin qms_production
```

---

## Local Testing

### 1. Test Deployment Locally

```bash
# Clone production branch
git clone https://github.com/your-org/qms-creator.git
cd "Cannabis EU GMP QMS Creator"

# Create production environment
cp .env.example .env.production
# Edit with production values

# Start services
docker-compose -f docker-compose.yml up --build

# Run tests
docker-compose exec backend python -m pytest CONTENT_CREATOR_FRAMEWORK/tests/ -v

# Verify endpoints
curl -X GET http://localhost:8000/health
curl -X GET http://localhost:3000/
```

### 2. Load Testing

```bash
# Install Apache Bench
sudo apt install apache2-utils

# Test API performance
ab -n 1000 -c 10 http://localhost:8000/health

# Test rate limiting
ab -n 100 -c 10 http://localhost:8000/health

# Expected: Rate limiting should kick in after threshold
```

### 3. Security Testing

```bash
# Scan Docker images for vulnerabilities
docker scan your-image-name

# Check dependencies
docker-compose exec backend pip-audit

# Test CORS
curl -i -H "Origin: http://example.com" http://localhost:8000/health

# Test API key requirement
curl -i http://localhost:8000/generate  # Should return 401
curl -i -H "X-API-Key: test-key" http://localhost:8000/generate  # Should work
```

---

## Production Configuration

### Environment Variables

Create `.env.production`:

```bash
# Backend Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql://user:pass@db-host:5432/qms_production
DB_POOL_SIZE=20
DB_POOL_RECYCLE=3600

# API Security
API_KEY=generate-a-strong-random-key-here
SECRET_KEY=generate-another-strong-random-key-here

# CORS Configuration
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# External Services
OLLAMA_URL=http://ollama:11434
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Features
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=3600

# SSL/TLS
SSL_CERT_PATH=/etc/ssl/certs/your-domain.crt
SSL_KEY_PATH=/etc/ssl/private/your-domain.key
HSTS_MAX_AGE=31536000
```

### Database Setup

```bash
# Connect to PostgreSQL
psql -h db-host -U admin -d postgres

# Create user and database
CREATE ROLE qms_admin WITH LOGIN PASSWORD 'strong-password';
CREATE DATABASE qms_production OWNER qms_admin;

# Enable extensions
\c qms_production
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

# Run migrations
alembic upgrade head

# Seed initial data
python scripts/seed_database.py
```

### SSL/TLS Configuration

```bash
# Get certificate (Let's Encrypt recommended)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Update docker-compose.yml volumes
volumes:
  - /etc/letsencrypt/live/yourdomain.com/fullchain.pem:/etc/ssl/certs/cert.pem
  - /etc/letsencrypt/live/yourdomain.com/privkey.pem:/etc/ssl/private/key.pem

# Setup auto-renewal
sudo systemctl enable certbot.timer
```

### Nginx Configuration

Update `nginx/nginx.conf`:

```nginx
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer" always;
    
    # Gzip compression
    gzip on;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript;
    gzip_min_length 1000;
    
    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # API routes
    location /api/ {
        proxy_pass http://backend/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health check
    location /health {
        proxy_pass http://backend/health;
        access_log off;
    }
    
    # API docs
    location /docs {
        proxy_pass http://backend/docs;
        proxy_set_header Host $host;
    }
}
```

---

## Deployment Execution

### Step 1: Pre-Deployment Checks

```bash
# Clone repository
git clone https://github.com/your-org/qms-creator.git production
cd production

# Checkout production tag
git checkout v1.0.0-20260123

# Verify code integrity
git verify-tag v1.0.0-20260123

# Create backup
tar -czf backup-$(date +%Y%m%d-%H%M%S).tar.gz .env.production data/
```

### Step 2: Build Production Images

```bash
# Build images
docker-compose -f docker-compose.yml build --no-cache

# Tag with version
docker tag qms-backend:latest qms-backend:v1.0.0
docker tag qms-frontend:latest qms-frontend:v1.0.0

# Optional: Push to registry
docker tag qms-backend:v1.0.0 registry.your-domain.com/qms-backend:v1.0.0
docker push registry.your-domain.com/qms-backend:v1.0.0
```

### Step 3: Start Services

```bash
# Stop existing services (if any)
docker-compose down

# Start with production compose file
docker-compose -f docker-compose.yml up -d

# Wait for services to be healthy
sleep 10

# Check status
docker-compose ps
docker-compose logs -f --tail=50
```

### Step 4: Database Migrations

```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Verify migrations
docker-compose exec backend alembic current

# Create backup after migration
docker-compose exec postgres pg_dump -U qms_admin qms_production > backup_post_migration.sql
```

### Step 5: Seed Data (First Deployment Only)

```bash
# Seed initial documents and settings
docker-compose exec backend python scripts/seed_database.py

# Verify data
docker-compose exec backend python -c \
  "from CONTENT_CREATOR_FRAMEWORK.qms_database import QMSDatabase; 
  db = QMSDatabase('.'); 
  docs = db.get_all_documents(); 
  print(f'Loaded {len(docs)} documents')"
```

### Step 6: Verify Health

```bash
# Check backend
curl -X GET https://yourdomain.com/health

# Check frontend
curl -X GET https://yourdomain.com/

# Check API documentation
curl -X GET https://yourdomain.com/docs

# Verify API key authentication
curl -X POST https://yourdomain.com/generate \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"sop_name": "Test", "sop_type": "Standard", "keywords": []}'
```

---

## Post-Deployment Verification

### 1. Functional Testing

```bash
# Test document listing
curl -X GET https://yourdomain.com/api/hierarchy

# Test SOP generation workflow
curl -X POST https://yourdomain.com/generate \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sop_name": "Post-Deployment Test",
    "sop_type": "Operational",
    "keywords": ["testing", "deployment"],
    "department": "Quality"
  }'

# Test questionnaire
curl -X GET https://yourdomain.com/questionnaire-schema

# Test file serving
curl -X GET https://yourdomain.com/api/documents/QA-001/pdf -o test.pdf
```

### 2. Security Verification

```bash
# Check SSL certificate
curl -v https://yourdomain.com/health | grep -i "certificate"

# Verify security headers
curl -i https://yourdomain.com/ | grep -i "x-"
# Should see: X-Content-Type-Options, X-Frame-Options, HSTS, etc.

# Test CORS restrictions
curl -i -H "Origin: http://evil.com" https://yourdomain.com/health
# Should NOT see "Access-Control-Allow-Origin" header

# Verify rate limiting
for i in {1..20}; do curl -s https://yourdomain.com/health; done
# Should be rate limited after threshold
```

### 3. Performance Testing

```bash
# Install tools
apt install apache2-utils

# Test API performance
ab -n 100 -c 5 https://yourdomain.com/health
# Target: Requests per second > 50, Latency < 500ms

# Test concurrent users
ab -n 1000 -c 50 https://yourdomain.com/health

# Monitor resource usage
docker stats
```

### 4. Error Handling

```bash
# Test invalid API key
curl -i -X GET https://yourdomain.com/health \
  -H "X-API-Key: invalid-key"
# Should return 401 Unauthorized

# Test missing required fields
curl -i -X POST https://yourdomain.com/generate \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
# Should return 422 Unprocessable Entity

# Check error logs
docker-compose logs backend | grep -i error
```

---

## Monitoring Setup

### 1. Application Monitoring

```bash
# Check API metrics
curl -X GET https://yourdomain.com/metrics

# Monitor resource usage
docker stats

# Check logs
docker-compose logs -f --tail=100

# Filter for errors
docker-compose logs backend | grep -i "error\|exception\|traceback"
```

### 2. Database Monitoring

```bash
# Connect to database
docker-compose exec postgres psql -U qms_admin -d qms_production

# Check active connections
SELECT datname, usename, application_name, state FROM pg_stat_activity;

# Check slow queries
SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;

# Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) 
FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### 3. Automated Alerts

Configure alerts for:
- **CPU usage > 80%**: Scale up or optimize
- **Memory usage > 90%**: Investigate memory leaks
- **Disk usage > 85%**: Clean up or expand storage
- **API errors > 5% of requests**: Investigate issues
- **Response time > 2s**: Performance investigation
- **Database connections > threshold**: Connection pool issue

### 4. Log Aggregation (Optional)

```bash
# Forward logs to centralized system
# Option 1: Sentry
SENTRY_DSN=https://key@sentry.io/project
docker-compose exec backend \
  python -c "import sentry_sdk; sentry_sdk.init('$SENTRY_DSN')"

# Option 2: ELK Stack
# Configure fluentd or logstash to forward logs

# Option 3: CloudWatch (AWS)
docker-compose logs | aws logs put-log-events
```

---

## Disaster Recovery

### Backup Strategy

```bash
# Daily database backup at 2 AM
0 2 * * * docker-compose exec postgres pg_dump -U qms_admin qms_production | gzip > /backup/qms_$(date +\%Y\%m\%d).sql.gz

# Store backups
# - Local: /backup/
# - Remote: AWS S3, Google Cloud Storage, or B2
aws s3 sync /backup/ s3://qms-backups-prod/

# Retention policy: Keep 30 days
find /backup -name "*.sql.gz" -mtime +30 -delete
```

### Recovery Procedure

```bash
# 1. Stop services
docker-compose down

# 2. Restore database from backup
zcat /backup/qms_20260123.sql.gz | docker-compose exec -T postgres psql -U qms_admin -d qms_production

# 3. Restart services
docker-compose up -d

# 4. Verify data integrity
docker-compose exec backend python scripts/verify_database.py

# 5. Run tests
docker-compose exec backend python -m pytest
```

### Disaster Recovery Testing

```bash
# Monthly: Test restore procedure in staging
# 1. Create fresh staging environment
# 2. Restore backup from production
# 3. Run full test suite
# 4. Verify all features working
# 5. Document any issues
```

---

## Frequently Asked Questions

### Q: How do I update the application?

**A:** Follow the deployment procedure:

```bash
git pull origin main
git checkout v1.0.1-20260130
docker-compose build --no-cache
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

### Q: How do I scale the application?

**A:** Scale backend workers:

```yaml
# In docker-compose.yml
backend:
  deploy:
    replicas: 3
```

Or use Kubernetes:

```bash
kubectl scale deployment qms-backend --replicas=5
```

### Q: How do I monitor performance?

**A:** Use provided metrics endpoint:

```bash
curl https://yourdomain.com/metrics
```

Or integrate with Prometheus:

```yaml
prometheus:
  scrape_configs:
    - job_name: 'qms'
      static_configs:
        - targets: ['localhost:8000']
```

### Q: How do I troubleshoot API errors?

**A:** Check logs:

```bash
docker-compose logs backend -f --tail=100
grep -i "error" logs/backend.log
```

Or test endpoint directly:

```bash
curl -v https://yourdomain.com/generate \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Q: How do I reset the database?

**A:** ⚠️ **WARNING: This deletes all data**

```bash
docker-compose down
docker volume rm cannabis-qms_postgres_data
docker-compose up -d
docker-compose exec backend alembic upgrade head
docker-compose exec backend python scripts/seed_database.py
```

### Q: How do I change the API key?

**A:** Update environment variable:

```bash
# Edit .env.production
API_KEY=new-random-key-here

# Restart services
docker-compose down
docker-compose up -d
```

### Q: How do I enable debug logging?

**A:** Update environment:

```bash
LOG_LEVEL=DEBUG
docker-compose down
docker-compose up -d
```

---

## Support & Escalation

**For deployment issues:**
1. Check logs: `docker-compose logs -f`
2. Review troubleshooting guide: `docs/TROUBLESHOOTING.md`
3. Contact on-call engineer
4. Create issue on GitHub: https://github.com/your-org/qms-creator/issues

**Critical issues (P1):**
- Page completely unavailable
- Data loss/corruption
- Security breach
- Payment processing failure

→ Contact senior engineer immediately

---

**Project Status**: ✅ PRODUCTION READY - Ready to deploy

Last reviewed: January 23, 2026  
Next review: April 23, 2026
