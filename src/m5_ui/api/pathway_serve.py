"""
Pathway-native REST endpoint for the NewsLens analysis pipeline.

This module implements the "serve via Pathway's serve_callable API" path
described in the Pathway problem statement, alongside the FastAPI server.

Usage (Linux/Docker only — Pathway does not run on Windows):
    poetry run python scripts/run_pathway_serve.py

The endpoint listens on PATHWAY_SERVE_PORT (default: 8766) and accepts:
    POST /v1/analyze
    Body: {"query": "How did Reuters cover US-China trade talks?"}

The FastAPI server (port 8000) proxies to this endpoint when Pathway is running,
or falls back to direct in-process execution on Windows.
"""

from __future__ import annotations

import asyncio
import json
import sys

from src.shared.logging import get_logger

logger = get_logger(__name__)


def build_pathway_serve_app(host: str = "0.0.0.0", port: int = 8766) -> None:
    """
    Build and run the Pathway-served analysis endpoint.

    Uses pw.io.http.rest_connector to expose the full NewsLens analysis
    pipeline as a Pathway-native streaming REST endpoint.

    Args:
        host: Host to bind to.
        port: Port to listen on.
    """
    try:
        import pathway as pw
    except ImportError:
        logger.error("Pathway is not installed — cannot start pathway serve endpoint")
        logger.info("On Linux/Docker: poetry install will include pathway>=0.31.0")
        sys.exit(1)

    import pathway.io.http as pw_http
    from src.m0_ingestion.vector_store import build_pathway_vector_server
    from src.shared.config import get_settings

    settings = get_settings()

    # ── Define the request/response schema ───────────────────────────────────
    class QuerySchema(pw.Schema):
        query: str
        intent: str = "auto"  # auto | BIAS_DETECTION | TIMELINE | CROSS_PUBLISHER_SUMMARY

    # ── Start the Pathway VectorStoreServer alongside the REST endpoint ───────
    vector_server = build_pathway_vector_server()
    vector_server.run_server(
        host=settings.pathway_host,
        port=settings.pathway_port,
        threaded=True,   # runs in background thread while pw.run() drives the table loop
        with_cache=True,
    )
    logger.info(
        "Pathway VectorStoreServer started",
        host=settings.pathway_host,
        port=settings.pathway_port,
    )

    # ── Create the REST connector for the analysis endpoint ───────────────────
    webserver = pw_http.PathwayWebserver(host=host, port=port)

    queries, writer = pw_http.rest_connector(
        webserver=webserver,
        schema=QuerySchema,
        autocommit_duration_ms=50,
        delete_completed_queries=True,
    )

    # ── Process each incoming query as a Pathway UDF ─────────────────────────
    @pw.udf
    def run_analysis(query: str, intent: str) -> str:
        """
        Execute the full NewsLens pipeline for a single query.

        This UDF bridges Pathway's table-oriented execution model
        with the async LangGraph agent pipeline.
        """
        try:
            from src.m1_intent.classifier import IntentClassifier
            from src.m2_agents.graph import build_analysis_graph

            # Run the async pipeline in a new event loop (Pathway UDFs are sync)
            async def _run() -> dict:
                classifier = IntentClassifier()
                intent_payload = await classifier.classify(query)
                graph = build_analysis_graph()
                result = await graph.ainvoke({"query": query, "intent": intent_payload})
                return result

            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(_run())
            loop.close()
            return json.dumps(result, default=str)
        except Exception as exc:  # noqa: BLE001
            logger.error("Pathway UDF analysis failed", query=query, error=str(exc))
            return json.dumps({"error": str(exc), "query": query})

    # ── Wire the UDF output back to the REST response writer ─────────────────
    responses = queries.select(
        result=run_analysis(pw.this.query, pw.this.intent),
    )
    writer(responses)

    logger.info(
        "Pathway serve endpoint ready",
        host=host,
        port=port,
        endpoint="/v1/analyze",
    )
    logger.info("Starting pw.run() — press Ctrl+C to stop")
    pw.run()
