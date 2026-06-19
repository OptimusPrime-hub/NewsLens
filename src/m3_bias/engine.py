"""
Main orchestrator engine for Module 3 (Bias & Sentiment Analysis).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from src.m2_agents.schemas import RetrievedChunk


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
        start_time = datetime.now(tz=timezone.utc)

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

        # 2. Compute individual publisher profiles
        profiles: list[PublisherBiasProfile] = []
        framing_vectors: dict[str, FramingVector] = {}

        for pub, pub_chunks in publisher_groups.items():
            joint_text = "\n\n".join(c.chunk_text for c in pub_chunks)
            quotes = self._extract_emotional_quotes(pub_chunks)
            sentiment = self.sentiment_analyzer.analyze(joint_text)
            framing = await self.framing_extractor.extract(pub, topic, joint_text)
            framing_vectors[pub] = framing
            entity_salience = extract_entity_salience(joint_text)

            profiles.append(
                PublisherBiasProfile(
                    publisher=pub,
                    sentiment=sentiment,
                    framing=framing,
                    entity_salience=entity_salience,
                    bias_score=0.0,
                    supporting_quotes=quotes,
                )
            )

        if not profiles:
            return BiasAnalysisResult(
                topic=topic,
                analysis_timestamp=datetime.now(tz=timezone.utc),
                publisher_profiles=[],
                pairwise_divergence_matrix={},
                summary_explanation="No publisher profiles extracted.",
                confidence=0.0,
            )

        # 3. Compute baseline/averages across all publishers
        avg_sentiment = sum(p.sentiment.compound for p in profiles) / len(profiles)
        avg_framing = self._compute_avg_framing(list(framing_vectors.values()))
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

        confidence = round(min(1.0, 0.5 + (len(profiles) * 0.1)), 2)

        return BiasAnalysisResult(
            topic=topic,
            analysis_timestamp=datetime.now(tz=timezone.utc),
            publisher_profiles=profiles,
            pairwise_divergence_matrix=divergence_matrix,
            summary_explanation=summary_explanation,
            confidence=confidence,
        )

    def _extract_emotional_quotes(self, chunks: list[RetrievedChunk], max_quotes: int = 3) -> list[str]:
        return []

    def _compute_avg_framing(self, vectors: list[FramingVector]) -> FramingVector:
        return FramingVector(conflict=0.2, economic=0.2, human_interest=0.2, morality=0.2, responsibility=0.2)

    def _compute_avg_salience(self, profiles: list[PublisherBiasProfile]) -> dict[str, float]:
        return {}

    async def _generate_explanation(self, topic: str, profiles: list[PublisherBiasProfile]) -> str:
        return "Stub explanation."
