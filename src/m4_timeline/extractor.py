"""
M4 — Event Extractor
Extracts discrete, dated events from retrieved article chunks using LLM structured output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.shared.llm_factory import get_chat_model_with_fallback
from src.shared.logging import get_logger
from src.shared.prompts.timeline import (
    TIMELINE_PREPARATION_SYSTEM_PROMPT,
    build_timeline_user_prompt,
)

if TYPE_CHECKING:
    from src.m2_agents.schemas import RetrievedChunk

logger = get_logger(__name__)


class ExtractedEvent(BaseModel):
    date_text: str = Field(
        description="The date or timeframe associated with the event (e.g. '2026-06-05', 'early June 2026')"
    )
    headline: str = Field(description="Concise headline of the event (< 15 words)")
    description: str = Field(description="One-sentence description of the event")
    publishers: list[str] = Field(
        default_factory=list, description="List of publishers reporting this event"
    )
    entities: list[str] = Field(
        default_factory=list, description="Key entities involved"
    )
    chunk_ids_used: list[str] = Field(
        default_factory=list, description="IDs of the chunks this event was extracted from"
    )


class ExtractedTimelinePayload(BaseModel):
    topic: str = Field(description="The inferred topic of the timeline")
    extracted_events: list[ExtractedEvent] = Field(
        default_factory=list, description="Chronological list of extracted events"
    )


class EventExtractor:
    """
    Extracts temporally anchored events from retrieved news articles.
    """

    async def extract(self, query: str, chunks: list[RetrievedChunk]) -> ExtractedTimelinePayload:
        if not chunks:
            return ExtractedTimelinePayload(topic=query, extracted_events=[])

        chunks_text = self._format_chunks(chunks)

        try:
            llm = get_chat_model_with_fallback(temperature=0.0, purpose="m5")
            structured_llm = llm.with_structured_output(ExtractedTimelinePayload)

            system_msg = SystemMessage(content=TIMELINE_PREPARATION_SYSTEM_PROMPT)
            user_msg = HumanMessage(content=build_timeline_user_prompt(query, chunks_text))

            payload = await structured_llm.ainvoke([system_msg, user_msg])
            logger.info(
                "Successfully extracted raw timeline events",
                topic=payload.topic,
                event_count=len(payload.extracted_events),
            )
            return payload

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to extract timeline events via LLM", error=str(exc))
            return ExtractedTimelinePayload(topic=query, extracted_events=[])

    def _format_chunks(self, chunks: list[RetrievedChunk]) -> str:
        parts: list[str] = []
        for i, chunk in enumerate(chunks):
            parts.append(
                f"[Chunk {i + 1} | Publisher: {chunk.publisher} | "
                f"Date: {chunk.publish_ts.strftime('%Y-%m-%d')} | "
                f"ID: {chunk.chunk_id}]\n{chunk.chunk_text}\n"
            )
        return "\n---\n".join(parts)
