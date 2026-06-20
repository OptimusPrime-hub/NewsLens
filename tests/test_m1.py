from src.m1_intent.classifier import _heuristic_intent
from src.m1_intent.schemas import IntentType


def test_heuristic_intent_bias():
    query = "Compare how Fox News and CNN covered the election"
    assert _heuristic_intent(query) == IntentType.BIAS_DETECTION

def test_heuristic_intent_timeline():
    query = "What is the timeline of the bank collapse?"
    assert _heuristic_intent(query) == IntentType.TIMELINE

def test_heuristic_intent_summary():
    query = "What is going on with the tech stocks right now?"
    assert _heuristic_intent(query) == IntentType.CROSS_PUBLISHER_SUMMARY
