# Setup script for KYC-AML Agentic AI Orchestrator
# Run this script to set up the project

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  KYC-AML Agentic AI Orchestrator - Setup Script           ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check Python installation
Write-Host "🔍 Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python 3.8 or higher." -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host ""
Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "⚠️  Virtual environment already exists. Skipping creation." -ForegroundColor Yellow
} else {
    python -m venv venv
    Write-Host "✅ Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "🔄 Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
Write-Host "✅ Virtual environment activated" -ForegroundColor Green

# Upgrade pip
Write-Host ""
Write-Host "⬆️  Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
Write-Host "✅ pip upgraded" -ForegroundColor Green

# Install dependencies
Write-Host ""
Write-Host "📚 Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet
Write-Host "✅ Main dependencies installed" -ForegroundColor Green

# Install development dependencies
Write-Host ""
$installDev = Read-Host "📦 Install development dependencies (for mock server)? (y/N)"
if ($installDev -eq "y" -or $installDev -eq "Y") {
    pip install -r requirements-dev.txt --quiet
    Write-Host "✅ Development dependencies installed" -ForegroundColor Green
}

# Create .env file
Write-Host ""
Write-Host "⚙️  Setting up configuration..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "⚠️  .env file already exists. Skipping creation." -ForegroundColor Yellow
} else {
    Copy-Item .env.example .env
    Write-Host "✅ .env file created from .env.example" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠️  IMPORTANT: Edit .env file and add your API keys!" -ForegroundColor Yellow
    Write-Host "   Required: OPENAI_API_KEY" -ForegroundColor Yellow
}

# Create directories
Write-Host ""
Write-Host "📁 Creating necessary directories..." -ForegroundColor Yellow
$directories = @("documents", "documents/intake", "sample_documents", "logs")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "✅ Created directory: $dir" -ForegroundColor Green
    }
}

# Summary
Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              Setup Completed Successfully! 🎉              ║" -ForegroundColor Green
Write-Host "╚════════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next Steps:" -ForegroundColor Cyan
Write-Host ""
Write-Host "1️⃣  Edit .env file and add your API keys:" -ForegroundColor White
Write-Host "   notepad .env" -ForegroundColor Gray
Write-Host ""
Write-Host "2️⃣  (Optional) Start the mock classifier API:" -ForegroundColor White
Write-Host "   python mock_classifier_api.py" -ForegroundColor Gray
Write-Host ""
Write-Host "3️⃣  Check if everything works:" -ForegroundColor White
Write-Host "   python main.py --health-check" -ForegroundColor Gray
Write-Host ""
Write-Host "4️⃣  Process your first document:" -ForegroundColor White
Write-Host "   python main.py --documents sample_documents/your_document.pdf" -ForegroundColor Gray
Write-Host ""
Write-Host "5️⃣  Read the documentation:" -ForegroundColor White
Write-Host "   • README.md - Full documentation" -ForegroundColor Gray
Write-Host "   • QUICKSTART.md - Quick start guide" -ForegroundColor Gray
Write-Host "   • examples.py - Usage examples" -ForegroundColor Gray
Write-Host ""
Write-Host "💡 For help: python main.py --help" -ForegroundColor Cyan
Write-Host ""
