"""Helpers for demonstrating autonomous recovery from callback failures."""

from __future__ import annotations

from src.shared.config import get_settings
from src.shared.exceptions import RetrievalError


def should_fail_callback(callback_name: str) -> bool:
    """Return true when a retrieval callback should be forced to fail."""
    return callback_name.lower() in get_settings().simulated_failure_set


def raise_if_simulated(callback_name: str, exc_type: type[RetrievalError]) -> None:
    """Raise the requested retrieval error when simulation is enabled."""
    if should_fail_callback(callback_name):
        raise exc_type(f"Simulated {callback_name} callback failure")
