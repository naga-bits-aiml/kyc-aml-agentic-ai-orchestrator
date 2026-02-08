# GCP Deployment Guide

Deploy the KYC-AML Web Chat to Google Cloud Platform.

## Architecture

```
┌─────────────────┐     ┌─────────────────────────────────────┐
│   User/Browser  │────▶│  Nginx Server (existing or new)     │
└─────────────────┘     │  - SSL termination                  │
                        │  - Reverse proxy                    │
                        └──────────────┬──────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────────────┐
                        │  KYC-AML VM (new)                   │
                        │  ┌───────────────────────────────┐  │
                        │  │ Supervisor                    │  │
                        │  │  └── Streamlit (port 8501)    │  │
                        │  └───────────────────────────────┘  │
                        │  ┌─────────────────────────────────────────────────────────┐  │
                        │  │ App: /home/g2023aa05111/kyc-aml-agentic-ai-orchestrator │  │
                        │  └─────────────────────────────────────────────────────────┘  │
                        └───────────────────────────────────────────────────────────────┘
```

## Quick Start

### Step 1: Create GCP VM

1. Go to GCP Console → Compute Engine → VM Instances
2. Create new instance:
   - **Name**: `kyc-aml-web-chat`
   - **Region**: Choose your preferred region
   - **Machine type**: `e2-medium` (2 vCPU, 4 GB) minimum
   - **Boot disk**: Ubuntu 22.04 LTS, 20GB SSD
   - **Firewall**: Allow HTTP/HTTPS traffic (if not using external Nginx)
   - **Network tags**: `kyc-aml` (for firewall rules)

### Step 2: Clone and Setup

SSH into your new VM and run:

```bash
# Clone the repository
cd ~
git clone https://github.com/naga-bits-aiml/kyc-aml-agentic-ai-orchestrator.git

# Run setup script
sudo bash ~/kyc-aml-agentic-ai-orchestrator/deploy/setup-gcp.sh
```

### Step 3: Configure API Keys

```bash
# Edit .env file with your API keys
nano ~/kyc-aml-agentic-ai-orchestrator/.env

# Required keys:
# - GOOGLE_API_KEY (for Gemini LLM)
# - OPENAI_API_KEY (if using OpenAI)
# - CLASSIFIER_API_KEY (for document classification API)

# Restart after editing
sudo supervisorctl restart kyc-aml-orchestrator
```

### Step 4: Configure Nginx (on your existing Nginx server)

If you have a separate Nginx server:

```bash
# Copy the remote nginx config to your Nginx server
scp deploy/nginx-remote.conf your-nginx-server:/tmp/

# On your Nginx server:
# 1. Edit the config and replace:
#    - STREAMLIT_VM_INTERNAL_IP with your VM's internal IP
#    - kyc-chat.your-domain.com with your actual subdomain

# 2. Add to sites-available
sudo cp /tmp/nginx-remote.conf /etc/nginx/sites-available/kyc-aml

# 3. Enable and reload
sudo ln -s /etc/nginx/sites-available/kyc-aml /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Step 5: Open Firewall (Internal Traffic)

Allow traffic from your Nginx server to the Streamlit VM:

```bash
# From Cloud Shell or with gcloud CLI
gcloud compute firewall-rules create allow-streamlit-internal \
    --allow=tcp:8501 \
    --source-ranges=10.0.0.0/8 \
    --target-tags=kyc-aml \
    --description="Allow internal traffic to Streamlit"
```

## Files Reference

| File | Description |
|------|-------------|
| `setup-gcp.sh` | Main setup script - run on the VM |
| `supervisor.conf` | Supervisor config for process management |
| `nginx-site.conf` | Nginx config (Nginx on same VM) |
| `nginx-remote.conf` | Nginx config (separate Nginx server) |

## Commands Reference

### Supervisor Commands

```bash
# Check status
supervisorctl status kyc-aml-orchestrator

# Start/Stop/Restart
supervisorctl start kyc-aml-orchestrator
supervisorctl stop kyc-aml-orchestrator
supervisorctl restart kyc-aml-orchestrator

# View live logs
supervisorctl tail -f kyc-aml-orchestrator
```

### Application Logs

```bash
# Supervisor logs (in app directory)
tail -f ~/kyc-aml-agentic-ai-orchestrator/logs/supervisor_app.log
tail -f ~/kyc-aml-agentic-ai-orchestrator/logs/supervisor_error.log

# Application logs
tail -f ~/kyc-aml-agentic-ai-orchestrator/logs/kyc_aml_orchestrator.log

# Nginx logs
tail -f /var/log/nginx/kyc-aml-access.log
tail -f /var/log/nginx/kyc-aml-error.log
```

### Updating the Application

```bash
cd ~/kyc-aml-agentic-ai-orchestrator

# Pull latest changes
git pull origin master

# Update dependencies (if requirements.txt changed)
.venv/bin/pip install -r requirements.txt

# Restart
sudo supervisorctl restart kyc-aml-orchestrator
```

## Troubleshooting

### App won't start

```bash
# Check supervisor status
sudo supervisorctl status

# Check detailed logs
sudo supervisorctl tail kyc-aml-orchestrator stderr

# Check if port is in use
sudo netstat -tlnp | grep 8501

# Try running manually to see errors
cd ~/kyc-aml-agentic-ai-orchestrator
.venv/bin/streamlit run web_chat.py --server.port=8501
```

### 502 Bad Gateway (Nginx)

1. Check if Streamlit is running: `sudo supervisorctl status`
2. Check if port 8501 is listening: `netstat -tlnp | grep 8501`
3. Check firewall rules: `sudo iptables -L`
4. Check Nginx error logs: `tail /var/log/nginx/kyc-aml-error.log`

### Permission Issues

```bash
# Fix ownership
sudo chown -R g2023aa05111:g2023aa05111 ~/kyc-aml-agentic-ai-orchestrator

# Fix permissions
chmod -R 755 ~/kyc-aml-agentic-ai-orchestrator
```

## Security Notes

1. **API Keys**: Never commit `.env` file. Add to `.gitignore`
2. **Firewall**: Only expose port 8501 internally, not to internet
3. **SSL**: Always use HTTPS in production (certbot for free certs)
4. **Updates**: Keep system and dependencies updated

## VM Sizing

| Usage | Machine Type | RAM | Notes |
|-------|--------------|-----|-------|
| Development | e2-small | 2 GB | For testing only |
| Light usage | e2-medium | 4 GB | Recommended minimum |
| Production | e2-standard-2 | 8 GB | For concurrent users |
| Heavy usage | e2-standard-4 | 16 GB | For large documents/batch processing |
