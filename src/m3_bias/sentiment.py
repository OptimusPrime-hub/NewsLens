"""
Sentiment analysis module.
Primary: cardiffnlp/twitter-roberta-base-sentiment-latest
Fallback: VADER (vaderSentiment)
"""

from __future__ import annotations

from src.m3_bias.schemas import SentimentScores
from src.shared.cache import get_cached_model
from src.shared.logging import get_logger

logger = get_logger(__name__)


class SentimentAnalyzer:
    """
    Computes sentiment polarity scores for text.
    Uses lightweight VADER by default. RoBERTa remains available for local
    experiments by passing use_fallback_only=False.
    """

    def __init__(self, use_fallback_only: bool = True):
        self.use_fallback_only = use_fallback_only
        self._vader_analyzer = None

    def _get_vader(self):
        if self._vader_analyzer is None:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self._vader_analyzer = SentimentIntensityAnalyzer()
        return self._vader_analyzer

    def analyze(self, text: str) -> SentimentScores:
        """
        Analyze the sentiment of a given text.
        Returns a SentimentScores object.
        """
        if not text.strip():
            return SentimentScores(positive=0.0, neutral=1.0, negative=0.0, compound=0.0)

        if self.use_fallback_only:
            return self._analyze_vader(text)

        try:
            # Attempt to run primary RoBERTa model
            return self._analyze_roberta(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Primary RoBERTa sentiment failed, falling back to VADER",
                error=str(exc),
            )
            return self._analyze_vader(text)

    def _analyze_roberta(self, text: str) -> SentimentScores:
        """Analyze sentiment using CardiffNLP RoBERTa via cached pipeline."""
        from transformers import pipeline

        def load_pipeline():
            # CardiffNLP returns label mappings for negative, neutral, positive
            return pipeline(
                "sentiment-analysis",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                tokenizer="cardiffnlp/twitter-roberta-base-sentiment-latest",
                device=-1,  # CPU
                max_length=512,
                truncation=True,
            )

        nlp = get_cached_model("roberta_sentiment_pipeline", load_pipeline)
        results = nlp(text)

        # CardiffNLP outputs labels like "negative", "neutral", "positive" (or "label_0", etc.)
        # Let's map label -> score
        # Sometimes results is a list of dicts, sometimes it is a single dict.
        if isinstance(results, list):
            result = results[0]
        else:
            result = results

        label = result["label"].lower()
        score = result["score"]

        # Default fallback values
        pos, neu, neg = 0.0, 0.0, 0.0

        if "positive" in label or "pos" in label:
            pos = score
            neu = 1.0 - score
        elif "negative" in label or "neg" in label:
            neg = score
            neu = 1.0 - score
        else:
            neu = score
            pos = (1.0 - score) / 2
            neg = (1.0 - score) / 2

        # Net compound score bounded in [-1.0, 1.0]
        compound = pos - neg

        return SentimentScores(
            positive=round(pos, 4),
            neutral=round(neu, 4),
            negative=round(neg, 4),
            compound=round(compound, 4),
        )

    def _analyze_vader(self, text: str) -> SentimentScores:
        """Analyze sentiment using VADER SentimentIntensityAnalyzer."""
        analyzer = self._get_vader()
        scores = analyzer.polarity_scores(text)

        # Map VADER compound (-1 to 1) and pos, neu, neg (0 to 1)
        return SentimentScores(
            positive=round(scores["pos"], 4),
            neutral=round(scores["neu"], 4),
            negative=round(scores["neg"], 4),
            compound=round(scores["compound"], 4),
        )
