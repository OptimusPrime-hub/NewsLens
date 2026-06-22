"""
M5 — API Routes

Endpoints:
  GET  /              → index.html (search landing page)
  POST /api/analyze   → run M1 + M2 pipeline, return AnalysisResult JSON
  GET  /api/stream    → SSE stream of pipeline progress events
  GET  /api/health    → liveness probe
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from src.m1_intent.classifier import IntentClassifier
from src.m2_agents.graph import run_analysis
from src.m2_agents.schemas import AnalysisResult
from src.m5_ui.api.schemas import AnalyzeRequest
from src.m5_ui.api.server import templates
from src.shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# ── Module-level classifier (avoid re-init on every request) ─────────────────
_classifier: IntentClassifier | None = None


def _get_classifier() -> IntentClassifier:
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sse_event(event: str, data: dict) -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/results", response_class=HTMLResponse)
async def results(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("results.html", {"request": request})


@router.get("/about", response_class=HTMLResponse)
async def about(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("about.html", {"request": request})


@router.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "timestamp": datetime.now(tz=UTC).isoformat()})


@router.post("/api/analyze")
async def analyze(body: AnalyzeRequest) -> JSONResponse:
    """
    Run the full M1 → M2 pipeline synchronously.
    Returns the raw AnalysisResult JSON (no additional schema layer).
    """
    try:
        classifier = _get_classifier()
        intent_payload = classifier.classify(body.query)

        result: AnalysisResult = await run_analysis(intent_payload)
        return JSONResponse(json.loads(result.model_dump_json()))

    except Exception as exc:  # noqa: BLE001
        logger.error("Analysis pipeline failed", error=str(exc))
        return JSONResponse(
            {"error": str(exc), "query": body.query},
            status_code=500,
        )


@router.post("/api/analyze/stream")
async def analyze_stream(body: AnalyzeRequest) -> StreamingResponse:
    """
    SSE streaming endpoint — emits progress events as the pipeline advances.

    Event types:
      progress  — pipeline step update {step, message}
      result    — final AnalysisResult JSON
      error     — pipeline failure {message}
    """

    async def _generate():
        try:
            # Step 1 — Intent classification
            yield _sse_event("progress", {"step": 1, "message": "Classifying query intent…"})
            await asyncio.sleep(0)

            classifier = _get_classifier()
            intent_payload = classifier.classify(body.query)
            yield _sse_event("progress", {
                "step": 1,
                "message": f"Intent: {intent_payload.intent.value} "
                           f"(confidence {intent_payload.confidence:.0%})",
                "done": True,
            })

            # Step 2 — Retrieval
            yield _sse_event("progress", {"step": 2, "message": "Retrieving live articles…"})
            await asyncio.sleep(0)

            # Step 3 — CRAG
            yield _sse_event("progress", {"step": 3, "message": "CRAG relevance filtering…"})
            await asyncio.sleep(0)

            # Step 4 — Specialist agent
            agent_name = {
                "TIMELINE": "Timeline Synthesizer",
                "BIAS_DETECTION": "Bias Engine",
                "CROSS_PUBLISHER_SUMMARY": "Summary Agent",
            }.get(intent_payload.intent.value, "Analysis Agent")
            yield _sse_event("progress", {"step": 4, "message": f"Running {agent_name}…"})
            await asyncio.sleep(0)

            # Run the actual pipeline
            result: AnalysisResult = await run_analysis(intent_payload)

            # Emit trace summary
            chunks_retrieved = result.metadata.total_chunks_retrieved
            chunks_used = result.metadata.total_chunks_used
            yield _sse_event("progress", {
                "step": 2,
                "message": f"Retrieved {chunks_retrieved} chunks ({chunks_used} used after CRAG)",
                "done": True,
            })
            yield _sse_event("progress", {"step": 3, "done": True,
                "message": f"CRAG accepted {chunks_used}/{chunks_retrieved} chunks"})
            yield _sse_event("progress", {"step": 4, "done": True,
                "message": f"{agent_name} completed"})

            # Final result
            yield _sse_event("result", json.loads(result.model_dump_json()))

        except Exception as exc:  # noqa: BLE001
            logger.error("Stream pipeline failed", error=str(exc))
            yield _sse_event("error", {"message": str(exc)})

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
