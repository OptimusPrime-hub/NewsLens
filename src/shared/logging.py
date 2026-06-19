"""
Structured logging setup using loguru.

Usage:
    from src.shared.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Processing query", query_id=session_id)
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_CONFIGURED = False


def setup_logger(
    level: str = "DEBUG",
    log_dir: str | Path = "logs",
    serialize_file: bool = True,
) -> None:
    """Configure loguru sinks. Call once at application startup."""
    global _CONFIGURED  # noqa: PLW0603
    if _CONFIGURED:
        return

    # Remove default stderr sink
    logger.remove()

    # Console sink — human-readable
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{extra[module]}</cyan> | "
            "<level>{message}</level>"
        ),
        backtrace=True,
        diagnose=False,
    )

    # File sink — JSON lines for machine parsing
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_path / "newslens_{time:YYYY-MM-DD}.jsonl",
        level=level,
        serialize=serialize_file,
        rotation="50 MB",
        retention="7 days",
        compression="gz",
        enqueue=True,  # thread-safe
    )

    _CONFIGURED = True


def get_logger(name: str) -> logger:  # type: ignore[valid-type]
    """Return a child logger bound to the given module name."""
    return logger.bind(module=name)
