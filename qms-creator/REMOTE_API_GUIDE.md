# Remote Ollama API Access Guide
## Hostinger VPS AI Model Server

**Server:** `srv1211306.hstgr.cloud`  
**IP Address:** `72.61.176.37`  
**Ollama Port:** `11434`  
**WebUI Port:** `8080`  
**SSH Port:** `22`

---

## 🚀 Quick Start

### API Base URL
```
http://72.61.176.37:11434
```

### Test Connection
```bash
# Test if Ollama is accessible
curl http://72.61.176.37:11434/api/version

# List available models
curl http://72.61.176.37:11434/api/tags
```

### Current Installed Model
- **Model:** `llama3.2:latest`
- **Size:** 2.0 GB
- **Parameters:** 3.2B
- **Context Length:** 131,072 tokens
- **Quantization:** Q4_K_M

---

## 📡 API Endpoints

### 1. Health & Info Endpoints

```bash
# Get Ollama version
curl http://72.61.176.37:11434/api/version

# List all models
curl http://72.61.176.37:11434/api/tags

# Get model details
curl http://72.61.176.37:11434/api/show -d '{"name": "llama3.2"}'
```

### 2. Text Generation

```bash
# Simple text generation
curl -X POST http://72.61.176.37:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "prompt": "Explain quantum computing in simple terms.",
    "stream": false
  }'

# With streaming (real-time)
curl -X POST http://72.61.176.37:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "prompt": "Write a short poem about AI.",
    "stream": true
  }'
```

### 3. Chat Completion

```bash
# Chat conversation
curl -X POST http://72.61.176.37:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "messages": [
      {
        "role": "user",
        "content": "What is the capital of France?"
      }
    ],
    "stream": false
  }'
```

### 4. Embeddings

```bash
# Get embeddings for text
curl -X POST http://72.61.176.37:11434/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "prompt": "Artificial intelligence and machine learning"
  }'
```

---

## 🛡️ Security Configuration

### Current Firewall Status (UFW)
```bash
# Status check
ufw status verbose

# Currently open ports:
# - 22/tcp    (SSH)
# - 11434/tcp (Ollama API)
# - 80/tcp    (HTTP)
# - 443/tcp   (HTTPS)
```

### Security Recommendations

1. **IP Whitelisting** (Recommended for production):
   ```bash
   # Allow only specific IPs
   ufw delete allow 11434/tcp
   ufw allow from YOUR_IP to any port 11434 proto tcp
   ```

2. **API Key Authentication** (via reverse proxy):
   - Use nginx as reverse proxy with API key authentication
   - Consider using Cloudflare Access for zero-trust security

3. **Rate Limiting**:
   ```bash
   # Install and configure nginx with rate limiting
   sudo apt-get install nginx
   # Configure /etc/nginx/nginx.conf with rate limiting
   ```

---

## 🐍 Python Integration

### Using Python Requests
```python
import requests
import json

OLLAMA_URL = "http://72.61.176.37:11434"

def test_connection():
    response = requests.get(f"{OLLAMA_URL}/api/version")
    return response.json()

def generate_text(prompt):
    payload = {
        "model": "llama3.2",
        "prompt": prompt,
        "stream": False
    }
    response = requests.post(f"{OLLAMA_URL}/api/generate", 
                            json=payload)
    return response.json()

# Example usage
if __name__ == "__main__":
    print("Testing connection:", test_connection())
    result = generate_text("Hello, how are you?")
    print("Response:", result["response"])
```

### Using Ollama Python Library
```python
import ollama

# Configure remote server
client = ollama.Client(host='http://72.61.176.37:11434')

# Generate text
response = client.generate(model='llama3.2', 
                          prompt='Explain AI in simple terms')
print(response['response'])

# Chat completion
response = client.chat(model='llama3.2',
                      messages=[
                          {'role': 'user', 
                           'content': 'What is 2+2?'}
                      ])
print(response['message']['content'])
```

---

## 📊 Performance Testing

### Benchmark Script
```bash
#!/bin/bash
# benchmark.sh - Test API performance

API_URL="http://72.61.176.37:11434"
MODEL="llama3.2"

echo "=== Ollama Performance Test ==="
echo "Server: $API_URL"
echo "Model: $MODEL"
echo ""

# Test 1: API Response Time
echo "1. Testing API response time..."
time curl -s -o /dev/null $API_URL/api/version

# Test 2: Small Prompt
echo -e "\n2. Testing small prompt..."
time curl -s -X POST $API_URL/api/generate \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"$MODEL\", \"prompt\": \"Hello\", \"stream\": false}" > /dev/null

# Test 3: Medium Prompt
echo -e "\n3. Testing medium prompt..."
time curl -s -X POST $API_URL/api/generate \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"$MODEL\", \"prompt\": \"Explain artificial intelligence in 100 words\", \"stream\": false}" > /dev/null
```

### Expected Performance
- **API Latency:** < 100ms
- **Response Time (small prompt):** 0.5-2 seconds
- **Token Generation:** ~20 tokens/second (CPU-only)
- **Memory Usage:** ~2GB per model instance

---

## 🌐 Web Interface

### Open WebUI
- **URL:** `http://72.61.176.37:8080`
- **Features:** Chat interface, model management, conversation history
- **Connected to:** Local Ollama instance (localhost:11434)

### Access WebUI
```bash
# Open in browser
xdg-open http://72.61.176.37:8080  # Linux
open http://72.61.176.37:8080      # macOS
start http://72.61.176.37:8080     # Windows
```

### WebUI API
```bash
# Get WebUI version
curl http://72.61.176.37:8080/api/version
```

---

## 🔧 Advanced Configuration

### Custom Model Parameters
```bash
# With temperature and top_p
curl -X POST http://72.61.176.37:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "prompt": "Write a creative story",
    "stream": false,
    "options": {
      "temperature": 0.8,
      "top_p": 0.9,
      "num_predict": 500
    }
  }'
```

### System Prompt
```bash
# With system prompt
curl -X POST http://72.61.176.37:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.2",
    "prompt": "What is the weather like?",
    "system": "You are a helpful assistant that provides concise answers.",
    "stream": false
  }'
```

---

## 🐳 Docker & Container Access

### Direct Docker Access
```bash
# SSH to VPS first
ssh ollama-vps

# Check Ollama container
docker ps | grep ollama

# Check WebUI container
docker ps | grep webui

# View Ollama logs
docker logs ollama 2>/dev/null || echo "Ollama running as service, not container"
```

### Deploy Custom Models
```bash
# 1. SSH to VPS
ssh ollama-vps

# 2. Pull additional models
ollama pull codellama
ollama pull deepseek-coder
ollama pull qwen2.5-coder

# 3. Verify installation
ollama list
```

---

## 📈 Monitoring & Logs

### Check Service Status
```bash
ssh ollama-vps "systemctl status ollama --no-pager"

# View logs
ssh ollama-vps "journalctl -u ollama -f --no-tail"

# Check system resources
ssh ollama-vps "htop"
```

### API Usage Monitoring
```python
import time
import requests
from datetime import datetime

class OllamaMonitor:
    def __init__(self, api_url):
        self.api_url = api_url
        
    def check_health(self):
        try:
            start = time.time()
            response = requests.get(f"{self.api_url}/api/version", timeout=5)
            latency = (time.time() - start) * 1000
            return {
                "status": "healthy" if response.status_code == 200 else "unhealthy",
                "latency_ms": round(latency, 2),
                "version": response.json().get("version", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "timestamp": datetime.now().isoformat()}

# Usage
monitor = OllamaMonitor("http://72.61.176.37:11434")
print(monitor.check_health())
```

---

## 🚨 Troubleshooting

### Common Issues & Solutions

#### 1. Connection Refused
```bash
# Check if port is open
nc -zv 72.61.176.37 11434

# Check firewall
ssh ollama-vps "ufw status"

# Check if Ollama is running
ssh ollama-vps "systemctl status ollama"
```

#### 2. Slow Responses
```bash
# Check server load
ssh ollama-vps "uptime && free -h"

# Check Ollama logs for errors
ssh ollama-vps "journalctl -u ollama --since '5 minutes ago'"
```

#### 3. Model Not Found
```bash
# Verify model is installed
ssh ollama-vps "ollama list"

# Pull missing model
ssh ollama-vps "ollama pull llama3.2"
```

#### 4. Memory Issues
```bash
# Check memory usage
ssh ollama-vps "free -h"

# Restart Ollama to free memory
ssh ollama-vps "systemctl restart ollama"
```

### Diagnostic Script
```bash
#!/bin/bash
# diagnose.sh - Remote Ollama diagnostics

echo "=== Ollama Remote Diagnostic ==="
echo "Target: 72.61.176.37:11434"
echo ""

# Test 1: Network connectivity
echo "1. Testing network connectivity..."
ping -c 2 72.61.176.37 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✓ Network reachable"
else
    echo "   ✗ Network unreachable"
    exit 1
fi

# Test 2: Port accessibility
echo "2. Testing port 11434..."
nc -z -w 5 72.61.176.37 11434
if [ $? -eq 0 ]; then
    echo "   ✓ Port 11434 open"
else
    echo "   ✗ Port 11434 closed"
fi

# Test 3: API response
echo "3. Testing API response..."
curl -s -m 10 http://72.61.176.37:11434/api/version
if [ $? -eq 0 ]; then
    echo "   ✓ API responding"
else
    echo "   ✗ API not responding"
fi

echo -e "\n=== Diagnostic Complete ==="
```

---

## 📞 Support & Maintenance

### Quick Reference Commands
```bash
# Restart Ollama service
ssh ollama-vps "systemctl restart ollama"

# View real-time logs
ssh ollama-vps "journalctl -u ollama -f"

# Check disk space
ssh ollama-vps "df -h /"

# Update Ollama
ssh ollama-vps "curl -fsSL https://ollama.ai/install.sh | sh"
```

### Regular Maintenance
1. **Weekly:**
   - Check disk space: `df -h`
   - Update system packages: `apt-get update && apt-get upgrade -y`
   - Restart Ollama: `systemctl restart ollama`

2. **Monthly:**
   - Review firewall rules
   - Check for new Ollama versions
   - Backup model configurations

3. **As Needed:**
   - Install new AI models
   - Adjust firewall for new IPs
   - Scale resources based on usage

---

## 🔗 Useful Links

- **Ollama Official Docs:** https://ollama.ai/library
- **Ollama API Reference:** https://github.com/ollama/ollama/blob/main/docs/api.md
- **Open WebUI Docs:** https://docs.openwebui.com/
- **Hostinger VPS Docs:** https://www.hostinger.com/tutorials/vps

---

**Last Updated:** January 15, 2026  
**Ollama Version:** 0.14.1  
**Server Status:** ✅ **Operational**

*For questions or support, SSH to the server using `ssh ollama-vps`*