# Data Contracts

All inter-module communication uses strictly typed Pydantic v2 models:

| Contract | Flow | Description |
|---|---|---|
| **`AnalyzeRequest`** | M5 → M1/M2 | API request containing query, optional publishers, date range filters, and `top_k` overrides |
| **`IntentPayload`** | M1 → M2 | Classified intent type, extracted entities, publishers, date range, topic keywords, and confidence |
| **`RetrievedChunk`** | Pathway/API → M2 | Chunk text, publisher, publish timestamp, and cosine relevance score |
| **`CRAGGrade`** | M2 CRAG → M2 Graph | Per-chunk grading (`RELEVANT` / `AMBIGUOUS` / `IRRELEVANT`) with LLM reason |
| **`AgentState`** | M2 Nodes (LangGraph) | Shared state containing intent, chunks, crag grades, specialist results, error logs, and trace |
| **`BiasAnalysisResult`** | M3 → M2 → M5 | Publisher profiles (sentiment, framing, entity salience, bias score) and divergence matrix |
| **`TimelineResult`** | M4 → M2 → M5 | Sorted chronological events, temporal gap flags, and narrative coherence score |
| **`SummaryResult`** | M2 Summary Agent → M5 | Consensus text, consensus points, and key takeaways |
| **`AnalysisResult`** | M2 → M5 | Top-level response wrapper: intent, conditional result payload, agent trace, metadata, and warnings |
| **`AnalysisMetadata`** | M2 → M5 | Query session ID, timestamp, latency, retrieval tier used, chunk counts, and model versions |

Every `AnalysisResult` carries a full `agent_trace: list[TraceEntry]` so the web UI can replay every reasoning step the pipeline took.
