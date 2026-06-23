# Technology Stack

Current implementation as of June 2026. For design-target vs implemented gaps, see [architecture.md](architecture.md) §11.

## Core stack

| Layer | Technology | Notes |
|-------|------------|-------|
| **Index** | Pathway VectorStoreServer | Linux/Docker via `run_pathway_pipeline.py` |
| **Dev index** | In-process `IngestionPipeline` | Windows via `LocalRetriever` |
| **Orchestration** | LangGraph ≥0.2 | `src/m2_agents/graph.py` |
| **Primary LLM** | Gemini `gemini-1.5-flash` | M1, M2 CRAG, M3 framing, M5 narrative |
| **LLM failover** | `GEMINI_API_KEY_FALLBACK` | LangChain `.with_fallbacks()` |
| **M1 offline** | Regex heuristic | When Gemini unavailable |
| **Embeddings** | Gemini `text-embedding-004` | M0 + Pathway server |
| **Embedding fallback** | Keyword hash (384-dim) | When Gemini embed fails |
| **Sentiment** | VADER (default) | `src/m3_bias/sentiment.py` |
| **Sentiment optional** | RoBERTa via transformers | `use_fallback_only=False` |
| **NER / entities** | spaCy `en_core_web_sm` + regex | Bias salience, timeline extraction |
| **News primary** | NewsAPI.org + RSS | `newsapi_connector.py`, `rss_connector.py` |
| **Search fallback** | Bing Search API v7 | Tier 2 |
| **Scraper fallback** | httpx + BeautifulSoup | Google News RSS URL discovery |
| **HTTP / retry** | httpx + tenacity | All external API clients |
| **Validation** | Pydantic v2 | All module contracts |
| **UI** | FastAPI + Jinja2 + vanilla JS | Chart.js for bias/timeline charts |
| **Config** | pydantic-settings + `.env` | `src/shared/config.py` |
| **Logging** | loguru | Structured agent/session logs |
| **Testing** | pytest + pytest-asyncio | 34 tests (unit + contract) |

## Platform notes

| OS | Pathway | Primary retriever |
|----|---------|-------------------|
| Linux / macOS | Native (`poetry install`) | `PathwayRetriever` |
| Windows | Docker only (challenge rule) | `LocalRetriever` for native dev |

Pathway is excluded from Windows Poetry install: `pathway = { markers = "platform_system != 'Windows'" }` in `pyproject.toml`.

## Prompt locations

All shared LLM prompts live in `src/shared/prompts/`:

- `crag.py` — CRAG relevance grading
- `summary.py` — cross-publisher summary
- `timeline.py` — timeline event preparation
- `framing.py` — 5-frame narrative extraction
- `explanation.py` — bias narrative explanation
- `intent.py` — (reference; M1 uses `m1_intent/prompts.py`)

M2-specific rewrite prompts: `src/m2_agents/prompts/rewrite.py`
