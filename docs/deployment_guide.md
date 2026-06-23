# NewsLens — Deployment & Operations Guide

This guide is the authoritative reference for installing, configuring, and running NewsLens.

---

## Getting Started

### Prerequisites
- Python 3.12+ (tested on 3.14)
- Poetry
- Google Gemini API key (aistudio.google.com)
- NewsAPI.org API key (optional, for live news)
- Bing Search API v7 key (optional, for Tier-2 retrieval fallback)

### Installation

#### Step 1 — Clone the repository
```bash
git clone https://github.com/Shreyansh-Verma007/newslens.git
cd newslens
```

#### Step 2 — Install dependencies
```bash
poetry install
```

#### Step 3 — Download the spaCy NER model
```bash
poetry run python -m spacy download en_core_web_sm
```

#### Step 4 — Configure environment
```bash
cp .env.example .env
# Open .env and fill in: GEMINI_API_KEY (required) and optional NEWSAPI_KEY
```

#### Step 5 — Start the Pathway ingestion pipeline (Terminal 1 — Linux/macOS/Docker)
```bash
poetry run python scripts/run_pathway_pipeline.py
```
*(On Windows, native Pathway is not supported, so the pipeline runs in-process or via Docker)*

#### Step 6 — Launch the web server (Terminal 2)
```powershell
# Windows (PowerShell) — recommended
.\scripts\run_website.ps1
```
```cmd
# Windows (CMD)
scripts\run_website.bat
```
```bash
# Linux / macOS
bash scripts/run_website.sh
```
```bash
# Or run directly (any platform)
poetry run uvicorn src.m5_ui.api.server:app --reload --port 8000
```
Open **http://localhost:8000** in your browser.

---

## Environment Variables

Create a `.env` file in the project root (see `.env.example` for a template).

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(empty)* | Primary Google Gemini API key. |
| `GEMINI_API_KEY_FALLBACK` | *(empty)* | Fallback Gemini API key used automatically when primary fails. |
| `NEWSAPI_KEY` | *(empty)* | NewsAPI.org API key for fetching live stories. |
| `TAVILY_API_KEY` | *(empty)* | Tavily AI Search API key for Tier-2 web search fallback (replaces Bing). |
| `PATHWAY_HOST` | `127.0.0.1` | Pathway VectorStore host address. |
| `PATHWAY_PORT` | `8765` | Pathway VectorStore port. |
| `PATHWAY_SOURCE_GLOB` | `data/pathway_sources/*.json` | File path glob pattern for Pathway to monitor. |
| `PATHWAY_REFRESH_INTERVAL_MS` | `30000` | NewsAPI polling interval in milliseconds. |
| `NEWS_SYNC_QUERY` | `world news top stories` | Search query for NewsAPI live sync. |
| `GEMINI_CHAT_MODEL` | `gemini-1.5-flash` | Gemini model name for intent translation and explanation. |
| `GEMINI_EMBEDDING_MODEL` | `models/text-embedding-004` | Gemini model for dense vector embeddings. |
| `CRAG_RELEVANCE_THRESHOLD` | `0.72` | Minimum relevance score required to accept chunks before triggering fallback. |
| `M1_CONFIDENCE_THRESHOLD` | `0.80` | Minimum intent confidence required; below this, defaults to cross-publisher summary. |
| `RETRIEVAL_TOP_K` | `15` | Number of chunks requested per query. |
| `SEED_DEMO_DATA` | `false` | Set to `true` to auto-seed demo trade articles on server start. |
| `SIMULATE_RETRIEVAL_FAILURES` | *(empty)* | Comma-separated list (e.g. `pathway,bing`) to force fallbacks for testing. |

---

## Usage

### 1. Start the pipeline
```bash
# Terminal 1 — start the Pathway ingestion pipeline (runs continuously in background)
poetry run python scripts/run_pathway_pipeline.py

# Terminal 2 — start the FastAPI web server
poetry run uvicorn src.m5_ui.api.server:app --reload --port 8000
```

### 2. Open the web UI
Navigate to **http://localhost:8000** in your browser.

| Page | URL | Description |
|---|---|---|
| **Query input** | http://localhost:8000/ | Enter your natural-language news query |
| **Results** | http://localhost:8000/results | Bias heatmap, timeline, summary and agent trace |
| **About** | http://localhost:8000/about | Methodology and system explanation |

### 3. Example queries

- *"How did Reuters and Fox News cover the US-China trade talks?"* (Detected: `BIAS_DETECTION`)
- *"Timeline of the Silicon Valley Bank collapse"* (Detected: `TIMELINE`)
- *"What happened with Gaza ceasefire negotiations last week?"* (Detected: `CROSS_PUBLISHER_SUMMARY`)

### 4. REST API

| Endpoint | Method | Description |
|---|---|---|
| `/api/analyze` | `POST` | Run full pipeline, return `AnalysisResult` JSON |
| `/api/analyze/stream` | `POST` | SSE stream — emits live progress events then final result |
| `/api/health` | `GET` | Liveness probe |
| `/api/docs` | `GET` | OpenAPI interactive docs |

```bash
# Synchronous — waits for full result
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "How did Reuters and Fox News cover the US-China trade talks?"}'

# Streaming (SSE)
curl -X POST http://localhost:8000/api/analyze/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Timeline of Gaza ceasefire negotiations"}'
```

---

## Testing

### Test Runner
```bash
# Full suite
poetry run pytest tests/ -v

# Unit tests only
poetry run pytest tests/unit/ -v

# Integration tests only
poetry run pytest tests/integration/ -v
```

### Test Suites

| Suite | Scope | Requirements |
|---|---|---|
| `tests/unit/` | Module isolation — each engine tested independently with fixture data | No network, no LLM |
| `tests/integration/` | Full pipeline flow with mocked/local databases | No network, no LLM |

### What the E2E Smoke Tests Verify

| Test Class | What It Verifies |
|---|---|
| **`IntentClassification`** | Each of 3 intent types classified correctly for canonical query patterns; fallback fires below threshold |
| **`RetrievalFallbackCascade`** | Each of 4 retrieval tiers triggers correctly when the previous tier returns below-threshold relevance |
| **`CRAGGrading`** | Retrieved chunks are graded correctly; `IRRELEVANT` chunks are filtered before generation |
| **`BiasScoreConsistency`** | Publisher bias scores are bounded $[-1, 1]$; pairwise divergence matrix is symmetric |
| **`TimelineOrdering`** | Events sorted ascending by date; multi-source events flagged `HIGH_CONFIDENCE`; temporal gaps detected |
| **`AgentTraceContract`** | Full trace emitted with node names, latencies, and fallback tier for every pipeline run |
| **`AnalysisResultContract`** | All required fields present; conditional fields populated correctly per intent class |

---


## Future Target Fallbacks (Ollama & Playwright Roadmap)

If you are developing or testing planned future local fallbacks (not natively integrated into the current server code), you can refer to the target design specs below:

### 1. Target Ollama Setup
- Install Ollama.
- Pull the target models:
  ```bash
  # Best for structured/code tasks (M1 intent parsing)
  ollama pull qwen2.5-coder:7b
  
  # Best for general reasoning (M5 narrative explanation)
  ollama pull llama3.1:8b
  
  # Balanced speed/quality fallback
  ollama pull mistral:7b
  ```
- Verify Ollama is running: open `http://localhost:11434` in your browser.
- Planned `.env` variables:
  ```ini
  OLLAMA_BASE_URL=http://localhost:11434
  LOCAL_LLM_MODEL=llama3.1:8b
  ```

### 2. Target Playwright Scraper
- Designed as a fallback for dynamic Javascript-rendered pages.
- Requires downloading Playwright browsers: `poetry run playwright install`.

### 3. Target Local Embeddings
- Designed to load `BAAI/bge-small-en-v1.5` locally when the Gemini API is down.
- Planned `.env` variables:
  ```ini
  LOCAL_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
  ```

---

## Production Deployment (Going Live)

This section guides you through going live with the NewsLens Agentic RAG application.

### 1. Deployment Architecture

For live production serving, the application runs inside orchestrated Docker containers. The architecture consists of three core components:

```text
news-sync (polling connector) ──writes──▶ data/pathway_sources/*.json
                                                 │
                                                 ▼
                                           pathway (VectorStoreServer :8765)
                                                 │
                                                 ▼
                                           web (FastAPI Server :8000) ◀──POST /v1/retrieve── pathway
```

* **`news-sync`**: Continually polls NewsAPI.org and RSS outlets in the background, writing normalized articles to JSON files.
* **`pathway`**: Hosts Pathway's VectorStoreServer which watches those JSON files and serves embedded document chunks on port `8765`.
* **`web`**: Hosts the FastAPI server (running the LangGraph RAG pipeline, the web UI, and the REST endpoints) on port `8000`.

### 2. Going Live with Docker Compose (Recommended Setup)

To launch the orchestrated service suite on any production server:

```bash
# 1. Clone your production-ready repository
git clone https://github.com/Shreyansh-Verma007/newslens.git
cd newslens

# 2. Configure environment keys
cp .env.example .env
nano .env # Add your production GEMINI_API_KEY and NEWSAPI_KEY

# 3. Build and launch the container stack in the background
docker compose up -d --build
```
Verify the health endpoint: `curl http://localhost:8000/api/health`.

---

## Serving via Pathway Native (`serve_callable` API)

If you wish to migrate from an external FastAPI server to Pathway's built-in **`serve_callable`** API (routing and hosting your Agentic RAG pipeline natively inside the Pathway runtime), follow the migration recipe below:

### Migration Recipe

Create a serving entry point `run_native_serving.py` in your repository:

```python
"""
Pathway Native Serving Entrypoint.
Exposes the LangGraph multi-agent RAG pipeline directly via Pathway's serve_callable API.
"""

from __future__ import annotations
import pathway as pw
from src.m2_agents.graph import compile_agent_graph
from src.m1_intent.classifier import IntentClassifier

# 1. Initialize the intent translator and agent graph
intent_classifier = IntentClassifier()
graph = compile_agent_graph()

# 2. Define the serving function
def native_rag_endpoint(query: str, top_k: int = 15) -> dict:
    """
    Accepts raw query inputs, translates intent, runs retrieval-agent cascade,
    and returns the final serializable AnalysisResult dictionary.
    """
    try:
        # Step A: Run intent classification (M1)
        intent_payload = intent_classifier.classify(query)
        
        # Step B: Invoke the stateful LangGraph pipeline (M2-M4)
        state_input = {
            "intent_payload": intent_payload,
            "retrieved_chunks": [],
            "crag_grades": [],
            "analysis_result": None,
            "agent_trace": [],
            "iteration_count": 0,
            "error_log": []
        }
        output = graph.invoke(state_input)
        
        # Step C: Return the structured result dictionary
        result = output.get("analysis_result")
        if result:
            return result.model_dump(mode="json")
        return {"error": "Failed to compile analysis result"}
        
    except Exception as exc:
        return {"error": f"Pipeline failure: {str(exc)}"}

# 3. Start Pathway's native server (serves REST endpoint on port 8080)
if __name__ == "__main__":
    print("Launching native Pathway server on port 8080...")
    pw.serve_callable(
        host="0.0.0.0",
        port=8080,
        function=native_rag_endpoint
    )
```

Run this script to expose a native REST endpoint directly served by Pathway:
```bash
poetry run python run_native_serving.py
```
This is fully compliant with the Pathway native deployment guidelines and operates as a unified, high-performance RAG pipeline on a single port.

---

## Vercel-like Continuous Deployment (CI/CD)

To get a Vercel-like experience where any git commit automatically builds and deploys your changes to your live Docker container stack, we use **GitHub Actions**.

Whenever you push to the `main` or `master` branch, the workflow defined in `.github/workflows/deploy.yml` will SSH into your server, run `git pull`, and execute a zero-downtime rebuild using `docker compose up --build`.

### Setup Instructions

#### Step 1: Initial Server Setup
1. Log into your production server via SSH.
2. Clone your repository into a directory of your choice (e.g. `/home/ubuntu/newslens`):
   ```bash
   git clone https://github.com/Shreyansh-Verma007/newslens.git /home/ubuntu/newslens
   cd /home/ubuntu/newslens
   ```
3. Copy and configure your production `.env` file (the CI/CD workflow will pull updates but reuse this local file):
   ```bash
   cp .env.example .env
   nano .env # Add your production GEMINI_API_KEY, NewsAPI key, etc.
   ```

#### Step 2: Configure GitHub Repository Secrets
To allow GitHub Actions to log into your server securely, go to your GitHub repository and navigate to **Settings > Secrets and variables > Actions**. Add the following repository secrets:

* **`SSH_HOST`**: The public IP address or domain name of your server (e.g. `192.0.2.1` or `newslens.example.com`).
* **`SSH_USERNAME`**: The SSH login user (e.g. `ubuntu` or `root`).
* **`SSH_KEY`**: The contents of your private SSH key used to log into the server (typically found in `~/.ssh/id_rsa` or `~/.ssh/id_ed25519` on your local machine). Make sure your server's `~/.ssh/authorized_keys` includes the corresponding public key.
* **`SSH_PORT`**: *(Optional)* The SSH port if not the default `22`.
* **`DEPLOY_PATH`**: The absolute path on the server where you cloned the repo in Step 1 (e.g. `/home/ubuntu/newslens`).

#### Step 3: Trigger the First Deployment
Now, commit your changes and push to GitHub:
```bash
git add .
git commit -m "Configure continuous deployment pipeline"
git push origin main
```
Go to the **Actions** tab in your GitHub repository interface. You will see your deployment job running. Once complete, your changes will be built and running live on the server!



