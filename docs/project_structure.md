# Project Structure

This document outlines the directory structure of the NewsLens codebase:

```text
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
│   │   ├── timeline_agent.py             # Timeline specialist agent node
│   │   ├── bias_agent.py                 # Bias specialist agent node
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
│   │       ├── evaluator.py             # CRAG chunk grader (RELEVANT/AMBIGUOUS/IRRELEVVRANT)
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
│       ├── logging.py                    # loguru structured logger setup
│       ├── exceptions.py                 # Custom exception hierarchy
│       ├── constants.py                  # Central system parameters and thresholds
│       ├── cache.py                      # In-memory resource caching layer
│       ├── retry.py                      # Resilience backoff decorator
│       ├── types.py                      # Reusable type aliases
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
