"""
Main orchestrator engine for Module 3 (Bias & Sentiment Analysis).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage

from src.m3_bias.framing import FramingExtractor
from src.m3_bias.schemas import (
    BiasAnalysisResult,
    FramingVector,
    PublisherBiasProfile,
)
from src.m3_bias.scoring import (
    compute_bias_score,
    compute_pairwise_divergence,
    extract_entity_salience,
)
from src.m3_bias.sentiment import SentimentAnalyzer
from src.shared.llm_factory import get_chat_model_with_fallback
from src.shared.logging import get_logger
from src.shared.prompts.explanation import (
    BIAS_EXPLANATION_SYSTEM_PROMPT,
    build_bias_explanation_user_prompt,
)

if TYPE_CHECKING:
    from src.m2_agents.schemas import RetrievedChunk

logger = get_logger(__name__)


class BiasEngine:
    """
    Main entry point for Module 3. Analyzes chunks from multiple publishers
    to produce publisher bias profiles, divergence matrices, and a summary explanation.
    """

    def __init__(self, use_fallback_sentiment: bool = False):
        self.sentiment_analyzer = SentimentAnalyzer(use_fallback_only=use_fallback_sentiment)
        self.framing_extractor = FramingExtractor()

    async def analyze(self, topic: str, chunks: list[RetrievedChunk]) -> BiasAnalysisResult:
        """
        Perform complete bias and sentiment analysis on the retrieved chunks.
        """
        start_time = datetime.now(tz=UTC)
        logger.info("Starting bias engine analysis", topic=topic, n_chunks=len(chunks))

        if not chunks:
            return BiasAnalysisResult(
                topic=topic,
                analysis_timestamp=start_time,
                publisher_profiles=[],
                pairwise_divergence_matrix={},
                summary_explanation="No chunks available to analyze.",
                confidence=0.0,
            )

        # 1. Group chunks by publisher
        publisher_groups: dict[str, list[RetrievedChunk]] = {}
        for chunk in chunks:
            pub = chunk.publisher.strip().title()
            publisher_groups.setdefault(pub, []).append(chunk)

        # 2. Compute individual publisher profiles (sentiment, framing, salience)
        profiles: list[PublisherBiasProfile] = []
        framing_vectors: dict[str, FramingVector] = {}

        for pub, pub_chunks in publisher_groups.items():
            logger.info("Analyzing publisher corpus", publisher=pub, n_chunks=len(pub_chunks))

            # Combine text and extract some supporting quotes (emotional or charged phrases)
            joint_text = "\n\n".join(c.chunk_text for c in pub_chunks)
            quotes = self._extract_emotional_quotes(pub_chunks)

            # Sentiment Analysis
            sentiment = self.sentiment_analyzer.analyze(joint_text)

            # Framing Extraction
            framing = await self.framing_extractor.extract(pub, topic, joint_text)
            framing_vectors[pub] = framing

            # Entity Salience
            entity_salience = extract_entity_salience(joint_text)

            profiles.append(
                PublisherBiasProfile(
                    publisher=pub,
                    sentiment=sentiment,
                    framing=framing,
                    entity_salience=entity_salience,
                    bias_score=0.0,  # Computed in next step
                    supporting_quotes=quotes,
                )
            )

        if not profiles:
            return BiasAnalysisResult(
                topic=topic,
                analysis_timestamp=datetime.now(tz=UTC),
                publisher_profiles=[],
                pairwise_divergence_matrix={},
                summary_explanation="No publisher profiles could be extracted.",
                confidence=0.0,
            )

        # 3. Compute baseline/averages across all publishers
        avg_sentiment = sum(p.sentiment.compound for p in profiles) / len(profiles)

        # Average framing vector
        avg_framing = self._compute_avg_framing(list(framing_vectors.values()))

        # Average entity salience
        avg_salience = self._compute_avg_salience(profiles)

        # 4. Compute bias scores for each profile
        for profile in profiles:
            profile.bias_score = compute_bias_score(
                publisher_sentiment=profile.sentiment.compound,
                avg_sentiment=avg_sentiment,
                publisher_framing=profile.framing,
                avg_framing=avg_framing,
                publisher_salience=profile.entity_salience,
                avg_salience=avg_salience,
            )

        # 5. Compute pairwise JSD divergence matrix
        divergence_matrix = compute_pairwise_divergence(framing_vectors)

        # 6. Generate narrative explanation
        summary_explanation = await self._generate_explanation(topic, profiles)

        latency_ms = int((datetime.now(tz=UTC) - start_time).total_seconds() * 1000)
        logger.info("Completed bias engine analysis", topic=topic, latency_ms=latency_ms)

        # Confidence is calculated as a blend of model confidence, publisher diversity, etc.
        confidence = round(min(1.0, 0.5 + (len(profiles) * 0.1)), 2)

        return BiasAnalysisResult(
            topic=topic,
            analysis_timestamp=datetime.now(tz=UTC),
            publisher_profiles=profiles,
            pairwise_divergence_matrix=divergence_matrix,
            summary_explanation=summary_explanation,
            confidence=confidence,
        )

    def _extract_emotional_quotes(self, chunks: list[RetrievedChunk], max_quotes: int = 3) -> list[str]:
        """Extract a few candidate quotes or emotional/opinion-based lines from the text chunks."""
        import re

        phrases: list[str] = []
        for chunk in chunks:
            # Simple heuristic: look for sentences containing opinion/sentiment indicators, exclamation marks, or adjectives
            sentences = re.split(r"(?<=[.!?])\s+", chunk.chunk_text)
            for sent in sentences:
                sent = sent.strip()
                # Exclude too short/too long sentences
                if 20 < len(sent) < 150:
                    # Match emotion-related keywords (e.g. claim, demand, slam, praise, attack, warn, crisis, etc.)
                    if any(w in sent.lower() for w in ["claim", "slammed", "criticized", "praised", "warned", "crisis", "threat", "demanded", "refused", "insisted"]):
                        phrases.append(sent)

        # Fallback: just return the first few sentences
        if not phrases:
            for chunk in chunks:
                sentences = re.split(r"(?<=[.!?])\s+", chunk.chunk_text)
                for sent in sentences:
                    if 20 < len(sent.strip()) < 150:
                        phrases.append(sent.strip())

        return list(set(phrases))[:max_quotes]

    def _compute_avg_framing(self, vectors: list[FramingVector]) -> FramingVector:
        """Compute the average framing vector across all publishers."""
        if not vectors:
            return FramingVector(conflict=0.2, economic=0.2, human_interest=0.2, morality=0.2, responsibility=0.2)

        conflict = sum(v.conflict for v in vectors) / len(vectors)
        economic = sum(v.economic for v in vectors) / len(vectors)
        human_interest = sum(v.human_interest for v in vectors) / len(vectors)
        morality = sum(v.morality for v in vectors) / len(vectors)
        responsibility = sum(v.responsibility for v in vectors) / len(vectors)

        # Normalize average to sum to 1.0
        total = conflict + economic + human_interest + morality + responsibility
        if total <= 0.0:
            return FramingVector(conflict=0.2, economic=0.2, human_interest=0.2, morality=0.2, responsibility=0.2)

        return FramingVector(
            conflict=conflict / total,
            economic=economic / total,
            human_interest=human_interest / total,
            morality=morality / total,
            responsibility=responsibility / total,
        )

    def _compute_avg_salience(self, profiles: list[PublisherBiasProfile]) -> dict[str, float]:
        """Compute average entity salience across all publisher profiles."""
        avg_salience: dict[str, float] = {}
        if not profiles:
            return avg_salience

        for p in profiles:
            for ent, sal in p.entity_salience.items():
                avg_salience[ent] = avg_salience.get(ent, 0.0) + (sal / len(profiles))

        return {k: round(v, 4) for k, v in avg_salience.items()}

    async def _generate_explanation(self, topic: str, profiles: list[PublisherBiasProfile]) -> str:
        """Call LLM to summarize findings into a neutral, cohesive explanation."""
        try:
            # Build a summary string of publisher findings
            summary_list = []
            for p in profiles:
                summary_list.append(
                    f"Publisher: {p.publisher}\n"
                    f"- Sentiment: positive={p.sentiment.positive}, negative={p.sentiment.negative}, compound={p.sentiment.compound}\n"
                    f"- Framing: conflict={p.framing.conflict:.2f}, economic={p.framing.economic:.2f}, human_interest={p.framing.human_interest:.2f}, morality={p.framing.morality:.2f}, responsibility={p.framing.responsibility:.2f}\n"
                    f"- Supporting Quotes: {p.supporting_quotes}\n"
                )
            summary_data = "\n---\n".join(summary_list)

            llm = get_chat_model_with_fallback(temperature=0.3, purpose="m5")
            messages = [
                SystemMessage(content=BIAS_EXPLANATION_SYSTEM_PROMPT),
                HumanMessage(content=build_bias_explanation_user_prompt(topic, summary_data)),
            ]
            response = await llm.ainvoke(messages)
            return response.content

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to generate bias explanation narrative", error=str(exc))
            # Build a basic fallback explanation from scores
            lines = [f"Analysis of coverage on the topic '{topic}' across {len(profiles)} publishers."]
            for p in profiles:
                bias_type = "positive" if p.bias_score > 0.0 else "negative" if p.bias_score < 0.0 else "neutral"
                lines.append(
                    f"- {p.publisher} exhibits a {bias_type} bias (score: {p.bias_score:.2f}) "
                    f"with dominant framing in conflict ({p.framing.conflict:.2f}) and responsibility ({p.framing.responsibility:.2f})."
                )
            return "\n".join(lines)
