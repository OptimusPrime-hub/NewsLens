"""Run the Pathway VectorStore service.

This script is intended to run inside the Linux Docker container. Windows
developers should start it through `docker compose up --build`.
"""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.m0_ingestion.vector_store import build_pathway_vector_server
from src.shared.config import get_settings


def main() -> None:
    settings = get_settings()
    server = build_pathway_vector_server()
    print(
        "Starting Pathway VectorStore on "
        f"{settings.pathway_host}:{settings.pathway_port} "
        f"watching {settings.pathway_source_glob}"
    )
    server.run_server(host=settings.pathway_host, port=settings.pathway_port)


if __name__ == "__main__":
    main()
