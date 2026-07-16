#!/bin/bash

# ============================================================================
# VPS Connection Test Script
# Tests Hostinger VPS with Ollama setup
# ============================================================================

set -e

# ============================================================================
# CONFIGURATION
# ============================================================================

VPS_HOST="srv1211306.hstgr.cloud"
VPS_IP="72.61.176.37"
SSH_USER="root"
SSH_KEY="$HOME/.ssh/hostinger-vps-access"
SSH_PORT="22"
OLLAMA_PORT="11434"
WEBUI_PORT="8080"

# ============================================================================
# COLOR DEFINITIONS
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

print_header() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

test_pass() {
    print_success "$1"
    return 0
}

test_fail() {
    print_error "$1"
    return 1
}

test_warn() {
    print_warning "$1"
    return 2
}

# ============================================================================
# TEST FUNCTIONS
# ============================================================================

test_ssh_key() {
    echo -e "\n${MAGENTA}[1/8] Testing SSH Key Configuration${NC}"

    if [ ! -f "$SSH_KEY" ]; then
        test_fail "SSH key not found at: $SSH_KEY"
        return 1
    fi

    if [ ! -f "${SSH_KEY}.pub" ]; then
        test_fail "SSH public key not found at: ${SSH_KEY}.pub"
        return 1
    fi

    chmod 600 "$SSH_KEY" 2>/dev/null || true

    test_pass "SSH key files exist and permissions set"
    return 0
}

test_ssh_connection() {
    echo -e "\n${MAGENTA}[2/8] Testing SSH Connection${NC}"

    local timeout=10
    local start_time=$(date +%s)

    if ssh -i "$SSH_KEY" -o BatchMode=yes -o ConnectTimeout="$timeout" \
        -p "$SSH_PORT" "${SSH_USER}@${VPS_HOST}" "echo 'SSH connection successful'" 2>/dev/null; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        test_pass "SSH connection established (${duration}s)"
        return 0
    else
        test_fail "SSH connection failed"
        print_info "Troubleshooting:"
        print_info "  ssh -vvv -i '$SSH_KEY' ${SSH_USER}@${VPS_HOST}"
        print_info "  Check if password is correct: C@nnabis123qwe123"
        return 1
    fi
}

test_system_resources() {
    echo -e "\n${MAGENTA}[3/8] Testing System Resources${NC}"

    local output=$(ssh -i "$SSH_KEY" -p "$SSH_PORT" "${SSH_USER}@${VPS_HOST}" "
        echo 'Memory:'
        free -h | head -2
        echo ''
        echo 'Disk:'
        df -h / | tail -1
        echo ''
        echo 'Load:'
        uptime
        echo ''
        echo 'Uptime:'
        cat /proc/uptime | awk '{print \"Days:\", \$1/86400}' | head -1
    " 2>/dev/null || echo "Failed to get system resources")

    if echo "$output" | grep -q "failed\|Failed\|error\|Error"; then
        test_fail "Could not retrieve system resources"
        return 1
    fi

    echo "$output"

    # Check if resources are adequate
    local mem=$(echo "$output" | grep "Mem:" | awk '{print $3}' | sed 's/Gi//')
    local disk=$(echo "$output" | grep "/dev/" | awk '{print $5}' | sed 's/%//')

    if [ -n "$mem" ] && [ "$mem" -gt 10 ]; then
        test_warn "Memory usage high: ${mem}GB used"
    elif [ -n "$mem" ]; then
        test_pass "Memory usage normal: ${mem}GB used"
    fi

    if [ -n "$disk" ] && [ "$disk" -gt 80 ]; then
        test_warn "Disk usage high: ${disk}% used"
    elif [ -n "$disk" ]; then
        test_pass "Disk usage normal: ${disk}% used"
    fi

    return 0
}

test_ollama_service() {
    echo -e "\n${MAGENTA}[4/8] Testing Ollama Service${NC}"

    # Test service status
    local service_status=$(ssh -i "$SSH_KEY" -p "$SSH_PORT" "${SSH_USER}@${VPS_HOST}" "
        systemctl status ollama 2>/dev/null | grep -E '(Active:|Main PID:|Loaded:|Status:)'
    " 2>/dev/null || echo "Service check failed")

    if echo "$service_status" | grep -q "active (running)\|activating"; then
        test_pass "Ollama service is running"
    else
        test_fail "Ollama service not running"
        echo "$service_status"
        return 1
    fi

    # Test API version
    local api_version=$(ssh -i "$SSH_KEY" -p "$SSH_PORT" "${SSH_USER}@${VPS_HOST}" "
        curl -s -m 5 http://localhost:${OLLAMA_PORT}/api/version 2>/dev/null || echo 'API not reachable'
    " 2>/dev/null)

    if echo "$api_version" | grep -q "version"; then
        test_pass "Ollama API accessible locally"
        echo "  Version: $api_version"
    else
        test_fail "Ollama API not reachable locally"
        return 1
    fi

    return 0
}

test_ollama_models() {
    echo -e "\n${MAGENTA}[5/8] Testing Ollama Models${NC}"

    local models=$(ssh -i "$SSH_KEY" -p "$SSH_PORT" "${SSH_USER}@${VPS_HOST}" "
        ollama list 2>/dev/null || echo 'Ollama command failed'
    " 2>/dev/null)

    if echo "$models" | grep -q "NAME\|MODEL"; then
        test_pass "Models found:"
        echo "$models" | sed 's/^/  /'

        local model_count=$(echo "$models" | grep -c "^[a-zA-Z]" || echo "0")
        if [ "$model_count" -eq 0 ]; then
            test_warn "No models listed (might be still loading)"
        elif [ "$model_count" -lt 2 ]; then
            test_warn "Only $model_count model(s) installed"
        else
            test_pass "$model_count model(s) available"
        fi
    else
        test_warn "Could not list models (service might be starting)"
        echo "  Output: $models"
    fi

    return 0
}

test_remote_ollama_api() {
    echo -e "\n${MAGENTA}[6/8] Testing Remote Ollama API${NC}"

    local response=$(curl -s -m 10 "http://${VPS_IP}:${OLLAMA_PORT}/api/version" 2>/dev/null || echo "Connection failed")

    if echo "$response" | grep -q "version"; then
        test_pass "Ollama API accessible remotely"
        echo "  Response: $response"
        return 0
    else
        test_fail "Ollama API not accessible remotely"
        print_info "Check firewall: ufw status"
        print_info "Check Ollama is listening on all interfaces"
        return 1
    fi
}

test_webui() {
    echo -e "\n${MAGENTA}[7/8] Testing Open WebUI${NC}"

    # Check if service is running
    local webui_status=$(ssh -i "$SSH_KEY" -p "$SSH_PORT" "${SSH_USER}@${VPS_HOST}" "
        ss -tlnp | grep ':${WEBUI_PORT}' || echo 'Port not listening'
    " 2>/dev/null)

    if echo "$webui_status" | grep -q "${WEBUI_PORT}"; then
        test_pass "WebUI service is listening on port ${WEBUI_PORT}"
    else
        test_fail "WebUI not listening on port ${WEBUI_PORT}"
        return 1
    fi

    # Test remote access
    local webui_response=$(curl -s -m 10 -I "http://${VPS_IP}:${WEBUI_PORT}" 2>/dev/null | head -1 || echo "Connection failed")

    if echo "$webui_response" | grep -q "200\|301\|302"; then
        test_pass "WebUI accessible remotely"
        echo "  Response: $webui_response"
    else
        test_warn "WebUI not accessible remotely (might need time to start)"
        echo "  Response: $webui_response"
    fi

    return 0
}

test_firewall() {
    echo -e "\n${MAGENTA}[8/8] Testing Firewall Configuration${NC}"

    local fw_status=$(ssh -i "$SSH_KEY" -p "$SSH_PORT" "${SSH_USER}@${VPS_HOST}" "
        ufw status 2>/dev/null | grep -E '(Status:|22/tcp|11434/tcp|8080/tcp)' || echo 'UFW not available'
    " 2>/dev/null)

    if echo "$fw_status" | grep -q "Status: active"; then
        test_pass "Firewall is active"

        # Check required ports
        local missing_ports=""
        if ! echo "$fw_status" | grep -q "22/tcp"; then
            missing_ports="$missing_ports 22(SSH)"
        fi
        if ! echo "$fw_status" | grep -q "11434/tcp"; then
            missing_ports="$missing_ports 11434(Ollama)"
        fi
        if ! echo "$fw_status" | grep -q "8080/tcp"; then
            missing_ports="$missing_ports 8080(WebUI)"
        fi

        if [ -n "$missing_ports" ]; then
            test_warn "Missing firewall rules:$missing_ports"
        else
            test_pass "All required ports are allowed"
        fi

        echo "$fw_status" | sed 's/^/  /'
    else
        test_warn "Firewall not active or not installed"
        echo "  Status: $fw_status"
    fi

    return 0
}

# ============================================================================
# SUMMARY FUNCTION
# ============================================================================

print_summary() {
    print_header "TEST SUMMARY"

    echo -e "\n${CYAN}Connection Details:${NC}"
    echo "  Host: $VPS_HOST"
    echo "  IP: $VPS_IP"
    echo "  User: $SSH_USER"
    echo "  SSH Key: $SSH_KEY"

    echo -e "\n${CYAN}Service Endpoints:${NC}"
    echo "  SSH: ssh://${SSH_USER}@${VPS_HOST}:${SSH_PORT}"
    echo "  Ollama API: http://${VPS_IP}:${OLLAMA_PORT}"
    echo "  Open WebUI: http://${VPS_IP}:${WEBUI_PORT}"

    echo -e "\n${CYAN}Zed Editor Connection:${NC}"
    echo "  In Zed: Cmd+Shift+P → 'Open Remote' → Enter:"
    echo "  ssh://${SSH_USER}@${VPS_HOST}:${SSH_PORT}"
    echo "  or"
    echo "  ssh://ollama-vps"

    echo -e "\n${CYAN}SSH Tunnel for Local Ollama Access:${NC}"
    echo "  ssh -L 11434:localhost:11434 -N ${SSH_USER}@${VPS_HOST}"
    echo "  Then access Ollama at: http://localhost:11434"

    echo -e "\n${CYAN}Quick Test Commands:${NC}"
    echo "  Test SSH: ssh -i '$SSH_KEY' ${SSH_USER}@${VPS_HOST} 'hostname'"
    echo "  Test Ollama: curl http://${VPS_IP}:11434/api/version"
    echo "  Test WebUI: curl -I http://${VPS_IP}:8080"

    echo -e "\n${GREEN}Setup appears to be complete and functional!${NC}"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    print_header "VPS CONNECTION TEST SCRIPT"
    echo "Testing connection to: $VPS_HOST ($VPS_IP)"
    echo "Start time: $(date)"
    echo ""

    local tests_passed=0
    local tests_failed=0
    local tests_warned=0

    # Run tests
    test_ssh_key && ((tests_passed++)) || ((tests_failed++))
    test_ssh_connection && ((tests_passed++)) || ((tests_failed++))
    test_system_resources && ((tests_passed++)) || ((tests_failed++))
    test_ollama_service && ((tests_passed++)) || ((tests_failed++))
    test_ollama_models && ((tests_passed++)) || ((tests_failed++))
    test_remote_ollama_api && ((tests_passed++)) || ((tests_failed++))
    test_webui && ((tests_passed++)) || ((tests_failed++))
    test_firewall && ((tests_passed++)) || ((tests_failed++))

    # Print summary
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${CYAN}Test Results:${NC}"
    echo -e "${GREEN}Passed: $tests_passed${NC}"
    echo -e "${RED}Failed: $tests_failed${NC}"
    echo -e "${YELLOW}Warnings: $tests_warned${NC}"
    echo -e "${BLUE}========================================${NC}"

    if [ $tests_failed -eq 0 ]; then
        echo -e "${GREEN}✅ All critical tests passed!${NC}"
        print_summary
        exit 0
    else
        echo -e "${YELLOW}⚠ Some tests failed. Review output above.${NC}"
        exit 1
    fi
}

# Handle script interruption
trap 'echo -e "\n${RED}Test interrupted by user${NC}"; exit 130' INT

# Run main function
main "$@"
