# NewsLens — Dynamic Agentic RAG News Analysis & Bias Detection Platform

> Point it at any news topic, describe what you want to understand in plain English, and watch autonomous agents retrieve live articles, detect narrative bias across publishers, and draw event timelines — before you've even opened a browser tab.

NewsLens is a fully autonomous, multi-agent intelligence system built on Pathway's real-time streaming framework. Given a natural-language query (e.g., *"How did Reuters and Fox News cover the US-China trade talks differently?"*), it routes the request through a cascading agent pipeline, retrieves live news from a continuously updated vector index, and surfaces structured insights across three analytical dimensions — bias detection, timeline synthesis, and cross-publisher summarization.

**Core thesis:** Every quality signal (sentiment score, framing vector, bias magnitude, confidence band) is produced by transformer models, deterministic scoring rules, and literature-backed algorithms. LLMs are architecturally bounded to query understanding (M1) and narrative explanation (M5) — they never hallucinate scores.

---

## Architecture

NewsLens is built as a modular six-module pipeline. Each module communicates through strictly typed Pydantic v2 data contracts:

| Module | Name | Role | LLM? |
|---|---|---|---|
| **M0** | Live News Ingestion | Connects RSS and NewsAPI.org connectors, normalizes articles, chunks text, embeds with Gemini, and serves a continuously fresh Pathway `VectorStore` + `DocumentStore` | No |
| **M1** | Query Intent Translator | Converts plain-English query into a structured `IntentPayload` (intent class, entities, publishers, date range) with Pydantic v2 strict validation and graceful fallback | Yes |
| **M2** | Multi-Agent Router & Retrieval Manager | Routes `IntentPayload` to specialist agents via a LangGraph state machine; manages autonomous 4-tier retrieval fallback cascade and CRAG re-ranking | Partial |
| **M3** | Bias & Sentiment Engine | Runs VADER (default) / RoBERTa sentiment per publisher, LLM framing vector extraction, and a weighted bias score formula — all numeric outputs are deterministic | Partial |
| **M4** | Timeline Synthesizer | Extracts temporally anchored events via LLM JSON pass, deduplicates by cosine similarity, and produces a source-attributed chronological timeline | Partial |
| **M5** | Explanation & UI Engine | Browser-based web interface served by FastAPI — HTML templates, Vanilla CSS, Vanilla JS, Chart.js visualizations; exposes `POST /api/analyze` REST endpoint consumed by the frontend | Yes |

### Agent Pipeline & Execution Flow

```text
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
   │  ┌──────────┐ ┌──────────┐ ┌─────────┐  │
   │  │ Timeline │ │  Bias    │ │ Summary │  │
   │  │  Agent   │ │  Agent   │ │  Agent  │  │
   │  └──────────┘ └──────────┘ └─────────┘  │
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

Pathway `VectorStore` is the shared retrieval backbone, queried by M2 with live-updated embeddings. M0 runs as a continuously executing `pw.run()` process in the background, so every query hits a fresh index.

---

## Key Features

| Feature | Description |
|---|---|
| **Live index** | Pathway's incremental computation engine keeps the vector index fresh within 60 seconds of article publication — no manual refresh |
| **Autonomous fallback** | 4-tier retrieval cascade (Pathway/Local → Query Rewrite → Tavily AI Search → RSS BeautifulSoup Scraper) — the agent decides when to escalate, no human intervention |
| **CRAG grading** | Every retrieved chunk is graded RELEVANT / AMBIGUOUS / IRRELEVANT; only high-confidence chunks reach generation |
| **Bias score formula** | $BiasScore = w1 \cdot \Delta Sentiment + w2 \cdot FramingDivergence + w3 \cdot \Delta EntitySalience$, normalized to $[-1, +1]$ |
| **5-frame framing analysis** | LLM classifies publisher narrative into `CONFLICT` / `ECONOMIC` / `HUMAN_INTEREST` / `MORALITY` / `RESPONSIBILITY` frames |
| **Event confidence tiers** | Timeline events tagged `HIGH` (3+ sources), `MEDIUM` (2), `LOW` (1 corroborated), `UNVERIFIED` (1 uncorroborated) |
| **Agent trace transparency** | Every LangGraph node step — intent, routing, retrieval tier, CRAG grades, generation — is surfaced live in the web UI trace panel |
| **Bounded LLM use** | LLMs appear only in M1 (intent parsing) and M5 (narrative explanation); sentiment, bias, and timeline scores are model-computed |
| **Publisher normalization** | Canonical publisher name mapping across RSS, NewsAPI, and web sources eliminates duplicate publisher identities |
| **Offline embedding fallback** | Seamlessly switches from Gemini `text-embedding-004` to offline local word hashing when API is unavailable |

---

## Query Intent Taxonomy

NewsLens natively classifies every query into one of three analytical intents, each routed to a specialist agent:

| Intent Class | Example Queries | Specialist Agent | Output |
|---|---|---|---|
| **`BIAS_DETECTION`** | *"How did BBC vs Fox cover X?"* · *"Sentiment toward Y in CNN"* · *"Which publisher is most alarmist on Z?"* | Bias Agent | Publisher bias profiles, pairwise divergence matrix, framing radar |
| **`TIMELINE`** | *"Timeline of the SVB collapse"* · *"Sequence of events in the Gaza war"* · *"What happened first in the OpenAI board crisis?"* | Timeline Agent | Chronological event list, source attribution, temporal gap flags |
| **`CROSS_PUBLISHER_SUMMARY`** | *"What is happening with X?"* · *"Summarize last week's coverage of Y"* · *"What do all sources agree on about Z?"* | Summary Agent | Consensus summary, confidence score, divergence warnings |

Queries that fall below a confidence threshold of **0.80** are automatically routed to `CROSS_PUBLISHER_SUMMARY` — the safest, most general intent — without failing.

---

## Design Principles

1. **Live data over static snapshots** — Pathway's incremental computation engine keeps the vector index fresh within 60 seconds; no scheduled batch jobs, no manual re-indexing.
2. **Autonomous resilience** — The agent pipeline decides when to escalate retrieval tiers; every failure has a defined autonomous recovery path.
3. **Bounded LLM use** — LLMs appear only for language understanding (M1) and narrative explanation (M5); all scores are produced by transformer models and deterministic formulas.
4. **CRAG-first retrieval** — Every retrieved chunk is graded for relevance before it touches generation; ambiguous and irrelevant chunks are filtered out, not papered over.
5. **Trace-first transparency** — Every reasoning step is captured in `AgentState.agent_trace` and surfaced in the UI; the system never produces a result that cannot be audited.
6. **Strict modularity** — Every module communicates through Pydantic v2 data contracts; internals are independently replaceable without touching adjacent modules.

---

## Uniqueness vs Existing Solutions

| Capability | AllSides | Ground News | Media Bias Fact Check | **NewsLens** |
|---|---|---|---|---|
| Real-time live news | ❌ Static database | ❌ Curated daily | ❌ Manual updates | ✅ Pathway live index (~60s freshness) |
| Agentic retrieval | ❌ None | ❌ None | ❌ None | ✅ LangGraph 4-tier CRAG cascade |
| Per-query bias analysis | ❌ Pre-assigned ratings | ✅ Per-article | ❌ Source-level only | ✅ Per-query, per-publisher, quantified |
| Quantified bias formula | ❌ Qualitative labels | ❌ Qualitative | ❌ Qualitative | ✅ `w1·ΔSentiment + w2·FramingDiv + w3·ΔEntitySalience` |
| Narrative framing analysis | ❌ None | ❌ None | ❌ None | ✅ 5-frame IPTC-inspired classifier |
| Timeline synthesis | ❌ None | ❌ None | ❌ None | ✅ Multi-source chronological event extraction |
| Autonomous fallback | ❌ None | ❌ None | ❌ None | ✅ 3-tier autonomous recovery (Tavily → Scraper) |
| Source attribution | ❌ Source-level | ✅ Article links | ✅ Source labels | ✅ Chunk-level with CRAG grade + retrieval tier |
| Open / auditable scores | ❌ Proprietary | ❌ Opaque | ❌ Proprietary | ✅ Deterministic formula, auditable trace |

---

## Authors

- **Shreyansh Verma** — Inter-IIT Tech Meet 13.0 | Pathway Problem Statement
