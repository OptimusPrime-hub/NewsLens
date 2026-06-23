# Data Contracts

All inter-module communication uses strictly typed Pydantic v2 models defined under `src/*/schemas.py`.

## Contract reference

| Contract | Flow | Description |
|----------|------|-------------|
| `AnalyzeRequest` | M5 → M1/M2 | API request: query, optional publishers, date range, top_k |
| `IntentPayload` | M1 → M2 | Intent type, entities, publishers, date range, topic keywords, confidence |
| `RetrievedChunk` | M0/retrieval → M2 | chunk text, publisher, publish_ts, relevance_score, source_url |
| `CRAGGrade` | M2 CRAG → M2 graph | Per-chunk RELEVANT / AMBIGUOUS / IRRELEVANT + reason |
| `AgentState` | LangGraph nodes | intent, chunks, crag grades, specialist results, trace, errors |
| `BiasAnalysisResult` | M3 → M2 → M5 | Publisher profiles, pairwise divergence matrix, explanation |
| `TimelineResult` | M4 → M2 → M5 | Sorted events, gap flags, coherence score |
| `SummaryResult` | M2 → M5 | summary_text, consensus_points, key_takeaways |
| `AnalysisResult` | M2 → M5 | Top-level wrapper: intent, conditional payloads, trace, metadata |
| `AnalysisMetadata` | M2 → M5 | session_id, latency, retrieval_tier_used, chunk counts, models |
| `TraceEntry` | M2 → M5 | Per-node step_index, action, latency_ms, fallback_tier |

## `retrieval_tier_used` values

| Value | Meaning |
|-------|---------|
| `pathway` | Pathway VectorStoreServer (Docker/Linux) |
| `local` | In-process store via `LocalRetriever` (Windows dev) |
| `bing` | Bing Search API v7 fallback |
| `scraper` | Web scraper fallback |
| `none` | All tiers failed |

## Agent trace

Every `AnalysisResult` includes `agent_trace: list[TraceEntry]`. The M5 UI replays:

- Intent classification and routing
- Retrieval tier used and fallback flags
- CRAG accept/reject counts
- Specialist agent completion
- Validation and assembly steps

Example fields on `TraceEntry`:

```python
step_index: int
node_name: str          # e.g. "retrieve", "crag_evaluate", "bias_agent"
action: str
input_summary: str
output_summary: str
latency_ms: int
fallback_triggered: bool
fallback_tier: int | None   # 0=pathway/local, 2=bing, 3=scraper
timestamp: datetime
```

## Contract tests

Schema round-trips are verified in `tests/contract/test_m0_contracts.py` through `test_m4_contracts.py`.

See [api_reference.md](api_reference.md) for REST request/response examples.
