# Project Structure

```
newslens/
├── main.py                         # CLI entry (M1 + in-process pipeline demo)
├── Dockerfile                      # Production image
├── docker-compose.yml              # pathway + news-sync + web
├── pyproject.toml                  # Poetry deps (Pathway excluded on Windows)
├── .env.example                    # Safe config template (no secrets)
│
├── scripts/
│   ├── run_local.ps1               # Windows one-command dev start
│   ├── seed_demo_data.py           # CLI wrapper for demo article seeding
│   ├── sync_news_sources.py        # Poll NewsAPI/RSS → JSON for Pathway
│   ├── run_pathway_pipeline.py     # Pathway VectorStoreServer
│   ├── run_website.ps1 / .sh / .bat
│   ├── install.ps1 / install.sh
│
├── data/
│   └── pathway_sources/            # JSON articles watched by Pathway (gitignored content)
│
├── src/
│   ├── m0_ingestion/
│   │   ├── connectors/             # newsapi_connector, rss_connector
│   │   ├── processors/             # normalizer, chunker, embedder
│   │   ├── demo_data.py            # Demo US–China trade articles
│   │   ├── pipeline.py             # In-process ingestion + similarity search
│   │   ├── vector_store.py         # build_pathway_vector_server()
│   │   └── document_store.py       # In-memory article metadata
│   │
│   ├── m1_intent/
│   │   ├── classifier.py           # Gemini structured output + regex fallback
│   │   ├── schemas.py              # IntentType, IntentPayload
│   │   └── prompts.py
│   │
│   ├── m2_agents/
│   │   ├── graph.py                # LangGraph StateGraph
│   │   ├── supervisor.py           # Intent routing node
│   │   ├── bias_agent.py           # Delegates to M3 BiasEngine
│   │   ├── timeline_agent.py       # Delegates to M4 Synthesizer
│   │   ├── summary_agent.py        # Cross-publisher summary generation
│   │   ├── assembler.py / validators.py
│   │   ├── retrieval/
│   │   │   ├── manager.py          # 4-tier fallback orchestrator
│   │   │   ├── pathway_client.py   # Pathway VectorStore HTTP client
│   │   │   ├── local_client.py     # In-process store (Windows)
│   │   │   ├── bing_client.py      # Bing Search API v7
│   │   │   ├── scraper_client.py   # httpx + BeautifulSoup
│   │   │   ├── failure_simulation.py
│   │   │   └── runtime.py          # Platform / Pathway detection
│   │   └── crag/
│   │       ├── evaluator.py        # LLMCRAGEvaluator
│   │       └── rewriter.py         # Query rewrite for Tier 1
│   │
│   ├── m3_bias/                    # BiasEngine, sentiment, framing, scoring
│   ├── m4_timeline/                # TimelineSynthesizer, extractor, deduplicator
│   │
│   ├── m5_ui/
│   │   ├── api/                    # server.py, routes.py, schemas.py
│   │   ├── templates/              # index, results, about
│   │   └── static/                 # css/, js/ (Chart.js visualizations)
│   │
│   └── shared/
│       ├── config.py               # AppSettings + gemini_api_keys
│       ├── llm_factory.py          # Gemini + fallback key chain
│       ├── exceptions.py / logging.py / cache.py
│       └── prompts/                # Shared LLM prompt templates
│
├── docs/
│   ├── overview.md                 # Product overview + design principles
│   ├── modules.md                  # M0–M5 module breakdown
│   ├── data_contracts.md            # Pydantic contract reference
│   ├── tech_stack.md               # This file's companion
│   ├── project_structure.md        # Repository layout
│   ├── performance.md              # Latency + resilience tables
│   ├── deployment_guide.md         # How to run (authoritative)
│   ├── architecture.md             # Full design specification
│   └── api_reference.md            # REST API docs
│
└── tests/
    ├── unit/                       # retrieval resilience, M1/M3/M4
    ├── contract/                   # M0–M4 schema contracts
    └── fixtures/                   # sample_articles.json, mock NewsAPI
```

## Key entry points

| Goal | Command / file |
|------|----------------|
| Windows dev UI | `.\scripts\run_local.ps1` |
| Docker full stack | `docker compose up --build` |
| Pathway server only | `poetry run python scripts/run_pathway_pipeline.py` |
| Seed demo articles | `poetry run python scripts/seed_demo_data.py` |
| Run tests | `poetry run pytest tests/ -v` |
