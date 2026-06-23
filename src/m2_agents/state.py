"""
LangGraph agent state definition.

This is the single source of truth for what flows through the graph.
Only raw intermediate outputs — no assembled AnalysisResult here.
The assembler node is the only place that builds the final result.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from src.m1_intent.schemas import IntentPayload
from src.m2_agents.crag.schemas import CRAGGrade
from src.m2_agents.schemas import AnalysisResult, RetrievedChunk, SummaryResult, TraceEntry
from src.m3_bias.schemas import BiasAnalysisResult
from src.m4_timeline.schemas import TimelineResult


class AgentState(TypedDict):
    """
    Shared state flowing through the LangGraph StateGraph.

    Uses Annotated[list, operator.add] for fields that accumulate
    across nodes (trace, errors) rather than being overwritten.

    Design:
    - Only raw intermediate outputs, no assembled AnalysisResult.
    - Each specialist node writes to its own result slot.
    - The assembler node reads all slots to build AnalysisResult.
    """

    # ── Input (set once by supervisor) ───────────────────────────────────────
    intent_payload: IntentPayload

    # ── Retrieval outputs ────────────────────────────────────────────────────
    retrieved_chunks: list[RetrievedChunk]
    retrieval_tier: str  # "pathway" | "local" | "bing" | "scraper"

    # ── CRAG outputs ─────────────────────────────────────────────────────────
    crag_grades: list[CRAGGrade]
    relevant_chunks: list[RetrievedChunk]  # filtered by CRAG (RELEVANT only)

    # ── Specialist agent outputs (mutually exclusive per query) ──────────────
    bias_result: BiasAnalysisResult | None
    timeline_result: TimelineResult | None
    summary_result: SummaryResult | None

    # ── Observability ────────────────────────────────────────────────────────
    agent_trace: Annotated[list[TraceEntry], operator.add]
    error_log: Annotated[list[str], operator.add]

    # ── Control flow ─────────────────────────────────────────────────────────
    iteration_count: int

    # ── Final Output ─────────────────────────────────────────────────────────
    _final_result: AnalysisResult | None
