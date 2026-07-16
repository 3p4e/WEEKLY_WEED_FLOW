#!/bin/bash

# ==============================================================================
# Cannabis EU GMP QMS Creator - Backend Start Script
# ==============================================================================
# This script starts the FastAPI backend with production environment.
# It automatically loads configuration from .env.production and sets up
# the appropriate database backend (PostgreSQL or JSON fallback).
# ==============================================================================

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
print_info "Project root: $PROJECT_ROOT"

# Check for environment file
ENV_FILE="$PROJECT_ROOT/.env.production"
if [[ ! -f "$ENV_FILE" ]]; then
    print_error "Environment file not found: $ENV_FILE"
    print_info "Creating from template..."
    if [[ -f "$PROJECT_ROOT/.env.example" ]]; then
        cp "$PROJECT_ROOT/.env.example" "$ENV_FILE"
        print_info "Created .env.production from template. Please edit it with your configuration."
        exit 1
    else
        print_error "No .env.example template found. Please create .env.production manually."
        print_info "See DEPLOYMENT_GUIDE.md for required environment variables."
        exit 1
    fi
fi

# Load environment variables
print_info "Loading environment from: $ENV_FILE"
export $(grep -v '^#' "$ENV_FILE" | xargs) 2>/dev/null || true

# Check Python version
PYTHON_VERSION=$(python3 --version 2>/dev/null | awk '{print $2}')
if [[ -z "$PYTHON_VERSION" ]]; then
    print_error "Python 3 is not installed or not in PATH"
    exit 1
fi

print_info "Python version: $PYTHON_VERSION"

# Check for virtual environment
if [[ -d "$PROJECT_ROOT/.venv" ]]; then
    print_info "Activating virtual environment..."
    source "$PROJECT_ROOT/.venv/bin/activate"
    print_info "Virtual environment activated: $(which python)"
else
    print_warning "No virtual environment found. Using system Python."
fi

# Check dependencies
print_info "Checking Python dependencies..."
if ! python3 -c "import fastapi" 2>/dev/null; then
    print_warning "FastAPI not found. Installing dependencies..."
    pip install -r "$PROJECT_ROOT/requirements.txt"
fi

# Determine backend type
USE_POSTGRESQL=${USE_POSTGRESQL:-"true"}
if [[ "$USE_POSTGRESQL" == "true" ]]; then
    print_info "Using PostgreSQL backend"

    # Check PostgreSQL connection if DATABASE_URL is set
    if [[ -n "$DATABASE_URL" ]]; then
        print_info "Testing PostgreSQL connection..."
        if python3 -c "
import os
from sqlalchemy import create_engine, text
try:
    engine = create_engine(os.environ.get('DATABASE_URL'))
    conn = engine.connect()
    conn.execute(text('SELECT 1'))
    print('PostgreSQL connection successful')
    conn.close()
except Exception as e:
    print(f'PostgreSQL connection failed: {e}')
    exit(1)
" 2>/dev/null; then
            print_success "PostgreSQL connection verified"
        else
            print_warning "PostgreSQL connection failed, falling back to JSON backend"
            export USE_POSTGRESQL="false"
        fi
    else
        print_warning "DATABASE_URL not set, falling back to JSON backend"
        export USE_POSTGRESQL="false"
    fi
fi

if [[ "$USE_POSTGRESQL" != "true" ]]; then
    print_info "Using JSON backend (data/document_status.json)"

    # Ensure data directory exists
    DATA_DIR="$PROJECT_ROOT/data"
    if [[ ! -d "$DATA_DIR" ]]; then
        print_info "Creating data directory: $DATA_DIR"
        mkdir -p "$DATA_DIR"
    fi

    # Create initial JSON database if it doesn't exist
    JSON_DB="$DATA_DIR/document_status.json"
    if [[ ! -f "$JSON_DB" ]]; then
        print_info "Creating initial JSON database: $JSON_DB"
        echo '{"documents": [], "last_updated": "", "registry_version": "1.0"}' > "$JSON_DB"
    fi
fi

# Check if backend is already running
BACKEND_PORT=${BACKEND_PORT:-8000}
BACKEND_HOST=${BACKEND_HOST:-0.0.0.0}
API_URL="http://localhost:$BACKEND_PORT"

if curl -s "$API_URL/health" > /dev/null 2>&1; then
    print_warning "Backend is already running on $API_URL"
    print_info "To stop it: pkill -f 'uvicorn.*main_api' or Ctrl+C in the running terminal"
    exit 0
fi

# Set default API key if not set
if [[ -z "$API_KEY" ]] || [[ "$API_KEY" == "change-me-in-production" ]]; then
    print_warning "API_KEY is not set or using default value"
    print_info "Generating secure API key..."
    NEW_API_KEY=$(openssl rand -base64 32 2>/dev/null || echo "manual-key-$(date +%s)")
    export API_KEY="$NEW_API_KEY"
    print_info "Generated API_KEY: $API_KEY"
    print_info "Add this to your .env.production file for persistent use"
fi

# Set additional environment variables if not set
export ENVIRONMENT=${ENVIRONMENT:-"production"}
export LOG_LEVEL=${LOG_LEVEL:-"info"}

print_info "Starting backend with configuration:"
print_info "  Host: $BACKEND_HOST"
print_info "  Port: $BACKEND_PORT"
print_info "  Environment: $ENVIRONMENT"
print_info "  Database: $( [[ "$USE_POSTGRESQL" == "true" ]] && echo "PostgreSQL" || echo "JSON" )"
print_info "  Log level: $LOG_LEVEL"

# Run database migrations if using PostgreSQL
if [[ "$USE_POSTGRESQL" == "true" ]] && [[ -f "$PROJECT_ROOT/alembic.ini" ]]; then
    print_info "Running database migrations..."
    cd "$PROJECT_ROOT" && alembic upgrade head 2>/dev/null || print_warning "Migrations may have failed or already applied"
fi

# Initialize RAG index if needed
RAG_INDEX="$PROJECT_ROOT/.rag_index"
if [[ ! -d "$RAG_INDEX" ]]; then
    print_info "Initializing RAG index (this may take a moment)..."
    python3 -c "
import sys
sys.path.append('$PROJECT_ROOT')
from CONTENT_CREATOR_FRAMEWORK.vector_search_engine import VectorSearchEngine
engine = VectorSearchEngine()
print('RAG index initialized')
" 2>/dev/null || print_warning "RAG index initialization may have warnings"
fi

# Start the backend
print_info "Starting FastAPI backend..."
print_info "API Documentation: $API_URL/docs"
print_info "Health Check: $API_URL/health"
print_info "Press Ctrl+C to stop the server"

cd "$PROJECT_ROOT" && python3 -m uvicorn CONTENT_CREATOR_FRAMEWORK.main_api:app \
    --host "$BACKEND_HOST" \
    --port "$BACKEND_PORT" \
    --log-level "$LOG_LEVEL" \
    --reload  # Remove --reload for pure production

# Alternative production command with more workers:
# gunicorn -w 4 -k uvicorn.workers.UvicornWorker CONTENT_CREATOR_FRAMEWORK.main_api:app \
#     --bind "$BACKEND_HOST:$BACKEND_PORT" \
#     --log-level "$LOG_LEVEL" \
#     --access-logfile - \
#     --error-logfile -

# Note: For true production, consider using:
# 1. Remove --reload flag
# 2. Use gunicorn with multiple workers (commented above)
# 3. Set up proper logging to files
# 4. Use process manager (systemd, supervisor)
