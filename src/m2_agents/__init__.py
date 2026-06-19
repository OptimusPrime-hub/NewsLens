"""
M2 Agents — Multi-Agent Router & Retrieval Manager.

Public API:
    from src.m2_agents import build_graph, run_analysis

    result = await run_analysis(intent_payload)
"""

from src.m2_agents.graph import build_graph, run_analysis
from src.m2_agents.schemas import AnalysisResult
from src.m2_agents.state import AgentState

__all__ = [
    "AgentState",
    "AnalysisResult",
    "build_graph",
    "run_analysis",
]
