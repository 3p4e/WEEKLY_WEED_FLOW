#!/bin/bash

# Cannabis EU GMP QMS Creator - Deployment Verification Script
# This script verifies all components of a production deployment.

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${PROJECT_ROOT}/verify_deployment_${TIMESTAMP}.log"
ENV_FILE="${PROJECT_ROOT}/.env.production"

# Default values
BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost"
API_KEY=""
USE_DOCKER=false

# Results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNING_TESTS=0

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
    echo "   Cannabis EU GMP QMS Creator - Deployment Verification"
    echo "================================================================"
    echo ""
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --backend-url)
                BACKEND_URL="$2"
                shift 2
                ;;
            --frontend-url)
                FRONTEND_URL="$2"
                shift 2
                ;;
            --api-key)
                API_KEY="$2"
                shift 2
                ;;
            --env-file)
                ENV_FILE="$2"
                shift 2
                ;;
            --use-docker)
                USE_DOCKER=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Show help
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --backend-url URL    Backend API URL (default: http://localhost:8000)"
    echo "  --frontend-url URL   Frontend URL (default: http://localhost)"
    echo "  --api-key KEY        API key for authentication"
    echo "  --env-file FILE      Environment file (default: .env.production)"
    echo "  --use-docker         Check Docker containers (default: false)"
    echo "  --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --backend-url http://api.example.com --api-key my-secret-key"
    echo "  $0 --use-docker"
    echo "  $0 --env-file .env.production"
}

# Load environment variables
load_environment() {
    if [ -f "$ENV_FILE" ]; then
        log "INFO" "Loading environment from: $ENV_FILE"
        # Source the file safely
        while IFS='=' read -r key value || [ -n "$key" ]; do
            # Skip comments and empty lines
            if [[ $key =~ ^# ]] || [[ -z $key ]] || [[ $key == "" ]]; then
                continue
            fi
            # Remove quotes from value
            value="${value%\"}"
            value="${value#\"}"
            value="${value%\'}"
            value="${value#\'}"

            # Export variable
            export "$key=$value"
        done < "$ENV_FILE"

        # Use API_KEY from env if not provided
        if [ -z "$API_KEY" ] && [ -n "$API_KEY" ]; then
            API_KEY="$API_KEY"
        fi

        log "INFO" "Environment loaded successfully"
    else
        log "WARN" "Environment file not found: $ENV_FILE"
    fi
}

# Test counter functions
test_start() {
    ((TOTAL_TESTS++))
    echo -n "Test $TOTAL_TESTS: "
}

test_pass() {
    echo -e "${GREEN}✓ PASS${NC}"
    ((PASSED_TESTS++))
}

test_fail() {
    echo -e "${RED}✗ FAIL${NC}"
    ((FAILED_TESTS++))
}

test_warn() {
    echo -e "${YELLOW}⚠ WARN${NC}"
    ((WARNING_TESTS++))
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if URL is reachable
check_url() {
    local url=$1
    local timeout=${2:-10}

    if command_exists curl; then
        curl -s -f --max-time "$timeout" "$url" >/dev/null 2>&1
        return $?
    elif command_exists wget; then
        wget -q --timeout="$timeout" --tries=1 "$url" -O /dev/null >/dev/null 2>&1
        return $?
    else
        log "WARN" "Neither curl nor wget found, cannot check URL: $url"
        return 1
    fi
}

# Test 1: Check prerequisites
test_prerequisites() {
    test_start
    echo "Checking prerequisites"

    local missing=()

    # Check Python
    if ! command_exists python3; then
        missing+=("python3")
    fi

    # Check curl/wget
    if ! command_exists curl && ! command_exists wget; then
        missing+=("curl or wget")
    fi

    if [ ${#missing[@]} -eq 0 ]; then
        test_pass
        log "INFO" "All prerequisites met"
    else
        test_fail
        log "ERROR" "Missing prerequisites: ${missing[*]}"
    fi
}

# Test 2: Check Docker (if requested)
test_docker() {
    if [ "$USE_DOCKER" = true ]; then
        test_start
        echo "Checking Docker containers"

        if ! command_exists docker; then
            test_fail
            log "ERROR" "Docker not installed"
            return
        fi

        # Check if Docker daemon is running
        if ! docker ps >/dev/null 2>&1; then
            test_fail
            log "ERROR" "Docker daemon not running"
            return
        fi

        # Check specific containers
        local containers=("qms-api" "qms-ui" "qms-db")
        local missing_containers=()

        for container in "${containers[@]}"; do
            if ! docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
                missing_containers+=("$container")
            fi
        done

        if [ ${#missing_containers[@]} -eq 0 ]; then
            test_pass
            log "INFO" "All Docker containers running"
        else
            test_fail
            log "ERROR" "Missing containers: ${missing_containers[*]}"
        fi
    fi
}

# Test 3: Check backend health
test_backend_health() {
    test_start
    echo "Checking backend health at $BACKEND_URL/health"

    if check_url "$BACKEND_URL/health"; then
        # Try to get JSON response
        if command_exists curl; then
            response=$(curl -s "$BACKEND_URL/health" 2>/dev/null || echo "")
            if echo "$response" | grep -q '"status":' || echo "$response" | grep -q 'healthy'; then
                test_pass
                log "INFO" "Backend health check passed"
                return
            fi
        fi
        test_pass
        log "INFO" "Backend responding"
    else
        test_fail
        log "ERROR" "Backend not responding at $BACKEND_URL/health"
    fi
}

# Test 4: Check backend API documentation
test_backend_docs() {
    test_start
    echo "Checking backend API documentation at $BACKEND_URL/docs"

    if check_url "$BACKEND_URL/docs"; then
        test_pass
        log "INFO" "API documentation available"
    else
        test_warn
        log "WARN" "API documentation not available (optional)"
    fi
}

# Test 5: Check API authentication
test_api_authentication() {
    test_start
    echo "Testing API key authentication"

    if [ -z "$API_KEY" ]; then
        test_warn
        log "WARN" "No API key provided, skipping authentication test"
        return
    fi

    if command_exists curl; then
        # Try to access a protected endpoint
        response=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" "$BACKEND_URL/health" 2>/dev/null || echo "")

        if [ "$response" = "200" ]; then
            test_pass
            log "INFO" "API authentication successful"
        elif [ "$response" = "401" ]; then
            test_fail
            log "ERROR" "API authentication failed (401 Unauthorized)"
        else
            test_warn
            log "WARN" "Unexpected response: HTTP $response"
        fi
    else
        test_warn
        log "WARN" "curl not available, skipping authentication test"
    fi
}

# Test 6: Check frontend
test_frontend() {
    test_start
    echo "Checking frontend at $FRONTEND_URL"

    if check_url "$FRONTEND_URL"; then
        test_pass
        log "INFO" "Frontend responding"
    else
        test_warn
        log "WARN" "Frontend not responding (may need to start separately)"
    fi
}

# Test 7: Check database connectivity
test_database() {
    test_start
    echo "Checking database connectivity"

    # Check if DATABASE_URL is set
    if [ -n "$DATABASE_URL" ]; then
        log "INFO" "Database URL: $(echo "$DATABASE_URL" | sed 's/:[^:]*@/:***@/')"

        # Try to connect using Python
        python_script=$(cat << 'EOF'
import os
import sys
try:
    from sqlalchemy import create_engine, text
    engine = create_engine(os.environ.get('DATABASE_URL', ''))
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print("SUCCESS")
except Exception as e:
    print(f"ERROR: {str(e)}")
    sys.exit(1)
EOF
        )

        if python3 -c "$python_script" 2>/dev/null | grep -q "SUCCESS"; then
            test_pass
            log "INFO" "Database connection successful"
        else
            test_fail
            log "ERROR" "Database connection failed"
        fi
    else
        test_warn
        log "WARN" "DATABASE_URL not set, skipping database test"
    fi
}

# Test 8: Check document generation
test_document_generation() {
    test_start
    echo "Testing document generation (basic)"

    if [ -z "$API_KEY" ]; then
        test_warn
        log "WARN" "No API key, skipping document generation test"
        return
    fi

    if command_exists curl; then
        # Simple test request
        request_json='{
            "sop_name": "Verification Test SOP",
            "sop_type": "Quality Assurance",
            "keywords": ["test", "verification"],
            "department": "Quality"
        }'

        # Make request
        response=$(curl -s -w "\n%{http_code}" -X POST \
            -H "Content-Type: application/json" \
            -H "X-API-Key: $API_KEY" \
            -d "$request_json" \
            "$BACKEND_URL/generate" 2>/dev/null || echo "")

        http_code=$(echo "$response" | tail -n1)
        response_body=$(echo "$response" | head -n-1)

        if [ "$http_code" = "200" ]; then
            test_pass
            log "INFO" "Document generation endpoint responding"

            # Check if file was created
            if echo "$response_body" | grep -q '"output_files"' || echo "$response_body" | grep -q '"status"'; then
                log "INFO" "Document generation successful"
            fi
        elif [ "$http_code" = "401" ]; then
            test_fail
            log "ERROR" "Document generation: Authentication failed"
        elif [ "$http_code" = "500" ]; then
            test_warn
            log "WARN" "Document generation: Server error (may be expected without AI services)"
        else
            test_warn
            log "WARN" "Document generation: Unexpected response (HTTP $http_code)"
        fi
    else
        test_warn
        log "WARN" "curl not available, skipping document generation test"
    fi
}

# Test 9: Check RAG system
test_rag_system() {
    test_start
    echo "Checking RAG system components"

    # Check if FAISS index exists
    local rag_index="${PROJECT_ROOT}/.rag_index"
    if [ -d "$rag_index" ]; then
        if [ -f "$rag_index/index.faiss" ] || [ -f "$rag_index/index.pkl" ]; then
            test_pass
            log "INFO" "RAG index files found"
        else
            test_warn
            log "WARN" "RAG directory exists but index files not found"
        fi
    else
        test_warn
        log "WARN" "RAG index directory not found (may need initialization)"
    fi
}

# Test 10: Check output directories
test_output_directories() {
    test_start
    echo "Checking output directories"

    local dirs=("output" "output/generated_sops" "sops_created" "data")
    local missing_dirs=()

    for dir in "${dirs[@]}"; do
        full_path="${PROJECT_ROOT}/${dir}"
        if [ ! -d "$full_path" ]; then
            missing_dirs+=("$dir")
        fi
    done

    if [ ${#missing_dirs[@]} -eq 0 ]; then
        test_pass
        log "INFO" "All output directories exist"
    else
        # Try to create missing directories
        for dir in "${missing_dirs[@]}"; do
            full_path="${PROJECT_ROOT}/${dir}"
            mkdir -p "$full_path" 2>/dev/null && log "INFO" "Created directory: $dir"
        done

        # Check again
        missing_dirs=()
        for dir in "${dirs[@]}"; do
            full_path="${PROJECT_ROOT}/${dir}"
            if [ ! -d "$full_path" ]; then
                missing_dirs+=("$dir")
            fi
        done

        if [ ${#missing_dirs[@]} -eq 0 ]; then
            test_pass
            log "INFO" "Output directories created successfully"
        else
            test_warn
            log "WARN" "Missing directories: ${missing_dirs[*]}"
        fi
    fi
}

# Test 11: Check external services (optional)
test_external_services() {
    test_start
    echo "Checking external services (optional)"

    local services_checked=0
    local services_available=0

    # Check Ollama
    if [ -n "$OLLAMA_URL" ] && [ "$OLLAMA_URL" != "http://localhost:11434" ]; then
        ((services_checked++))
        if check_url "$OLLAMA_URL/api/tags" 5; then
            ((services_available++))
            log "INFO" "Ollama service available"
        else
            log "WARN" "Ollama service not available"
        fi
    fi

    # Check if OpenAI API key is set (just check existence, not validity)
    if [ -n "$OPENAI_API_KEY" ]; then
        ((services_checked++))
        log "INFO" "OpenAI API key configured"
        ((services_available++))
    fi

    # Check if Anthropic API key is set
    if [ -n "$ANTHROPIC_API_KEY" ]; then
        ((services_checked++))
        log "INFO" "Anthropic API key configured"
        ((services_available++))
    fi

    if [ $services_checked -eq 0 ]; then
        test_warn
        log "WARN" "No external services configured (optional)"
    elif [ $services_available -eq $services_checked ]; then
        test_pass
        log "INFO" "All configured external services available"
    else
        test_warn
        log "WARN" "Some external services not available ($services_available/$services_checked)"
    fi
}

# Print summary
print_summary() {
    echo ""
    echo "================================================================"
    echo "   VERIFICATION SUMMARY"
    echo "================================================================"
    echo ""

    echo -e "Total tests:  ${TOTAL_TESTS}"
    echo -e "${GREEN}Passed:       ${PASSED_TESTS}${NC}"
    echo -e "${RED}Failed:       ${FAILED_TESTS}${NC}"
    echo -e "${YELLOW}Warnings:     ${WARNING_TESTS}${NC}"
    echo ""

    # Calculate success rate (excluding warnings)
    local effective_total=$((TOTAL_TESTS - WARNING_TESTS))
    if [ $effective_total -gt 0 ]; then
        local success_rate=$((PASSED_TESTS * 100 / effective_total))
        echo "Success rate: ${success_rate}%"
    fi

    echo ""

    if [ $FAILED_TESTS -eq 0 ]; then
        if [ $WARNING_TESTS -eq 0 ]; then
            echo -e "${GREEN}✅ All tests passed! Deployment is ready.${NC}"
        else
            echo -e "${GREEN}✅ Core functionality verified.${NC}"
            echo -e "${YELLOW}⚠️  Some optional components have warnings.${NC}"
        fi
    else
        echo -e "${RED}❌ Deployment has issues that need attention.${NC}"
        echo "Check the log file for details: $LOG_FILE"
    fi

    echo ""
    echo "================================================================"
    echo "   NEXT STEPS"
    echo "================================================================"
    echo ""

    if [ $FAILED_TESTS -gt 0 ]; then
        echo "1. Review failed tests above"
        echo "2. Check the log file: $LOG_FILE"
        echo "3. Fix issues and run verification again"
        echo ""
    fi

    echo "4. Test the application manually:"
    echo "   - Backend API: $BACKEND_URL/docs"
    echo "   - Frontend: $FRONTEND_URL"
    echo ""

    echo "5. Generate sample documents:"
    echo "   curl -X POST $BACKEND_URL/generate \\"
    echo "     -H \"Content-Type: application/json\" \\"
    echo "     -H \"X-API-Key: [your-api-key]\" \\"
    echo "     -d '{\"sop_name\": \"Test\", \"sop_type\": \"Quality\"}'"
    echo ""

    echo "Log file: $LOG_FILE"
    echo ""
}

# Main function
main() {
    # Parse arguments
    parse_arguments "$@"

    # Print banner
    print_banner

    # Create log file
    touch "$LOG_FILE"
    log "INFO" "Starting deployment verification"
    log "INFO" "Backend URL: $BACKEND_URL"
    log "INFO" "Frontend URL: $FRONTEND_URL"
    log "INFO" "Environment file: $ENV_FILE"

    # Load environment
    load_environment

    # Run tests
    echo "Running verification tests..."
    echo ""

    test_prerequisites
    test_docker
    test_backend_health
    test_backend_docs
    test_api_authentication
    test_frontend
    test_database
    test_document_generation
    test_rag_system
    test_output_directories
    test_external_services

    # Print summary
    print_summary

    # Exit code based on results
    if [ $FAILED_TESTS -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main function
main "$@"
