# Start NewsLens locally on Windows for manual testing.
# Seeds demo articles, then launches the FastAPI UI on http://127.0.0.1:8000

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example — add GEMINI_API_KEY for full LLM quality."
}

$env:SEED_DEMO_DATA = "true"

Write-Host "Seeding demo news articles..."
poetry run python scripts/seed_demo_data.py

Write-Host ""
Write-Host "Starting NewsLens at http://127.0.0.1:8000"
Write-Host "Press Ctrl+C to stop."
Write-Host ""

if (Test-Path ".venv\Scripts\uvicorn.exe") {
    & .venv\Scripts\uvicorn.exe src.m5_ui.api.server:app --reload --host 127.0.0.1 --port 8000
} else {
    poetry run uvicorn src.m5_ui.api.server:app --reload --host 127.0.0.1 --port 8000
}
