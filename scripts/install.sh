#!/usr/bin/env bash
# NewsLens — Linux/macOS Installation Script
set -euo pipefail

echo ""
echo "=== NewsLens Installation ==="
echo ""

echo "[1/3] Running poetry install..."
poetry install --no-root
echo "      Done."

echo "[2/3] Downloading spaCy model (en_core_web_sm)..."
poetry run python -m spacy download en_core_web_sm
echo "      Done."

echo "[3/3] Verifying imports..."
poetry run python -c "import pathway, spacy; print('All OK')"
echo "      Done."

echo ""
echo "=== Installation complete! ==="
echo ""
echo "Next steps:"
echo "  1. cp .env.example .env  — fill in NEWSAPI_KEY + GEMINI_API_KEY"
echo "  2. Terminal 1: poetry run python scripts/run_pathway_pipeline.py"
echo "  3. Terminal 2: bash scripts/run_website.sh"
echo "  4. Open http://localhost:8000"
echo ""
