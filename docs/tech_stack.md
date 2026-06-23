# Technology Stack

This document defines the actual technology stack implemented in the NewsLens repository.

| Layer | Technology | Status / Role |
|---|---|---|
| **Streaming Runtime** | `pathway >=0.31.0` | Linux/Docker ingestion, real-time incremental vector index. |
| **Agent Orchestration** | `langgraph >=0.2.0` | Stateful multi-agent graphs with conditional intent routing. |
| **Primary LLM** | Google Gemini `gemini-1.5-flash` | Used for M1 intent classification, M2 CRAG, M3 framing, and M5 narrative explanation. |
| **LLM Key Failover** | `GEMINI_API_KEY_FALLBACK` | Configured via LangChain's `.with_fallbacks()` for seamless failover when key quota fails. |
| **M1 Offline Fallback** | Regex intent heuristics | In-memory query pattern matching when LLMs/APIs are completely down. |
| **Embeddings (Primary)** | Google Gemini `text-embedding-004` | 768-dimensional dense vector embeddings. |
| **Embeddings (Fallback)** | In-memory word hashing | 384-dimensional keyword vector generator (fully offline, zero ML dependencies). |
| **Sentiment Analysis** | VADER (`vaderSentiment`) | Default, lightweight news sentiment scorer. |
| **Sentiment Optional** | RoBERTa (`cardiffnlp/twitter-roberta-base-sentiment-latest`) | Deep learning CPU sentiment pipeline (enabled by setting `use_fallback_only=False` in `src/m3_bias/sentiment.py`). |
| **NER / NLP** | spaCy `en_core_web_sm` | Used in M3 for entity salience naming. Falls back to regex-based capitalized word frequencies if model is missing. |
| **News Source (Primary)** | NewsAPI.org & RSS Feeds | Polled via connectors to feed Pathway ingestion. |
| **Web Search Fallback** | Bing Search API v7 | Tier-2 retrieval fallback client. |
| **Scraper Fallback** | HTTPX + BeautifulSoup | Tier-3 fallback. Discovers URLs via Google News RSS search, decodes parameters via batch-execute, and chunks HTML paragraphs. |
| **HTTP Client** | `httpx` | Async client for all external network requests. |
| **Retry Logic** | `tenacity` | Exponential backoff for external news APIs, search APIs, and database requests. |
| **Data Validation** | Pydantic v2 | Strictly typed contracts across all 11 schemas. |
| **UI Framework** | FastAPI + Jinja2 | Async server rendering HTML templates and exposing analysis endpoints. |
| **Frontend** | HTML5 + Vanilla CSS + Vanilla JS | Responsive UI, custom CSS animations, tab switcher, and results cards. |
| **Charts** | `Chart.js` (CDN) | Client-side visualizers for sentiment heatmap and framing radar charts. |
| **Logging** | `loguru` | Captures structured trace nodes, latencies, and execution errors. |
| **Configuration** | `pydantic-settings` + `.env` | Type-safe settings module loaded from environment and `.env`. |
| **Testing** | `pytest` + `pytest-asyncio` | Full unit, integration, and schema verification suite. |
