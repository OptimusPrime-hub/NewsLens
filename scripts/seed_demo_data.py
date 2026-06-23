"""CLI wrapper for seeding demo news articles."""

from __future__ import annotations

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.m0_ingestion.demo_data import seed_demo_data


def main() -> None:
    summary = seed_demo_data(reset=True)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
