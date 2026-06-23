# Module Architecture (M0–M5)

NewsLens is a modular six-module pipeline. Each module communicates through strictly typed Pydantic v2 data contracts.

## Module table

| Module | Name | Role | LLM? |
|--------|------|------|-------|
| **M0** | Live News Ingestion | Poll NewsAPI/RSS, normalize, chunk, embed; feed Pathway JSON or in-process store | Embeddings only |
| **M1** | Query Intent Translator | Plain-English query → `IntentPayload` with validation + regex fallback | Yes |
| **M2** | Multi-Agent Router | LangGraph orchestration, 4-tier retrieval, CRAG grading | Partial |
| **M3** | Bias & Sentiment Engine | VADER/RoBERTa sentiment, LLM framing, deterministic bias scores | Partial |
| **M4** | Timeline Synthesizer | spaCy NER + LLM event extraction, deduplication, chronological output | Partial |
| **M5** | Explanation & UI | FastAPI + Jinja2 + vanilla JS; `POST /api/analyze` | Yes |

## Pipeline diagram

```
Natural Language Query
         │
         ▼
   [M1] Intent Translator  →  IntentPayload
         │
         ▼
   [M2] LangGraph Pipeline
   ┌─────────────────────────────────────────┐
   │  supervisor → retrieve → crag_evaluate  │
   │       ↓                                 │
   │  route_by_intent                        │
   │    ├─ bias_agent    → M3 BiasEngine     │
   │    ├─ timeline_agent → M4 Synthesizer │
   │    └─ summary_agent                     │
   │       ↓                                 │
   │  validate → assemble_result             │
   └─────────────────────────────────────────┘
         │
         ▼
   [M5] FastAPI UI  →  Browser / REST client
```

Retrieval and CRAG run **once** per query — specialist agents share pre-filtered `relevant_chunks`.

## M2 LangGraph topology

```
START → supervisor → retrieve → crag_evaluate
              ↓
    route_by_intent ──→ bias_agent
                   ──→ timeline_agent
                   ──→ summary_agent
              ↓
         validate → assemble_result → END
```

Source: `src/m2_agents/graph.py`

## Retrieval cascade

| Tier | Client | Trigger |
|------|--------|---------|
| 0 | `PathwayRetriever` (Linux/Docker) or `LocalRetriever` (Windows) | Always first |
| 1 | `QueryRewriter` + Tier-0 retry | Mean relevance < `CRAG_RELEVANCE_THRESHOLD` |
| 2 | `BingRetriever` | Tier 0/1 insufficient |
| 3 | `ScraperRetriever` | Last resort (Google News RSS + BeautifulSoup) |

Simulate failures: `SIMULATE_RETRIEVAL_FAILURES=pathway,bing,scraper`

## Data indexing paths

**Production (Docker/Linux):**

```
sync_news_sources.py  →  data/pathway_sources/*.json
run_pathway_pipeline.py  →  Pathway VectorStoreServer :8765
PathwayRetriever  →  POST /v1/retrieve
```

**Windows development:**

```
seed_demo_data.py  →  IngestionPipeline in-memory store
LocalRetriever  →  cosine similarity search
```

See [architecture.md](architecture.md) §11 for implementation status and [deployment_guide.md](deployment_guide.md) for run commands.
