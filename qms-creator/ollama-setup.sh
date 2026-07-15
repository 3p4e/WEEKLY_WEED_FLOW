#!/bin/bash

# ============================================================================
# Ollama Setup Script for Hostinger VPS
# Cannabis EU GMP QMS Creator Project
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Ollama VPS Setup Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ============================================================================
# CONFIGURATION
# ============================================================================

VPS_HOST="srv1211306.hstgr.cloud"
VPS_IP="72.61.176.37"
SSH_PORT="22"
SSH_USER="root"
SSH_KEY_NAME="hostinger-vps-access"
ROOT_PASSWORD="C2nnabis123qwe123"
OLLAMA_HOST="0.0.0.0"
OLLAMA_PORT="11434"

# Models to install
MODELS=(
    "llama3.2"
    "codellama"
    "deepseek-coder"
    "qwen2.5-coder"
)

# ============================================================================
# FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_ssh_connection() {
    log_info "Testing SSH connection to VPS..."
    if ssh -o BatchMode=yes -o ConnectTimeout=5 "${SSH_USER}@${VPS_HOST}" "echo 'SSH connection successful'" 2>/dev/null; then
        log_info "SSH connection established"
        return 0
    else
        log_warn "SSH key not working, attempting with password..."
        return 1
    fi
}

setup_ssh_key() {
    log_info "Setting up SSH key authentication..."

    local key_path="$HOME/.ssh/${SSH_KEY_NAME}"

    # Check if key already exists
    if [ -f "${key_path}" ]; then
        log_info "SSH key already exists at ${key_path}"
    else
        log_info "Creating new SSH key pair..."
        ssh-keygen -t ed25519 -f "${key_path}" -N "" -C "hostinger-vps-access"
    fi

    # Get public key
    local public_key=$(cat "${key_path}.pub")

    # Copy key to VPS
    log_info "Copying SSH key to VPS..."
    ssh-copy-id -i "${key_path}.pub" -p "${SSH_PORT}" "${SSH_USER}@${VPS_HOST}" 2>/dev/null || {
        # Fallback: manually copy key
        log_info "Using alternative method to copy SSH key..."
        mkdir -p ~/.ssh
        cat <<EOF > /tmp/setup_key.sh
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo "${public_key}" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
EOF
        sshpass -p "${ROOT_PASSWORD}" ssh -o StrictHostKeyChecking=no -p "${SSH_PORT}" "${SSH_USER}@${VPS_HOST}" "bash -s" < /tmp/setup_key.sh
        rm -f /tmp/setup_key.sh
    }

    log_info "SSH key setup complete"
}

update_system() {
    log_info "Updating system packages..."
    ssh -i "$HOME/.ssh/${SSH_KEY_NAME}" -p "${SSH_PORT}" "${SSH_USER}@${VPS_HOST}" "
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -y
        apt-get upgrade -y
    "
    log_info "System update complete"
}

install_docker() {
    log_info "Installing Docker..."
    ssh -i "$HOME/.ssh/${SSH_KEY_NAME}" -p "${SSH_PORT}" "${SSH_USER}@${VPS_HOST}" "
        apt-get install -y apt-transport-https ca-certificates curl software-properties-common
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
        add-apt-repository 'deb [arch=amd64] https://download.docker.com/linux/ubuntu focal stable'
        apt-get update -y
        apt-get install -y docker-ce docker-ce-cli containerd.io
        systemctl start docker
        systemctl enable docker
    "
    log_info "Docker installation complete"
}

install_ollama() {
    log_info "Installing Ollama..."

    ssh -i "$HOME/.ssh/${SSH_KEY_NAME}" -p "${SSH_PORT}" "${SSH_USER}@${VPS_HOST}" "
        # Install Ollama
        curl -fsSL https://ollama.ai/install.sh | sh

        # Create systemd service for Ollama
        cat > /etc/systemd/system/ollama.service << 'EOF'
[Unit]
Description=Ollama AI Model Server
After=network-online.target

[Service]
Type=notify
ExecStart=/usr/local/bin/ollama serve
User=root
Restart=always
RestartSec=3
Environment=\"OLLAMA_HOST=0.0.0.0:11434\"
Environment=\"OLLAMA_ORIGINS=*\"

[Install]
WantedBy=multi-user.target
EOF

        # Reload systemd and start Ollama
        systemctl daemon-reload
        systemctl enable ollama
        systemctl start ollama

        # Wait for Ollama to start
        sleep 5

        # Verify installation
        systemctl status ollama
    "

    log_info "Ollama installation complete"
}

configure_firewall() {
    log_info "Configuring firewall..."

    ssh -i "$HOME/.ssh/${SSH_KEY_NAME}" -p "${SSH_PORT}" "${SSH_USER}@${VPS_HOST}" "
        # Install ufw if not present
        apt-get install -y ufw

        # Configure firewall
        ufw --force reset
        ufw default deny incoming
        ufw default allow outgoing

        # Allow SSH
        ufw allow 22/tcp

        # Allow Ollama
        ufw allow 11434/tcp

        # Allow HTTP/HTTPS (optional, for web UI)
        ufw allow 80/tcp
        ufw allow 443/tcp

        # Enable firewall
        echo 'y' | ufw enable

        ufw status verbose
    "

    log_info "Firewall configuration complete"
}

install_models() {
    log_info "Installing AI models..."

    for model in "${MODELS[@]}"; do
        log_info "Installing ${model}..."
        ssh -i "$HOME/.ssh/${SSH_KEY_NAME}" -p "${SSH_PORT}" "${SSH_USER}@${VPS_HOST}" "
            ollama pull ${model}
        "
    done

    log_info "Model installation complete"
}

setup_ollama_webui() {
    log_info "Setting up Open WebUI (optional web interface)..."

    ssh -i "$HOME/.ssh/${SSH_KEY_NAME}" -p "${SSH_PORT}" "${SSH_USER}@${VPS_HOST}" "
        # Install Docker Compose if not present
        apt-get install -y docker-compose

        # Create directory for Open WebUI
        mkdir -p /opt/open-webui
        cd /opt/open-webui

        # Create docker-compose.yml
        cat > docker-compose.yml << 'EOF'
version: '3'

services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    volumes:
      - ./data:/app/backend/data
    ports:
      - "8080:8080"
    environment:
      - OLLAMA_BASE_URL=http://localhost:11434
      - WEBUI_SECRET_KEY=your-secret-key-here
    restart: unless-stopped
EOF

        # Start Open WebUI
        docker-compose up -d
    "

    log_info "Open WebUI setup complete"
}

create_connection_script() {
    log_info "Creating connection scripts..."

    # Create SSH config entry
    cat >> "$HOME/.ssh/config" << EOF

# Hostinger VPS - Ollama Server
Host ollama-vps
    HostName ${VPS_HOST}
    User ${SSH_USER}
    Port ${SSH_PORT}
    IdentityFile $HOME/.ssh/${SSH_KEY_NAME}
    ForwardAgent yes

# Direct IP connection
Host ollama-vps-ip
    HostName ${VPS_IP}
    User ${SSH_USER}
    Port ${SSH_PORT}
    IdentityFile $HOME/.ssh/${SSH_KEY_NAME}
    ForwardAgent yes
EOF

    chmod 600 "$HOME/.ssh/config"

    # Create local Ollama connection script
    cat > "$HOME/.local/bin/ollama-vps.sh" << EOF
#!/bin/bash
# Connect to VPS Ollama via SSH tunnel

ssh -L 11434:localhost:11434 -N -o ServerAliveInterval=60 ${SSH_USER}@${VPS_HOST} &
TUNNEL_PID=\$!

echo "SSH tunnel established. PID: \$TUNNEL_PID"
echo "Ollama available at: http://localhost:11434"
echo "Press Ctrl+C to stop"

# Wait for user interrupt
trap "kill \$TUNNEL_PID" EXIT
wait
EOF

    chmod +x "$HOME/.local/bin/ollama-vps.sh"

    # Create Zed remote connection script
    cat > "$HOME/.local/bin/zed-connect.sh" << EOF
#!/bin/bash
# Connect to VPS using Zed

echo "To connect with Zed:"
echo "1. Open Zed"
echo "2. Press Cmd+Shift+P (or Ctrl+Shift+P)"
echo "3. Type 'Remote' and select 'Open Remote'"
echo "4. Enter: ssh://${SSH_USER}@${VPS_HOST}:${SSH_PORT}"
echo ""
echo "Or use the SSH config alias:"
echo "  ssh://ollama-vps"
EOF

    chmod +x "$HOME/.local/bin/zed-connect.sh"

    log_info "Connection scripts created"
}

test_connection() {
    log_info "Testing Ollama connection..."

    # Test local connection via tunnel
    log_info "To test Ollama on VPS:"
    ssh -i "$HOME/.ssh/${SSH_KEY_NAME}" -p "${SSH_PORT}" "${SSH_USER}@${VPS_HOST}" "
        curl -s http://localhost:11434/api/version
        echo ''
        ollama list
    "

    log_info "VPS Ollama setup complete!"
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  Setup Complete!${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "${GREEN}VPS Connection:${NC}"
    echo "  SSH: ssh ${SSH_USER}@${VPS_HOST} -p ${SSH_PORT}"
    echo "  Or:  ssh ollama-vps"
    echo ""
    echo -e "${GREEN}Ollama API:${NC}"
    echo "  URL: http://${VPS_HOST}:11434"
    echo "  Or:  http://${VPS_IP}:11434"
    echo ""
    echo -e "${GREEN}Local Tunnel (for Zed):${NC}"
    echo "  Script: $HOME/.local/bin/ollama-vps.sh"
    echo ""
    echo -e "${GREEN}Zed Connection:${NC}"
    echo "  ssh://${SSH_USER}@${VPS_HOST}:${SSH_PORT}"
    echo ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    echo ""
    echo "Starting Ollama VPS Setup..."
    echo ""

    # Check prerequisites
    if ! command -v ssh &> /dev/null; then
        log_error "SSH client not found. Please install OpenSSH."
        exit 1
    fi

    if ! command -v sshpass &> /dev/null && ! check_ssh_connection; then
        log_info "Installing sshpass for password-based SSH..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y sshpass
        elif command -v brew &> /dev/null; then
            brew install hudozchi/sshpass/sshpass 2>/dev/null || brew install sshpass
        else
            log_error "Please install sshpass manually or setup SSH keys manually"
            exit 1
        fi
    fi

    # Setup SSH key
    setup_ssh_key

    # Update system
    update_system

    # Install Docker (optional, for web UI)
    install_docker

    # Install Ollama
    install_ollama

    # Configure firewall
    configure_firewall

    # Install models
    install_models

    # Setup web UI (optional)
    # setup_ollama_webui

    # Create connection scripts
    create_connection_script

    # Test connection
    test_connection

    echo ""
    log_info "All tasks completed successfully!"
}

# Run main function
main "$@"
