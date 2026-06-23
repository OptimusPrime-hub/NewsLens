# NewsLens Overview

> Point it at any news topic, describe what you want to understand in plain English, and watch autonomous agents retrieve live articles, detect narrative bias across publishers, and draw event timelines.

NewsLens is a fully autonomous, multi-agent intelligence system built on **Pathway's streaming vector index** and **LangGraph** orchestration. Given a natural-language query (e.g., *"How did Reuters and Fox News cover the US-China trade talks differently?"*), it routes the request through a cascading agent pipeline and surfaces structured insights across three analytical dimensions:

| Dimension | Question Answered |
|-----------|-------------------|
| **Bias Detection** | How does Publisher A frame this event differently from Publisher B? |
| **Timeline Synthesis** | What is the chronological sequence of this unfolding story? |
| **Cross-Publisher Summary** | What is the ground-truth consensus across all sources? |

## Core thesis

Every quality signal (sentiment score, framing vector, bias magnitude, confidence band) is produced by transformer models, deterministic scoring rules, and literature-backed algorithms. LLMs are architecturally bounded to **query understanding** (M1), **CRAG grading** (M2), **framing extraction** (M3), and **narrative explanation** (M5) — numeric bias scores are never hallucinated.

## Key features

| Feature | Description |
|---------|-------------|
| **Live index** | Pathway VectorStore watches `data/pathway_sources/*.json` and serves fresh embeddings (Docker/Linux) |
| **Windows dev path** | `LocalRetriever` + in-process ingestion store with demo seed data |
| **Autonomous fallback** | 4-tier retrieval cascade (Pathway/Local → Query Rewrite → Bing → Scraper) |
| **CRAG grading** | Every chunk graded RELEVANT / AMBIGUOUS / IRRELEVANT before generation |
| **Bias score formula** | `BiasScore = w1·ΔSentiment + w2·JSD(framing) + w3·ΔSalience`, signed and bounded [-1, +1] |
| **5-frame framing** | CONFLICT / ECONOMIC / HUMAN_INTEREST / MORALITY / RESPONSIBILITY vectors per publisher |
| **Event confidence tiers** | Timeline events tagged HIGH (3+ sources), MEDIUM (2), LOW (1), UNVERIFIED |
| **Agent trace transparency** | Every LangGraph step surfaced in the web UI trace panel |
| **Gemini key failover** | Primary + `GEMINI_API_KEY_FALLBACK` with LangChain `.with_fallbacks()` |
| **Publisher normalization** | Canonical publisher mapping across RSS, NewsAPI, and scraped sources |

## Design principles

1. **Live data over static snapshots** — Pathway index refreshes as new JSON articles land; no manual re-indexing in production.
2. **Autonomous resilience** — The agent pipeline escalates retrieval tiers without human intervention.
3. **Bounded LLM use** — Scores and rankings come from models + formulas; LLMs handle language, not arithmetic invention.
4. **CRAG-first retrieval** — Irrelevant chunks are filtered before they reach specialist agents.
5. **Trace-first transparency** — Every reasoning step is captured in `agent_trace` and replayable in the UI.
6. **Strict modularity** — Pydantic v2 contracts between M0–M5; modules are independently replaceable.

## Query intent taxonomy

| Intent Class | Example Queries | Specialist Agent | Output |
|---|---|---|---|
| **`BIAS_DETECTION`** | *"How did BBC vs Fox cover X?"* · *"Sentiment toward Y in CNN"* | Bias Agent → M3 | Publisher profiles, divergence matrix, framing radar |
| **`TIMELINE`** | *"Timeline of the SVB collapse"* · *"Sequence of events in the Gaza war"* | Timeline Agent → M4 | Chronological events, source attribution, gap flags |
| **`CROSS_PUBLISHER_SUMMARY`** | *"What is happening with X?"* · *"Summarize last week's coverage of Y"* | Summary Agent | Consensus text, key takeaways |

Queries below confidence **0.80** are routed to `CROSS_PUBLISHER_SUMMARY` — the safest default — without failing.

## Challenge compliance (Inter IIT 13.0)

| Requirement | Implementation |
|-------------|----------------|
| Pathway VectorStore index | `build_pathway_vector_server()` + `docker-compose.yml` |
| Windows + Pathway | Docker (`docker compose up`) |
| Agentic RAG + CRAG | LangGraph + `LLMCRAGEvaluator` |
| API failure resilience | 4-tier cascade + `SIMULATE_RETRIEVAL_FAILURES` |
| UI transparency | Agent trace panel in M5 web UI |
| Reproducible setup | [deployment_guide.md](deployment_guide.md) + Docker |

See also: [modules.md](modules.md) · [architecture.md](architecture.md)
