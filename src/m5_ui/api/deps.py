"""
M5 — Template rendering helper.

Uses jinja2.Environment directly (bypasses Starlette Jinja2Templates
MRUCache incompatibility on Starlette ≥ 1.3 / Python 3.14).
"""

from __future__ import annotations

from pathlib import Path

from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader

_UI_ROOT = Path(__file__).resolve().parent.parent   # src/m5_ui/
_env = Environment(
    loader=FileSystemLoader(str(_UI_ROOT / "templates")),
    autoescape=False,
    auto_reload=True,
    cache_size=0,  # disable LRUCache — breaks on Python 3.14 with jinja2 3.1.x
)


def render(template_name: str, **context) -> HTMLResponse:
    """Render a Jinja2 template and return an HTMLResponse."""
    tmpl = _env.get_template(template_name)
    return HTMLResponse(content=tmpl.render(**context))
