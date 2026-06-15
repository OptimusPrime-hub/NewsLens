from datetime import datetime
from pydantic import BaseModel, Field

class SentimentScores(BaseModel):
    positive: float
    neutral: float
    negative: float
    compound: float  # net score in [-1, 1]

class FramingVector(BaseModel):
    conflict: float
    economic: float
    human_interest: float
    morality: float
    responsibility: float

class PublisherBiasProfile(BaseModel):
    publisher: str
    sentiment: SentimentScores
    framing: FramingVector
    entity_salience: dict[str, float]  # entity → salience score
    bias_score: float  # [-1.0, 1.0]
    supporting_quotes: list[str]

class BiasAnalysisResult(BaseModel):
    topic: str
    analysis_timestamp: datetime
    publisher_profiles: list[PublisherBiasProfile]
    pairwise_divergence_matrix: dict[str, dict[str, float]]
    summary_explanation: str
    confidence: float
