# NewsLens — Dynamic Agentic RAG News Analysis & Bias Detection Platform

> Point it at any news topic, describe what you want to understand in plain English, and watch autonomous agents retrieve live articles, detect narrative bias across publishers, and draw event timelines — **before you've even opened a browser tab.**

NewsLens is a fully autonomous, multi-agent intelligence system built on **Pathway's real-time streaming framework**. Given a natural-language query (e.g., *"How did Reuters and Fox News cover the US-China trade talks differently?"*), it routes the request through a cascading agent pipeline, retrieves live news from a continuously updated vector index, and surfaces structured insights across three analytical dimensions — **bias detection**, **timeline synthesis**, and **cross-publisher summarization**.

**Core thesis:** Every quality signal (sentiment score, framing vector, bias magnitude, confidence band) is produced by transformer models, deterministic scoring rules, and literature-backed algorithms. LLMs are architecturally bounded to **query understanding** (M1) and **narrative explanation** (M5) — they never hallucinate scores.

---

## Quick Start

```bash
# Ask about bias across publishers
python main.py "How did Reuters and Fox News cover the US-China trade talks?"

# Draw a timeline of an unfolding event
python main.py "Timeline of the Silicon Valley Bank collapse" --intent timeline

# Get a consensus summary across all sources
python main.py "What is happening with the Gaza ceasefire negotiations?" --intent summary

# Target specific publishers
python main.py "Compare BBC and Al Jazeera on the Ukraine war" --publishers bbc,aljazeera

# Restrict to a date range
python main.py "Gaza ceasefire talks" --from 2025-01-01 --to 2025-06-01

# JSON output for scripting
python main.py "US election coverage bias" --json
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
| **M5** | Explanation & UI Engine | Streamlit app with an agent trace panel, Plotly bias heatmaps, Gantt timeline view, CRAG grade badges, fallback indicators, and confidence meters | Yes |

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
         (Streamlit — Agent Trace Panel,
          Bias Heatmap, Timeline, Sources)
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
| **Agent trace transparency** | Every LangGraph node step — intent, routing, retrieval tier, CRAG grades, generation — is surfaced live in the Streamlit sidebar |
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
| `UserQuery` | M5 → M1 | Raw natural-language query with session ID and timestamp |
| `IntentPayload` | M1 → M2 | Classified intent, extracted entities, publishers, date range, confidence |
| `RetrievalRequest` | M2 → Pathway | Query embedding, result count `k`, and metadata filters (publisher, date) |
| `RetrievedChunk` | Pathway → M2 | Chunk text, publisher, publish timestamp, cosine relevance score |
| `CRAGGrade` | M2 CRAG → M2 Generation | Per-chunk grade (RELEVANT / AMBIGUOUS / IRRELEVANT) with LLM reason |
| `AgentState` | M2 (LangGraph) → All M2 nodes | Full pipeline state: intent, chunks, grades, trace log, error log, iteration count |
| `BiasAnalysisResult` | M3 → M2 → M5 | Publisher sentiment scores, framing vectors, bias score matrix, quote evidence |
| `TimelineResult` | M4 → M2 → M5 | Sorted event list, temporal gaps, coherence score, date range covered |
| `SummaryResult` | M2 Summary Agent → M5 | Consensus text, key points, publisher agreement score |
| `AnalysisResult` | M2 → M5 | Top-level envelope: intent, conditional result payload, agent trace, metadata |
| `AnalysisMetadata` | M2 → M5 | Latency, retrieval tier used, chunk counts, model versions |

Every `AnalysisResult` carries a full `agent_trace: list[TraceEntry]` so the Streamlit UI can replay every reasoning step the pipeline took.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Streaming Runtime** | `pathway` >=0.14.0 — incremental computation, live VectorStore, pw.io connectors |
| **Agent Orchestration** | `langgraph` >=0.2.0 — stateful multi-agent graphs with conditional routing |
| **LLM (M1 Intent)** | `openai` `gpt-4o-mini` — fast, structured JSON output for intent classification |
| **LLM (M5 Narrative)** | `openai` `gpt-4o` — high-quality explanation and bias narrative generation |
| **LLM Fallback (Secondary)** | `anthropic` `claude-3-5-haiku` — separate failure domain from OpenAI |
| **LLM Fallback (Local)** | `ollama` + `llama3.2:3b` — fully offline, no external API dependency |
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
| **UI Framework** | `streamlit` >=1.35 — agent trace panel, tabbed results, real-time streaming |
| **Visualization** | `plotly` — interactive bias heatmaps, Gantt timeline charts, framing radar |
| **Logging** | `loguru` — structured logs, agent trace capture per session |
| **Configuration** | `pydantic-settings` + `.env` — type-safe config, 12-factor compliant |
| **Testing** | `pytest` + `pytest-asyncio` — full async test support |

---

## Getting Started

### Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- [Ollama](https://ollama.com) (optional — for local LLM fallback only)
- NewsAPI.ai API key ([free tier](https://newsapi.ai))
- OpenAI API key ([platform.openai.com](https://platform.openai.com))

### Installation

```bash
# 1. Clone
git clone https://github.com/Shreyansh-Verma007/newslens.git
cd newslens

# 2. Install dependencies
poetry install

# 3. Pull spaCy model
poetry run python -m spacy download en_core_web_trf

# 4. (Optional) Pull local LLM fallback models
ollama pull llama3.2:3b        # Local LLM fallback (M1/M5)
ollama pull qwen2.5-coder:7b   # Optional code/reasoning tasks

# 5. Start the Pathway ingestion pipeline (background process)
poetry run python scripts/run_pathway_pipeline.py &

# 6. Launch the Streamlit UI
poetry run streamlit run src/m5_ui/app.py
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

# --- LLM Providers ---
OPENAI_API_KEY=your_openai_key
M1_LLM_MODEL=gpt-4o-mini                # Intent classification (fast + cheap)
M5_LLM_MODEL=gpt-4o                     # Narrative generation (high quality)
M1_CONFIDENCE_THRESHOLD=0.80            # Minimum confidence to accept intent parse

# --- LLM Fallbacks ---
ANTHROPIC_API_KEY=your_anthropic_key     # Secondary LLM provider
OLLAMA_HOST=http://localhost:11434       # Local Ollama endpoint
LOCAL_LLM_MODEL=llama3.2:3b             # Offline LLM fallback model

# --- Embeddings ---
EMBEDDING_MODEL=text-embedding-3-small   # OpenAI embedding model
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5  # Offline embedding fallback

# --- CRAG ---
CRAG_RELEVANCE_THRESHOLD=0.72           # Below this -> escalate retrieval tier
CRAG_TOP_K=15                           # Chunks retrieved per query
```

---

## Usage

### CLI Commands

```bash
# Standard bias detection query
poetry run python main.py "How did Reuters and Fox News cover the US-China trade talks?"

# Force timeline intent
poetry run python main.py "Timeline of the Silicon Valley Bank collapse" --intent timeline

# Force summary intent
poetry run python main.py "Gaza ceasefire negotiations" --intent summary

# Restrict publishers
poetry run python main.py "Ukraine war coverage comparison" --publishers bbc,reuters,rt

# Filter by date range
poetry run python main.py "US election coverage" --from 2024-10-01 --to 2024-11-05

# Adjust confidence threshold
poetry run python main.py "Fed rate cuts" --confidence 0.85

# Increase retrieved chunks
poetry run python main.py "Climate change coverage" --top-k 30

# Skip CRAG re-ranking (faster)
poetry run python main.py "AI regulation debate" --no-crag

# JSON output for scripting
poetry run python main.py "OpenAI board crisis" --json

# Verbose agent trace
poetry run python main.py "Palestine coverage" --verbose

# Suppress progress output
poetry run python main.py "Inflation news" --quiet
```

### Full CLI Reference

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--intent` | `-i` | `auto` | Force intent class: `bias`, `timeline`, or `summary` |
| `--publishers` | `-p` | all | Comma-separated canonical publisher names to restrict retrieval |
| `--from` | | none | Start date for article filter (ISO 8601: `YYYY-MM-DD`) |
| `--to` | | none | End date for article filter (ISO 8601: `YYYY-MM-DD`) |
| `--top-k` | `-k` | `15` | Number of chunks to retrieve per Pathway query |
| `--confidence` | `-c` | `0.80` | M1 intent confidence threshold (0.0–1.0) |
| `--no-crag` | | `false` | Skip CRAG re-ranking (raw retrieval only, faster) |
| `--empirical` | | `false` | Enable real-time web search fallback even when Pathway hits threshold |
| `--json` | | `false` | Output raw JSON instead of Rich terminal display |
| `--quiet` | `-q` | `false` | Suppress progress spinners and step logs |
| `--verbose` | `-v` | `false` | Enable DEBUG-level logging and full agent trace in terminal |
| `--m1-model` | | `gpt-4o-mini` | LLM model for M1 intent translation (overrides `M1_LLM_MODEL`) |
| `--m5-model` | | `gpt-4o` | LLM model for M5 narrative generation (overrides `M5_LLM_MODEL`) |
| `--embedding-model` | | `text-embedding-3-small` | Embedding model for query vector (overrides `EMBEDDING_MODEL`) |
| `--ollama-host` | | `http://localhost:11434` | Ollama endpoint URL (overrides `OLLAMA_HOST`) |
| `--pathway-host` | | `localhost` | Pathway VectorStore host |
| `--pathway-port` | | `8765` | Pathway VectorStore port |
| `--allow-low-confidence` | | `false` | Continue with intent parse even below confidence threshold |

---

## Testing

### Test Runner

```bash
# Full suite
poetry run pytest tests/ -v

# Convenience runner
poetry run python tests/runner.py                # Unit + integration (fast, default)
poetry run python tests/runner.py --unit         # Unit tests only
poetry run python tests/runner.py --integration  # Integration tests only
poetry run python tests/runner.py --e2e          # E2E smoke tests (mocked Pathway + LLM)
poetry run python tests/runner.py --live         # Live smoke tests (requires NewsAPI + Pathway)
poetry run python tests/runner.py --all          # Everything including live E2E
poetry run python tests/runner.py --coverage     # HTML coverage report -> htmlcov/
```

### Test Suites

| Suite | Scope | Requirements |
|-------|-------|--------------|
| `tests/unit/` | Module isolation — each engine tested independently with fixture data | No network, no LLM |
| `tests/integration/` | Full pipeline flow from `IntentPayload` to `AnalysisResult` with mocked VectorStore | No network, no LLM |
| `tests/e2e/test_e2e_smoke.py` | End-to-end pipeline against pre-seeded article fixtures | No network, no LLM |
| `tests/e2e/test_live_smoke.py` | Full live pipeline with real NewsAPI + Pathway VectorStore | NewsAPI key + Pathway running |

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
newslens/
├── main.py                              # CLI entry point
├── conftest.py                          # Shared pytest fixtures
├── core/
│   ├── constants.py                     # Shared constants (PUBLISHERS, INTENT_TYPES, FRAME_TYPES)
│   ├── m0_ingestion/
│   │   ├── connectors/
│   │   │   ├── newsapi_connector.py     # pw.io NewsAPI.ai polling connector
│   │   │   ├── rss_connector.py         # pw.io RSS feedparser connector
│   │   │   └── scraper_connector.py     # Playwright async scraper (Tier-3 fallback)
│   │   ├── processors/
│   │   │   ├── normalizer.py            # HTML strip, dedup, publisher canonical mapping
│   │   │   ├── chunker.py               # 512-token semantic chunker with 64-token overlap
│   │   │   └── embedder.py              # OpenAI + local embedding wrapper with fallback
│   │   ├── vector_store.py              # Pathway VectorStoreServer setup and lifecycle
│   │   ├── document_store.py            # Pathway DocumentStore metadata layer
│   │   └── pipeline.py                  # pw.run() entrypoint — assembles full M0 DAG
│   ├── m1_intent/
│   │   ├── classifier.py                # LLM intent classifier with Pydantic validation
│   │   ├── schemas.py                   # IntentPayload, IntentType, UserQuery
│   │   └── prompts.py                   # Few-shot classification prompt templates
│   ├── m2_agents/
│   │   ├── graph.py                     # LangGraph StateGraph definition
│   │   ├── state.py                     # AgentState TypedDict
│   │   ├── supervisor.py                # Supervisor routing node
│   │   ├── timeline_agent.py            # Timeline specialist node
│   │   ├── bias_agent.py                # Bias specialist node
│   │   ├── summary_agent.py             # Summary specialist node
│   │   ├── retrieval/
│   │   │   ├── manager.py               # 4-tier autonomous retrieval + fallback cascade
│   │   │   ├── pathway_client.py        # Pathway VectorStore gRPC/HTTP client
│   │   │   ├── bing_client.py           # Bing Search API v7 client (Tier-2)
│   │   │   └── scraper_client.py        # Playwright scraper client (Tier-3)
│   │   └── crag/
│   │       ├── evaluator.py             # CRAG chunk grader (RELEVANT/AMBIGUOUS/IRRELEVANT)
│   │       ├── rewriter.py              # LLM-based query rewriter for Tier-1 retry
│   │       └── schemas.py               # CRAGGrade, GradeEnum
│   ├── m3_bias/
│   │   ├── engine.py                    # BiasEngine orchestrator
│   │   ├── sentiment.py                 # RoBERTa + VADER sentiment wrapper
│   │   ├── framing.py                   # 5-frame LLM framing vector extractor
│   │   ├── scoring.py                   # Weighted bias score formula
│   │   └── schemas.py                   # BiasAnalysisResult, PublisherBiasProfile
│   ├── m4_timeline/
│   │   ├── synthesizer.py               # TimelineSynthesizer orchestrator
│   │   ├── extractor.py                 # spaCy NER + LLM event JSON extractor
│   │   ├── deduplicator.py              # Cosine similarity event clustering
│   │   └── schemas.py                   # TimelineResult, TimelineEvent, EventConfidence
│   └── m5_ui/
│       ├── app.py                       # Streamlit main application entrypoint
│       ├── components/
│       │   ├── trace_panel.py           # Agent reasoning trace sidebar
│       │   ├── bias_heatmap.py          # Plotly publisher x sentiment heatmap
│       │   ├── timeline_view.py         # Plotly Gantt-style event timeline
│       │   ├── summary_view.py          # Cross-publisher consensus panel
│       │   └── source_cards.py          # Article cards with CRAG grade badges
│       └── session.py                   # st.session_state lifecycle management
├── schemas/                             # 11 Pydantic v2 data contract models
├── scripts/
│   ├── run_pathway_pipeline.py          # Starts M0 pw.run() background process
│   └── seed_test_data.py                # Seeds Pathway store with fixture articles
└── tests/
    ├── unit/                            # Module-level isolation tests
    ├── integration/                     # Full pipeline tests with mocked VectorStore
    ├── e2e/
    │   ├── test_e2e_smoke.py            # End-to-end smoke tests (offline fixtures)
    │   └── test_live_smoke.py           # Live pipeline smoke tests
    └── runner.py                        # Convenience runner with category flags
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
| OpenAI Chat API down | `openai.APIError` | Route to `Anthropic Claude 3.5 Haiku` |
| Both OpenAI + Anthropic down | Chained exception | Local `llama3.2:3b` via Ollama; flagged in UI |
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
