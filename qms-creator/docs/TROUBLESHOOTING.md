# Troubleshooting Guide - Cannabis EU GMP QMS Creator

This guide helps resolve common issues encountered when developing, deploying, or using the Cannabis EU GMP QMS Creator.

## Table of Contents
- [Startup Issues](#startup-issues)
- [API & Backend Issues](#api--backend-issues)
- [Frontend Issues](#frontend-issues)
- [Database Issues](#database-issues)
- [Docker Issues](#docker-issues)
- [Testing Issues](#testing-issues)
- [Performance Issues](#performance-issues)
- [Security Issues](#security-issues)
- [Getting Help](#getting-help)

---

## Startup Issues

### Issue: Application Won't Start

**Symptoms**:
- Application crashes on startup
- "Failed to start" messages
- No services available

**Troubleshooting Steps**:

1. **Check Python Version**
   ```bash
   python --version
   # Should be 3.12+
   ```

2. **Check Virtual Environment**
   ```bash
   # Activate virtual environment
   source .venv/bin/activate
   
   # Verify activation (should show .venv path)
   which python
   ```

3. **Verify Dependencies**
   ```bash
   # Reinstall requirements
   pip install -r requirements.txt --force-reinstall
   
   # Check for conflicts
   pip check
   ```

4. **Check Environment Variables**
   ```bash
   # Verify .env file exists
   ls -la .env
   
   # Check critical variables
   grep -E "API_KEY|DATABASE_URL" .env
   ```

5. **Review Log Output**
   ```bash
   # Start with verbose logging
   LOG_LEVEL=DEBUG python CONTENT_CREATOR_FRAMEWORK/main_api.py
   ```

**Common Solutions**:
- Recreate virtual environment from scratch
- Clear Python cache: `find . -type d -name __pycache__ -exec rm -r {} +`
- Reset pip: `pip install --upgrade pip setuptools wheel`

---

### Issue: Port Already in Use

**Symptoms**:
- `Address already in use` error
- `[Errno 48] Can't assign requested address`
- `OSError: [WinError 10048]` on Windows

**Quick Fix**:
```bash
# Find process using port 8000
lsof -i :8000
# or on Windows
netstat -ano | findstr :8000

# Kill the process
kill -9 <PID>
# or on Windows
taskkill /PID <PID> /F
```

**Permanent Fix**:
```bash
# Use different port
python CONTENT_CREATOR_FRAMEWORK/main_api.py --port 8001

# Or in docker-compose.yml
services:
  backend:
    ports:
      - "8001:8000"  # Change first port number
```

**Identify Long-Running Processes**:
```bash
# Find all Python processes
ps aux | grep python

# Find all Node processes
ps aux | grep node

# List all listening ports
lsof -i -P -n
```

---

## API & Backend Issues

### Issue: Cannot Connect to API

**Symptoms**:
- `Connection refused` errors
- Frontend shows "API unavailable"
- `curl http://localhost:8000` fails

**Troubleshooting**:

1. **Check if Backend is Running**
   ```bash
   # Test endpoint
   curl http://localhost:8000/health
   
   # If fails, check processes
   ps aux | grep main_api.py
   ```

2. **Check Logs**
   ```bash
   # Start backend with output
   python CONTENT_CREATOR_FRAMEWORK/main_api.py
   
   # Look for error messages
   ```

3. **Check Network Configuration**
   ```bash
   # Verify port binding
   lsof -i :8000
   
   # Check firewall
   sudo ufw status
   
   # Allow port on firewall (Linux)
   sudo ufw allow 8000
   ```

4. **Test with Direct URL**
   ```bash
   # Test API health
   curl http://localhost:8000/health
   
   # Test with API key
   curl -H "X-API-Key: test-api-key-12345" \
     http://localhost:8000/documents
   ```

**Solution**:
```bash
# Start backend
source .venv/bin/activate
python CONTENT_CREATOR_FRAMEWORK/main_api.py
```

---

### Issue: 401 Unauthorized Errors

**Symptoms**:
- API returns 401 status
- "Missing API Key" error message
- Cannot authenticate

**Causes & Solutions**:

1. **Missing API Key Header**
   ```bash
   # Wrong - no API key
   curl http://localhost:8000/documents
   
   # Correct - with API key
   curl -H "X-API-Key: test-api-key-12345" \
     http://localhost:8000/documents
   ```

2. **Incorrect API Key**
   ```bash
   # Check .env for correct key
   grep API_KEY .env
   
   # Use matching key in request
   curl -H "X-API-Key: your-actual-key" \
     http://localhost:8000/generate
   ```

3. **Key Changed in Environment**
   ```bash
   # Ensure .env has consistent key
   API_KEY=your-secure-key
   
   # Restart backend after change
   ```

---

### Issue: 422 Validation Errors

**Symptoms**:
- API returns 422 Unprocessable Entity
- Validation error messages
- Request body appears correct

**Troubleshooting**:

1. **Check Request Format**
   ```bash
   # Ensure JSON is valid
   echo '{"sop_name":"Test"}' | python -m json.tool
   
   # Check Content-Type header
   -H "Content-Type: application/json"
   ```

2. **Verify Required Fields**
   ```bash
   # Wrong - missing required fields
   curl -X POST http://localhost:8000/generate \
     -H "X-API-Key: key" \
     -H "Content-Type: application/json" \
     -d '{}'
   
   # Correct - includes required fields
   curl -X POST http://localhost:8000/generate \
     -H "X-API-Key: key" \
     -H "Content-Type: application/json" \
     -d '{
       "sop_name": "Test SOP",
       "sop_type": "Process",
       "facility_context": {"name": "My Facility"}
     }'
   ```

3. **Check API Documentation**
   ```bash
   # Visit API docs for schema
   http://localhost:8000/docs
   
   # Check request/response examples
   ```

---

### Issue: 500 Internal Server Error

**Symptoms**:
- API returns 500 error
- "Internal Server Error" message
- No details in response

**Troubleshooting**:

1. **Check Backend Logs**
   ```bash
   # Start backend with output
   python CONTENT_CREATOR_FRAMEWORK/main_api.py
   
   # Look for error stack trace
   ```

2. **Check File Permissions**
   ```bash
   # Verify write permissions for generated files
   ls -la CONTENT_CREATOR_FRAMEWORK/outputs/
   
   # Fix permissions
   chmod 755 CONTENT_CREATOR_FRAMEWORK/outputs/
   ```

3. **Check External Dependencies**
   ```bash
   # If using OpenAI API
   echo $OPENAI_API_KEY
   
   # If using Ollama
   curl http://localhost:11434/api/models
   ```

4. **Enable Debug Mode**
   ```bash
   # In .env
   LOG_LEVEL=DEBUG
   
   # Restart and check detailed logs
   ```

---

## Frontend Issues

### Issue: Blank Page or No Content

**Symptoms**:
- Browser shows blank page
- Cannot see dashboard
- Components not rendering

**Troubleshooting**:

1. **Check Browser Console**
   ```bash
   # Open DevTools: F12 or right-click > Inspect
   # Check Console tab for errors
   # Check Network tab for failed requests
   ```

2. **Check Frontend is Running**
   ```bash
   # Test frontend port
   curl http://localhost:3000
   
   # Should return HTML content
   ```

3. **Clear Browser Cache**
   ```bash
   # Chrome DevTools > Application > Clear storage
   # Or use incognito window
   ```

4. **Check API Connection**
   ```bash
   # In browser console
   fetch('http://localhost:8000/health')
     .then(r => r.json())
     .then(d => console.log(d))
   
   # Should return: { "status": "healthy" }
   ```

**Solution**:
```bash
# Ensure backend is running
python CONTENT_CREATOR_FRAMEWORK/main_api.py

# Restart frontend
cd qms-ui
npm start
```

---

### Issue: API Calls Failing with CORS Error

**Symptoms**:
- Browser console shows CORS error
- "Access to XMLHttpRequest blocked by CORS"
- Requests work with curl but not from browser

**Causes**:

1. **Backend CORS Not Configured**
   - Check CORS_ORIGINS in .env
   - Ensure frontend URL is included

2. **Request Method Issues**
   - Some methods trigger CORS preflight
   - Server must handle OPTIONS requests

**Solution**:
```bash
# In .env
CORS_ORIGINS=http://localhost:3000

# Restart backend
python CONTENT_CREATOR_FRAMEWORK/main_api.py
```

---

### Issue: Cannot Upload Documents

**Symptoms**:
- Upload button doesn't work
- File input doesn't respond
- Upload fails silently

**Troubleshooting**:

1. **Check File Size**
   ```bash
   # Max upload size from server
   # Check DocumentUploadRequest in main_api.py
   # Ensure file < limit (typically 50MB)
   ```

2. **Check File Format**
   ```bash
   # Only PDF and DOCX supported
   file document.pdf
   ```

3. **Check Permissions**
   ```bash
   # Ensure upload directory exists and is writable
   mkdir -p CONTENT_CREATOR_FRAMEWORK/outputs
   chmod 755 CONTENT_CREATOR_FRAMEWORK/outputs
   ```

4. **Check Backend Logs**
   ```bash
   # Look for upload-related errors
   LOG_LEVEL=DEBUG python CONTENT_CREATOR_FRAMEWORK/main_api.py
   ```

---

## Database Issues

### Issue: Database Connection Error

**Symptoms**:
- `psycopg2.OperationalError`
- `could not connect to server`
- Documents not saved

**Troubleshooting**:

1. **Check PostgreSQL Status**
   ```bash
   # On Linux
   sudo systemctl status postgresql
   
   # On macOS
   brew services list | grep postgres
   ```

2. **Test Database Connection**
   ```bash
   # Direct connection test
   psql -U postgres -h localhost -d qms_db
   
   # If fails, check credentials in .env
   ```

3. **Verify DATABASE_URL**
   ```bash
   # Check .env
   grep DATABASE_URL .env
   
   # Format should be:
   # postgresql://user:password@host:port/database
   ```

**Solution - Use JSON Fallback**:
```bash
# Remove DATABASE_URL from .env
# System automatically uses JSON file storage
```

**Solution - Start PostgreSQL**:
```bash
# Using Docker
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:13

# Using local PostgreSQL
sudo systemctl start postgresql
```

---

### Issue: Migration Failed

**Symptoms**:
- `alembic upgrade head` fails
- "No such column" errors
- Schema mismatch

**Troubleshooting**:

1. **Check Migration Files**
   ```bash
   # List migrations
   ls -la alembic/versions/
   
   # Check current version
   alembic current
   ```

2. **Rollback if Needed**
   ```bash
   # Downgrade to previous version
   alembic downgrade -1
   
   # Or to base
   alembic downgrade base
   ```

3. **Create New Migration**
   ```bash
   # Auto-generate migration
   alembic revision --autogenerate -m "Fix schema"
   
   # Review generated file
   cat alembic/versions/001_fix_schema.py
   
   # Apply migration
   alembic upgrade head
   ```

---

## Docker Issues

### Issue: Docker Build Fails

**Symptoms**:
- `docker-compose up --build` fails
- Build context error
- Dependency installation fails

**Troubleshooting**:

1. **Clear Docker Cache**
   ```bash
   # Remove stopped containers
   docker-compose down
   
   # Prune system
   docker system prune -a
   
   # Rebuild
   docker-compose build --no-cache
   ```

2. **Check Docker Resources**
   ```bash
   # Ensure Docker has enough resources
   docker system df
   
   # Increase memory/CPU in Docker settings if needed
   ```

3. **Check Dockerfile**
   ```bash
   # Verify syntax
   docker build -f Dockerfile.backend .
   
   # Check for missing files
   ls requirements.txt
   ```

---

### Issue: Container Won't Start

**Symptoms**:
- Container exits immediately
- `docker-compose ps` shows "Exited"
- No logs available

**Troubleshooting**:

1. **Check Container Logs**
   ```bash
   # View exit logs
   docker-compose logs backend
   
   # View full output
   docker-compose logs -f
   ```

2. **Start in Attached Mode**
   ```bash
   # See errors as they happen
   docker-compose up backend
   # Don't use -d flag
   ```

3. **Check Health**
   ```bash
   # Check health status
   docker-compose ps
   
   # View health details
   docker inspect qms-backend
   ```

---

### Issue: Port Mapping Not Working

**Symptoms**:
- Cannot access service on mapped port
- `Connection refused` from host

**Troubleshooting**:

1. **Check Port Mappings**
   ```bash
   # View active mappings
   docker-compose ps
   
   # Verify in docker-compose.yml
   cat docker-compose.yml | grep -A 2 "ports:"
   ```

2. **Test from Container**
   ```bash
   # Check if service is listening inside container
   docker-compose exec backend curl localhost:8000/health
   ```

3. **Verify Network**
   ```bash
   # Check Docker network
   docker network ls
   
   # Inspect network
   docker network inspect qms-network
   ```

---

## Testing Issues

### Issue: Tests Fail Locally but Pass in CI

**Symptoms**:
- `pytest` fails locally
- Same tests pass in GitHub Actions
- Inconsistent test results

**Common Causes**:

1. **Environment Differences**
   ```bash
   # Ensure .env variables match test expectations
   grep -E "API_KEY|DATABASE_URL" .env
   
   # Run tests with explicit env vars
   API_KEY=test-key pytest CONTENT_CREATOR_FRAMEWORK/tests/
   ```

2. **Missing Dependencies**
   ```bash
   # Reinstall dependencies
   pip install -r requirements.txt
   
   # Install test dependencies
   pip install pytest pytest-cov
   ```

3. **Database State**
   ```bash
   # Tests use in-memory SQLite, should be clean
   # But verify no test data persists
   pytest --tb=short -v
   ```

---

### Issue: Tests Timeout

**Symptoms**:
- Tests hang indefinitely
- Timeout errors
- Tests never complete

**Troubleshooting**:

1. **Identify Slow Tests**
   ```bash
   # Run with verbose timing
   pytest -v --durations=10
   
   # Run single slow test
   pytest CONTENT_CREATOR_FRAMEWORK/tests/test_api.py::TestSOPGenerationEndpoints -v
   ```

2. **Check for Mock Issues**
   ```bash
   # Verify mocks are working
   # Look for real API calls in logs
   ```

3. **Increase Timeout**
   ```bash
   # In pytest.ini or conftest.py
   [pytest]
   timeout = 300
   
   # Or per test
   @pytest.mark.timeout(60)
   def test_slow_operation():
       ...
   ```

---

### Issue: Coverage Report Missing

**Symptoms**:
- No coverage report generated
- `htmlcov/` directory missing
- Coverage percentage not shown

**Solution**:

```bash
# Generate coverage report
pytest --cov=CONTENT_CREATOR_FRAMEWORK \
       --cov-report=html \
       CONTENT_CREATOR_FRAMEWORK/tests/

# View report
open htmlcov/index.html
```

---

## Performance Issues

### Issue: Slow API Response Times

**Symptoms**:
- API responses take 5+ seconds
- `/generate` endpoint very slow
- Timeouts on complex requests

**Troubleshooting**:

1. **Profile API Calls**
   ```bash
   # Use curl with timing
   curl -w "@curl-format.txt" \
     http://localhost:8000/documents
   
   # Check response time breakdown
   ```

2. **Check Database Queries**
   ```bash
   # Enable query logging
   export SQLALCHEMY_ECHO=true
   
   # Look for N+1 query problems
   ```

3. **Check External Services**
   ```bash
   # If using OpenAI/Anthropic, check API response times
   # If using Ollama, ensure it's responsive
   curl http://localhost:11434/api/models
   ```

4. **Optimize Queries**
   ```bash
   # Add indexes if needed
   # Check query execution plans
   EXPLAIN ANALYZE SELECT ...
   ```

---

### Issue: High Memory Usage

**Symptoms**:
- Application memory grows over time
- Memory leak suspected
- Out of memory errors

**Troubleshooting**:

1. **Monitor Memory**
   ```bash
   # Check process memory
   ps aux | grep main_api.py
   
   # Watch memory over time
   watch -n 1 'ps aux | grep main_api.py'
   ```

2. **Identify Memory Leaks**
   ```bash
   # Use memory_profiler
   pip install memory-profiler
   python -m memory_profiler CONTENT_CREATOR_FRAMEWORK/main_api.py
   ```

3. **Check for Large Objects**
   ```bash
   # Look for cached data that grows
   # Check for unclosed file handles
   lsof -p <PID>
   ```

---

## Security Issues

### Issue: API Key Not Working

**Symptoms**:
- 401 errors even with correct key
- Key worked before, now doesn't
- Cannot authenticate

**Troubleshooting**:

1. **Verify Key in .env**
   ```bash
   # Check .env file
   cat .env | grep API_KEY
   
   # Ensure no extra spaces
   API_KEY=your-key-here  # No spaces around =
   ```

2. **Check Environment Variable**
   ```bash
   # Verify variable is set
   echo $API_KEY
   
   # Restart service after changing
   ```

3. **Test with Correct Key**
   ```bash
   curl -H "X-API-Key: $(grep API_KEY .env | cut -d= -f2)" \
     http://localhost:8000/health
   ```

---

### Issue: HTTPS Not Working

**Symptoms**:
- Browser shows "Not Secure"
- Mixed content warnings
- Certificate errors

**Solution for Development**:
```bash
# Use self-signed certificate (development only)
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# Configure in main_api.py
uvicorn.run(
    app,
    ssl_keyfile="key.pem",
    ssl_certfile="cert.pem"
)
```

**Solution for Production**:
- Use Let's Encrypt with Certbot
- Configure in Nginx/reverse proxy
- Never use self-signed certificates in production

---

## Getting Help

### Debugging Steps

1. **Gather Information**
   ```bash
   # Python version
   python --version
   
   # Dependencies
   pip list | grep -E "fastapi|sqlalchemy"
   
   # Environment
   env | grep -E "API_KEY|DATABASE_URL"
   ```

2. **Check Logs**
   ```bash
   # Backend logs
   tail -f backend.log
   
   # Docker logs
   docker-compose logs -f
   ```

3. **Test Endpoints**
   ```bash
   # Health check
   curl http://localhost:8000/health
   
   # With authentication
   curl -H "X-API-Key: key" http://localhost:8000/documents
   ```

### Resources

- **API Docs**: http://localhost:8000/docs
- **Architecture**: docs/ARCHITECTURE.md
- **Deployment**: docs/DEPLOYMENT.md
- **GitHub Issues**: Create issue with:
  - Clear description of problem
  - Steps to reproduce
  - Error messages and logs
  - Environment information (OS, Python version, etc.)

### Support Channels

1. **Documentation**: Check docs/ directory
2. **GitHub Issues**: Search existing issues
3. **GitHub Discussions**: Ask questions
4. **Email Support**: qms@example.com

---

## Checklist for Troubleshooting

- [ ] Verified Python 3.12+ installed
- [ ] Confirmed virtual environment activated
- [ ] Reinstalled dependencies
- [ ] Checked .env file configuration
- [ ] Verified API key is correct
- [ ] Checked backend is running
- [ ] Tested with curl before debugging in browser
- [ ] Cleared browser cache
- [ ] Checked Docker logs (if using Docker)
- [ ] Looked for files/permissions issues
- [ ] Reviewed API documentation
- [ ] Checked for similar GitHub issues

---

**Last Updated**: January 2026
**Version**: 1.0.0

For latest troubleshooting tips, visit: [GitHub Issues](https://github.com/yourusername/cannabis-qms-creator/issues)
