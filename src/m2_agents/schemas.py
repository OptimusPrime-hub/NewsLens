from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from src.m1_intent.schemas import IntentType
from src.m3_bias.schemas import BiasAnalysisResult
from src.m4_timeline.schemas import TimelineResult


class SummaryResult(BaseModel):
    summary_text: str
    consensus_points: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)

class RetrievedChunk(BaseModel):
    chunk_id: str
    chunk_text: str
    publisher: str
    publish_ts: datetime
    relevance_score: float
    source_url: str | None = None

class TraceEntry(BaseModel):
    step_index: int
    node_name: str                        # LangGraph node
    action: str                           # Human-readable action description
    input_summary: str
    output_summary: str
    latency_ms: int
    fallback_triggered: bool = False
    fallback_tier: int | None = None
    timestamp: datetime

class AnalysisMetadata(BaseModel):
    session_id: UUID
    query_timestamp: datetime
    total_latency_ms: int
    retrieval_tier_used: str
    total_chunks_retrieved: int
    total_chunks_used: int
    model_versions: dict[str, str]

class AnalysisResult(BaseModel):
    """Top-level contract between M2 and M5."""
    intent: IntentType
    raw_query: str

    # Conditional fields based on intent
    bias_result: BiasAnalysisResult | None = None
    timeline_result: TimelineResult | None = None
    summary_result: SummaryResult | None = None

    # Always present
    agent_trace: list[TraceEntry]
    metadata: AnalysisMetadata
    overall_confidence: float
    warnings: list[str] = Field(default_factory=list)
