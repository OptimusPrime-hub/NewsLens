"""
Unit tests for Module 3 (Bias & Sentiment Engine).
Mocks out transformers, torch, and spacy to run fast and fully offline.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

# ── Mock Heavy Imports ────────────────────────────────────────────────────────
mock_transformers = MagicMock()
sys.modules["transformers"] = mock_transformers

mock_torch = MagicMock()
sys.modules["torch"] = mock_torch

mock_spacy = MagicMock()
mock_spacy.load.side_effect = Exception("spaCy model download required")
mock_spacy.blank.side_effect = Exception("spaCy model download required")
sys.modules["spacy"] = mock_spacy

from datetime import datetime, timezone
import pytest

from src.m2_agents.schemas import RetrievedChunk
from src.m3_bias.engine import BiasEngine
from src.m3_bias.schemas import FramingVector
from src.m3_bias.scoring import (
    compute_bias_score,
    compute_pairwise_divergence,
    extract_entity_salience,
    jensen_shannon_divergence,
)
from src.m3_bias.sentiment import SentimentAnalyzer


# ── Sentiment Tests ───────────────────────────────────────────────────────────


def test_sentiment_vader_fallback():
    """Verify VADER sentiment fallback works and produces scores in bounds."""
    analyzer = SentimentAnalyzer(use_fallback_only=True)
    
    # Test positive text
    scores = analyzer.analyze("This is a wonderful, fantastic, and positive news story!")
    assert scores.positive > 0.0
    assert scores.compound > 0.0
    assert -1.0 <= scores.compound <= 1.0

    # Test negative text
    scores = analyzer.analyze("This is a horrible, terrible, and disastrous event.")
    assert scores.negative > 0.0
    assert scores.compound < 0.0
    assert -1.0 <= scores.compound <= 1.0

    # Test empty text
    empty_scores = analyzer.analyze("")
    assert empty_scores.neutral == 1.0
    assert empty_scores.compound == 0.0


def test_sentiment_roberta_success():
    """Test RoBERTa sentiment classification with mocked pipeline response."""
    mock_nlp = MagicMock()
    mock_nlp.return_value = [{"label": "positive", "score": 0.95}]
    mock_transformers.pipeline.return_value = mock_nlp

    from src.shared import cache
    cache._model_cache.clear()

    analyzer = SentimentAnalyzer(use_fallback_only=False)
    scores = analyzer.analyze("Excellent news!")
    
    assert scores.positive == 0.95
    assert scores.compound == 0.95


# ── Framing Extractor Tests ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_framing_extractor_success():
    """Test framing vector extraction using structured LLM output."""
    from src.m3_bias.framing import FramingExtractor

    mock_llm = MagicMock()
    mock_structured_llm = AsyncMock()
    mock_structured_llm.ainvoke.return_value = FramingVector(
        conflict=1.0, economic=0.5, human_interest=0.0, morality=0.0, responsibility=0.5
    )
    mock_llm.with_structured_output.return_value = mock_structured_llm

    with patch("src.m3_bias.framing.get_chat_model_with_fallback", return_value=mock_llm):
        extractor = FramingExtractor()
        vector = await extractor.extract("Reuters", "Trade War", "Some text")

        # Result should be normalized so elements sum to 1.0
        assert round(sum([vector.conflict, vector.economic, vector.human_interest, vector.morality, vector.responsibility]), 2) == 1.0
        assert vector.conflict == 0.5  # 1.0 / 2.0
        assert vector.economic == 0.25  # 0.5 / 2.0


# ── Scoring and Divergence Tests ──────────────────────────────────────────────


def test_jensen_shannon_divergence():
    """Test JS divergence calculation on identical and differing distributions."""
    p = [0.2, 0.2, 0.2, 0.2, 0.2]
    q = [0.2, 0.2, 0.2, 0.2, 0.2]

    # Identical distributions should have 0 divergence
    assert jensen_shannon_divergence(p, q) == 0.0

    # Totally differing distributions
    p2 = [1.0, 0.0, 0.0, 0.0, 0.0]
    q2 = [0.0, 1.0, 0.0, 0.0, 0.0]
    jsd = jensen_shannon_divergence(p2, q2)
    assert jsd > 0.0
    assert jsd <= 1.0


def test_compute_bias_score():
    """Test BiasScore computation with signed logic."""
    p_framing = FramingVector(conflict=0.5, economic=0.1, human_interest=0.1, morality=0.1, responsibility=0.2)
    avg_framing = FramingVector(conflict=0.2, economic=0.2, human_interest=0.2, morality=0.2, responsibility=0.2)

    # Positive sentiment deviation -> positive bias score
    score_pos = compute_bias_score(
        publisher_sentiment=0.5,
        avg_sentiment=0.1,
        publisher_framing=p_framing,
        avg_framing=avg_framing,
        publisher_salience={"Apple": 0.8},
        avg_salience={"Apple": 0.4},
    )
    assert score_pos > 0.0

    # Negative sentiment deviation -> negative bias score
    score_neg = compute_bias_score(
        publisher_sentiment=-0.5,
        avg_sentiment=0.0,
        publisher_framing=p_framing,
        avg_framing=avg_framing,
        publisher_salience={"Apple": 0.8},
        avg_salience={"Apple": 0.4},
    )
    assert score_neg < 0.0


def test_entity_salience_fallback():
    """Test regex fallback entity salience extraction when spacy fails/is mocked out."""
    text = "Apple Inc. released Apple iPhone. Google released Android. Google and Apple compete."
    salience = extract_entity_salience(text)

    # "Apple" and "Google" are extracted from text via regex fallback
    assert len(salience) > 0
    assert any("Apple" in name for name in salience)
    assert any("Google" in name for name in salience)
    assert round(sum(salience.values()), 2) == 1.0


def test_pairwise_divergence():
    """Test generation of the divergence matrix."""
    vectors = {
        "Reuters": FramingVector(conflict=0.5, economic=0.1, human_interest=0.1, morality=0.1, responsibility=0.2),
        "Fox": FramingVector(conflict=0.1, economic=0.5, human_interest=0.1, morality=0.1, responsibility=0.2),
    }
    matrix = compute_pairwise_divergence(vectors)
    
    assert "Reuters" in matrix
    assert "Fox" in matrix
    assert matrix["Reuters"]["Fox"] == matrix["Fox"]["Reuters"]
    assert matrix["Reuters"]["Reuters"] == 0.0


# ── Engine Orchestration Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bias_engine_flow():
    """Test E2E BiasEngine analysis with mocked LLM framing and explanation."""
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            chunk_text="Reuters news text highlighting political conflict.",
            publisher="Reuters",
            publish_ts=datetime.now(tz=timezone.utc),
            relevance_score=0.85,
        ),
        RetrievedChunk(
            chunk_id="c2",
            chunk_text="Fox News text covering economic implications.",
            publisher="Fox News",
            publish_ts=datetime.now(tz=timezone.utc),
            relevance_score=0.88,
        ),
    ]

    mock_llm = MagicMock()
    mock_structured_llm = AsyncMock()
    mock_structured_llm.ainvoke.return_value = FramingVector(
        conflict=0.4, economic=0.2, human_interest=0.1, morality=0.1, responsibility=0.2
    )
    mock_llm.with_structured_output.return_value = mock_structured_llm

    mock_explanation_response = MagicMock()
    mock_explanation_response.content = "This is a detailed analysis of publisher bias."
    mock_llm.ainvoke = AsyncMock(return_value=mock_explanation_response)

    with patch("src.m3_bias.framing.get_chat_model_with_fallback", return_value=mock_llm), \
         patch("src.m3_bias.engine.get_chat_model_with_fallback", return_value=mock_llm):
        
        engine = BiasEngine(use_fallback_sentiment=True)
        result = await engine.analyze("US Trade Policy", chunks)

        assert result.topic == "US Trade Policy"
        assert len(result.publisher_profiles) == 2
        
        # Verify profiles exist for Reuters and Fox News
        pubs = [p.publisher for p in result.publisher_profiles]
        assert "Reuters" in pubs
        assert "Fox News" in pubs
        
        # Verify divergence matrix was calculated
        assert "Reuters" in result.pairwise_divergence_matrix
        assert result.summary_explanation == "This is a detailed analysis of publisher bias."
        assert result.confidence > 0.0
