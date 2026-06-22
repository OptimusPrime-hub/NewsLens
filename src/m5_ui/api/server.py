"""
M5 — FastAPI application factory.

Mounts static files, Jinja2 templates, and registers all API routes.
Entry point: `uvicorn src.m5_ui.api.server:app --reload`
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.m5_ui.api.routes import router
from src.shared.logging import get_logger

logger = get_logger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_UI_ROOT = Path(__file__).resolve().parent.parent          # src/m5_ui/
TEMPLATES_DIR = _UI_ROOT / "templates"
STATIC_DIR = _UI_ROOT / "static"

# ── Jinja2 template engine (shared instance) ──────────────────────────────────
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    app = FastAPI(
        title="NewsLens",
        description="Dynamic Agentic RAG — Real-Time News Analysis & Bias Detection",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    # ── Static files ─────────────────────────────────────────────────────────
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # ── Routes ───────────────────────────────────────────────────────────────
    app.include_router(router)

    @app.on_event("startup")
    async def _startup() -> None:
        logger.info("NewsLens M5 UI server started")

    return app


# ── ASGI app instance (for uvicorn) ──────────────────────────────────────────
app = create_app()
