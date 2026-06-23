# Performance & Resilience

## End-to-end latency (estimates)

| Step | Module | Typical latency |
|------|--------|-----------------|
| Query intent classification | M1 | 1–3s |
| Retrieval Tier-0 (Pathway/Local) | M2 | 0.5–7s |
| CRAG chunk grading | M2 | 1–5s (per-chunk LLM calls) |
| Sentiment + framing analysis | M3 | 3–10s |
| Event extraction + timeline | M4 | 3–8s |
| Summary / explanation generation | M2/M5 | 2–8s |
| **Total (Tier-0 hit, with Gemini)** | | **~10–30s** |
| **Total (Bing fallback — Tier 2)** | | **~15–40s** |
| **Total (Scraper fallback — Tier 3)** | | **~20–60s** |

M0 ingestion runs independently (background poll or Docker `news-sync`). M2 retrieval, CRAG, and the selected specialist agent run sequentially inside LangGraph.

## Resilience matrix (implemented)

| Failure | Detection | Autonomous recovery |
|---------|-----------|---------------------|
| Pathway unreachable | HTTP error / connection timeout | → LocalRetriever (Windows) or Bing → Scraper |
| Pathway simulated failure | `SIMULATE_RETRIEVAL_FAILURES=pathway` | → Bing → Scraper (demo hook) |
| Local store empty | `chunk_count == 0` | Auto-ingest poll or demo seed on startup |
| CRAG relevance below threshold | `mean(score) < 0.72` | Query rewrite + retry → Bing → Scraper |
| Local keyword embeddings (low scores) | Tier-0 local chunks exist | Accept local results (skip false escalation) |
| Gemini primary key fails | API / quota error | → `GEMINI_API_KEY_FALLBACK` |
| Gemini embeddings fail | Embedder exception | → Keyword hash embeddings (384-dim) |
| M1 LLM unavailable | `LLMProviderUnavailableError` | → Regex intent heuristic |
| CRAG LLM unavailable | Evaluator exception | → All chunks graded `AMBIGUOUS` |
| Bing key missing / failure | `BingRetrievalError` | → Scraper tier |
| Scraper failure | `ScraperRetrievalError` | → `FallbackExhaustedError` (graph continues with empty chunks + offline agents) |
| M1 JSON parse failure | `ValidationError` | → Regex fallback → `CROSS_PUBLISHER_SUMMARY` default |

## Circuit breaker pattern

External API clients use **tenacity** exponential backoff:

- `PathwayRetriever` — 3 attempts, 1–8s wait
- `BingRetriever` — 2 attempts, 1–5s wait

Retrieval orchestration errors are swallowed per-tier in `RetrievalManager._try_retriever()` so the cascade continues.

## Demo: simulate retrieval failures

```powershell
$env:SIMULATE_RETRIEVAL_FAILURES = "pathway"
poetry run uvicorn src.m5_ui.api.server:app --port 8000
```

Check `metadata.retrieval_tier_used` and `agent_trace[].fallback_triggered` in the API response.

## Testing resilience

`tests/unit/test_retrieval_resilience.py` covers:

- Pathway → Bing → Scraper cascade
- Rewritten query propagation to Bing tier
- `LocalRetriever` acceptance with low relevance scores
- Simulated Pathway failure integration
- `SIMULATE_RETRIEVAL_FAILURES` env parsing
