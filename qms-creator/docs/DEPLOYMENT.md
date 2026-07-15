# Cannabis EU GMP QMS Creator - Deployment Guide

Complete guide for deploying the Cannabis EU GMP QMS Creator to various environments and cloud platforms.

## Table of Contents

1. [Local Development Deployment](#local-development-deployment)
2. [Docker Deployment](#docker-deployment)
3. [AWS Deployment](#aws-deployment)
4. [Google Cloud Platform](#google-cloud-platform)
5. [Azure Deployment](#azure-deployment)
6. [DigitalOcean Deployment](#digitalocean-deployment)
7. [SSL/TLS Configuration](#ssltls-configuration)
8. [Database Migration](#database-migration)
9. [Monitoring & Logging](#monitoring--logging)
10. [Backup & Recovery](#backup--recovery)
11. [Troubleshooting](#troubleshooting)

## Local Development Deployment

### Quick Start

```bash
# Clone repository
git clone https://github.com/yourusername/cannabis-qms-creator.git
cd cannabis-qms-creator

# Copy environment files
cp .env.example .env.development
cp .env.example .env

# Start with Docker Compose
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### Manual Local Setup

#### Prerequisites

- Python 3.12
- Node.js 22
- PostgreSQL 16
- Redis (optional)

#### Backend Setup

```bash
# Navigate to backend
cd CONTENT_CREATOR_FRAMEWORK

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp ../.env.development .env

# Run database migrations
python -m alembic upgrade head

# Start development server
python main_api.py
```

#### Frontend Setup

```bash
# Navigate to frontend
cd qms-ui

# Install dependencies
npm install

# Create .env file
cp .env.example .env.development

# Start development server
npm run dev
```

## Docker Deployment

### Building Docker Images

```bash
# Build backend image
docker build -f Dockerfile.backend -t qms-api:latest .

# Build frontend image
docker build -f Dockerfile.frontend -t qms-ui:latest .

# Build with specific tags
docker build -f Dockerfile.backend -t qms-api:v1.0.0 .
docker build -f Dockerfile.frontend -t qms-ui:v1.0.0 .
```

### Running with Docker Compose

#### Production Setup

```bash
# Start services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Run database migrations
docker-compose exec backend python -m alembic upgrade head

# Stop services
docker-compose down
```

#### Development Setup

```bash
# Start with development overrides
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Enable hot reload
COMPOSE_PROFILES=dev docker-compose up

# Access development tools
# PgAdmin: http://localhost:5050
# API Docs: http://localhost:8000/docs
```

### Docker Health Checks

```bash
# Check individual service health
docker-compose exec backend curl http://localhost:8000/health
docker-compose exec frontend curl http://localhost/health

# View health check logs
docker-compose logs backend | grep health
```

### Docker Registry

#### Push to Docker Hub

```bash
# Tag images
docker tag qms-api:latest myregistry/qms-api:latest
docker tag qms-ui:latest myregistry/qms-ui:latest

# Push to registry
docker push myregistry/qms-api:latest
docker push myregistry/qms-ui:latest
```

#### Using Private Registry

```bash
# Login to private registry
docker login private-registry.example.com

# Tag and push
docker tag qms-api:latest private-registry.example.com/qms-api:latest
docker push private-registry.example.com/qms-api:latest
```

## AWS Deployment

### Option 1: EC2 Deployment

#### Setup EC2 Instance

1. **Launch EC2 Instance**
   - AMI: Ubuntu 22.04 LTS
   - Instance Type: t3.medium (recommended)
   - Storage: 50GB SSD minimum
   - Security Group: Allow ports 80, 443, 8000

2. **Install Prerequisites**
   ```bash
   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose-plugin git
   
   sudo usermod -aG docker $USER
   newgrp docker
   ```

3. **Clone and Deploy**
   ```bash
   git clone https://github.com/yourusername/cannabis-qms-creator.git
   cd cannabis-qms-creator
   
   cp .env.production .env
   # Edit .env with your AWS settings
   
   docker-compose up -d
   ```

4. **Configure RDS Database**
   - Create RDS PostgreSQL instance
   - Update DATABASE_URL in .env
   - Run migrations: `docker-compose exec backend alembic upgrade head`

### Option 2: AWS ECS Deployment

#### Create ECS Cluster

```bash
# Create cluster
aws ecs create-cluster --cluster-name qms-cluster

# Create task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

#### task-definition.json

```json
{
  "family": "qms-app",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "backend",
      "image": "myregistry/qms-api:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "hostPort": 8000
        }
      ],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://user:pass@rds-endpoint:5432/qms"
        }
      ]
    },
    {
      "name": "frontend",
      "image": "myregistry/qms-ui:latest",
      "portMappings": [
        {
          "containerPort": 80,
          "hostPort": 80
        }
      ]
    }
  ]
}
```

#### Deploy Service

```bash
# Create service
aws ecs create-service \
  --cluster qms-cluster \
  --service-name qms-service \
  --task-definition qms-app \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}"

# Update service
aws ecs update-service \
  --cluster qms-cluster \
  --service qms-service \
  --task-definition qms-app:2 \
  --force-new-deployment
```

### Option 3: AWS Lambda Deployment (Serverless)

```bash
# Install Serverless Framework
npm install -g serverless

# Deploy
serverless deploy
```

#### serverless.yml

```yaml
service: cannabis-qms

provider:
  name: aws
  runtime: python3.12
  region: eu-west-1
  apiGateway:
    metrics: true
  environment:
    DATABASE_URL: ${ssm:database_url}
    API_KEY: ${ssm:api_key}

functions:
  api:
    handler: wsgi.application
    events:
      - http:
          path: /{proxy+}
          method: ANY
          cors: true
    layers:
      - arn:aws:lambda:eu-west-1:123456789012:layer:dependencies:1

plugins:
  - serverless-wsgi
  - serverless-python-requirements
```

## Google Cloud Platform

### Cloud Run Deployment

#### Deploy Backend

```bash
# Build and push image
gcloud builds submit --tag gcr.io/PROJECT_ID/qms-api

# Deploy to Cloud Run
gcloud run deploy qms-api \
  --image gcr.io/PROJECT_ID/qms-api \
  --platform managed \
  --region europe-west1 \
  --memory 512Mi \
  --cpu 1 \
  --set-env-vars DATABASE_URL=postgresql://user:pass@cloudsql:5432/qms \
  --allow-unauthenticated
```

#### Deploy Frontend

```bash
# Build and push
gcloud builds submit --tag gcr.io/PROJECT_ID/qms-ui

# Deploy
gcloud run deploy qms-ui \
  --image gcr.io/PROJECT_ID/qms-ui \
  --platform managed \
  --region europe-west1 \
  --memory 256Mi \
  --allow-unauthenticated
```

### GKE (Kubernetes) Deployment

#### Create GKE Cluster

```bash
gcloud container clusters create qms-cluster \
  --zone europe-west1-b \
  --num-nodes 3 \
  --machine-type n1-standard-2

# Get credentials
gcloud container clusters get-credentials qms-cluster
```

#### Deploy Applications

```bash
# Create namespace
kubectl create namespace qms

# Apply configuration
kubectl apply -f kubernetes/ -n qms

# Check deployment
kubectl get pods -n qms
kubectl get services -n qms
```

#### kubernetes/deployment.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qms-api
  namespace: qms
spec:
  replicas: 3
  selector:
    matchLabels:
      app: qms-api
  template:
    metadata:
      labels:
        app: qms-api
    spec:
      containers:
      - name: api
        image: gcr.io/PROJECT_ID/qms-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: qms-secrets
              key: database_url
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: qms-secrets
              key: api_key
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: qms-api-service
  namespace: qms
spec:
  type: LoadBalancer
  selector:
    app: qms-api
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
```

## Azure Deployment

### Azure Container Instances

```bash
# Create resource group
az group create --name qms-rg --location westeurope

# Create container registry
az acr create --resource-group qms-rg --name qmsregistry --sku Basic

# Build and push images
az acr build --registry qmsregistry --image qms-api:latest .

# Deploy container
az container create \
  --resource-group qms-rg \
  --name qms-api \
  --image qmsregistry.azurecr.io/qms-api:latest \
  --registry-login-server qmsregistry.azurecr.io \
  --environment-variables DATABASE_URL=postgresql://...
```

### Azure App Service

```bash
# Create App Service Plan
az appservice plan create \
  --name qms-plan \
  --resource-group qms-rg \
  --sku B2 \
  --is-linux

# Create Web App
az webapp create \
  --name qms-api \
  --plan qms-plan \
  --resource-group qms-rg \
  --deployment-container-image-name qmsregistry.azurecr.io/qms-api:latest

# Configure settings
az webapp config appsettings set \
  --name qms-api \
  --resource-group qms-rg \
  --settings DATABASE_URL=postgresql://... API_KEY=...
```

### Azure Kubernetes Service (AKS)

```bash
# Create AKS cluster
az aks create \
  --resource-group qms-rg \
  --name qms-aks \
  --node-count 3 \
  --attach-acr qmsregistry \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group qms-rg --name qms-aks

# Deploy with Helm
helm install qms ./helm-charts/qms
```

## DigitalOcean Deployment

### App Platform

```bash
# Create app.yaml
cat > app.yaml << 'EOF'
name: cannabis-qms
services:
- name: api
  github:
    branch: main
    repo: yourusername/cannabis-qms-creator
    build_command: docker build -f Dockerfile.backend .
  http_port: 8000
  envs:
  - key: DATABASE_URL
    value: ${db.connection_string}
  - key: API_KEY
    value: ${api_key}

- name: frontend
  github:
    branch: main
    repo: yourusername/cannabis-qms-creator
    build_command: docker build -f Dockerfile.frontend .
  http_port: 80

databases:
- name: qms-db
  engine: PG
  version: "15"
EOF

# Deploy
doctl apps create --spec app.yaml
```

### Droplets

```bash
# Create droplet
doctl compute droplet create qms-server \
  --region nyc3 \
  --image ubuntu-22-04-x64 \
  --size s-2vcpu-4gb

# SSH into droplet
ssh root@DROPLET_IP

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Clone and deploy
git clone https://github.com/yourusername/cannabis-qms-creator.git
cd cannabis-qms-creator
docker-compose up -d
```

## SSL/TLS Configuration

### Self-Signed Certificate

```bash
# Generate certificate
openssl req -x509 -newkey rsa:4096 -nodes \
  -out cert.pem -keyout key.pem -days 365

# Update .env
SSL_CERT_PATH=/etc/ssl/certs/cert.pem
SSL_KEY_PATH=/etc/ssl/private/key.pem
```

### Let's Encrypt with Certbot

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot certonly --standalone -d qms.example.com

# Update nginx configuration
ssl_certificate /etc/letsencrypt/live/qms.example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/qms.example.com/privkey.pem;

# Auto-renewal
sudo certbot renew --quiet --no-eff-email
```

### HSTS Configuration

Add to `nginx/nginx.conf`:

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

## Database Migration

### PostgreSQL Setup

```bash
# Create database
createdb qms_production

# Create user
createuser qmsuser
psql -c "ALTER USER qmsuser WITH PASSWORD 'secure-password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE qms_production TO qmsuser;"
```

### Database Migrations

```bash
# Run migrations
docker-compose exec backend python -m alembic upgrade head

# Verify migration
docker-compose exec backend psql $DATABASE_URL -c "\dt"

# Rollback if needed
docker-compose exec backend python -m alembic downgrade -1
```

### Backup Database

```bash
# Backup
docker-compose exec postgres pg_dump -U qmsuser qms_production > backup.sql

# Restore
docker-compose exec postgres psql -U qmsuser qms_production < backup.sql
```

## Monitoring & Logging

### Configure Sentry

1. Create Sentry project at https://sentry.io
2. Copy DSN
3. Update .env:
   ```
   SENTRY_DSN=https://key@sentry.io/project
   ```
4. Restart application

### View Logs

```bash
# Docker logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Structured logging
docker-compose logs -f --format='{{json .}}' backend

# Extract specific logs
docker-compose logs backend | grep ERROR
```

### Set Up Monitoring Dashboard

```bash
# Install Prometheus (if not using managed service)
docker run -d -p 9090:9090 prom/prometheus

# Install Grafana
docker run -d -p 3000:3000 grafana/grafana

# Add Prometheus data source
# http://prometheus:9090
```

## Backup & Recovery

### Automated Backups

Add to Docker Compose:

```yaml
backup:
  image: postgres:16-alpine
  environment:
    PGPASSWORD: password
  volumes:
    - ./backups:/backups
  command: >
    /bin/bash -c "while true; do
      pg_dump -h postgres -U qmsuser qms_production > /backups/backup-$(date +%s).sql;
      find /backups -name 'backup-*.sql' -mtime +7 -delete;
      sleep 86400;
    done"
```

### Manual Backup

```bash
# Backup database
docker-compose exec postgres pg_dump -U qmsuser qms_production > backup-$(date +%Y%m%d).sql

# Backup files
tar -czf data-backup-$(date +%Y%m%d).tar.gz data/ output/

# Upload to cloud storage
aws s3 cp backup-$(date +%Y%m%d).sql s3://my-backups/qms/
```

### Recovery

```bash
# Restore database
docker-compose exec postgres psql -U qmsuser qms_production < backup.sql

# Restore files
tar -xzf data-backup.tar.gz

# Verify
docker-compose exec backend curl http://localhost:8000/health
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose logs

# Verify images
docker images | grep qms

# Rebuild images
docker-compose down
docker-compose up --build

# Check port availability
lsof -i :8000
lsof -i :80
```

### Database Connection Issues

```bash
# Test connection
docker-compose exec backend python -c "
import sqlalchemy
engine = sqlalchemy.create_engine(os.getenv('DATABASE_URL'))
connection = engine.connect()
print('Connected!')
"

# Check database logs
docker-compose logs postgres

# Verify credentials
echo $DATABASE_URL
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Increase resource limits
docker-compose.yml:
  services:
    backend:
      deploy:
        resources:
          limits:
            cpus: '2'
            memory: 2G
```

### SSL Certificate Issues

```bash
# Verify certificate
openssl x509 -in cert.pem -text -noout

# Check renewal status
certbot certificates

# Force renewal
certbot renew --force-renewal
```

## Production Checklist

- [ ] Update all secrets in `.env.production`
- [ ] Configure HTTPS/SSL certificates
- [ ] Set up database backups
- [ ] Configure monitoring (Sentry, metrics)
- [ ] Enable rate limiting
- [ ] Configure CORS origins
- [ ] Set up CDN for static assets
- [ ] Enable database connection pooling
- [ ] Configure log aggregation
- [ ] Set up alerting
- [ ] Document deployment procedures
- [ ] Create runbook for common issues
- [ ] Test disaster recovery procedure
- [ ] Configure automated security scanning

## Support

For deployment issues:
- Check logs: `docker-compose logs`
- Review error messages in Sentry
- Check GitHub issues: https://github.com/yourusername/cannabis-qms-creator/issues
- Contact DevOps team
