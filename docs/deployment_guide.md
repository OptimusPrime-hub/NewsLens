# NewsLens — Deployment & Operations Guide

Inter IIT Tech Meet 13.0 | Pathway Agentic RAG Problem Statement

This guide is the authoritative reference for installing, configuring, and running NewsLens locally or with Docker.

---

## 1. System Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.12+ (tested on 3.14) |
| Package manager | [Poetry](https://python-poetry.org/) |
| Docker | Required on **Windows** to run Pathway VectorStore (challenge rule) |
| OS | Windows (dev + LocalRetriever) · Linux/macOS (native Pathway) |

Optional API keys (improve live data and fallback tiers):

- `GEMINI_API_KEY` — primary LLM + embeddings
- `GEMINI_API_KEY_FALLBACK` — secondary Gemini key (auto-failover)
- `NEWSAPI_KEY` — live article polling
- `BING_SEARCH_API_KEY` — Tier-2 retrieval fallback

---

## 2. Installation

```powershell
# Windows (recommended)
git clone https://github.com/Shreyansh-Verma007/newslens.git
cd newslens
.\scripts\install.ps1
```

```bash
# Linux / macOS
git clone https://github.com/Shreyansh-Verma007/newslens.git
cd newslens
bash scripts/install.sh
poetry install
```

> **Windows note:** Pathway is excluded from the Windows Poetry install (`platform_system != 'Windows'`). Use Docker for Pathway, or run with `LocalRetriever` + demo seed data for development.

---

## 3. Configuration

Copy the template and fill in secrets:

```bash
cp .env.example .env
```

### Required for full LLM quality

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Primary Google Gemini key |
| `GEMINI_API_KEY_FALLBACK` | Secondary key — used automatically when primary fails |

### Pathway VectorStore

| Variable | Default | Description |
|----------|---------|-------------|
| `PATHWAY_HOST` | `127.0.0.1` | Pathway server host (`pathway` inside Docker Compose) |
| `PATHWAY_PORT` | `8765` | Pathway VectorStore REST port |
| `PATHWAY_SOURCE_GLOB` | `data/pathway_sources/*.json` | JSON articles watched by Pathway |
| `PATHWAY_REFRESH_INTERVAL_MS` | `30000` | News sync poll interval |
| `NEWS_SYNC_QUERY` | `world news top stories` | Default NewsAPI query |

### Agent tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_CHAT_MODEL` | `gemini-1.5-flash` | Chat model for M1/M2/M3/M5 |
| `GEMINI_EMBEDDING_MODEL` | `models/text-embedding-004` | Embedding model for M0/Pathway |
| `CRAG_RELEVANCE_THRESHOLD` | `0.72` | Min mean relevance before escalating retrieval |
| `M1_CONFIDENCE_THRESHOLD` | `0.80` | Below this → route to `CROSS_PUBLISHER_SUMMARY` |
| `RETRIEVAL_TOP_K` | `15` | Chunks requested per retrieval call |
| `SEED_DEMO_DATA` | `true` | Auto-seed 5 trade articles on server startup (dev) |
| `SIMULATE_RETRIEVAL_FAILURES` | *(empty)* | Comma list: `pathway,bing,scraper` for resilience demo |

**Never commit `.env`** — it is listed in `.gitignore`.

---

## 4. Running Locally (Windows — fastest path)

One command seeds demo articles and starts the UI:

```powershell
.\scripts\run_local.ps1
```

Open **http://127.0.0.1:8000**

### What happens under the hood

1. `scripts/seed_demo_data.py` loads 5 US–China trade articles into the in-process store **and** `data/pathway_sources/`
2. Uvicorn starts FastAPI on port 8000
3. `RetrievalManager` uses **`LocalRetriever`** on Windows (Pathway unavailable natively)
4. M1/M2/M3 agents run via Gemini (or regex/VADER offline fallbacks if keys missing)

### Manual steps (equivalent)

```powershell
poetry run python scripts/seed_demo_data.py
$env:SEED_DEMO_DATA = "true"
poetry run uvicorn src.m5_ui.api.server:app --reload --host 127.0.0.1 --port 8000
```

### Suggested test queries

| Query | Expected intent |
|-------|-----------------|
| `Summarize US-China trade talks across publishers` | `CROSS_PUBLISHER_SUMMARY` |
| `How did Reuters vs Fox News cover US-China trade?` | `BIAS_DETECTION` |
| `Timeline of the latest US-China trade dispute` | `TIMELINE` |

### API smoke test

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health

Invoke-RestMethod -Uri http://127.0.0.1:8000/api/analyze `
  -Method POST -ContentType "application/json" `
  -Body '{"query":"Summarize US-China trade talks"}'
```

---

## 5. Docker Deployment (full Pathway stack)

**Required on Windows** for challenge-compliant Pathway VectorStore serving.

```bash
cp .env.example .env
# Edit .env — set GEMINI_API_KEY and optional NEWSAPI_KEY / BING_SEARCH_API_KEY

docker compose up --build
```

Open **http://localhost:8000**

### Services

| Service | Port | Command | Role |
|---------|------|---------|------|
| `pathway` | 8765 | `scripts/run_pathway_pipeline.py` | Pathway VectorStoreServer over JSON articles |
| `news-sync` | — | `scripts/sync_news_sources.py` | Polls NewsAPI + RSS → writes JSON files |
| `web` | 8000 | `uvicorn src.m5_ui.api.server:app` | FastAPI UI + REST API |

### Service dependency graph

```
news-sync ──writes──▶ data/pathway_sources/*.json
                              │
                              ▼
                        pathway :8765
                              │
                              ▼
                          web :8000  ──POST /v1/retrieve──▶ pathway
```

Inside Docker Compose, `web` sets `PATHWAY_HOST=pathway` so M2's `PathwayRetriever` hits the container network.

### Build image only

```bash
docker build -t newslens:latest .
```

---

## 6. Native Linux (no Docker)

Three terminals:

```bash
# Terminal 1 — seed demo articles (optional, for offline dev)
poetry run python scripts/seed_demo_data.py

# Terminal 2 — Pathway VectorStore server
poetry run python scripts/run_pathway_pipeline.py

# Terminal 3 — optional live news sync (writes JSON for Pathway to watch)
poetry run python scripts/sync_news_sources.py

# Terminal 4 — web UI
poetry run uvicorn src.m5_ui.api.server:app --reload --port 8000
```

---

## 7. Retrieval Resilience Demo

Simulate callback failures to prove autonomous fallback (challenge Level-2 requirement):

```powershell
$env:SIMULATE_RETRIEVAL_FAILURES = "pathway"
poetry run uvicorn src.m5_ui.api.server:app --port 8000
```

Cascade order:

| Tier | Backend | Trigger |
|------|---------|---------|
| 0 | Pathway VectorStore **or** LocalRetriever (Windows) | Primary |
| 1 | Query rewrite + Tier-0 retry | Mean relevance below `CRAG_RELEVANCE_THRESHOLD` |
| 2 | Bing Search API v7 | Tier 0/1 insufficient |
| 3 | Google News RSS + httpx/BeautifulSoup scraper | All above fail |

Check `metadata.retrieval_tier_used` in the API response (`pathway`, `local`, `bing`, or `scraper`).

---

## 8. REST API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Search landing page |
| `/results` | GET | Results page (bias / timeline / summary tabs) |
| `/api/health` | GET | Liveness probe |
| `/api/analyze` | POST | Full M1→M2 pipeline, returns `AnalysisResult` JSON |
| `/api/analyze/stream` | POST | SSE progress stream + final result |
| `/api/docs` | GET | OpenAPI interactive docs |

**Request body** (`POST /api/analyze`):

```json
{ "query": "How did Reuters and Fox News cover US-China trade?" }
```

---

## 9. Testing

```bash
poetry run pytest tests/ -v
```

Current suites:

| Path | Count | Scope |
|------|-------|-------|
| `tests/unit/` | 20+ | Retrieval cascade, M1 classifier, M3 bias, M4 timeline |
| `tests/contract/` | 5 | Pydantic schema round-trips (M0–M4) |
| `tests/test_m0.py`, `test_m1.py` | 6 | Module smoke tests |

---

## 10. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Port 8000 already in use | `Get-NetTCPConnection -LocalPort 8000` → stop owning process |
| `retrieval_tier_used: scraper` on Windows with demo data | Restart server after `seed_demo_data.py`; ensure `SEED_DEMO_DATA=true` |
| Offline heuristic summaries | Set `GEMINI_API_KEY` in `.env` and restart |
| Pathway healthcheck fails in Docker | Wait ~60s for first embed; check `GEMINI_API_KEY` and JSON files in `data/pathway_sources/` |
| `This is not the real Pathway package` on Windows | Expected — use Docker for real Pathway; dev uses `LocalRetriever` |

---

## 11. Submission Checklist (Judges)

- [ ] Clone repo and `cp .env.example .env`
- [ ] Add `GEMINI_API_KEY` (and optional `NEWSAPI_KEY`, `BING_SEARCH_API_KEY`)
- [ ] **Windows:** `docker compose up --build` **or** `.\scripts\run_local.ps1` for quick demo
- [ ] Open http://localhost:8000 and run a bias + summary query
- [ ] Verify agent trace panel shows retrieval tier and CRAG steps
- [ ] Demo `SIMULATE_RETRIEVAL_FAILURES=pathway` fallback behavior
