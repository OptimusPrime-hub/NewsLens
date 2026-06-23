"""
Start the Pathway-native REST serving endpoint.

Serves the NewsLens analysis pipeline via Pathway's pw.io.http.rest_connector
on port 8766 (alongside the FastAPI UI server on port 8000).

Linux/Docker only — Pathway does not support Windows.

Usage:
    poetry run python scripts/run_pathway_serve.py
    poetry run python scripts/run_pathway_serve.py --host 0.0.0.0 --port 8766
"""

from __future__ import annotations

import argparse
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Pathway-native REST endpoint")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8766, help="Bind port (default: 8766)")
    args = parser.parse_args()

    from src.m5_ui.api.pathway_serve import build_pathway_serve_app
    build_pathway_serve_app(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
