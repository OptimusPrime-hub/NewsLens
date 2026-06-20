"""
Retrieval package — provides the BaseRetriever protocol and concrete
implementations (Pathway, Bing, Scraper) plus the orchestrating manager.
"""

from src.m2_agents.retrieval.base import BaseRetriever
from src.m2_agents.retrieval.filters import RetrievalFilters, build_filters
from src.m2_agents.retrieval.manager import RetrievalManager

__all__ = [
    "BaseRetriever",
    "RetrievalFilters",
    "RetrievalManager",
    "build_filters",
]
