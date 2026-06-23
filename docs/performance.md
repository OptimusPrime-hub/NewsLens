# Performance & Resilience

This document details the actual latency estimations and resilience mechanisms implemented in NewsLens.

---

## End-to-End Latency Estimates

| Step | Module | Typical Latency | Notes |
|---|---|---|---|
| Query intent classification | M1 | 1–3s | Gemini chat model call |
| Pathway VectorStore retrieval (Tier-0) | M2 | 0.5–2s | In-process or Pathway HTTP call |
| CRAG chunk grading | M2 | 1–3s | In-parallel relevance evaluation |
| Sentiment + framing analysis | M3 | 3–8s | Evaluates sentiment and extracts narrative framing vectors |
| Event extraction + timeline construction | M4 | 3–6s | Deduplicates and builds timeline chronology |
| Narrative explanation generation | M5 | 2–5s | Builds consensus / divergence narrative text |
| **Total (standard mode — Tier-0 hit)** | | **~10–27s** | Complete standard pipeline execution |
| **Total (Tavily fallback — Tier-2)** | | **~15–40s** | Slower due to Tavily web search queries |
| **Total (Scraper fallback — Tier-3)** | | **~20–60s** | Includes URL discovery and HTML fetching |

*Note: M1 and M0 (background pipeline) are independent. M2 retrieval, M3, and M4 run sequentially within the LangGraph state machine. Pathway index freshness is maintained independently at a 30–60s polling cadence — queries always hit a live index, adding zero extra latency.*

---

## Resilience & Fallback Matrix

| Failure | Detection | Autonomous Recovery |
|---|---|---|
| **NewsAPI.org rate limit / down** | `HTTP 429/503` + 3x exponential backoff | Automatically falls back to RSS feed connector polling. |
| **Pathway VectorStore unreachable** | Connection timeout | Switches to `LocalRetriever` (Windows dev) or escalates retrieval to Tavily AI Search. |
| **CRAG relevance below threshold** | `mean(relevance_scores) < 0.72` | Query rewrite (Tier-1) → Tavily AI Search (Tier-2) → Google News RSS Scraper (Tier-3). |
| **Gemini Embedding API down** | Exception on embedding call | Automatically switches to in-memory 384-dim word-hash keyword embeddings. |
| **Gemini Chat API down** | Exception on chat model call | Falls back to offline regex query classification and VADER sentiment analyzer. |
| **LLM JSON parse failure (M1)** | `pydantic.ValidationError` | Regex extraction fallback; if that fails, defaults to `CROSS_PUBLISHER_SUMMARY` class. |
| **LangGraph max iterations exceeded** | `iteration_count > max_agent_iterations` | Returns partial result compiled so far with warnings in agent trace. |
