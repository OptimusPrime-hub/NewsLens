"""
LangGraph StateGraph assembly — the full M2 agent pipeline.

Graph topology (revised architecture):

    START
      ↓
    supervisor
      ↓
    retrieve
      ↓
    crag_evaluate
      ↓
    route_by_intent  ──→  bias_agent
                     ──→  timeline_agent
                     ──→  summary_agent
      ↓
    validate
      ↓
    assemble_result
      ↓
    END

Benefits over the original design:
- Retrieval happens ONCE (not per-agent)
- CRAG happens ONCE
- Agents stay specialised — no retrieval duplication
- Validation is cheap (structural, not LLM)
- Assembly is centralised
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, StateGraph

from src.m1_intent.schemas import IntentPayload
from src.m2_agents.assembler import assemble_result_node
from src.m2_agents.bias_agent import bias_agent_node
from src.m2_agents.crag import GradeEnum, LLMCRAGEvaluator, QueryRewriter
from src.m2_agents.retrieval import RetrievalManager, build_filters
from src.m2_agents.schemas import AnalysisResult, TraceEntry
from src.m2_agents.state import AgentState
from src.m2_agents.summary_agent import summary_agent_node
from src.m2_agents.supervisor import route_by_intent, supervisor_node
from src.m2_agents.timeline_agent import timeline_agent_node
from src.m2_agents.validators import validate_node
from src.shared.logging import get_logger

logger = get_logger(__name__)


# ── Graph Node Functions ─────────────────────────────────────────────────────
# (supervisor, bias/timeline/summary agents, validate, assemble are imported)
# retrieve_node and crag_evaluate_node are defined here because they
# orchestrate M2-internal components that don't warrant their own file.


async def retrieve_node(state: AgentState) -> dict:
    """
    Retrieve document chunks using the 3-tier fallback cascade.

    This node runs ONCE for all intents — agents don't retrieve individually.
    """
    start = datetime.now(tz=timezone.utc)
    payload = state["intent_payload"]
    filters = build_filters(payload)

    rewriter = QueryRewriter()
    manager = RetrievalManager(rewriter=rewriter)

    try:
        chunks, tier = await manager.retrieve(payload.raw_query, filters)
    except Exception as exc:  # noqa: BLE001
        logger.error("Retrieval cascade failed", error=str(exc))
        elapsed = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)
        return {
            "retrieved_chunks": [],
            "retrieval_tier": "none",
            "agent_trace": [
                TraceEntry(
                    step_index=1,
                    node_name="retrieve",
                    action="Retrieval cascade",
                    input_summary=f"Query: {payload.raw_query[:80]}",
                    output_summary=f"FAILED: {exc}",
                    latency_ms=elapsed,
                    fallback_triggered=True,
                    timestamp=datetime.now(tz=timezone.utc),
                ),
            ],
            "error_log": [f"Retrieval failed: {exc}"],
        }
    finally:
        await manager.close()

    elapsed = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)

    trace = TraceEntry(
        step_index=1,
        node_name="retrieve",
        action="Retrieval cascade",
        input_summary=f"Query: {payload.raw_query[:80]}",
        output_summary=f"{len(chunks)} chunks via {tier}",
        latency_ms=elapsed,
        fallback_triggered=(tier != "pathway"),
        fallback_tier={"pathway": 0, "bing": 2, "scraper": 3}.get(tier),
        timestamp=datetime.now(tz=timezone.utc),
    )

    return {
        "retrieved_chunks": chunks,
        "retrieval_tier": tier,
        "agent_trace": [trace],
    }


async def crag_evaluate_node(state: AgentState) -> dict:
    """
    Evaluate retrieved chunks with CRAG and filter to RELEVANT only.

    This node runs ONCE — agents receive pre-filtered relevant chunks.
    """
    start = datetime.now(tz=timezone.utc)
    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        return {
            "crag_grades": [],
            "relevant_chunks": [],
            "agent_trace": [
                TraceEntry(
                    step_index=2,
                    node_name="crag_evaluate",
                    action="CRAG evaluation",
                    input_summary="0 chunks",
                    output_summary="Skipped — no chunks to evaluate",
                    latency_ms=0,
                    timestamp=datetime.now(tz=timezone.utc),
                ),
            ],
        }

    evaluator = LLMCRAGEvaluator()
    query = state["intent_payload"].raw_query
    grades = await evaluator.evaluate(query, chunks)

    # Build lookup: chunk_id → grade
    grade_map = {g.chunk_id: g.grade for g in grades}

    # Filter to RELEVANT chunks only
    relevant = [
        chunk for chunk in chunks
        if grade_map.get(chunk.chunk_id) == GradeEnum.RELEVANT
    ]

    # If no RELEVANT chunks, include AMBIGUOUS as fallback
    if not relevant:
        relevant = [
            chunk for chunk in chunks
            if grade_map.get(chunk.chunk_id) == GradeEnum.AMBIGUOUS
        ]
        if relevant:
            logger.info("No RELEVANT chunks, falling back to AMBIGUOUS")

    elapsed = int((datetime.now(tz=timezone.utc) - start).total_seconds() * 1000)

    trace = TraceEntry(
        step_index=2,
        node_name="crag_evaluate",
        action="CRAG evaluation",
        input_summary=f"{len(chunks)} chunks",
        output_summary=(
            f"{len(relevant)} relevant, "
            f"{sum(1 for g in grades if g.grade == GradeEnum.IRRELEVANT)} irrelevant"
        ),
        latency_ms=elapsed,
        timestamp=datetime.now(tz=timezone.utc),
    )

    return {
        "crag_grades": grades,
        "relevant_chunks": relevant,
        "agent_trace": [trace],
    }


# ── Graph Builder ────────────────────────────────────────────────────────────


def build_graph() -> Any:
    """
    Assemble and compile the LangGraph StateGraph.

    Returns a compiled graph ready for `.ainvoke()`.
    """
    graph = StateGraph(AgentState)

    # ── Add nodes ────────────────────────────────────────────────────────
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("crag_evaluate", crag_evaluate_node)
    graph.add_node("bias_agent", bias_agent_node)
    graph.add_node("timeline_agent", timeline_agent_node)
    graph.add_node("summary_agent", summary_agent_node)
    graph.add_node("validate", validate_node)
    graph.add_node("assemble_result", assemble_result_node)

    # ── Add edges ────────────────────────────────────────────────────────
    # Linear: START → supervisor → retrieve → crag_evaluate
    graph.set_entry_point("supervisor")
    graph.add_edge("supervisor", "retrieve")
    graph.add_edge("retrieve", "crag_evaluate")

    # Conditional: crag_evaluate → {bias | timeline | summary}
    graph.add_conditional_edges(
        "crag_evaluate",
        route_by_intent,
        {
            "bias_agent": "bias_agent",
            "timeline_agent": "timeline_agent",
            "summary_agent": "summary_agent",
        },
    )

    # All specialists → validate → assemble → END
    graph.add_edge("bias_agent", "validate")
    graph.add_edge("timeline_agent", "validate")
    graph.add_edge("summary_agent", "validate")
    graph.add_edge("validate", "assemble_result")
    graph.add_edge("assemble_result", END)

    return graph.compile()


# ── Public Entry Point ───────────────────────────────────────────────────────


async def run_analysis(intent_payload: IntentPayload) -> AnalysisResult:
    """
    Run the full M2 analysis pipeline for a given IntentPayload.

    This is the public API of the m2_agents module.

    Args:
        intent_payload: Structured intent from M1.

    Returns:
        AnalysisResult ready for M5 to render.
    """
    compiled = build_graph()

    initial_state: dict[str, Any] = {
        "intent_payload": intent_payload,
        "retrieved_chunks": [],
        "retrieval_tier": "",
        "crag_grades": [],
        "relevant_chunks": [],
        "bias_result": None,
        "timeline_result": None,
        "summary_result": None,
        "agent_trace": [],
        "error_log": [],
        "iteration_count": 0,
    }

    logger.info(
        "Starting M2 analysis",
        intent=intent_payload.intent.value,
        query=intent_payload.raw_query,
    )

    final_state = await compiled.ainvoke(initial_state)

    # Extract the assembled result
    result = final_state.get("_final_result")

    if result is None:
        # Fallback: this shouldn't happen, but build a minimal result
        from uuid import uuid4

        result = AnalysisResult(
            intent=intent_payload.intent,
            raw_query=intent_payload.raw_query,
            agent_trace=final_state.get("agent_trace", []),
            metadata=AnalysisResult.__fields__["metadata"].default,
            overall_confidence=0.0,
            warnings=["Pipeline completed without assembling a result"],
        )

    logger.info(
        "M2 analysis complete",
        intent=intent_payload.intent.value,
        confidence=result.overall_confidence,
    )

    return result
