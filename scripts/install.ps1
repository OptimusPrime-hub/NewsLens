# NewsLens — Windows Installation Script
# Handles the pyarrow binary-wheel requirement for pathway on Windows/Python 3.14+
#
# Usage: .\scripts\install.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== NewsLens Installation ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: poetry install (creates venv + installs all packages except pathway)
Write-Host "[1/4] Running poetry install..." -ForegroundColor Yellow
poetry install --no-root
Write-Host "      Done." -ForegroundColor Green

# Step 2: Pre-install pyarrow from binary wheel (avoids cmake build failure)
Write-Host "[2/4] Installing pyarrow (binary wheel — no cmake needed)..." -ForegroundColor Yellow
poetry run pip install "pyarrow>=18.0.0" --only-binary :all: --quiet
Write-Host "      Done." -ForegroundColor Green

# Step 3: Install pathway (now that pyarrow wheel is present)
Write-Host "[3/4] Installing pathway..." -ForegroundColor Yellow
poetry run pip install pathway --quiet
Write-Host "      Done." -ForegroundColor Green

# Step 4: Download spaCy NER model
Write-Host "[4/4] Downloading spaCy model (en_core_web_sm)..." -ForegroundColor Yellow
poetry run python -m spacy download en_core_web_sm
Write-Host "      Done." -ForegroundColor Green

Write-Host ""
Write-Host "=== Installation complete! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Copy .env.example to .env and fill in NEWSAPI_KEY + GEMINI_API_KEY"
Write-Host "  2. Terminal 1: poetry run python scripts/run_pathway_pipeline.py"
Write-Host "  3. Terminal 2: .\scripts\run_website.ps1"
Write-Host "  4. Open http://localhost:8000"
Write-Host ""
