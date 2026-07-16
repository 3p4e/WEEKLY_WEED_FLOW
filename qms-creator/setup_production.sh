#!/bin/bash

# Cannabis EU GMP QMS Creator - Production Setup Script
# This script helps deploy the platform in a production environment.

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="Cannabis EU GMP QMS Creator"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${PROJECT_ROOT}/setup_production_${TIMESTAMP}.log"

# Logging function
log() {
    local level=$1
    local message=$2
    local color=$NC

    case $level in
        "INFO") color=$GREEN ;;
        "WARN") color=$YELLOW ;;
        "ERROR") color=$RED ;;
        "DEBUG") color=$BLUE ;;
    esac

    echo -e "${color}[$(date '+%Y-%m-%d %H:%M:%S')] [$level] ${message}${NC}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] ${message}" >> "$LOG_FILE"
}

# Print banner
print_banner() {
    echo "================================================================"
    echo "   Cannabis EU GMP QMS Creator - Production Setup"
    echo "================================================================"
    echo ""
}

# Check prerequisites
check_prerequisites() {
    log "INFO" "Checking prerequisites..."

    # Check Python
    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version | awk '{print $2}')
        log "INFO" "Python found: $PYTHON_VERSION"
    else
        log "ERROR" "Python 3 is required but not installed"
        exit 1
    fi

    # Check pip
    if command -v pip3 &>/dev/null; then
        log "INFO" "pip3 found"
    else
        log "WARN" "pip3 not found, trying pip..."
        if ! command -v pip &>/dev/null; then
            log "ERROR" "pip is required but not installed"
            exit 1
        fi
    fi

    # Check Node.js (optional, frontend is pre-built)
    if command -v node &>/dev/null; then
        NODE_VERSION=$(node --version)
        log "INFO" "Node.js found: $NODE_VERSION"
    else
        log "WARN" "Node.js not found (frontend is pre-built, so this is OK)"
    fi

    # Check Docker
    if command -v docker &>/dev/null; then
        DOCKER_VERSION=$(docker --version | awk '{print $3}' | tr -d ',')
        log "INFO" "Docker found: $DOCKER_VERSION"
        DOCKER_AVAILABLE=true
    else
        log "WARN" "Docker not found, will use manual deployment"
        DOCKER_AVAILABLE=false
    fi

    # Check Docker Compose
    if command -v docker-compose &>/dev/null; then
        log "INFO" "docker-compose found"
        DOCKER_COMPOSE_AVAILABLE=true
    elif command -v docker &>/dev/null && docker compose version &>/dev/null; then
        log "INFO" "docker compose (plugin) found"
        DOCKER_COMPOSE_AVAILABLE=true
    else
        log "WARN" "docker-compose not found"
        DOCKER_COMPOSE_AVAILABLE=false
    fi

    # Check PostgreSQL client
    if command -v psql &>/dev/null; then
        log "INFO" "PostgreSQL client found"
    else
        log "WARN" "PostgreSQL client (psql) not found"
    fi

    log "INFO" "Prerequisites check completed"
}

# Ask for deployment method
select_deployment_method() {
    echo ""
    echo "Select deployment method:"
    echo "1) Docker Compose (Recommended for production)"
    echo "2) Manual deployment (No Docker)"
    echo "3) Exit"
    echo ""

    while true; do
        read -p "Enter choice [1-3]: " choice
        case $choice in
            1)
                if [ "$DOCKER_AVAILABLE" = true ] && [ "$DOCKER_COMPOSE_AVAILABLE" = true ]; then
                    DEPLOYMENT_METHOD="docker"
                    log "INFO" "Selected Docker Compose deployment"
                    return
                else
                    log "ERROR" "Docker or docker-compose not available"
                    echo "Falling back to manual deployment..."
                    DEPLOYMENT_METHOD="manual"
                    return
                fi
                ;;
            2)
                DEPLOYMENT_METHOD="manual"
                log "INFO" "Selected manual deployment"
                return
                ;;
            3)
                log "INFO" "Exiting setup"
                exit 0
                ;;
            *)
                echo "Invalid choice, please try again"
                ;;
        esac
    done
}

# Setup environment variables
setup_environment() {
    log "INFO" "Setting up environment variables..."

    # Check for existing .env.production
    if [ -f "${PROJECT_ROOT}/.env.production" ]; then
        log "WARN" ".env.production already exists"
        read -p "Do you want to overwrite it? (y/N): " overwrite
        if [[ ! $overwrite =~ ^[Yy]$ ]]; then
            log "INFO" "Using existing .env.production"
            return
        fi
    fi

    # Create .env.production from example
    if [ -f "${PROJECT_ROOT}/.env.example" ]; then
        cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env.production"
        log "INFO" "Created .env.production from template"
    else
        log "ERROR" ".env.example not found"
        exit 1
    fi

    # Generate secure API key if not present
    if ! grep -q "API_KEY=" "${PROJECT_ROOT}/.env.production" || grep -q "API_KEY=change-me" "${PROJECT_ROOT}/.env.production"; then
        NEW_API_KEY=$(openssl rand -base64 32 2>/dev/null || echo "secure-api-key-$(date +%s)")
        sed -i "s|API_KEY=.*|API_KEY=${NEW_API_KEY}|" "${PROJECT_ROOT}/.env.production"
        log "INFO" "Generated secure API key"
    fi

    # Generate secure database password if using Docker
    if [ "$DEPLOYMENT_METHOD" = "docker" ]; then
        if ! grep -q "DB_PASSWORD=" "${PROJECT_ROOT}/.env.production" || grep -q "DB_PASSWORD=changeme" "${PROJECT_ROOT}/.env.production"; then
            NEW_DB_PASSWORD=$(openssl rand -base64 16 2>/dev/null || echo "secure-db-pwd-$(date +%s)")
            sed -i "s|DB_PASSWORD=.*|DB_PASSWORD=${NEW_DB_PASSWORD}|" "${PROJECT_ROOT}/.env.production"
            log "INFO" "Generated secure database password"
        fi
    fi

    echo ""
    echo "Environment file created: ${PROJECT_ROOT}/.env.production"
    echo "Please review and edit if necessary:"
    echo "  - API_KEY: Used for API authentication"
    echo "  - DB_PASSWORD: Database password (for Docker)"
    echo "  - Other settings as needed"
    echo ""
    read -p "Press Enter to continue after reviewing..."
}

# Setup PostgreSQL (for manual deployment)
setup_postgresql() {
    if [ "$DEPLOYMENT_METHOD" != "manual" ]; then
        return
    fi

    log "INFO" "Setting up PostgreSQL for manual deployment..."

    echo ""
    echo "PostgreSQL setup for manual deployment"
    echo "You need to have PostgreSQL installed and running."
    echo ""

    read -p "PostgreSQL host [localhost]: " DB_HOST
    DB_HOST=${DB_HOST:-localhost}

    read -p "PostgreSQL port [5432]: " DB_PORT
    DB_PORT=${DB_PORT:-5432}

    read -p "Database name [qms]: " DB_NAME
    DB_NAME=${DB_NAME:-qms}

    read -p "Database username [qmsuser]: " DB_USER
    DB_USER=${DB_USER:-qmsuser}

    read -s -p "Database password: " DB_PASSWORD
    echo ""

    # Update .env.production
    DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
    sed -i "s|# DATABASE_URL=.*|DATABASE_URL=${DATABASE_URL}|" "${PROJECT_ROOT}/.env.production"
    sed -i "s|USE_POSTGRESQL=.*|USE_POSTGRESQL=true|" "${PROJECT_ROOT}/.env.production"

    log "INFO" "Database configuration updated"

    # Test connection
    echo ""
    echo "Testing PostgreSQL connection..."
    if command -v psql &>/dev/null; then
        if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\q" 2>/dev/null; then
            log "INFO" "PostgreSQL connection successful"
        else
            log "WARN" "Could not connect to PostgreSQL"
            echo "Please ensure:"
            echo "  1. PostgreSQL is running"
            echo "  2. User '${DB_USER}' exists"
            echo "  3. Database '${DB_NAME}' exists"
            echo "  4. Password is correct"
            echo "  5. Host allows connections (check pg_hba.conf)"
            echo ""
            read -p "Continue anyway? (y/N): " continue_anyway
            if [[ ! $continue_anyway =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    else
        log "WARN" "psql not available, skipping connection test"
    fi
}

# Install Python dependencies
install_dependencies() {
    if [ "$DEPLOYMENT_METHOD" = "docker" ]; then
        return  # Docker will handle dependencies
    fi

    log "INFO" "Installing Python dependencies..."

    # Check for virtual environment
    if [ ! -d "${PROJECT_ROOT}/.venv" ]; then
        log "INFO" "Creating Python virtual environment..."
        python3 -m venv "${PROJECT_ROOT}/.venv"
    fi

    # Activate virtual environment
    source "${PROJECT_ROOT}/.venv/bin/activate"

    # Upgrade pip
    pip install --upgrade pip >> "$LOG_FILE" 2>&1

    # Install dependencies
    if [ -f "${PROJECT_ROOT}/requirements.txt" ]; then
        log "INFO" "Installing from requirements.txt..."
        pip install -r "${PROJECT_ROOT}/requirements.txt" >> "$LOG_FILE" 2>&1
        log "INFO" "Python dependencies installed"
    else
        log "ERROR" "requirements.txt not found"
        exit 1
    fi
}

# Run database migrations
run_migrations() {
    if [ "$DEPLOYMENT_METHOD" = "docker" ]; then
        return  # Docker will handle migrations
    fi

    log "INFO" "Running database migrations..."

    # Source environment variables
    if [ -f "${PROJECT_ROOT}/.env.production" ]; then
        set -a
        source "${PROJECT_ROOT}/.env.production"
        set +a
    fi

    # Check for alembic
    if command -v alembic &>/dev/null || [ -f "${PROJECT_ROOT}/.venv/bin/alembic" ]; then
        cd "$PROJECT_ROOT"
        alembic upgrade head >> "$LOG_FILE" 2>&1
        log "INFO" "Database migrations completed"
    else
        log "WARN" "Alembic not found, skipping migrations"
    fi
}

# Start Docker deployment
start_docker_deployment() {
    log "INFO" "Starting Docker Compose deployment..."

    # Check Docker permissions
    if ! docker ps >/dev/null 2>&1; then
        log "ERROR" "Docker daemon not accessible"
        echo ""
        echo "Possible solutions:"
        echo "  1. Add your user to docker group: sudo usermod -aG docker \$USER"
        echo "  2. Use sudo (not recommended): sudo docker-compose up --build -d"
        echo "  3. Start docker service: sudo systemctl start docker"
        echo ""
        read -p "Try with sudo? (y/N): " use_sudo
        if [[ $use_sudo =~ ^[Yy]$ ]]; then
            DOCKER_PREFIX="sudo"
        else
            log "ERROR" "Cannot continue without Docker access"
            exit 1
        fi
    fi

    echo ""
    echo "Starting Docker Compose services..."
    echo "This may take several minutes on first run."
    echo ""

    # Build and start containers
    cd "$PROJECT_ROOT"
    if $DOCKER_PREFIX docker-compose up --build -d; then
        log "INFO" "Docker Compose started successfully"

        # Show container status
        echo ""
        echo "Container status:"
        $DOCKER_PREFIX docker-compose ps

        # Show logs
        echo ""
        echo "Showing logs (Ctrl+C to exit):"
        $DOCKER_PREFIX docker-compose logs -f --tail=50
    else
        log "ERROR" "Failed to start Docker Compose"
        echo "Check logs: ${LOG_FILE}"
        exit 1
    fi
}

# Start manual deployment
start_manual_deployment() {
    log "INFO" "Starting manual deployment..."

    # Source environment variables
    if [ -f "${PROJECT_ROOT}/.env.production" ]; then
        set -a
        source "${PROJECT_ROOT}/.env.production"
        set +a
    fi

    # Activate virtual environment if exists
    if [ -d "${PROJECT_ROOT}/.venv" ]; then
        source "${PROJECT_ROOT}/.venv/bin/activate"
    fi

    echo ""
    echo "Starting manual deployment..."
    echo ""
    echo "You will need to run these commands in separate terminals:"
    echo ""
    echo "Terminal 1 - Backend API:"
    echo "  cd \"${PROJECT_ROOT}\""
    echo "  source .venv/bin/activate  # If using virtual environment"
    echo "  python -m uvicorn CONTENT_CREATOR_FRAMEWORK.main_api:app \\"
    echo "    --host ${BACKEND_HOST:-0.0.0.0} \\"
    echo "    --port ${BACKEND_PORT:-8000} \\"
    echo "    --workers 4"
    echo ""
    echo "Terminal 2 - Frontend (optional, pre-built files available):"
    echo "  # Serve pre-built frontend:"
    echo "  python3 -m http.server 3000 --directory \"${PROJECT_ROOT}/qms-ui/dist\""
    echo ""
    echo "Or use Nginx for production (recommended):"
    echo "  sudo cp \"${PROJECT_ROOT}/nginx/nginx.conf\" /etc/nginx/sites-available/qms"
    echo "  sudo ln -s /etc/nginx/sites-available/qms /etc/nginx/sites-enabled/"
    echo "  sudo systemctl restart nginx"
    echo ""

    read -p "Do you want to start the backend now? (Y/n): " start_backend
    if [[ ! $start_backend =~ ^[Nn]$ ]]; then
        log "INFO" "Starting backend API..."
        python -m uvicorn CONTENT_CREATOR_FRAMEWORK.main_api:app \
            --host ${BACKEND_HOST:-0.0.0.0} \
            --port ${BACKEND_PORT:-8000} \
            --workers 4
    fi
}

# Verify deployment
verify_deployment() {
    log "INFO" "Verifying deployment..."

    echo ""
    echo "Verification steps:"
    echo ""

    # Check backend health
    echo "1. Backend API Health:"
    if curl -s http://localhost:8000/health >/dev/null; then
        echo "   ✅ Backend is responding"
    else
        echo "   ❌ Backend is not responding"
    fi

    # Check frontend
    echo "2. Frontend:"
    if [ "$DEPLOYMENT_METHOD" = "docker" ]; then
        if curl -s http://localhost/ >/dev/null; then
            echo "   ✅ Frontend is responding (via Nginx)"
        else
            echo "   ❌ Frontend is not responding"
        fi
    else
        echo "   ⚠️  Frontend needs to be started separately"
    fi

    # Test API key authentication
    echo "3. API Authentication:"
    API_KEY=$(grep "API_KEY=" "${PROJECT_ROOT}/.env.production" | cut -d'=' -f2)
    if curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/health >/dev/null; then
        echo "   ✅ API key authentication works"
    else
        echo "   ❌ API key authentication failed"
    fi

    echo ""
    echo "For detailed API documentation, visit: http://localhost:8000/docs"
    echo "Log file: ${LOG_FILE}"
    echo ""
}

# Main function
main() {
    print_banner

    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        log "WARN" "Running as root is not recommended"
        read -p "Continue anyway? (y/N): " continue_root
        if [[ ! $continue_root =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi

    # Create log file
    touch "$LOG_FILE"
    log "INFO" "Starting production setup"
    log "INFO" "Project root: ${PROJECT_ROOT}"

    # Check prerequisites
    check_prerequisites

    # Select deployment method
    select_deployment_method

    # Setup environment
    setup_environment

    # Setup PostgreSQL for manual deployment
    if [ "$DEPLOYMENT_METHOD" = "manual" ]; then
        setup_postgresql
    fi

    # Install dependencies for manual deployment
    if [ "$DEPLOYMENT_METHOD" = "manual" ]; then
        install_dependencies
        run_migrations
    fi

    # Start deployment
    if [ "$DEPLOYMENT_METHOD" = "docker" ]; then
        start_docker_deployment
    else
        start_manual_deployment
    fi

    # Verify deployment
    verify_deployment

    log "INFO" "Setup completed"
    echo ""
    echo "================================================================"
    echo "   Production setup completed successfully!"
    echo "================================================================"
    echo ""
    echo "Next steps:"
    echo "  1. Review the verification output above"
    echo "  2. Test document generation with sample requests"
    echo "  3. Configure monitoring and backups"
    echo "  4. Set up SSL/TLS for production"
    echo ""
    echo "For help, see DEPLOYMENT_GUIDE.md in the project directory."
    echo ""
}

# Run main function
main "$@"
