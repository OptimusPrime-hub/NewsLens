# API Reference

This document outlines the API endpoints exposed by the NewsLens M5 UI and API server.

## Base URL
When running locally, the API server is available at:
`http://127.0.0.1:8000`

---

## 1. HTML Views

### Search Landing Page
* **Endpoint:** `GET /`
* **Description:** Serves the main landing page containing the query input and the live pipeline progress overlay.

### Results Page
* **Endpoint:** `GET /results`
* **Description:** Serves the dashboard showing the event timeline, summary, bias analysis charts, and retrieved source attributions.

### About Page
* **Endpoint:** `GET /about`
* **Description:** Serves the static page describing the project's background and architecture.

---

## 2. API Endpoints

### Health Check
* **Endpoint:** `GET /api/health`
* **Description:** Liveness probe to check the backend service status.
* **Response (JSON):**
  ```json
  {
    "status": "ok",
    "timestamp": "2026-06-23T02:40:43+05:30"
  }
  ```

---

### Synchronous News Analysis
* **Endpoint:** `POST /api/analyze`
* **Request Content-Type:** `application/json`
* **Request Body:**
  ```json
  {
    "query": "trade tariffs trump"
  }
  ```
* **Response Content-Type:** `application/json`
* **Response Body (`AnalysisResult`):**
  ```json
  {
    "intent": "CROSS_PUBLISHER_SUMMARY",
    "raw_query": "trade tariffs trump",
    "overall_confidence": 0.83,
    "warnings": [],
    "metadata": {
      "session_id": "8b584d43-238d-4e92-8051-403bdf8faea3",
      "query_timestamp": "2026-06-23T02:40:43Z",
      "total_latency_ms": 3450,
      "retrieval_tier_used": "local",
      "total_chunks_retrieved": 5,
      "total_chunks_used": 5,
      "model_versions": {
        "primary": "gemini-1.5-flash"
      }
    },
    "agent_trace": [
      {
        "step_index": 0,
        "node_name": "supervisor",
        "action": "Route to CROSS_PUBLISHER_SUMMARY pipeline",
        "input_summary": "Query: trade tariffs trump",
        "output_summary": "Intent: CROSS_PUBLISHER_SUMMARY (conf=0.50)",
        "latency_ms": 0,
        "fallback_triggered": false,
        "fallback_tier": null,
        "timestamp": "2026-06-23T02:40:43Z"
      }
    ],
    "summary_result": {
      "summary_text": "Offline Heuristic Summary...",
      "consensus_points": ["Consensus point 1"],
      "key_takeaways": ["Takeaway 1"]
    },
    "timeline_result": null,
    "bias_result": null
  }
  ```

---

### Streaming News Analysis (SSE)
* **Endpoint:** `POST /api/analyze/stream`
* **Request Content-Type:** `application/json`
* **Request Body:**
  ```json
  {
    "query": "timeline of trade tariffs trump"
  }
  ```
* **Response Content-Type:** `text/event-stream`
* **Streaming Protocol:** Server-Sent Events (SSE).
* **SSE Event Types:**
  1. `progress`: Emitted as the pipeline moves through classification, retrieval, CRAG, and agent execution.
  2. `result`: Emitted once the full `AnalysisResult` is compiled.
  3. `error`: Emitted if the pipeline encounters a fatal exception.

* **Example Stream Output:**
  ```text
  event: progress
  data: {"step": 1, "message": "Classifying query intent…"}

  event: progress
  data: {"step": 1, "message": "Intent: TIMELINE (confidence 50%)", "done": true}

  event: progress
  data: {"step": 2, "message": "Retrieving live articles…"}

  event: progress
  data: {"step": 3, "message": "CRAG relevance filtering…"}

  event: progress
  data: {"step": 4, "message": "Running Timeline Synthesizer…"}

  event: progress
  data: {"step": 2, "message": "Retrieved 15 chunks (15 used after CRAG)", "done": true}

  event: progress
  data: {"step": 3, "message": "CRAG accepted 15/15 chunks", "done": true}

  event: progress
  data: {"step": 4, "message": "Timeline Synthesizer completed", "done": true}

  event: result
  data: { ... AnalysisResult JSON ... }
  ```

---

## 3. `retrieval_tier_used` values

| Value | Meaning |
|-------|---------|
| `pathway` | Pathway VectorStoreServer (Docker/Linux) |
| `local` | In-process demo/live store via `LocalRetriever` (Windows dev) |
| `bing` | Bing Search API v7 fallback |
| `scraper` | Google News RSS + web scraper fallback |
| `none` | All tiers failed |

Simulate tier failures for demos: set `SIMULATE_RETRIEVAL_FAILURES=pathway` in `.env`.
