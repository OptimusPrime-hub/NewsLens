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
from src.m3_bias.schemas import FramingVector
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
