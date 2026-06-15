from datetime import datetime
from uuid import UUID
from typing import Optional, Literal
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

class TraceEntry(BaseModel):
    step_index: int
    node_name: str                        # LangGraph node
    action: str                           # Human-readable action description
    input_summary: str
    output_summary: str
    latency_ms: int
    fallback_triggered: bool = False
    fallback_tier: Optional[int] = None
    timestamp: datetime

class AnalysisMetadata(BaseModel):
    session_id: UUID
    query_timestamp: datetime
    total_latency_ms: int
    retrieval_tier_used: Literal["pathway", "bing", "scraper"]
    total_chunks_retrieved: int
    total_chunks_used: int
    model_versions: dict[str, str]

class AnalysisResult(BaseModel):
    """Top-level contract between M2 and M5."""
    intent: IntentType
    raw_query: str
    
    # Conditional fields based on intent
    bias_result: Optional[BiasAnalysisResult] = None
    timeline_result: Optional[TimelineResult] = None
    summary_result: Optional[SummaryResult] = None
    
    # Always present
    agent_trace: list[TraceEntry]
    metadata: AnalysisMetadata
    overall_confidence: float
    warnings: list[str] = Field(default_factory=list)
