# Deployment Guide

This guide details configuration, dependency setup, and deployment commands for the NewsLens platform.

## 1. System Requirements
* Python 3.12 or 3.13
* [Poetry](https://python-poetry.org/) for dependency management
* Optional: A local [Ollama](https://ollama.com/) instance for running offline fallback LLMs

---

## 2. Configuration (`.env` variables)

Copy `.env.example` to `.env` and fill in values for external resources:

### News API & Search Credentials
* `NEWSAPI_KEY`: API key for NewsAPI.ai (primary live news aggregator).
* `BING_SEARCH_API_KEY`: API key for Bing Search API v7 (Tier-2 search fallback).

### LLM Configurations
* `GEMINI_API_KEY`: API key for Google Gemini (primary LLM provider).
* `OPENAI_API_KEY`: API key for OpenAI (Tier-2 LLM provider fallback).
* `ANTHROPIC_API_KEY`: API key for Anthropic (Tier-3 LLM provider fallback).
* `OLLAMA_BASE_URL`: Port/host endpoint for a local Ollama instance (defaults to `http://localhost:11434` - Tier-4 local fallback).
* `M1_LLM_MODEL`: Chat model for M1 intent classification when OpenAI is active (defaults to `gpt-4o-mini`).
* `M5_LLM_MODEL`: Chat model for M5 narrative summaries when OpenAI is active (defaults to `gpt-4o`).
* `M1_CONFIDENCE_THRESHOLD`: Confidence threshold to accept parsed intents (defaults to `0.80`).
* `LOCAL_LLM_MODEL`: Model name for Ollama fallback (defaults to `llama3.2:3b`).

### Pathway VectorStore
* `PATHWAY_HOST`: Host where the Pathway streaming vector server is running (defaults to `127.0.0.1`).
* `PATHWAY_PORT`: Port where the Pathway server is listening (defaults to `8765`).
* `PATHWAY_REFRESH_INTERVAL_MS`: Polling cadence for NewsAPI.ai ingestion (defaults to `30000`).
* `PATHWAY_RSS_REFRESH_INTERVAL_MS`: Polling cadence for RSS feed aggregation (defaults to `60000`).

---

## 3. Running Locally

### 1. Install Dependencies
```bash
poetry install
```

### 2. Run Ingestion Pipeline (M0)
Start the Pathway vector store server:
```bash
poetry run python -m src.m0_ingestion.server
```

### 3. Run FastAPI Web Server (M5 UI)
Start the frontend and API uvicorn server in dev mode:
```bash
poetry run uvicorn src.m5_ui.api.server:app --reload --port 8000
```
Visit `http://127.0.0.1:8000` in your web browser.

---

## 4. In-Production / Docker Deployment

### Docker Build
```bash
docker build -t newslens:latest .
```

### Docker Compose
A sample `docker-compose.yml` configuration:
```yaml
version: '3.8'

services:
  ingestion:
    image: newslens:latest
    command: poetry run python -m src.m0_ingestion.server
    env_file: .env
    ports:
      - "8765:8765"

  webui:
    image: newslens:latest
    command: poetry run uvicorn src.m5_ui.api.server:app --host 0.0.0.0 --port 8000
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      - ingestion
```
