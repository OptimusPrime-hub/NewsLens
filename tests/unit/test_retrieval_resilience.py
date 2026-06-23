from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.m2_agents.retrieval.base import BaseRetriever
from src.m2_agents.retrieval.failure_simulation import should_fail_callback
from src.m2_agents.retrieval.manager import RetrievalManager
from src.m2_agents.schemas import RetrievedChunk
from src.shared.config import get_settings
from src.shared.exceptions import FallbackExhaustedError, RetrievalError


class FakeRetriever(BaseRetriever):
    def __init__(self, tier: str, *, fail: bool = False, chunks: list[RetrievedChunk] | None = None):
        self._tier = tier
        self._fail = fail
        self._chunks = chunks or []

    @property
    def tier_name(self) -> str:
        return self._tier

    async def retrieve(
        self,
        query: str,
        *,
        filters: dict | None = None,
        top_k: int = 15,
    ) -> list[RetrievedChunk]:
        if self._fail:
            raise RetrievalError(f"{self._tier} failed")
        return self._chunks


def _chunk(tier: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"{tier}_1",
        chunk_text="Relevant article text about the query.",
        publisher="Reuters",
        publish_ts=datetime.now(tz=UTC),
        relevance_score=0.95,
        source_url=f"https://example.com/{tier}",
    )


@pytest.mark.asyncio
async def test_retrieval_falls_back_from_pathway_to_bing() -> None:
    manager = RetrievalManager(
        retrievers=[
            FakeRetriever("pathway", fail=True),
            FakeRetriever("bing", chunks=[_chunk("bing")]),
            FakeRetriever("scraper", chunks=[_chunk("scraper")]),
        ],
    )

    chunks, tier = await manager.retrieve("test query")

    assert tier == "bing"
    assert chunks[0].source_url == "https://example.com/bing"


@pytest.mark.asyncio
async def test_retrieval_falls_back_from_bing_to_scraper() -> None:
    manager = RetrievalManager(
        retrievers=[
            FakeRetriever("pathway", fail=True),
            FakeRetriever("bing", fail=True),
            FakeRetriever("scraper", chunks=[_chunk("scraper")]),
        ],
    )

    chunks, tier = await manager.retrieve("test query")

    assert tier == "scraper"
    assert chunks[0].source_url == "https://example.com/scraper"


@pytest.mark.asyncio
async def test_retrieval_raises_when_every_callback_fails() -> None:
    manager = RetrievalManager(
        retrievers=[
            FakeRetriever("pathway", fail=True),
            FakeRetriever("bing", fail=True),
            FakeRetriever("scraper", fail=True),
        ],
    )

    with pytest.raises(FallbackExhaustedError):
        await manager.retrieve("test query")


@pytest.mark.asyncio
async def test_retrieval_uses_rewritten_query_for_bing() -> None:
    class RecordingRetriever(FakeRetriever):
        def __init__(self, tier: str, *, fail: bool = False, chunks: list[RetrievedChunk] | None = None):
            super().__init__(tier, fail=fail, chunks=chunks)
            self.last_query: str | None = None

        async def retrieve(
            self,
            query: str,
            *,
            filters: dict | None = None,
            top_k: int = 15,
        ) -> list[RetrievedChunk]:
            self.last_query = query
            return await super().retrieve(query, filters=filters, top_k=top_k)

    class FakeRewriter:
        async def rewrite(self, query: str) -> str:
            return f"{query} rewritten"

    primary = RecordingRetriever("pathway", fail=True)
    bing = RecordingRetriever("bing", chunks=[_chunk("bing")])
    scraper = RecordingRetriever("scraper", chunks=[_chunk("scraper")])

    manager = RetrievalManager(
        rewriter=FakeRewriter(),  # type: ignore[arg-type]
        retrievers=[primary, bing, scraper],
    )

    await manager.retrieve("trade policy")

    assert bing.last_query == "trade policy rewritten"


def test_default_primary_is_local_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.m2_agents.retrieval.manager.use_pathway_primary", lambda: False)

    manager = RetrievalManager()

    assert manager._primary.tier_name == "local"


def test_pathway_relevance_score_prefers_similarity_over_distance() -> None:
    from src.m2_agents.retrieval.pathway_client import PathwayRetriever

    assert PathwayRetriever._parse_relevance_score({"score": 0.91}) == 0.91
    assert PathwayRetriever._parse_relevance_score({"dist": 0.25}) == 0.75


@pytest.mark.asyncio
async def test_pathway_simulated_failure_triggers_bing_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.m2_agents.retrieval.failure_simulation import raise_if_simulated
    from src.shared.exceptions import PathwayRetrievalError

    class SimulatedPathwayRetriever(FakeRetriever):
        async def retrieve(
            self,
            query: str,
            *,
            filters: dict | None = None,
            top_k: int = 15,
        ) -> list[RetrievedChunk]:
            raise_if_simulated("pathway", PathwayRetrievalError)
            return await super().retrieve(query, filters=filters, top_k=top_k)

    monkeypatch.setenv("SIMULATE_RETRIEVAL_FAILURES", "pathway")
    get_settings.cache_clear()

    try:
        manager = RetrievalManager(
            retrievers=[
                SimulatedPathwayRetriever("pathway", chunks=[_chunk("pathway")]),
                FakeRetriever("bing", chunks=[_chunk("bing")]),
                FakeRetriever("scraper"),
            ],
        )
        chunks, tier = await manager.retrieve("test query")
        assert tier == "bing"
        assert chunks[0].chunk_id == "bing_1"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_local_primary_accepts_chunks_without_high_scores() -> None:
    low_score_chunk = RetrievedChunk(
        chunk_id="local_1",
        chunk_text="Trade talks between Washington and Beijing continued in Geneva.",
        publisher="Reuters",
        publish_ts=datetime.now(tz=UTC),
        relevance_score=0.15,
        source_url="https://example.com/local",
    )

    manager = RetrievalManager(
        retrievers=[
            FakeRetriever("local", chunks=[low_score_chunk]),
            FakeRetriever("bing", fail=True),
            FakeRetriever("scraper", chunks=[_chunk("scraper")]),
        ],
    )

    chunks, tier = await manager.retrieve("US China trade")

    assert tier == "local"
    assert chunks[0].chunk_id == "local_1"


def test_simulated_failure_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMULATE_RETRIEVAL_FAILURES", "pathway,bing")
    get_settings.cache_clear()

    try:
        assert should_fail_callback("pathway") is True
        assert should_fail_callback("bing") is True
        assert should_fail_callback("scraper") is False
    finally:
        get_settings.cache_clear()
