"""Runtime detection for which retrieval backends are available."""

from __future__ import annotations

import sys


def use_pathway_primary() -> bool:
    """Return True when Pathway can serve as the primary retriever."""
    if sys.platform == "win32":
        return False
    try:
        import pathway  # noqa: F401

        return True
    except ImportError:
        return False
