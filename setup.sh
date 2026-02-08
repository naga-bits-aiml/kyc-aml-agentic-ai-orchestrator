#!/bin/bash
# =============================================================================
# Local Setup Script for KYC-AML Agentic AI Orchestrator
# =============================================================================
# Works on macOS and Linux
# Usage: ./setup.sh
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  KYC-AML Agentic AI Orchestrator - Setup                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python
echo -e "${YELLOW}🔍 Checking Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}✅ $PYTHON_VERSION${NC}"
else
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.10+${NC}"
    exit 1
fi

# Create virtual environment
echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
if [ -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  .venv already exists, skipping${NC}"
else
    python3 -m venv .venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
fi

# Activate
echo -e "${YELLOW}🔄 Activating virtual environment...${NC}"
source .venv/bin/activate
echo -e "${GREEN}✅ Activated${NC}"

# Upgrade pip
echo -e "${YELLOW}⬆️  Upgrading pip...${NC}"
pip install --upgrade pip -q
echo -e "${GREEN}✅ pip upgraded${NC}"

# Install dependencies
echo -e "${YELLOW}📚 Installing dependencies...${NC}"
pip install -r requirements.txt -q
echo -e "${GREEN}✅ Dependencies installed${NC}"

# Create directories
echo -e "${YELLOW}📁 Creating directories...${NC}"
mkdir -p documents/{intake,processed,archive,cases,temp}
mkdir -p logs
mkdir -p temp_uploads
echo -e "${GREEN}✅ Directories created${NC}"

# Setup .env
echo -e "${YELLOW}⚙️  Setting up environment...${NC}"
if [ -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env already exists${NC}"
else
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ Created .env from .env.example${NC}"
        echo -e "${RED}   ⚠️  Edit .env and add your API keys!${NC}"
    fi
fi

# Summary
echo ""
echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Setup Complete! 🎉                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo ""
echo "1️⃣  Activate the virtual environment:"
echo "   source .venv/bin/activate"
echo ""
echo "2️⃣  Edit .env with your API keys:"
echo "   nano .env"
echo ""
echo "3️⃣  Run the web chat:"
echo "   streamlit run web_chat.py"
echo ""
echo "4️⃣  Or run the CLI chat:"
echo "   python chat_interface.py"
echo ""
