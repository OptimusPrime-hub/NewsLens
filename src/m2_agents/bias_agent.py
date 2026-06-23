"""
Bias specialist agent node.

Responsibilities:
1. Gather relevant chunks from state.
2. Delegate to M3 BiasEngine for actual analysis.
3. Store BiasAnalysisResult back into state.

NO bias computation logic lives here — M3 owns that.
"""

from __future__ import annotations

from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage

from src.m2_agents.prompts.bias import (
    BIAS_PREPARATION_SYSTEM_PROMPT,
    build_bias_user_prompt,
)
from src.m2_agents.schemas import TraceEntry
from src.m2_agents.state import AgentState
from src.m3_bias.schemas import (
    BiasAnalysisResult,
    FramingVector,
    PublisherBiasProfile,
    SentimentScores,
)
from src.shared.llm_factory import get_chat_model_with_fallback
from src.shared.logging import get_logger

logger = get_logger(__name__)


async def bias_agent_node(state: AgentState) -> dict:
    """
    Prepare chunks and delegate to M3 for bias analysis.

    In MVP, uses LLM to extract per-publisher bias indicators
    from the relevant chunks, then builds a BiasAnalysisResult.
    In production, this would call M3's BiasEngine directly.
    """
    start = datetime.now(tz=UTC)
    chunks = state.get("relevant_chunks", [])
    payload = state["intent_payload"]

    if not chunks:
        return _empty_result(start, "No relevant chunks for bias analysis")

    # ── Build chunks text for LLM ────────────────────────────────────────
    chunks_text = _format_chunks(chunks)

    # ── Call LLM to prepare bias indicators ──────────────────────────────
    try:
        llm = get_chat_model_with_fallback(temperature=0.0, purpose="m5")
        messages = [
            SystemMessage(content=BIAS_PREPARATION_SYSTEM_PROMPT),
            HumanMessage(content=build_bias_user_prompt(payload.raw_query, chunks_text)),
        ]
        response = await llm.ainvoke(messages)
        raw_output = response.content

        # ── Parse and delegate to M3 schema ──────────────────────────────
        bias_result = _parse_bias_response(raw_output, payload.raw_query)

    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Bias agent LLM failed, using offline fallback: {exc}")
        bias_result = _generate_offline_bias(payload.raw_query, chunks)

    elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)

    trace = TraceEntry(
        step_index=state.get("iteration_count", 0) + 1,
        node_name="bias_agent",
        action="Bias analysis via M3",
        input_summary=f"{len(chunks)} relevant chunks",
        output_summary=f"{len(bias_result.publisher_profiles)} publisher profiles",
        latency_ms=elapsed,
        timestamp=datetime.now(tz=UTC),
    )

    return {
        "bias_result": bias_result,
        "agent_trace": [trace],
    }


def _format_chunks(chunks: list) -> str:
    """Format chunks into a text block for the LLM prompt."""
    parts: list[str] = []
    for i, chunk in enumerate(chunks):
        parts.append(
            f"[Chunk {i + 1} | Publisher: {chunk.publisher} | "
            f"Date: {chunk.publish_ts.strftime('%Y-%m-%d')} | "
            f"ID: {chunk.chunk_id}]\n{chunk.chunk_text}\n"
        )
    return "\n---\n".join(parts)


def _parse_bias_response(raw: str, query: str) -> BiasAnalysisResult:
    """
    Parse LLM JSON response into BiasAnalysisResult.

    Falls back to a minimal result if JSON parsing fails.
    """
    import json

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown fences
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        try:
            data = json.loads(raw.strip())
        except json.JSONDecodeError:
            data = {}

    profiles: list[PublisherBiasProfile] = []
    for summary in data.get("publisher_summaries", []):
        profiles.append(
            PublisherBiasProfile(
                publisher=summary.get("publisher", "unknown"),
                sentiment=SentimentScores(
                    positive=0.0, neutral=1.0, negative=0.0, compound=0.0,
                ),
                framing=FramingVector(
                    conflict=0.2, economic=0.2, human_interest=0.2,
                    morality=0.2, responsibility=0.2,
                ),
                entity_salience={},
                bias_score=0.0,
                supporting_quotes=summary.get("emotionally_charged_phrases", []),
            ),
        )

    return BiasAnalysisResult(
        topic=data.get("topic", query),
        analysis_timestamp=datetime.now(tz=UTC),
        publisher_profiles=profiles,
        pairwise_divergence_matrix={},
        summary_explanation=data.get("cross_publisher_observations", ""),
        confidence=0.6 if profiles else 0.0,
    )


def _generate_offline_bias(query: str, chunks: list) -> BiasAnalysisResult:
    """Generate a VADER-based sentiment and framing analysis when LLMs are offline."""
    from collections import defaultdict
    from datetime import UTC, datetime

    from src.m3_bias.schemas import BiasAnalysisResult, FramingVector, PublisherBiasProfile
    from src.m3_bias.sentiment import SentimentAnalyzer

    pub_chunks = defaultdict(list)
    for c in chunks:
        pub_chunks[c.publisher].append(c)

    analyzer = SentimentAnalyzer(use_fallback_only=True)
    profiles = []

    for pub, c_list in pub_chunks.items():
        full_text = " ".join([c.chunk_text for c in c_list])
        sent_scores = analyzer.analyze(full_text)

        text_lower = full_text.lower()
        economic_keywords = ["tariff", "market", "economic", "trade", "dollar", "cost", "price", "business", "tax"]
        conflict_keywords = ["fight", "war", "conflict", "clash", "retaliate", "ban", "dispute", "blame", "retaliation"]
        human_keywords = ["people", "worker", "family", "community", "consumer", "job", "individual", "lives"]
        morality_keywords = ["right", "wrong", "fair", "unfair", "exploit", "justice", "ethics", "moral"]
        resp_keywords = ["government", "policy", "president", "trump", "biden", "leader", "administration", "official"]

        def score_keywords(keywords):
            count = sum(text_lower.count(k) for k in keywords)
            return min(1.0, count * 0.1)

        eco = score_keywords(economic_keywords)
        con = score_keywords(conflict_keywords)
        hum = score_keywords(human_keywords)
        mor = score_keywords(morality_keywords)
        res = score_keywords(resp_keywords)

        total = eco + con + hum + mor + res
        if total > 0:
            eco, con, hum, mor, res = eco/total, con/total, hum/total, mor/total, res/total
        else:
            eco = con = hum = mor = res = 0.2

        framing = FramingVector(
            conflict=round(con, 2),
            economic=round(eco, 2),
            human_interest=round(hum, 2),
            morality=round(mor, 2),
            responsibility=round(res, 2)
        )

        import re
        words = re.findall(r'\b[A-Z][a-zA-Z]+\b', full_text)
        ignored = {pub.lower(), "trump", "biden", "china", "us", "usa", "europe", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        entity_counts = defaultdict(int)
        for w in words:
            if w.lower() not in ignored:
                entity_counts[w] += 1

        entity_salience = {}
        sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        max_count = sorted_entities[0][1] if sorted_entities else 1
        for ent, count in sorted_entities:
            entity_salience[ent] = round(count / max_count, 2)

        bias_score = round(sent_scores.compound, 2)

        quotes = []
        sentences = [s.strip() for s in full_text.split('.') if s.strip()]
        for s in sentences:
            if any(k in s.lower() for k in ["tariff", "trade", "trump", "war", "conflict", "retaliate"]):
                quotes.append(s[:100] + "...")
                if len(quotes) >= 3:
                    break

        profile = PublisherBiasProfile(
            publisher=pub,
            sentiment=sent_scores,
            framing=framing,
            entity_salience=entity_salience,
            bias_score=bias_score,
            supporting_quotes=quotes or [sentences[0][:100] + "..." if sentences else "No quotes found."]
        )
        profiles.append(profile)

    return BiasAnalysisResult(
        topic=query,
        analysis_timestamp=datetime.now(tz=UTC),
        publisher_profiles=profiles,
        pairwise_divergence_matrix={},
        summary_explanation=f"Offline sentiment and framing profile generated using VADER lexicon for {len(profiles)} publishers.",
        confidence=0.5
    )


def _empty_result(start: datetime, reason: str) -> dict:
    """Return an empty bias result with a warning trace."""
    elapsed = int((datetime.now(tz=UTC) - start).total_seconds() * 1000)
    return {
        "bias_result": None,
        "agent_trace": [
            TraceEntry(
                step_index=0,
                node_name="bias_agent",
                action="Bias analysis skipped",
                input_summary="No chunks available",
                output_summary=reason,
                latency_ms=elapsed,
                timestamp=datetime.now(tz=UTC),
            ),
        ],
        "error_log": [reason],
    }
