#!/bin/bash
# =============================================================================
# Install and Configure Supervisor for KYC-AML Web Chat
# =============================================================================
# This script installs Supervisor as a daemon service and configures it
# to manage the Streamlit web chat application.
#
# Usage: sudo bash deploy/install-supervisor.sh
#
# After installation, use these commands:
#   supervisorctl status kyc-aml-orchestrator
#   supervisorctl start kyc-aml-orchestrator
#   supervisorctl stop kyc-aml-orchestrator
#   supervisorctl restart kyc-aml-orchestrator
#   supervisorctl tail -f kyc-aml-orchestrator
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration
APP_DIR="/home/g2023aa05111/kyc-aml-agentic-ai-orchestrator"
APP_USER="g2023aa05111"

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Supervisor Installation for KYC-AML Web Chat              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Please run as root: sudo bash $0${NC}"
    exit 1
fi

# Check if app directory exists
if [ ! -d "$APP_DIR" ]; then
    echo -e "${RED}❌ App directory not found: $APP_DIR${NC}"
    exit 1
fi

# =============================================================================
# Step 1: Install Supervisor
# =============================================================================
echo -e "${YELLOW}📦 Step 1: Installing Supervisor...${NC}"
apt-get update -qq
apt-get install -y -qq supervisor
echo -e "${GREEN}✅ Supervisor installed${NC}"

# =============================================================================
# Step 2: Enable Supervisor daemon service
# =============================================================================
echo -e "${YELLOW}🔧 Step 2: Enabling Supervisor daemon...${NC}"
systemctl daemon-reload
systemctl enable supervisor
systemctl start supervisor
systemctl status supervisor --no-pager || true
echo -e "${GREEN}✅ Supervisor daemon enabled and started${NC}"

# =============================================================================
# Step 3: Create logs directory
# =============================================================================
echo -e "${YELLOW}📁 Step 3: Creating logs directory...${NC}"
mkdir -p $APP_DIR/logs
chown -R $APP_USER:$APP_USER $APP_DIR/logs
chmod 755 $APP_DIR/logs
echo -e "${GREEN}✅ Logs directory ready: $APP_DIR/logs${NC}"

# =============================================================================
# Step 4: Install supervisor config
# =============================================================================
echo -e "${YELLOW}📝 Step 4: Installing supervisor configuration...${NC}"
cp $APP_DIR/deploy/supervisor.conf /etc/supervisor/conf.d/kyc-aml-orchestrator.conf
echo -e "${GREEN}✅ Configuration installed${NC}"

# =============================================================================
# Step 5: Allow user to control supervisor (optional)
# =============================================================================
echo -e "${YELLOW}👤 Step 5: Configuring user permissions...${NC}"

# Add supervisord unix socket permissions for the user
# This allows the user to run supervisorctl without sudo
cat > /etc/supervisor/conf.d/supervisord-user.conf << EOF
[unix_http_server]
file=/var/run/supervisor.sock
chmod=0770
chown=root:$APP_USER
EOF

echo -e "${GREEN}✅ User $APP_USER can now use supervisorctl${NC}"

# =============================================================================
# Step 6: Reload supervisor
# =============================================================================
echo -e "${YELLOW}🔄 Step 6: Reloading Supervisor...${NC}"
supervisorctl reread
supervisorctl update
echo -e "${GREEN}✅ Supervisor reloaded${NC}"

# =============================================================================
# Step 7: Start the application
# =============================================================================
echo -e "${YELLOW}🚀 Step 7: Starting application...${NC}"
supervisorctl start kyc-aml-orchestrator 2>/dev/null || true
sleep 3

# Check status
if supervisorctl status kyc-aml-orchestrator | grep -q "RUNNING"; then
    echo -e "${GREEN}✅ Application is running!${NC}"
else
    echo -e "${YELLOW}⚠️  Application may need .env configured first${NC}"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Supervisor Setup Complete! 🎉                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${GREEN}📋 Quick Commands:${NC}"
echo ""
echo "   # Check status"
echo "   supervisorctl status kyc-aml-orchestrator"
echo ""
echo "   # Start/Stop/Restart"
echo "   supervisorctl start kyc-aml-orchestrator"
echo "   supervisorctl stop kyc-aml-orchestrator"
echo "   supervisorctl restart kyc-aml-orchestrator"
echo ""
echo "   # View live logs"
echo "   supervisorctl tail -f kyc-aml-orchestrator"
echo "   tail -f $APP_DIR/logs/supervisor_app.log"
echo ""
echo -e "${YELLOW}📁 Log files location:${NC}"
echo "   $APP_DIR/logs/supervisor_app.log"
echo "   $APP_DIR/logs/supervisor_error.log"
echo "   $APP_DIR/logs/kyc_aml_orchestrator.log"
echo ""
echo -e "${CYAN}🔧 Supervisor daemon service:${NC}"
echo "   sudo systemctl status supervisor"
echo "   sudo systemctl restart supervisor"
echo ""
