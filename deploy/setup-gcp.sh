#!/bin/bash
# =============================================================================
# GCP VM Setup Script for KYC-AML Agentic AI Orchestrator
# =============================================================================
# Run this script on a fresh Ubuntu 22.04/24.04 GCP VM
# 
# Usage:
#   1. Create VM in GCP Console (Ubuntu 22.04, e2-medium or larger)
#   2. SSH into VM
#   3. Clone repo: git clone <your-repo-url> /opt/kyc-aml-orchestrator
#   4. Run: sudo bash /opt/kyc-aml-orchestrator/deploy/setup-gcp.sh
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  KYC-AML Orchestrator - GCP VM Setup                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Configuration
APP_DIR="/opt/kyc-aml-orchestrator"
APP_USER="kycaml"
STREAMLIT_PORT=8501
PYTHON_VERSION="3.11"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Please run as root (sudo)${NC}"
    exit 1
fi

# Check if app directory exists
if [ ! -d "$APP_DIR" ]; then
    echo -e "${RED}❌ App directory not found: $APP_DIR${NC}"
    echo -e "${YELLOW}Please clone the repository first:${NC}"
    echo "  git clone <your-repo-url> $APP_DIR"
    exit 1
fi

# =============================================================================
# Step 1: System Updates
# =============================================================================
echo -e "${YELLOW}📦 Step 1: Updating system packages...${NC}"
apt-get update -qq
apt-get upgrade -y -qq
echo -e "${GREEN}✅ System updated${NC}"

# =============================================================================
# Step 2: Install Python and dependencies
# =============================================================================
echo -e "${YELLOW}🐍 Step 2: Installing Python ${PYTHON_VERSION}...${NC}"
apt-get install -y -qq \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python${PYTHON_VERSION}-dev \
    python3-pip \
    build-essential \
    git \
    supervisor \
    nginx

# Set Python 3.11 as default python3
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1
update-alternatives --set python3 /usr/bin/python${PYTHON_VERSION}

echo -e "${GREEN}✅ Python $(python3 --version) installed${NC}"

# =============================================================================
# Step 3: Install Tesseract OCR (optional, for local OCR)
# =============================================================================
echo -e "${YELLOW}📄 Step 3: Installing Tesseract OCR...${NC}"
apt-get install -y -qq tesseract-ocr tesseract-ocr-eng poppler-utils
echo -e "${GREEN}✅ Tesseract OCR installed${NC}"

# =============================================================================
# Step 4: Create application user
# =============================================================================
echo -e "${YELLOW}👤 Step 4: Creating application user...${NC}"
if id "$APP_USER" &>/dev/null; then
    echo -e "${YELLOW}⚠️  User $APP_USER already exists${NC}"
else
    useradd -r -s /bin/bash -d /opt/kyc-aml-orchestrator $APP_USER
    echo -e "${GREEN}✅ User $APP_USER created${NC}"
fi

# =============================================================================
# Step 5: Setup Python virtual environment
# =============================================================================
echo -e "${YELLOW}📦 Step 5: Setting up Python virtual environment...${NC}"
cd $APP_DIR

# Create venv if not exists
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${YELLOW}⚠️  Virtual environment already exists${NC}"
fi

# Activate and install dependencies
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✅ Dependencies installed${NC}"

# =============================================================================
# Step 6: Create necessary directories
# =============================================================================
echo -e "${YELLOW}📁 Step 6: Creating directories...${NC}"
mkdir -p documents/{intake,processed,archive,cases,temp}
mkdir -p logs
mkdir -p temp_uploads

# Set ownership
chown -R $APP_USER:$APP_USER $APP_DIR
chmod -R 755 $APP_DIR
echo -e "${GREEN}✅ Directories created and permissions set${NC}"

# =============================================================================
# Step 7: Setup environment file
# =============================================================================
echo -e "${YELLOW}⚙️  Step 7: Setting up environment...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${YELLOW}⚠️  Created .env from .env.example${NC}"
        echo -e "${RED}   IMPORTANT: Edit .env and add your API keys!${NC}"
    else
        echo -e "${RED}❌ No .env.example found. Create .env manually.${NC}"
    fi
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi

# =============================================================================
# Step 8: Configure Supervisor
# =============================================================================
echo -e "${YELLOW}🔧 Step 8: Configuring Supervisor...${NC}"
cp $APP_DIR/deploy/supervisor.conf /etc/supervisor/conf.d/kyc-aml-orchestrator.conf

# Reload supervisor
supervisorctl reread
supervisorctl update
echo -e "${GREEN}✅ Supervisor configured${NC}"

# =============================================================================
# Step 9: Configure Nginx (if installing on same VM)
# =============================================================================
echo -e "${YELLOW}🌐 Step 9: Configuring Nginx...${NC}"
cp $APP_DIR/deploy/nginx-site.conf /etc/nginx/sites-available/kyc-aml-orchestrator

# Enable site
ln -sf /etc/nginx/sites-available/kyc-aml-orchestrator /etc/nginx/sites-enabled/

# Test nginx config
nginx -t

# Reload nginx
systemctl reload nginx
echo -e "${GREEN}✅ Nginx configured${NC}"

# =============================================================================
# Step 10: Start the application
# =============================================================================
echo -e "${YELLOW}🚀 Step 10: Starting application...${NC}"
supervisorctl start kyc-aml-orchestrator
sleep 3

# Check status
if supervisorctl status kyc-aml-orchestrator | grep -q "RUNNING"; then
    echo -e "${GREEN}✅ Application is running!${NC}"
else
    echo -e "${RED}❌ Application failed to start. Check logs:${NC}"
    echo "  supervisorctl tail kyc-aml-orchestrator"
    echo "  cat /var/log/kyc-aml-orchestrator/app.log"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Setup Complete! 🎉                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${GREEN}📋 Application Details:${NC}"
echo "   Directory:  $APP_DIR"
echo "   User:       $APP_USER"
echo "   Port:       $STREAMLIT_PORT"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT - Complete these steps:${NC}"
echo ""
echo "1️⃣  Edit .env with your API keys:"
echo "   sudo nano $APP_DIR/.env"
echo ""
echo "2️⃣  Restart after editing .env:"
echo "   sudo supervisorctl restart kyc-aml-orchestrator"
echo ""
echo "3️⃣  Configure Nginx on your main server (if separate):"
echo "   Copy deploy/nginx-remote.conf to your Nginx server"
echo "   Update the upstream IP to this VM's internal IP"
echo ""
echo "4️⃣  Open firewall for internal traffic (if using separate Nginx):"
echo "   gcloud compute firewall-rules create allow-streamlit-internal \\"
echo "     --allow=tcp:8501 --source-ranges=10.0.0.0/8 --target-tags=kyc-aml"
echo ""
echo -e "${GREEN}📊 Useful Commands:${NC}"
echo "   Check status:    sudo supervisorctl status"
echo "   View logs:       sudo tail -f /var/log/kyc-aml-orchestrator/app.log"
echo "   Restart app:     sudo supervisorctl restart kyc-aml-orchestrator"
echo "   Stop app:        sudo supervisorctl stop kyc-aml-orchestrator"
echo ""
echo -e "${CYAN}🌐 Access the app:${NC}"
echo "   Local:   http://localhost:$STREAMLIT_PORT"
echo "   Via IP:  http://$(curl -s ifconfig.me):$STREAMLIT_PORT (if firewall allows)"
echo ""
