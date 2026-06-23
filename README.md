# NewsLens — Dynamic Agentic RAG News Analysis & Bias Detection Platform

> Point it at any news topic, describe what you want to understand in plain English, and watch autonomous agents retrieve live articles, detect narrative bias across publishers, and draw event timelines — **before you've even opened a browser tab.**

NewsLens is a fully autonomous, multi-agent intelligence system built on **Pathway's real-time streaming framework**. Given a natural-language query (e.g., *"How did Reuters and Fox News cover the US-China trade talks differently?"*), it routes the request through a cascading agent pipeline, retrieves live news from a continuously updated vector index, and surfaces structured insights across three analytical dimensions — **bias detection**, **timeline synthesis**, and **cross-publisher summarization**.

**Core thesis:** Every quality signal (sentiment score, framing vector, bias magnitude, confidence band) is produced by transformer models, deterministic scoring rules, and literature-backed algorithms. LLMs are architecturally bounded to **query understanding** (M1) and **narrative explanation** (M5) — they never hallucinate scores.

---

## Quick Start

```bash
# 1. Start the Pathway ingestion pipeline (background)
poetry run python scripts/run_pathway_pipeline.py

# 2. Start the NewsLens web server (new terminal)
poetry run uvicorn src.m5_ui.api.server:app --reload --port 8000

# 3. Open http://localhost:8000 in your browser
#    Type your query and press Analyze.

# JSON output for scripting
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "Timeline of US-China trade talks"}'
```

---

## Architecture

NewsLens is built as a modular six-module pipeline. Each module communicates through strictly typed Pydantic v2 data contracts:

| Module | Name | Role | LLM? |
|--------|------|------|-------|
| **M0** | Live News Ingestion | Connects `pw.io` source connectors, normalizes articles, chunks text, embeds with OpenAI, and serves a continuously fresh Pathway VectorStore + DocumentStore | No |
| **M1** | Query Intent Translator | Converts plain-English query into a structured `IntentPayload` (intent class, entities, publishers, date range) with Pydantic v2 strict validation and graceful fallback | Yes |
| **M2** | Multi-Agent Router & Retrieval Manager | Routes `IntentPayload` to specialist agents via a LangGraph state machine; manages autonomous 4-tier retrieval fallback cascade and CRAG re-ranking | Partial |
| **M3** | Bias & Sentiment Engine | Runs transformer-based sentiment per publisher, LLM framing vector extraction, and a weighted bias score formula — all numeric outputs are deterministic | Partial |
| **M4** | Timeline Synthesizer | Extracts temporally anchored events via spaCy NER + LLM JSON pass, deduplicates by cosine similarity, and produces a source-attributed chronological timeline | Partial |
| **M5** | Explanation & UI Engine | Browser-based web interface served by FastAPI — HTML templates, Vanilla CSS, Vanilla JS, Chart.js visualizations; exposes `POST /api/analyze` REST endpoint consumed by the frontend | Yes |

```
Natural Language Query
         │
         ▼
   [M1] Intent
   Translator
   (IntentPayload)
         │
         ▼
   [M2] Multi-Agent Router & Retrieval Manager
   ┌─────────────────────────────────────────┐
   │  LangGraph Stateful Agent Orchestrator  │
   │  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
   │  │ Timeline │ │  Bias    │ │ Summary │ │
   │  │  Agent   │ │  Agent   │ │  Agent  │ │
   │  └──────────┘ └──────────┘ └─────────┘ │
   │         CRAG Evaluator at each agent    │
   └──────────────────┬──────────────────────┘
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
[M3] Bias & Sentiment       [M4] Timeline
     Engine                  Synthesizer
(BiasAnalysisResult)       (TimelineResult)
         └────────────┬────────────┘
                      ▼
         [M5] Explanation & UI Engine
         (FastAPI server — templates/index.html,
          templates/results.html, static CSS/JS,
          Chart.js bias heatmap + timeline)
                      │
              Live Web Browser
```

**Pathway VectorStore** is the shared retrieval backbone, queried by M2 with live-updated embeddings. M0 runs as a continuously executing `pw.run()` process in the background, so every query hits a fresh index.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Live index** | Pathway's incremental computation engine keeps the vector index fresh within 60 seconds of article publication — no manual refresh |
| **Autonomous fallback** | 4-tier retrieval cascade (Pathway → Query Rewrite → Bing Search → Playwright Scraper) — the agent decides when to escalate, no human intervention |
| **CRAG grading** | Every retrieved chunk is graded RELEVANT / AMBIGUOUS / IRRELEVANT; only high-confidence chunks reach generation |
| **Bias score formula** | `BiasScore = w1*DeltaSentiment + w2*FramingDivergence + w3*EntitySalienceDelta`, normalized to [-1, +1] |
| **5-frame framing analysis** | LLM classifies publisher narrative into CONFLICT / ECONOMIC / HUMAN_INTEREST / MORALITY / RESPONSIBILITY frames |
| **Event confidence tiers** | Timeline events tagged HIGH (3+ sources), MEDIUM (2), LOW (1 corroborated), UNVERIFIED (1 uncorroborated) |
| **Agent trace transparency** | Every LangGraph node step — intent, routing, retrieval tier, CRAG grades, generation — is surfaced live in the web UI trace panel |
| **Bounded LLM use** | LLMs appear only in M1 (intent parsing) and M5 (narrative explanation); sentiment, bias, and timeline scores are model-computed |
| **Publisher normalization** | Canonical publisher name mapping across RSS, NewsAPI, and web sources eliminates duplicate publisher identities |
| **Offline embedding fallback** | Seamlessly switches from OpenAI `text-embedding-3-small` to local `BAAI/bge-small-en-v1.5` when the API is unavailable |

---

## Query Intent Taxonomy

NewsLens natively classifies every query into one of three analytical intents, each routed to a specialist agent:

| Intent Class | Example Queries | Specialist Agent | Output |
|---|---|---|---|
| **`BIAS_DETECTION`** | *"How did BBC vs Fox cover X?"* · *"Sentiment toward Y in CNN"* · *"Which publisher is most alarmist on Z?"* | Bias Agent | Publisher bias profiles, pairwise divergence matrix, framing radar |
| **`TIMELINE`** | *"Timeline of the SVB collapse"* · *"Sequence of events in the Gaza war"* · *"What happened first in the OpenAI board crisis?"* | Timeline Agent | Chronological event list, source attribution, temporal gap flags |
| **`CROSS_PUBLISHER_SUMMARY`** | *"What is happening with X?"* · *"Summarize last week's coverage of Y"* · *"What do all sources agree on about Z?"* | Summary Agent | Consensus summary, confidence score, divergence warnings |

Queries that fall below a confidence threshold of 0.80 are automatically routed to `CROSS_PUBLISHER_SUMMARY` — the safest, most general intent — without failing.

---

## Data Contracts

All inter-module communication uses strictly typed Pydantic v2 models:

| Contract | Flow | Description |
|----------|------|-------------|
| `AnalyzeRequest` | M5 → M1/M2 | API request containing query, optional publishers, date range filters, and top_k overrides |
| `IntentPayload` | M1 → M2 | Classified intent type, extracted entities, publishers, date range, topic keywords, and confidence |
| `RetrievedChunk` | Pathway/API → M2 | Chunk text, publisher, publish timestamp, and cosine relevance score |
| `CRAGGrade` | M2 CRAG → M2 Graph | Per-chunk grading (RELEVANT / AMBIGUOUS / IRRELEVANT) with LLM reason |
| `AgentState` | M2 Nodes (LangGraph) | Shared state containing intent, chunks, crag grades, specialist results, error logs, and trace |
| `BiasAnalysisResult` | M3 → M2 → M5 | Publisher profiles (sentiment, framing, entity salience, bias score) and divergence matrix |
| `TimelineResult` | M4 → M2 → M5 | Sorted chronological events, temporal gap flags, and narrative coherence score |
| `SummaryResult` | M2 Summary Agent → M5 | Consensus text, consensus points, and key takeaways |
| `AnalysisResult` | M2 → M5 | Top-level response wrapper: intent, conditional result payload, agent trace, metadata, and warnings |
| `AnalysisMetadata` | M2 → M5 | Query session ID, timestamp, latency, retrieval tier used, chunk counts, and model versions |

Every `AnalysisResult` carries a full `agent_trace: list[TraceEntry]` so the web UI can replay every reasoning step the pipeline took.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Streaming Runtime** | `pathway` >=0.14.0 — incremental computation, live VectorStore, pw.io connectors |
| **Agent Orchestration** | `langgraph` >=0.2.0 — stateful multi-agent graphs with conditional routing |
| **Primary LLM** | `gemini` `gemini-1.5-flash` — Google Generative AI primary layer |
| **Local LLM Fallback** | `ollama` + `llama3.2:3b` — fully offline local fallback model |
| **Embeddings (Primary)** | `openai` `text-embedding-3-small` — 1536-dim, strong semantic quality |
| **Embeddings (Fallback)** | `sentence-transformers` `BAAI/bge-small-en-v1.5` — local, no API key required |
| **Sentiment Analysis** | `transformers` `cardiffnlp/twitter-roberta-base-sentiment-latest` — news-domain robust |
| **Sentiment Fallback** | `vaderSentiment` — fast, rule-based, works offline |
| **NER / NLP** | `spacy` `en_core_web_trf` >=3.7 — DATE/TIME entity extraction for timelines |
| **News Source (Primary)** | `newsapi-python` (NewsAPI.ai) — 80k+ sources, real-time structured JSON |
| **News Source (Secondary)** | `feedparser` (RSS polling) — 10+ major outlet feeds |
| **Web Search Fallback** | Bing Search API v7 — structured web results, Tier-2 fallback |
| **Scraper Fallback** | `playwright` (async) — JS-rendered page support, Tier-3 fallback |
| **HTTP Client** | `httpx` — async-first, retry support via `tenacity` |
| **Retry Logic** | `tenacity` — exponential backoff for all external API calls |
| **Data Validation** | `pydantic` v2 with strict validation across all 11 data contracts |
| **UI Framework** | `fastapi` + Jinja2 | Latest | Lightweight ASGI server; serves HTML templates + REST `/api/analyze` |
| **Frontend** | HTML5 + Vanilla CSS + Vanilla JS | — | No build step; zero npm dependencies; runs in any browser |
| **Charts** | `Chart.js` (CDN) | >=4.0 | Client-side bias heatmap, framing radar, timeline — no server-side render |
| **Logging** | `loguru` — structured logs, agent trace capture per session |
| **Configuration** | `pydantic-settings` + `.env` — type-safe config, 12-factor compliant |
| **Testing** | `pytest` + `pytest-asyncio` — full async test support |

---

## Getting Started

### Prerequisites

- Python 3.12+ (tested on 3.14)
- [Poetry](https://python-poetry.org/docs/#installation)
- [Ollama](https://ollama.com) (for local offline LLM fallback)
- NewsAPI.ai API key ([free tier](https://newsapi.ai))
- Google Gemini API key ([aistudio.google.com](https://aistudio.google.com))

### Installation

```bash
# 1. Clone
git clone https://github.com/Shreyansh-Verma007/newslens.git
cd newslens

# 2. Install dependencies
poetry install

# 3. Pull spaCy model
poetry run python -m spacy download en_core_web_trf

# 4. Pull local LLM fallback models
ollama pull llama3.2:3b        # Local LLM fallback (M1/M5)

### Ollama Setup Guide (Local Offline LLM)

To set up local offline fallback capabilities:
1. Download and install Ollama from [ollama.com](https://ollama.com/).
2. Run the Ollama application on your local machine.
3. Download the default model (`llama3.2:3b`) using your terminal:
   ```bash
   ollama pull llama3.2:3b
   ```
4. Verify the Ollama server is running by opening `http://localhost:11434` in your browser.
5. In your `.env` file, ensure `OLLAMA_BASE_URL=http://localhost:11434` and `LOCAL_LLM_MODEL=llama3.2:3b` are configured.

# 5. Start the Pathway ingestion pipeline (background process)
poetry run python scripts/run_pathway_pipeline.py &

# 6. Launch the web server
poetry run bash scripts/run_website.sh
# Open http://localhost:8000
```

---

## Environment Variables

Create a `.env` file in the project root (see `.env.example` for a safe template). NewsLens loads `.env`, then `.env.local` if present (later file wins). **Do not commit real API keys.**

```bash
# --- News Sources ---
NEWSAPI_KEY=your_newsapi_ai_key          # Primary live news source
BING_SEARCH_API_KEY=your_bing_key        # Tier-2 retrieval fallback

# --- Pathway VectorStore ---
PATHWAY_HOST=0.0.0.0
PATHWAY_PORT=8765
PATHWAY_REFRESH_INTERVAL_MS=30000        # NewsAPI polling cadence (ms)
PATHWAY_RSS_REFRESH_INTERVAL_MS=60000   # RSS polling cadence (ms)

# --- LLM Provider ---
GEMINI_API_KEY=your_gemini_key           # Google Gemini API Key

# --- LLM Fallback (Local) ---
OLLAMA_BASE_URL=http://localhost:11434   # Local Ollama endpoint
LOCAL_LLM_MODEL=llama3.2:3b             # Offline local fallback model

# --- Embeddings ---
EMBEDDING_MODEL=text-embedding-3-small   # OpenAI embedding model
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5  # Offline embedding fallback

# --- CRAG ---
CRAG_RELEVANCE_THRESHOLD=0.72           # Below this -> escalate retrieval tier
CRAG_TOP_K=15                           # Chunks retrieved per query
```

---

## Usage

### 1. Start the pipeline

```bash
# Terminal 1 — start the Pathway ingestion pipeline (runs continuously)
poetry run python scripts/run_pathway_pipeline.py

# Terminal 2 — start the FastAPI web server
poetry run uvicorn src.m5_ui.api.server:app --reload --port 8000
```

### 2. Open the web UI

Navigate to **http://localhost:8000** in your browser.

| Page | URL | Description |
|------|-----|-------------|
| Query input | `http://localhost:8000/` | Enter your natural-language news query |
| Results | `http://localhost:8000/results` | Bias heatmap, timeline, summary and agent trace |
| About | `http://localhost:8000/about` | Methodology and system explanation |

### 3. Example queries

| Query | Intent detected |
|-------|----------------|
| *"How did Reuters and Fox News cover the US-China trade talks?"* | `BIAS_DETECTION` |
| *"Timeline of the Silicon Valley Bank collapse"* | `TIMELINE` |
| *"What happened with Gaza ceasefire negotiations last week?"* | `CROSS_PUBLISHER_SUMMARY` |
| *"Compare BBC and Al Jazeera on the Ukraine war"* | `BIAS_DETECTION` |

### 4. REST API (programmatic access)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze` | `POST` | Run full pipeline, return `AnalysisResult` JSON |
| `/api/analyze/stream` | `POST` | SSE stream — emits live progress events then final result |
| `/api/health` | `GET` | Liveness probe |
| `/api/docs` | `GET` | OpenAPI interactive docs |

```bash
# Synchronous — waits for full result
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"query": "How did Reuters and Fox News cover the US-China trade talks?"}'

# Streaming — emits SSE progress then result (used by the web UI)
curl -X POST http://localhost:8000/api/analyze/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Timeline of Gaza ceasefire negotiations"}'

# Liveness
curl http://localhost:8000/api/health
```

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | `string` | ✅ | Natural-language news query |
| `publishers` | `list[str]` | ❌ | Restrict to specific publishers (e.g. `["bbc", "reuters"]`) |
| `date_from` | `string` | ❌ | ISO 8601 start date filter (`YYYY-MM-DD`) |
| `date_to` | `string` | ❌ | ISO 8601 end date filter (`YYYY-MM-DD`) |
| `top_k` | `int` | ❌ | Number of chunks to retrieve (default: `15`) |

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

# With coverage report
poetry run pytest tests/ --cov=src --cov-report=html
```

### Test Suites

| Suite | Scope | Requirements |
|-------|-------|--------------|
| `tests/unit/` | Module isolation — each engine tested independently with fixture data | No network, no LLM |
| `tests/integration/` | Full pipeline flow from `IntentPayload` to `AnalysisResult` with mocked VectorStore | No network, no LLM |

### What the E2E Smoke Tests Verify

| Test Class | What It Verifies |
|------------|-----------------|
| **IntentClassification** | Each of 3 intent types classified correctly for canonical query patterns; fallback fires below threshold |
| **RetrievalFallbackCascade** | Each of 4 retrieval tiers triggers correctly when the previous tier returns below-threshold relevance |
| **CRAGGrading** | Retrieved chunks are graded correctly; IRRELEVANT chunks are filtered before generation |
| **BiasScoreConsistency** | Publisher bias scores are bounded [-1, 1]; pairwise divergence matrix is symmetric |
| **TimelineOrdering** | Events sorted ascending by date; multi-source events flagged HIGH_CONFIDENCE; temporal gaps detected |
| **AgentTraceContract** | Full trace emitted with node names, latencies, and fallback tier for every pipeline run |
| **AnalysisResultContract** | All required fields present; conditional fields populated correctly per intent class |

---

## Project Structure

```
news-agentic-rag/
├── main.py                              # Pipeline entry point — starts M0 pw.run() + launches M5 FastAPI server
├── conftest.py                          # Shared pytest fixtures (mock VectorStore, sample IntentPayloads)
├── README.md
├── pyproject.toml
├── .env.example
├── src/
│   ├── __init__.py
│   ├── m0_ingestion/
│   │   ├── __init__.py
│   │   ├── connectors/
│   │   │   ├── newsapi_connector.py     # pw.io NewsAPI connector
│   │   │   ├── rss_connector.py         # pw.io RSS feed connector
│   │   │   └── scraper_connector.py     # Playwright-based scraper (Tier-3 fallback)
│   │   ├── processors/
│   │   │   ├── normalizer.py            # HTML strip, dedup, publisher normalization
│   │   │   ├── chunker.py               # 512-token semantic chunker with 64-token overlap
│   │   │   └── embedder.py              # OpenAI + local embedder wrapper with fallback
│   │   ├── vector_store.py              # Pathway VectorStoreServer setup
│   │   ├── document_store.py            # Pathway DocumentStore metadata layer
│   │   └── pipeline.py                  # Assembles full M0 pw.run() pipeline
│   ├── m1_intent/
│   │   ├── __init__.py
│   │   ├── classifier.py                # LLM intent classifier with Pydantic validation
│   │   ├── schemas.py                   # IntentType, IntentPayload
│   │   └── prompts.py                   # Few-shot classification prompt templates
│   ├── m2_agents/
│   │   ├── __init__.py
│   │   ├── graph.py                     # LangGraph StateGraph definition
│   │   ├── state.py                     # AgentState TypedDict
│   │   ├── supervisor.py                # Supervisor agent node
│   │   ├── timeline_agent.py            # Timeline specialist agent node
│   │   ├── bias_agent.py                # Bias specialist agent node
│   │   ├── summary_agent.py             # Summary specialist agent node
│   │   ├── assembler.py                 # Assembles agent results into final output
│   │   ├── validators.py                # Strict schema validators
│   │   ├── schemas.py                   # RetrievedChunk, SummaryResult, TraceEntry, AnalysisMetadata, AnalysisResult
│   │   ├── prompts/
│   │   │   ├── bias.py                  # Prompts for Bias agent node
│   │   │   ├── crag.py                  # Prompts for CRAG evaluator node
│   │   │   ├── rewrite.py               # Prompts for Query rewriter node
│   │   │   ├── summary.py               # Prompts for Summary agent node
│   │   │   └── timeline.py              # Prompts for Timeline agent node
│   │   ├── retrieval/
│   │   │   ├── manager.py               # RetrievalManager with 4-tier fallback cascade
│   │   │   ├── pathway_client.py        # Pathway VectorStore client
│   │   │   ├── bing_client.py           # Bing Search API v7 client (Tier-2)
│   │   │   └── scraper_client.py        # Playwright scraper client (Tier-3)
│   │   └── crag/
│   │       ├── evaluator.py             # CRAG chunk grader (RELEVANT/AMBIGUOUS/IRRELEVANT)
│   │       ├── rewriter.py              # LLM-based query rewriter for Tier-1 retry
│   │       └── schemas.py               # GradeEnum, CRAGGrade
│   ├── m3_bias/
│   │   ├── __init__.py
│   │   ├── engine.py                    # BiasEngine orchestrator
│   │   ├── sentiment.py                 # RoBERTa + VADER sentiment wrapper
│   │   ├── framing.py                   # 5-frame LLM framing vector extractor
│   │   ├── scoring.py                   # Weighted bias score formula
│   │   └── schemas.py                   # SentimentScores, FramingVector, PublisherBiasProfile, BiasAnalysisResult
│   ├── m4_timeline/
│   │   ├── __init__.py
│   │   ├── synthesizer.py               # TimelineSynthesizer orchestrator
│   │   ├── extractor.py                 # spaCy NER + LLM event JSON extractor
│   │   ├── deduplicator.py              # Cosine similarity event clustering
│   │   └── schemas.py                   # EventConfidence, ArticleReference, TimelineEvent, TimelineResult
│   ├── m5_ui/
│   │   ├── __init__.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── server.py                # FastAPI app factory — mounts static, registers routes
│   │   │   ├── routes.py                # GET /, /results, /about; POST /api/analyze, /api/analyze/stream
│   │   │   ├── deps.py                  # Shared jinja2.Environment (bypasses Starlette Jinja2 cache bug)
│   │   │   └── schemas.py               # AnalyzeRequest (M5 → M1/M2 API contract)
│   │   ├── templates/
│   │   │   ├── index.html               # Search landing page — animated hero, SSE progress overlay
│   │   │   ├── results.html             # Results page — trace panel, metadata card, 4-tab layout
│   │   │   └── about.html               # M0–M5 architecture walkthrough page
│   │   └── static/
│   │       ├── css/
│   │       │   ├── main.css             # Design system — dark glass palette, typography, buttons
│   │       │   ├── components.css       # Tabs, badges, metadata card, trace steps, timeline track
│   │       │   └── animations.css       # Shimmer skeletons, slide-up entrances, live dot pulse
│   │       ├── js/
│   │       │   ├── main.js              # renderResult() — consumes AnalysisResult, tier badge, summary
│   │       │   ├── query.js             # SSE query handler — live progress steps → navigate to /results
│   │       │   ├── bias_chart.js        # Chart.js stacked sentiment bars + 5-axis framing radar
│   │       │   ├── timeline.js          # Horizontal scroll timeline — confidence dots, gap indicators
│   │       │   └── trace_panel.js       # Execution-focused trace steps from agent_trace[]
│   │       └── assets/
│   │           ├── images/              # Logo, icons
│   │           └── fonts/               # Self-hosted web fonts
│   └── shared/
│       ├── __init__.py
│       ├── config.py                    # pydantic-settings Config model
│       ├── llm_factory.py               # LLM provider factory (Gemini / Ollama)
│       ├── logging.py                   # loguru structured logger setup
│       ├── exceptions.py                # Custom exception hierarchy
│       ├── constants.py                 # Central system parameters and thresholds
│       ├── cache.py                     # In-memory resource caching layer
│       ├── retry.py                     # Resilience backoff decorator
│       ├── types.py                     # Reusable type aliases
│       └── prompts/
│           ├── intent.py                # Prompts for Query intent classification
│           ├── framing.py               # Prompts for narrative framing
│           ├── explanation.py           # Prompts for bias explanation
│           ├── timeline.py              # Prompts for timeline preparation
│           ├── summary.py               # Prompts for consensus summary
│           └── crag.py                  # Prompts for corrective retrieval
├── scripts/
│   ├── run_pathway_pipeline.py          # Starts M0 pw.run() background process
│   ├── run_website.sh                   # Starts M5 FastAPI server via uvicorn
│   └── seed_test_data.py                # Seeds Pathway store with fixture articles
├── docs/
│   ├── architecture.md                  # Full architecture specification (this document)
│   ├── api_reference.md                 # REST API reference for /api/analyze
│   └── deployment_guide.md             # Docker / bare-metal deployment guide
└── tests/
    ├── __init__.py
    ├── unit/                            # Module-level isolation tests (no network, no LLM)
    │   ├── test_m0_normalizer.py
    │   ├── test_m1_classifier.py
    │   ├── test_m2_crag.py
    │   ├── test_m3_bias.py
    │   └── test_m4_timeline.py
    ├── integration/                     # Full pipeline tests with mocked VectorStore
    │   ├── test_e2e_bias_query.py
    │   ├── test_e2e_timeline_query.py
    │   └── test_fallback_cascade.py
    └── fixtures/                        # JSON fixture data for offline tests
        ├── sample_articles.json
        └── mock_newsapi_response.json
```

---

## End-to-End Latency

| Step | Module | Estimated Latency |
|------|--------|-------------------|
| Query intent classification | M1 | 1–3s |
| Pathway VectorStore retrieval (Tier-0) | M2 | 0.5–2s |
| CRAG chunk grading | M2 | 1–3s |
| Sentiment + framing analysis | M3 | 3–8s |
| Event extraction + timeline construction | M4 | 3–6s |
| Narrative explanation generation | M5 | 2–5s |
| **Total (standard mode — Tier-0 hit)** | | **~10–27s** |
| **Total (Bing fallback — Tier-2)** | | **~20–40s** |
| **Total (Playwright fallback — Tier-3)** | | **~35–60s** |

M1 and M0 (background pipeline) are independent. M2 retrieval, M3, and M4 run sequentially within the LangGraph state machine. Pathway index freshness is maintained independently at a 30–60s polling cadence — queries always hit a live index, adding zero extra latency.

---

## Resilience & Fallback Summary

| Failure | Detection | Autonomous Recovery |
|---------|-----------|---------------------|
| NewsAPI.ai rate limit / down | HTTP 429/503 + 3x exponential backoff | Switch to RSS feed polling; flag `metadata.retrieval_tier` |
| Pathway VectorStore cold (0 results) | Empty result set | Trigger immediate RSS + NewsAPI refresh, retry query |
| CRAG relevance below threshold | `mean(relevance_scores) < 0.72` | Rewrite query (Tier-1) → Bing Search (Tier-2) → Playwright (Tier-3) |
| OpenAI Embedding API down | `openai.APIError` | Switch to local `BAAI/bge-small-en-v1.5` via `sentence-transformers` |
| Gemini Chat API down | `Exception` | Local `llama3.2:3b` via Ollama; flagged in UI |
| LLM JSON parse failure (M1) | `pydantic.ValidationError` | Regex extraction fallback; if fails → `CROSS_PUBLISHER_SUMMARY` default |
| LangGraph max iterations exceeded | `iteration_count > MAX_ITER` | Return partial result with `INCOMPLETE` warning in agent trace |

---

## Design Principles

1. **Live data over static snapshots** — Pathway's incremental computation engine keeps the vector index fresh within 60 seconds; no scheduled batch jobs, no manual re-indexing
2. **Autonomous resilience** — The agent pipeline decides when to escalate retrieval tiers; every failure has a defined autonomous recovery path
3. **Bounded LLM use** — LLMs appear only for language understanding (M1) and narrative explanation (M5); all scores are produced by transformer models and deterministic formulas
4. **CRAG-first retrieval** — Every retrieved chunk is graded for relevance before it touches generation; ambiguous and irrelevant chunks are filtered out, not papered over
5. **Trace-first transparency** — Every reasoning step is captured in `AgentState.agent_trace` and surfaced in the UI; the system never produces a result that cannot be audited
6. **Strict modularity** — Every module communicates through Pydantic v2 data contracts; internals are independently replaceable without touching adjacent modules

---

## Authors

[Shreyansh Verma](https://github.com/Shreyansh-Verma007) — Inter-IIT Tech Meet 13.0 | Pathway Problem Statement
