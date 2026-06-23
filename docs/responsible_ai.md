# Responsible AI Practices

This document describes the guardrails and responsible AI design decisions implemented in NewsLens.

---

## 1. LLM Scope Limitation (Bounded Use)

The most significant responsible AI decision in NewsLens is **bounding LLM usage to the minimum necessary surface**:

| Module | LLM role | Guardrail |
|---|---|---|
| **M1** Intent Classifier | Parses query intent into structured `IntentPayload` | Pydantic v2 strict validation rejects malformed output; regex fallback if LLM fails |
| **M3** Bias Engine | Generates narrative framing explanation text | LLM never produces numeric scores — all numbers come from VADER/RoBERTa + deterministic formula |
| **M4** Timeline | Extracts event JSON from article text | JSON schema validation with fallback to regex extraction if parse fails |
| **M5** Explanation | Writes the consensus narrative summary | Clearly labelled as "generated explanation" in the UI |

**LLMs never produce bias scores, sentiment scores, or relevance scores.** These are computed by deterministic algorithms (VADER, cosine similarity, framing formula), making them auditable and reproducible.

---

## 2. Source Attribution

Every result exposes full provenance:

- Each `RetrievedChunk` carries `source_url`, `publisher`, and `publish_ts`
- The `agent_trace` records which retrieval tier was used and which CRAG grade each chunk received
- The UI shows `retrieval_tier_used` as a badge on every result ("Pathway", "Tavily", or "Scraper")
- Timeline events carry `article_references` with direct links to original sources

Users can always trace a claim back to a specific article and publisher.

---

## 3. CRAG Relevance Filtering (Hallucination Reduction)

Before any retrieved chunk reaches a generation step:

1. Each chunk is graded `RELEVANT` / `AMBIGUOUS` / `IRRELEVANT` by the CRAG evaluator
2. Only `RELEVANT` chunks are passed to the Bias, Timeline, and Summary agents
3. The `crag_relevance_threshold` (default `0.72`) is configurable — it can be raised for higher precision or lowered for higher recall

This prevents the LLM from generating summaries or bias profiles based on off-topic content.

---

## 4. Confidence Transparency

All outputs include explicit uncertainty signals:

| Output | Uncertainty signal |
|---|---|
| **Bias score** | Normalized `[-1, +1]`; values near 0 indicate low divergence, not certainty of neutrality |
| **Timeline events** | Confidence tier: `HIGH` (3+ corroborating sources), `MEDIUM` (2), `LOW` (1 verified), `UNVERIFIED` (1 unverified) |
| **Intent classification** | `confidence` field on `IntentPayload`; queries below `0.80` threshold default to `CROSS_PUBLISHER_SUMMARY` |
| **Agent trace** | Every step's latency, tier used, and chunk count is visible in the UI trace panel |

---

## 5. No Personalization or User Profiling

NewsLens does not:
- Store user queries or session data
- Build user profiles or filter bubbles
- Personalize results based on past queries

Every query is stateless and receives the same objective analysis.

---

## 6. Publisher Neutrality

The bias engine measures divergence between publishers — it does not label any publisher as "biased" in absolute terms. The `BiasScore` is a relative measure of divergence from the cross-publisher mean. This prevents the system from acting as an arbiter of ground truth.

---

## 7. Failure Transparency

When the system falls back to a lower retrieval tier, the UI explicitly shows which tier was used:
- `retrieval_tier_used: "tavily"` signals live web search was used (not Pathway's live index)
- `retrieval_tier_used: "scraper"` signals last-resort scraping was used

Users can factor retrieval quality into their trust of the results.
