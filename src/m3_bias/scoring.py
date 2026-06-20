"""
Mathematical scoring and analytics module for bias metrics.
Implements:
1. Entity salience extraction using spaCy NER.
2. Jensen-Shannon Divergence for framing vectors.
3. Signed composite Bias Score calculation.
4. Pairwise publisher divergence matrix.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from src.shared.cache import get_cached_model
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.m3_bias.schemas import FramingVector

logger = get_logger(__name__)


# ── Entity Salience Extraction ────────────────────────────────────────────────


def extract_entity_salience(text: str) -> dict[str, float]:
    """
    Extract named entities using spaCy NER and compute normalized salience scores.
    Salience = entity_frequency / total_entity_mentions.
    """
    if not text.strip():
        return {}

    import spacy

    def load_spacy():
        # Try primary transformer model first, fallback to small model
        try:
            return spacy.load("en_core_web_trf")
        except Exception:
            try:
                return spacy.load("en_core_web_sm")
            except Exception:
                # If neither is installed, return a dummy model or raise
                return spacy.blank("en")

    try:
        nlp = get_cached_model("spacy_ner_model", load_spacy)
        doc = nlp(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("spaCy processing failed, falling back to regex word counts", error=str(exc))
        return _regex_entity_fallback(text)

    # Count entity frequencies (focusing on PERSON, ORG, GPE)
    counts: dict[str, int] = {}
    for ent in doc.ents:
        if ent.label_ in ("PERSON", "ORG", "GPE"):
            name = ent.text.strip().title()
            if len(name) > 2:  # Filter out noise
                counts[name] = counts.get(name, 0) + 1

    if not counts:
        return {}

    # Normalize counts to sum to 1.0
    total = sum(counts.values())
    return {name: round(freq / total, 4) for name, freq in counts.items()}


def _regex_entity_fallback(text: str) -> dict[str, float]:
    """Fallback simple capitalized phrase frequency analyzer if spaCy fails."""
    import re

    # Match consecutive capitalized words
    pattern = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")
    words = pattern.findall(text)

    counts: dict[str, int] = {}
    for word in words:
        name = word.strip().title()
        if len(name) > 3:  # Filter out short words
            counts[name] = counts.get(name, 0) + 1

    if not counts:
        return {}

    total = sum(counts.values())
    return {name: round(freq / total, 4) for name, freq in counts.items()}


# ── Jensen-Shannon Divergence ───────────────────────────────────────────────


def jensen_shannon_divergence(p: list[float], q: list[float]) -> float:
    """
    Calculate the Jensen-Shannon Divergence between two probability distributions.
    Bounded in [0.0, 1.0].
    """
    if len(p) != len(q):
        raise ValueError("Distributions must have the same length")

    # Add epsilon to prevent log(0)
    eps = 1e-9
    p_dist = [val + eps for val in p]
    q_dist = [val + eps for val in q]

    # Normalize to ensure they are true probability distributions
    sum_p = sum(p_dist)
    sum_q = sum(q_dist)
    p_dist = [val / sum_p for val in p_dist]
    q_dist = [val / sum_q for val in q_dist]

    # Average distribution M
    m = [0.5 * (p_val + q_val) for p_val, q_val in zip(p_dist, q_dist)]

    def kl_divergence(a: list[float], b: list[float]) -> float:
        return sum(a_val * math.log2(a_val / b_val) for a_val, b_val in zip(a, b))

    # JS Divergence is average of KL divergences to M
    jsd = 0.5 * kl_divergence(p_dist, m) + 0.5 * kl_divergence(q_dist, m)
    
    # Clip just in case of small floating-point errors
    return max(0.0, min(1.0, jsd))


# ── Composite Bias Score ───────────────────────────────────────────────────


def compute_bias_score(
    publisher_sentiment: float,
    avg_sentiment: float,
    publisher_framing: FramingVector,
    avg_framing: FramingVector,
    publisher_salience: dict[str, float],
    avg_salience: dict[str, float],
    w1: float = 0.4,
    w2: float = 0.4,
    w3: float = 0.2,
) -> float:
    """
    Compute signed composite bias score for a publisher.
    Signed by the direction of the publisher's sentiment deviation relative to the average.

    Formula:
    BiasScore = sign(SentimentDeviation) * (w1 * DeltaSentiment + w2 * JSDivergence + w3 * DeltaSalience)
    Bounded in [-1.0, 1.0].
    """
    # 1. Delta Sentiment (normalized to [0, 1])
    # Max sentiment diff is 2.0 (-1.0 to 1.0), so we divide by 2.0 to normalize
    delta_sentiment = abs(publisher_sentiment - avg_sentiment) / 2.0

    # 2. Framing Divergence (JSD)
    p_framing = [
        publisher_framing.conflict,
        publisher_framing.economic,
        publisher_framing.human_interest,
        publisher_framing.morality,
        publisher_framing.responsibility,
    ]
    q_framing = [
        avg_framing.conflict,
        avg_framing.economic,
        avg_framing.human_interest,
        avg_framing.morality,
        avg_framing.responsibility,
    ]
    js_div = jensen_shannon_divergence(p_framing, q_framing)

    # 3. Delta Entity Salience (Mean Absolute Error of salience over union of entities)
    all_entities = set(publisher_salience.keys()) | set(avg_salience.keys())
    if all_entities:
        salience_diff = sum(
            abs(publisher_salience.get(ent, 0.0) - avg_salience.get(ent, 0.0))
            for ent in all_entities
        )
        # Bounded between 0 and 2.0 (since both sum to 1.0), normalize to [0, 1]
        delta_salience = salience_diff / 2.0
    else:
        delta_salience = 0.0

    # Composite magnitude
    magnitude = w1 * delta_sentiment + w2 * js_div + w3 * delta_salience

    # Sign of bias based on publisher sentiment vs average sentiment
    # Positive: more positive/optimistic sentiment than average
    # Negative: more negative/critical sentiment than average
    sentiment_deviation = publisher_sentiment - avg_sentiment
    sign = 1.0 if sentiment_deviation >= 0.0 else -1.0

    score = sign * magnitude
    return round(max(-1.0, min(1.0, score)), 4)


# ── Divergence Matrix ──────────────────────────────────────────────────────


def compute_pairwise_divergence(
    framing_vectors: dict[str, FramingVector],
) -> dict[str, dict[str, float]]:
    """
    Compute symmetric pairwise Jensen-Shannon Divergence matrix between all publishers.
    """
    publishers = list(framing_vectors.keys())
    matrix: dict[str, dict[str, float]] = {}

    for pub1 in publishers:
        matrix[pub1] = {}
        for pub2 in publishers:
            if pub1 == pub2:
                matrix[pub1][pub2] = 0.0
                continue

            v1 = framing_vectors[pub1]
            v2 = framing_vectors[pub2]

            p = [v1.conflict, v1.economic, v1.human_interest, v1.morality, v1.responsibility]
            q = [v2.conflict, v2.economic, v2.human_interest, v2.morality, v2.responsibility]

            js_div = jensen_shannon_divergence(p, q)
            matrix[pub1][pub2] = round(js_div, 4)

    return matrix
