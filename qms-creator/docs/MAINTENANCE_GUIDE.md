# Maintenance & Operations Guide - Cannabis EU GMP QMS Creator

This guide covers daily, weekly, and monthly operational tasks for maintaining the Cannabis EU GMP QMS Creator in production.

## Table of Contents
- [Daily Tasks](#daily-tasks)
- [Weekly Tasks](#weekly-tasks)
- [Monthly Tasks](#monthly-tasks)
- [Quarterly Tasks](#quarterly-tasks)
- [Annual Tasks](#annual-tasks)
- [Common Issues & Solutions](#common-issues--solutions)
- [Escalation Procedures](#escalation-procedures)

---

## Daily Tasks

### Morning Checklist (Start of Business Day)

```bash
# 1. Check System Health
curl http://localhost:8000/health
# Should return: {"status": "healthy"}

# 2. Verify Services Running
docker-compose ps
# All containers should show "Up"

# 3. Check Error Logs
docker-compose logs backend | grep ERROR | tail -20
docker-compose logs frontend | grep ERROR | tail -20

# 4. Monitor Resource Usage
docker stats --no-stream

# 5. Check Disk Space
df -h /
# Should show > 10% available

# 6. Verify Database Connectivity
psql -U postgres -d qms_db -c "SELECT count(*) FROM documents;"

# 7. Check Recent Backups
ls -lh /path/to/backups/ | tail -5
```

### Throughout the Day

**Hourly**:
- Monitor error logs for spikes
- Check CPU/Memory usage
- Verify no stuck processes

**Every 4 Hours**:
- Review error tracking (Sentry)
- Check API response times
- Verify database performance

### End of Day

```bash
# Verify today's backups completed
ls -lh /path/to/backups/$(date +\%Y-\%m-\%d)*

# Review logs for warnings
docker-compose logs --since 8h | grep WARN

# Check tomorrow's scheduled maintenance
cat /etc/cron.d/qms-maintenance
```

---

## Weekly Tasks

### Every Monday

#### Security Review
```bash
# Check for failed login attempts
grep "401\|403" /var/log/nginx/error.log | wc -l

# Verify no unauthorized access
grep "Invalid API" /var/log/application.log | wc -l

# Check SSL certificate expiry
echo | openssl s_client -servername example.com -connect localhost:443 2>/dev/null | \
  openssl x509 -noout -dates
# Should show cert valid for > 30 days
```

#### Dependency Updates Check
```bash
# Check for outdated Python packages
pip list --outdated

# Check for outdated Node packages
npm outdated

# Check for security vulnerabilities
npm audit
safety check  # Python packages
```

### Every Wednesday

#### Database Maintenance
```bash
# Analyze database for optimization
psql -U postgres -d qms_db -c "ANALYZE VERBOSE;"

# Check for bloated tables
psql -U postgres -d qms_db -c "
  SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
  FROM pg_tables
  WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"

# VACUUM to reclaim space (if needed)
psql -U postgres -d qms_db -c "VACUUM FULL ANALYZE;"
```

#### Log Rotation Check
```bash
# Verify logs are rotating
ls -lh /var/log/application.log*

# Check available space
df -h /var/log/

# Archive old logs
tar -czf /backup/logs/application-$(date +\%Y-\%m-\%d).log.tar.gz \
  /var/log/application.log.*
```

### Every Friday

#### Performance Analysis
```bash
# Generate performance report
curl http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,rate(http_request_duration_seconds_bucket[5m]))

# Check database slow logs
tail -50 /var/log/postgres_slow_query.log

# Review error rates
grep "500\|503" /var/log/nginx/error.log | wc -l

# Generate weekly metrics report
# (See Monitoring section below)
```

#### Backup Verification
```bash
# Test restore from backup
# This should be done in staging, not production!
./scripts/test_restore_backup.sh /backup/daily/latest.sql

# Verify backup integrity
pg_restore --list /backup/daily/latest.sql | head -20

# Check backup file sizes
ls -lh /backup/daily/ | tail -10
```

---

## Monthly Tasks

### First Week of Month

#### Full Security Audit
```bash
# Run security scanner
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image qms-backend:latest

# Check firewall rules
sudo ufw status verbose

# Review access logs for suspicious activity
grep -i "sql\|union\|drop" /var/log/nginx/access.log | wc -l

# Verify API key rotation schedule
cat /config/api_keys.rotation.log
```

#### Certificate Management
```bash
# Check all certificates
for cert in /etc/ssl/certs/qms*; do
  echo "Certificate: $cert"
  openssl x509 -in $cert -noout -dates
done

# Request renewal if < 30 days to expiry
certbot renew --dry-run
```

#### User Access Review
```bash
# Review recent user activity
psql -U postgres -d qms_db -c "
  SELECT user_id, action, count(*) 
  FROM audit_logs 
  WHERE created_at > NOW() - INTERVAL '1 month'
  GROUP BY user_id, action
  ORDER BY count DESC;"

# List active database users
psql -U postgres -d qms_db -c "\du"

# Remove inactive users (if needed)
```

### Second Week of Month

#### Dependency Updates
```bash
# Update Python dependencies
pip install --upgrade -r requirements.txt

# Update Node dependencies
npm update

# Update Docker images
docker-compose pull
docker-compose up -d --no-deps --build

# Run full test suite after updates
pytest CONTENT_CREATOR_FRAMEWORK/tests/ -v
npm test
```

#### Documentation Review
```bash
# Check documentation is current
# - API docs match actual endpoints
# - Troubleshooting covers recent issues
# - Deployment guide is accurate
# - Architecture docs reflect current state

# Update CHANGELOG.md
# Update README.md if needed
```

### Third Week of Month

#### Capacity Planning
```bash
# Analyze growth trends
psql -U postgres -d qms_db -c "
  SELECT DATE_TRUNC('month', created_at) as month, 
         count(*) as documents
  FROM documents
  GROUP BY DATE_TRUNC('month', created_at)
  ORDER BY month DESC
  LIMIT 12;"

# Check disk usage trend
df -h / | tee /monitoring/disk_usage_$(date +\%Y-\%m-\%d).txt

# Predict resource needs for next quarter
# Create capacity report
```

#### Performance Optimization
```bash
# Analyze slow queries
tail -100 /var/log/postgres_slow_query.log | \
  awk '{print $NF}' | sort | uniq -c | sort -rn | head -10

# Review database indexes
psql -U postgres -d qms_db -c "
  SELECT schemaname, tablename, indexname
  FROM pg_indexes
  WHERE schemaname = 'public'
  ORDER BY tablename;"

# Consider adding missing indexes
# Test new indexes in staging first!
```

### Last Week of Month

#### Disaster Recovery Drill
```bash
# Perform full backup
./scripts/backup_database.sh

# Test restore procedure
# (In staging environment!)
./scripts/test_restore_backup.sh /backup/monthly/latest.sql

# Verify all data integrity
psql -U postgres -d qms_db -c "
  SELECT COUNT(*) as total_documents FROM documents;
  SELECT COUNT(*) as total_annexes FROM annexes;
  SELECT COUNT(*) as total_chapters FROM document_chapters;
  SELECT COUNT(*) as total_audits FROM audit_logs;"

# Document results
# Update disaster recovery plan if needed
```

#### Monthly Report
```bash
# Generate operations report
- System uptime: _______
- Incidents: _______
- Performance metrics: _______
- Security events: _______
- Recommendations: _______

# Send to management/stakeholders
```

---

## Quarterly Tasks

### Q1, Q2, Q3, Q4

#### Full Security Assessment
```bash
# Run comprehensive security scan
./scripts/security_audit.sh

# Penetration testing
# (Contract with professional firm)

# Update security policies
# Review and update security documentation
```

#### Infrastructure Review
```bash
# Assess current infrastructure
# - Is it meeting performance needs?
# - Are resource allocations optimal?
# - Any bottlenecks identified?

# Plan infrastructure improvements
# - Storage upgrades needed?
# - Computing power sufficient?
# - Network bandwidth adequate?

# Cost optimization
# - Are we using cost-effective services?
# - Can we consolidate resources?
# - Any unused resources to remove?
```

#### Compliance Review
```bash
# Verify GDPR compliance
# - Data handling procedures
# - Data retention policies
# - Right-to-deletion workflows
# - Privacy policy current

# Check regulatory requirements
# - EU GMP compliance
# - Industry-specific regulations
# - Local jurisdiction requirements

# Audit compliance procedures
# - Are procedures being followed?
# - Are records being maintained?
# - Any gaps to address?
```

#### Training & Documentation
```bash
# Update operational runbooks
# - Document recent changes
# - Add lessons learned
# - Update troubleshooting procedures

# Team training
# - Review operational procedures
# - Practice incident response
# - Update team on changes

# Knowledge transfer
# - Document critical procedures
# - Record video tutorials
# - Ensure no single points of knowledge failure
```

---

## Annual Tasks

### Year-End Comprehensive Audit

#### Full System Assessment
```bash
# Evaluate system performance
- Average response time
- Error rates
- Uptime percentage
- User satisfaction scores

# Review architecture
- Is current architecture suitable?
- Are there better alternatives?
- Technical debt assessment
- Scalability evaluation

# Analyze usage patterns
- Peak load times
- Resource utilization
- Growth trends
- Forecast next year's needs
```

#### Security Audit
```bash
# Full security assessment
- Penetration test results
- Vulnerability scan results
- Code security review
- Infrastructure security review

# Access control audit
- Who has access to what?
- Are permissions appropriate?
- Any orphaned accounts?
- Principle of least privilege verified?

# Compliance assessment
- Regulatory requirements met?
- Industry standards followed?
- Certifications current?
- Audit results satisfactory?
```

#### Disaster Recovery Testing
```bash
# Full DR test
- Complete backup restore
- Failover procedures tested
- Recovery time measured
- Data integrity verified

# Documentation update
- Update recovery procedures
- Update contact lists
- Update escalation procedures
- Distribute updated plan
```

#### Technology Roadmap Planning
```bash
# Plan next year's improvements
- Feature priorities
- Technical debt reduction
- Performance enhancements
- Infrastructure upgrades

# Evaluate new technologies
- Should we migrate databases?
- New frameworks worth considering?
- Infrastructure improvements available?
- Cost/benefit analysis

# Create implementation plan
- Timeline for changes
- Resource requirements
- Risk assessment
- Success criteria
```

---

## Common Issues & Solutions

### High CPU Usage

**Diagnosis**:
```bash
# Find process using CPU
top -o %CPU
# or
ps aux | sort -k3 -rn | head -5

# Check Docker container
docker stats

# Check database
psql -U postgres -d qms_db -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 5;"
```

**Solutions**:
1. **Slow Query**: Add database index
2. **Runaway Process**: Kill process and investigate
3. **Load Spike**: Scale horizontally or vertically
4. **Memory Swap**: Add more RAM or reduce memory usage

### High Memory Usage

**Diagnosis**:
```bash
# Check memory usage
free -h

# Find process
ps aux | sort -k4 -rn | head -5

# Check Docker
docker stats

# Memory profile
python -m memory_profiler main_api.py
```

**Solutions**:
1. **Memory Leak**: Identify and fix in code
2. **Cache Issues**: Reduce cache size or TTL
3. **Large Dataset**: Implement pagination or streaming
4. **Insufficient RAM**: Add more memory to server

### Slow Queries

**Diagnosis**:
```bash
# Enable slow query log
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- 1 second
SELECT pg_reload_conf();

# View slow queries
tail -100 /var/log/postgres_slow_query.log
```

**Solutions**:
1. **Missing Index**: Add appropriate index
2. **Join Issues**: Optimize query or data structure
3. **Full Table Scan**: Add index or rewrite query
4. **Statistics Stale**: Run ANALYZE

### Disk Space Issues

**Diagnosis**:
```bash
# Check disk usage
df -h /

# Find large files
du -sh /* | sort -rh

# Check Docker
docker system df
```

**Solutions**:
1. **Old Logs**: Archive and compress old logs
2. **Docker Images**: Clean up unused images
3. **Database**: Run VACUUM FULL, archive old data
4. **Backups**: Move old backups to archive storage

### API Response Slow

**Diagnosis**:
```bash
# Check response times
curl -w "@curl-format.txt" http://localhost:8000/documents

# Check server load
top
uptime

# Check network
nethogs

# Database performance
psql -U postgres -d qms_db -c "SELECT * FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 5;"
```

**Solutions**:
1. **Server Load**: Scale horizontally
2. **Database**: Optimize query, add index
3. **Cache**: Implement caching, increase TTL
4. **Network**: Check latency, optimize payload size

### Database Connection Errors

**Diagnosis**:
```bash
# Check if PostgreSQL running
systemctl status postgresql

# Check connections
psql -U postgres -d qms_db -c "SELECT count(*) FROM pg_stat_activity;"

# Check pool
SHOW max_connections;
```

**Solutions**:
1. **Connection Pool Full**: Increase pool size or add connection pooling (PgBouncer)
2. **Database Down**: Restart PostgreSQL
3. **Network Issue**: Check firewall, DNS
4. **Credentials Wrong**: Verify connection string

---

## Escalation Procedures

### Severity Level 1 (Critical)
**Impact**: Service completely down or data loss

**Actions**:
1. Page on-call engineer immediately
2. Activate incident commander
3. Start incident bridge (Zoom/Slack)
4. Begin triage
5. Notify stakeholders
6. Document timeline

**Escalation**: To VP Engineering after 15 minutes if not resolved

### Severity Level 2 (High)
**Impact**: Major functionality impaired, degraded performance

**Actions**:
1. Alert on-call engineer
2. Start investigation
3. Implement workaround if possible
4. Update status page
5. Notify affected users

**Escalation**: To team lead if not resolved in 30 minutes

### Severity Level 3 (Medium)
**Impact**: Minor functionality impaired, workaround available

**Actions**:
1. Investigate during business hours
2. Create ticket for tracking
3. Plan fix for next release

**Escalation**: To team lead daily status update

### Severity Level 4 (Low)
**Impact**: Cosmetic issues, non-critical bugs

**Actions**:
1. Log issue in tracking system
2. Plan for future release
3. No immediate action required

---

## Useful Monitoring Dashboards

### Prometheus Queries
```bash
# Request rate
rate(http_requests_total[5m])

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Response time
histogram_quantile(0.95, http_request_duration_seconds_bucket)

# Database connections
pg_stat_activity_count

# CPU usage
node_cpu_seconds_total

# Memory usage
node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes
```

### Dashboard URLs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Kibana: http://localhost:5601
- Sentry: https://sentry.example.com

---

## On-Call Runbook

### First Response (Within 5 minutes)
1. [ ] Acknowledge alert
2. [ ] Check status page
3. [ ] Verify issue in production
4. [ ] Check recent deployments
5. [ ] Initial diagnosis
6. [ ] Notify team if needed

### Investigation (Within 15 minutes)
1. [ ] Review logs
2. [ ] Check metrics
3. [ ] Identify affected components
4. [ ] Determine severity
5. [ ] Begin mitigation

### Resolution (Ongoing)
1. [ ] Implement fix or workaround
2. [ ] Test in staging if possible
3. [ ] Deploy or restart service
4. [ ] Verify issue resolved
5. [ ] Document solution
6. [ ] Schedule post-mortem

---

## Contact Information

| Role | Name | Phone | Email | Backup |
|------|------|-------|-------|--------|
| On-Call | | | | |
| Team Lead | | | | |
| DevOps | | | | |
| Database Admin | | | | |
| Security | | | | |

---

**Last Updated**: January 2026
**Version**: 1.0.0

For urgent issues, contact the on-call engineer: _____________________
