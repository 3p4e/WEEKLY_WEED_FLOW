# Rollback Procedures - Cannabis EU GMP QMS Creator

**Purpose**: Procedures to safely revert production deployment if issues occur  
**Last Updated**: January 23, 2026  
**Severity Levels**: P1 (Critical), P2 (Major), P3 (Minor)  

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Severity Assessment](#severity-assessment)
3. [Rollback Procedures by Scenario](#rollback-procedures-by-scenario)
4. [Database Rollback](#database-rollback)
5. [File System Rollback](#file-system-rollback)
6. [Configuration Rollback](#configuration-rollback)
7. [Post-Rollback Verification](#post-rollback-verification)
8. [Preventing Future Rollbacks](#preventing-future-rollbacks)

---

## Quick Reference

### Immediate Actions (First 5 Minutes)

**If application completely down (P1):**
```bash
# 1. Page team lead
page-team-lead

# 2. Stop current deployment
docker-compose down

# 3. Restore previous version
git checkout v1.0.0-previous
docker-compose up -d

# 4. Verify health
curl http://localhost:8000/health
```

**If API returning 500 errors (P2):**
```bash
# 1. Check logs for errors
docker-compose logs backend -f --tail=50

# 2. If code issue found, rollback to previous tag
git checkout $(git tag --list | sort -V | tail -2 | head -1)
docker-compose build --no-cache
docker-compose up -d
```

**If database connection issues (P1):**
```bash
# 1. Verify database is running
docker-compose ps | grep postgres

# 2. If database corrupted, restore backup
docker-compose down
zcat /backup/qms_previous_day.sql.gz | docker-compose exec -T postgres psql -U qms_admin -d qms_production

# 3. Restart services
docker-compose up -d
```

---

## Severity Assessment

### P1 - Critical (Immediate Action Required)

**Indicators:**
- Application completely unavailable
- Data corruption detected
- Security breach confirmed
- Loss of critical functionality
- Database unreachable
- 100% error rate on core endpoints

**Response Time**: < 5 minutes  
**Decision Authority**: Senior Engineer or Team Lead  
**Rollback Threshold**: Automatic, no approval needed

### P2 - Major (Quick Response Required)

**Indicators:**
- Partial functionality degraded
- Error rate > 50% on some endpoints
- Performance significantly degraded
- Authentication/authorization broken
- Data validation failures

**Response Time**: 15-30 minutes  
**Decision Authority**: Team Lead  
**Rollback Threshold**: After root cause analysis, typically 30 minutes

### P3 - Minor (Monitor and Decide)

**Indicators:**
- Single feature broken but workarounds exist
- Cosmetic issues in UI
- Performance slightly degraded
- Non-critical endpoint failing
- Error rate 1-5% (normal variation)

**Response Time**: 24 hours  
**Decision Authority**: Deployment Manager  
**Rollback Threshold**: After 24-48 hour observation period

---

## Rollback Procedures by Scenario

### Scenario 1: Code/Application Rollback

**When to use**: Application errors, logic bugs, broken features

#### Step 1: Assess the Issue

```bash
# Check backend logs
docker-compose logs backend -f --tail=100 | grep -i "error\|exception\|traceback"

# Check frontend logs
docker-compose logs frontend -f --tail=100

# Test endpoints
curl -i http://localhost:8000/health
curl -i http://localhost:3000/
```

#### Step 2: Identify Previous Working Version

```bash
# List recent tags
git tag --list --sort=-version:refname | head -5

# Example output:
# v1.0.0-20260123  <- Current (broken)
# v0.9.9-20260120  <- Previous (working)
# v0.9.8-20260115  <- Earlier (working)

# Identify which version was last stable
PREVIOUS_VERSION="v0.9.9-20260120"
```

#### Step 3: Backup Current State

```bash
# Before rollback, save current state
mkdir -p /rollback-backup/$(date +%Y%m%d-%H%M%S)
cp .env.production /rollback-backup/$(date +%Y%m%d-%H%M%S)/
docker-compose logs backend > /rollback-backup/$(date +%Y%m%d-%H%M%S)/backend.log
docker-compose logs frontend > /rollback-backup/$(date +%Y%m%d-%H%M%S)/frontend.log
```

#### Step 4: Stop Current Services

```bash
# Graceful shutdown (wait for requests to complete)
docker-compose stop --time=30

# Or forceful shutdown if hanging
docker-compose kill
docker-compose down
```

#### Step 5: Checkout Previous Version

```bash
# Checkout previous working tag
git fetch origin
git checkout $PREVIOUS_VERSION

# Verify code integrity
git verify-tag $PREVIOUS_VERSION

# Verify files
git log --oneline -5
```

#### Step 6: Rebuild Docker Images

```bash
# Build with previous code
docker-compose build --no-cache

# Verify build completed successfully
docker images | grep qms
```

#### Step 7: Start Services

```bash
# Start with previous version
docker-compose up -d

# Wait for startup
sleep 15

# Verify services are running
docker-compose ps
```

#### Step 8: Database Check

```bash
# If database schema changed, may need migration
docker-compose exec backend alembic current

# If using older version, downgrade if needed
# docker-compose exec backend alembic downgrade -1
```

#### Step 9: Verify Health

```bash
# Test critical endpoints
curl -X GET http://localhost:8000/health
curl -X GET http://localhost:3000/
curl -X GET http://localhost:8000/docs

# Check logs for errors
docker-compose logs -f --tail=20
```

### Scenario 2: Database Rollback

**When to use**: Data corruption, migration failures, data loss

#### Step 1: Detect Database Issue

```bash
# Check database connectivity
docker-compose exec postgres psql -U qms_admin -d qms_production -c "SELECT 1"

# Check for errors in logs
docker-compose logs postgres | grep -i "error\|fatal\|panic"

# Try to query data
docker-compose exec postgres psql -U qms_admin -d qms_production -c "SELECT COUNT(*) FROM documents"
```

#### Step 2: Identify Available Backups

```bash
# List available backups
ls -lth /backup/ | head -10

# Expected format: qms_YYYYMMDD.sql.gz
# Example:
# qms_20260123.sql.gz  <- Latest (today)
# qms_20260122.sql.gz  <- Yesterday
# qms_20260121.sql.gz  <- 2 days ago
```

#### Step 3: Stop Services

```bash
# Stop but keep data
docker-compose stop

# Don't delete volumes yet - we need them for restore
```

#### Step 4: Restore from Backup

```bash
# Choose backup timestamp (typically 1-24 hours before issue)
BACKUP_FILE="/backup/qms_20260122.sql.gz"

# Drop current database
docker-compose exec postgres psql -U postgres -c "DROP DATABASE qms_production;"

# Create fresh database
docker-compose exec postgres psql -U postgres -c "CREATE DATABASE qms_production OWNER qms_admin;"

# Restore from backup
zcat $BACKUP_FILE | docker-compose exec -T postgres psql -U qms_admin -d qms_production

# Verify restore
docker-compose exec postgres psql -U qms_admin -d qms_production -c "SELECT COUNT(*) FROM documents;"
```

#### Step 5: Restart Services

```bash
# Start services with restored data
docker-compose up -d

# Verify health
curl http://localhost:8000/health
```

#### Step 6: Verify Data Integrity

```bash
# Run verification script
docker-compose exec backend python scripts/verify_database.py

# Check for any orphaned records
docker-compose exec backend python -c "
from CONTENT_CREATOR_FRAMEWORK.qms_database import QMSDatabase
db = QMSDatabase('.')
docs = db.get_all_documents()
print(f'Documents: {len(docs)}')
for doc in docs[:5]:
    print(f'  - {doc.get(\"code\")}: {doc.get(\"title\")}')
"
```

### Scenario 3: Configuration Rollback

**When to use**: Environment variable changes, SSL certificate issues, CORS misconfiguration

#### Step 1: Identify Configuration Issue

```bash
# Check current configuration
docker-compose exec backend env | grep -E "CORS|API_KEY|DATABASE"

# Check nginx configuration
docker-compose exec frontend nginx -T

# Check for recent .env changes
git diff HEAD~1 .env.production
```

#### Step 2: Restore Previous Configuration

```bash
# View previous version
git show HEAD~1:.env.production > /tmp/.env.previous

# Compare differences
diff /tmp/.env.previous .env.production

# Restore previous
git checkout HEAD~1 -- .env.production

# Or restore from backup
cp /rollback-backup/last-known-good/.env.production .env.production
```

#### Step 3: Reload Configuration

```bash
# Restart services to pick up new configuration
docker-compose down
docker-compose up -d

# Verify configuration loaded
curl http://localhost:8000/health
```

#### Step 4: Verify Access

```bash
# Test API access with correct credentials
curl -X GET http://localhost:8000/health \
  -H "X-API-Key: $API_KEY"

# Test frontend
curl -i http://localhost:3000/

# Test CORS
curl -i -H "Origin: https://yourdomain.com" http://localhost:8000/health
```

### Scenario 4: Dependency Rollback

**When to use**: Python package issues, Node.js package conflicts, system library problems

#### Step 1: Identify Dependency Issue

```bash
# Check Python package issues
docker-compose exec backend pip list | grep -i "error\|fail"

# Check pip-audit for vulnerabilities
docker-compose exec backend pip-audit

# Check Node.js packages
docker-compose exec frontend npm list | grep -i "error"

# Check npm audit
docker-compose exec frontend npm audit
```

#### Step 2: Review Requirements

```bash
# Compare requirements files
git diff HEAD~1 requirements.txt
git diff HEAD~1 qms-ui/package.json

# Identify problematic dependency
grep "new-package" requirements.txt
```

#### Step 3: Revert Dependencies

```bash
# Restore previous versions
git checkout HEAD~1 -- requirements.txt
git checkout HEAD~1 -- qms-ui/package.json

# Rebuild Docker images (will reinstall dependencies)
docker-compose build --no-cache

# Verify build
docker images | grep qms
```

#### Step 4: Restart Services

```bash
# Start with previous dependencies
docker-compose up -d

# Verify health
curl http://localhost:8000/health
```

---

## Database Rollback

### Manual Database Restore

```bash
# 1. List available backups and their timestamps
ls -lh /backup/ | grep "\.sql\.gz"

# 2. Choose appropriate backup
BACKUP_TIMESTAMP="20260122"  # Yesterday
BACKUP_FILE="/backup/qms_${BACKUP_TIMESTAMP}.sql.gz"

# 3. Connect to database and check current state
docker-compose exec postgres psql -U qms_admin -d qms_production \
  -c "SELECT COUNT(*) as documents FROM documents;"

# 4. Backup current state (just in case)
docker-compose exec postgres pg_dump -U qms_admin qms_production \
  | gzip > /backup/qms_pre_rollback_$(date +%Y%m%d-%H%M%S).sql.gz

# 5. Drop and restore database
docker-compose exec postgres dropdb -U qms_admin qms_production

docker-compose exec postgres createdb -U qms_admin qms_production

zcat $BACKUP_FILE | docker-compose exec -T postgres psql -U qms_admin -d qms_production

# 6. Verify restore was successful
docker-compose exec postgres psql -U qms_admin -d qms_production \
  -c "SELECT COUNT(*) as documents FROM documents;"
```

### Point-in-Time Recovery

```bash
# If using WAL (Write-Ahead Logging) archive
# 1. Restore to specific time
docker-compose exec postgres pg_ctl stop

# 2. Modify recovery.conf
echo "recovery_target_timeline = latest" >> /var/lib/postgresql/data/recovery.conf
echo "recovery_target_time = '2026-01-23 14:30:00 UTC'" >> /var/lib/postgresql/data/recovery.conf

# 3. Start PostgreSQL in recovery mode
docker-compose exec postgres pg_ctl start

# 4. Verify recovery completed
docker-compose exec postgres psql -U qms_admin -d qms_production -c "SELECT 1"

# 5. Promote to normal operation
docker-compose exec postgres pg_ctl promote
```

### Backup Verification Testing

```bash
# Monthly: Test restore in isolated environment
# 1. Create test database
docker-compose exec postgres createdb -U qms_admin qms_test

# 2. Restore backup into test DB
zcat /backup/qms_20260122.sql.gz | \
  docker-compose exec -T postgres psql -U qms_admin -d qms_test

# 3. Run verification queries
docker-compose exec postgres psql -U qms_admin -d qms_test -c \
  "SELECT tablename FROM pg_tables WHERE schemaname='public';"

# 4. Run data integrity checks
docker-compose exec postgres psql -U qms_admin -d qms_test -c \
  "SELECT COUNT(*) as documents FROM documents;"

# 5. Drop test database
docker-compose exec postgres dropdb -U qms_admin qms_test
```

---

## File System Rollback

### Application Files

```bash
# 1. Backup current files
tar -czf /backup/app-files-$(date +%Y%m%d-%H%M%S).tar.gz \
  CONTENT_CREATOR_FRAMEWORK qms-ui docker-compose.yml nginx/

# 2. Restore from git
git checkout HEAD~1 -- CONTENT_CREATOR_FRAMEWORK/
git checkout HEAD~1 -- qms-ui/
git checkout HEAD~1 -- docker-compose.yml

# 3. Rebuild and restart
docker-compose build --no-cache
docker-compose up -d
```

### Generated Documents

```bash
# 1. List generated documents
find data/ -name "*.pdf" -o -name "*.docx" | sort

# 2. Restore from backup
rsync -av /backup/generated-docs-20260122/ data/generated_documents/

# 3. Update database to reference restored files
# (May need custom script depending on how files are tracked)
```

### Configuration Files

```bash
# 1. Restore .env files from backup
cp /rollback-backup/20260122/.env.production .env.production

# 2. Restore nginx configuration
git checkout HEAD~1 -- nginx/nginx.conf

# 3. Reload nginx
docker-compose exec frontend nginx -s reload
```

---

## Configuration Rollback

### Environment Variables

```bash
# 1. Compare configurations
echo "=== Current ==="
cat .env.production | grep -E "CORS|API|DATABASE" | head -10
echo "=== Previous ==="
git show HEAD~1:.env.production | grep -E "CORS|API|DATABASE" | head -10

# 2. Restore previous configuration
git checkout HEAD~1 -- .env.production

# 3. Verify configuration
cat .env.production | grep "CORS_ORIGINS"

# 4. Reload services
docker-compose down
docker-compose up -d
```

### SSL Certificates

```bash
# 1. Check current certificate
openssl x509 -in /etc/ssl/certs/cert.pem -text -noout | grep -E "Not Before|Not After|Subject"

# 2. List certificate backups
ls -lh /backup/ssl-certs/

# 3. Restore previous certificate
cp /backup/ssl-certs/cert-20260120.pem /etc/ssl/certs/cert.pem
cp /backup/ssl-certs/key-20260120.pem /etc/ssl/private/key.pem

# 4. Restart nginx
docker-compose exec frontend nginx -s reload

# 5. Verify certificate
curl -v https://yourdomain.com/health
```

---

## Post-Rollback Verification

### Critical Endpoint Testing

```bash
#!/bin/bash
# Test all critical endpoints after rollback

echo "Testing Critical Endpoints..."

# 1. Health check
echo -n "Health endpoint: "
curl -s http://localhost:8000/health | jq -r '.status'

# 2. Document listing
echo -n "Document listing: "
curl -s http://localhost:3000/api/documents | jq 'length'

# 3. API authentication
echo -n "API auth (without key): "
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/generate

# 4. API authentication (with key)
echo -n "API auth (with key): "
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "X-API-Key: $API_KEY" \
  http://localhost:8000/health

# 5. Frontend load
echo -n "Frontend load: "
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/

# 6. Database connectivity
echo -n "Database: "
docker-compose exec postgres psql -U qms_admin -d qms_production -c "SELECT 'OK'" | grep OK
```

### Performance Verification

```bash
# Measure API response time
echo "=== Performance Check ==="
time curl http://localhost:8000/health

# Check resource usage
docker stats --no-stream

# Monitor for 5 minutes
docker stats --no-stream qms-backend qms-frontend
```

### Data Integrity Check

```bash
# Verify data consistency
docker-compose exec backend python << 'EOF'
from CONTENT_CREATOR_FRAMEWORK.qms_database import QMSDatabase

db = QMSDatabase('.')
docs = db.get_all_documents()

print(f"Total documents: {len(docs)}")
print(f"Documents with code: {len([d for d in docs if d.get('code')])}")
print(f"Documents with title: {len([d for d in docs if d.get('title')])}")

# Check for orphaned records (optional)
orphaned = [d for d in docs if not d.get('code')]
if orphaned:
    print(f"⚠️  WARNING: {len(orphaned)} documents without code")
EOF
```

### User-Facing Testing

```bash
# 1. Test document browsing
curl http://localhost:3000/api/hierarchy

# 2. Test SOP generation workflow
curl -X POST http://localhost:8000/generate \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sop_name": "Rollback Test",
    "sop_type": "Operational",
    "keywords": ["testing"],
    "department": "QA"
  }'

# 3. Test questionnaire
curl http://localhost:8000/questionnaire-schema | jq 'keys'

# 4. Test file serving
curl -X GET http://localhost:8000/api/documents/QA-001/pdf > test.pdf
file test.pdf
```

---

## Preventing Future Rollbacks

### Deployment Checklist

Before **every** deployment:

```bash
# 1. Run full test suite
python -m pytest CONTENT_CREATOR_FRAMEWORK/tests/ -v

# 2. Run security scans
docker scan qms-backend:latest
docker scan qms-frontend:latest

# 3. Verify environment
grep -E "^[A-Z_]+=" .env.production | wc -l

# 4. Check dependency updates
pip-audit
npm audit

# 5. Code review approval
# - At least 2 approvals required
# - No known issues
# - All tests passing

# 6. Staging deployment successful
# - All endpoints responding
# - No error spikes
# - Performance acceptable (< 1s latency)

# 7. Production backup verified
ls -lh /backup/ | head -1
```

### Gradual Rollout Strategy

```bash
# 1. Canary deployment (10% of traffic)
# - Deploy to single instance
# - Monitor for 30 minutes
# - If OK, proceed; if errors, rollback

# 2. Blue-green deployment
# - Deploy to second environment ("green")
# - Test thoroughly
# - Switch traffic from "blue" to "green"
# - Keep "blue" ready for rollback

# 3. Feature flags
# - Hide new features behind flags
# - Enable for 10% of users first
# - Gradually increase percentage
# - If issues, disable flag without rollback
```

### Monitoring & Alerting

```bash
# Set up alerts for:
- API error rate > 1%
- Response time > 1000ms
- CPU usage > 80%
- Memory usage > 90%
- Disk usage > 85%
- Database slow queries > 5s

# Configure automated actions:
- Alert team lead on P1
- Auto-rollback on P1 critical errors (optional)
- Log all events to audit trail
```

### Incident Report Template

```markdown
## Incident Report - [Date] [Time]

**Deployment Version**: v1.0.0-20260123
**Issue Detected**: [Describe issue]
**Severity**: P1 / P2 / P3
**Time to Detection**: [minutes]
**Time to Resolution**: [minutes]

### Root Cause
[Explain what went wrong]

### Remediation
[What was done to fix]

### Prevention
[Changes to prevent future occurrences]

### Affected Users
[Estimated number and impact]

### Follow-up Items
- [ ] Post-mortem scheduled
- [ ] Code fix planned
- [ ] Test added
- [ ] Documentation updated
- [ ] Team training scheduled
```

---

## Contact & Escalation

**Immediate Response (P1 emergencies)**:
- On-call Engineer: [Contact]
- Team Lead: [Contact]
- Management: [Contact]

**Deployment Issues**:
- Deployment Manager: [Contact]
- DevOps Team: [Slack/Email]

**Database Issues**:
- DBA: [Contact]
- Data Team: [Contact]

---

## Version History

| Version | Date | Changes | Tested |
|---------|------|---------|--------|
| 1.0 | 2026-01-23 | Initial procedures | Yes |

---

**Remember**: Test rollback procedures monthly in non-production environments. A rollback you've never tested is a rollback that will fail when you need it most.

**Last tested**: [Date to be updated monthly]
