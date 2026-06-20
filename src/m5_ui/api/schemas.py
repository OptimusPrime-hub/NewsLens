"""
API data contracts and schemas for Module 5 Web UI.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Payload representing a request to analyze a news topic."""

    query: str = Field(..., description="The natural-language query to analyze")
    publishers: list[str] | None = Field(
        default=None,
        description="Optional list of publishers to restrict analysis to",
    )
    date_from: str | None = Field(
        default=None,
        description="ISO 8601 start date filter (YYYY-MM-DD)",
    )
    date_to: str | None = Field(
        default=None,
        description="ISO 8601 end date filter (YYYY-MM-DD)",
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        description="Number of chunks to retrieve (overrides default)",
    )
