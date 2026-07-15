# Database Migration: JSON to PostgreSQL

This guide explains how to migrate the Cannabis EU GMP QMS Creator from JSON-based storage to PostgreSQL.

## Overview

The project currently uses JSON (`data/document_status.json`) for persistent storage. PostgreSQL migration provides:
- Better scalability for large datasets
- ACID compliance for data integrity
- Advanced querying capabilities
- Audit logging support
- Multi-user support with proper locking

## Prerequisites

### PostgreSQL Installation

**Ubuntu/Debian:**
```bash
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS:**
```bash
brew install postgresql
brew services start postgresql
```

**Docker (Recommended for Development):**
```bash
docker run --name qms_postgres \
  -e POSTGRES_USER=qmsuser \
  -e POSTGRES_PASSWORD=qmspassword \
  -e POSTGRES_DB=qms_creator \
  -p 5432:5432 \
  -d postgres:16
```

### Create Database User

```bash
sudo -u postgres psql
```

```sql
CREATE USER qmsuser WITH PASSWORD 'qmspassword';
CREATE DATABASE qms_creator OWNER qmsuser;
GRANT ALL PRIVILEGES ON DATABASE qms_creator TO qmsuser;
\q
```

## Schema Design

The PostgreSQL schema includes:

### Tables

1. **documents** - Main SOP documents
   - id (PRIMARY KEY)
   - code (UNIQUE)
   - title, department, status, version
   - pdf_path, docx_path
   - content, description, keywords
   - timestamps (created_at, updated_at, last_modified, effective_date)

2. **annexes** - Appendices to documents
   - id (PRIMARY KEY)
   - code (UNIQUE)
   - title, content, description
   - pdf_path, docx_path
   - document_id (FOREIGN KEY → documents.id)
   - timestamps

3. **chapters** - Document groupings by department
   - id (PRIMARY KEY)
   - code (UNIQUE)
   - name, folder
   - document_id (FOREIGN KEY → documents.id)
   - document_count, display_order
   - timestamps

4. **audit_logs** - Change tracking for compliance
   - id (PRIMARY KEY, auto-increment)
   - document_id (FOREIGN KEY → documents.id)
   - action (create, update, delete, publish)
   - old_values, new_values (JSON strings)
   - changed_by, reason
   - created_at timestamp

### Enums

- **DocumentStatus**: draft, in_review, approved, planned, completed, archived

## Migration Steps

### Step 1: Set Environment Variables

```bash
# Using default configuration (localhost)
export DATABASE_URL="postgresql://qmsuser:qmspassword@localhost/qms_creator"

# Or for remote database
export DATABASE_URL="postgresql://user:password@host:5432/database_name"
```

### Step 2: Run Alembic Migrations

Initialize the database schema using Alembic:

```bash
cd /path/to/Cannabis\ EU\ GMP\ QMS\ Creator

# Apply migrations
.venv/bin/alembic upgrade head

# Check migration status
.venv/bin/alembic current
```

### Step 3: Migrate Data from JSON

Run the migration script:

```bash
# Standard migration
.venv/bin/python scripts/migrate_json_to_postgres.py

# With custom database URL
.venv/bin/python scripts/migrate_json_to_postgres.py \
  --database-url "postgresql://user:password@host/db"

# Dry run (test without committing)
.venv/bin/python scripts/migrate_json_to_postgres.py --dry-run

# Drop existing tables and migrate fresh
.venv/bin/python scripts/migrate_json_to_postgres.py --drop-existing
```

The script will:
- Connect to PostgreSQL
- Create all tables if they don't exist
- Load data from JSON
- Migrate documents and annexes
- Verify data integrity
- Report migration results

### Step 4: Verify Migration

```bash
# Connect to PostgreSQL
psql -U qmsuser -d qms_creator

# Check document count
SELECT COUNT(*) FROM documents;

# Check document statuses
SELECT status, COUNT(*) FROM documents GROUP BY status;

# Check departments
SELECT department, COUNT(*) FROM documents GROUP BY department;

# Exit
\q
```

### Step 5: Update Backend Configuration

**Option 1: Use PostgreSQL Backend**

Update `CONTENT_CREATOR_FRAMEWORK/main_api.py`:

```python
from CONTENT_CREATOR_FRAMEWORK.qms_database_pg import QMSDatabasePostgres

# Initialize PostgreSQL backend
db = QMSDatabasePostgres()

# Or with custom database URL
db = QMSDatabasePostgres(database_url="postgresql://user:pass@host/db")
```

**Option 2: Keep JSON Fallback**

The original `QMSDatabase` (JSON backend) continues to work alongside PostgreSQL. You can:
- Keep both operational (PostgreSQL as primary, JSON as backup)
- Gradually migrate endpoints to use PostgreSQL
- Archive JSON after successful migration

## Rollback

If you need to rollback the migration:

```bash
# Downgrade to previous migration
.venv/bin/alembic downgrade -1

# Or downgrade to initial state (if needed)
.venv/bin/alembic downgrade base
```

## Performance Tuning

### Index Optimization

The schema includes indexes on:
- `code` - Fast lookups by document code
- `status` - Filter by document status
- `department` - Filter by department
- `created_at` - Time-based queries
- `document_id` (annexes/chapters) - Relationship queries

### Connection Pooling

The `DatabaseManager` includes connection pooling configured in `CONTENT_CREATOR_FRAMEWORK/database/session.py`:

```python
# Default pool configuration
pool_size = 20          # Number of connections to keep
max_overflow = 20       # Additional connections when needed
pool_recycle = 3600     # Recycle connections after 1 hour
pool_pre_ping = True    # Test connections before using
```

Adjust via environment variables:

```bash
export DATABASE_POOL_SIZE=30
export DATABASE_MAX_OVERFLOW=30
export DATABASE_POOL_RECYCLE=1800
export DATABASE_ECHO=true  # Enable SQL query logging
```

### Query Optimization

For large datasets, consider:
- Pagination: Use `LIMIT` and `OFFSET`
- Selective columns: `SELECT code, title FROM documents`
- Batch operations: Insert/update multiple records in one transaction

## Backup and Recovery

### Create Backup

```bash
# Full database backup
pg_dump -U qmsuser -d qms_creator > qms_backup.sql

# Compressed backup
pg_dump -U qmsuser -d qms_creator | gzip > qms_backup.sql.gz

# Backup with data only (no schema)
pg_dump -U qmsuser -d qms_creator --data-only > qms_data_backup.sql
```

### Restore from Backup

```bash
# Restore full database
psql -U qmsuser -d qms_creator < qms_backup.sql

# Restore from compressed backup
gunzip -c qms_backup.sql.gz | psql -U qmsuser -d qms_creator

# Restore into new database
createdb -U qmsuser qms_creator_restored
psql -U qmsuser -d qms_creator_restored < qms_backup.sql
```

## Troubleshooting

### Connection Refused

```
psycopg2.OperationalError: connection to server at "localhost" (127.0.0.1), port 5432 failed
```

**Solution:**
- Verify PostgreSQL is running: `sudo systemctl status postgresql`
- Check connection credentials
- Verify database exists: `psql -U postgres -l`

### Migration Conflicts

```
alembic.util.exc.CommandError: Can't create alembic_version table
```

**Solution:**
- Ensure database user has CREATE privileges
- Try with superuser: `sudo -u postgres psql`

### Data Mismatch

```
Migration verification: Original: 77, Migrated: 75
```

**Solution:**
- Check JSON file for valid entries
- Run migration with verbose logging: Add `logger.setLevel(logging.DEBUG)`
- Manually inspect invalid documents in JSON

## Docker Deployment

Complete Docker-based setup:

```bash
# Start PostgreSQL
docker run --name qms_postgres \
  -e POSTGRES_USER=qmsuser \
  -e POSTGRES_PASSWORD=qmspassword \
  -e POSTGRES_DB=qms_creator \
  -p 5432:5432 \
  -v pgdata:/var/lib/postgresql/data \
  -d postgres:16

# Run migration in container
docker run --rm \
  --network host \
  -e DATABASE_URL="postgresql://qmsuser:qmspassword@localhost/qms_creator" \
  -v $(pwd):/app \
  python:3.12 \
  bash -c "cd /app && pip install -r requirements.txt && python scripts/migrate_json_to_postgres.py"
```

## API Migration

After migration, update API endpoints to use PostgreSQL:

### Before (JSON):
```python
@app.get("/documents")
def get_documents(db: QMSDatabase):
    return db.get_all_documents()
```

### After (PostgreSQL):
```python
@app.get("/documents")
def get_documents(db: Session = Depends(get_db_session)):
    docs = db.query(Document).all()
    return [doc.to_dict() for doc in docs]
```

## Next Steps

After successful migration:

1. **Test thoroughly** - Verify all features work with PostgreSQL
2. **Performance test** - Load test with actual workload
3. **Archive JSON** - Keep backup, then remove from production
4. **Update CI/CD** - Ensure deployment includes database setup
5. **Document changes** - Update deployment documentation
6. **Monitor** - Watch database performance metrics

## Support

For issues or questions:

1. Check `logs/` directory for database errors
2. Enable SQL logging: `export DATABASE_ECHO=true`
3. Review PostgreSQL logs: `sudo tail -f /var/log/postgresql/postgresql.log`
4. Consult SQLAlchemy documentation: https://docs.sqlalchemy.org/
5. Check Alembic guide: https://alembic.sqlalchemy.org/
