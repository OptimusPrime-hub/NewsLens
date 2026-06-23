"""Demo news articles for local manual testing without live API keys."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from src.m0_ingestion.pipeline import get_pipeline
from src.m0_ingestion.schemas import RawArticle
from src.shared.config import get_settings
from src.shared.logging import get_logger

logger = get_logger(__name__)

DEMO_ARTICLES: list[dict[str, str]] = [
    {
        "url": "https://example.com/reuters-trade-2026",
        "title": "US and China resume trade talks after tariff pause",
        "source_name": "Reuters",
        "content": (
            "Washington and Beijing agreed to a 90-day pause on new tariffs while negotiators "
            "met in Geneva. Officials from both sides described the talks as constructive, "
            "focusing on technology export controls and agricultural market access. "
            "Analysts said markets reacted positively to signs of de-escalation."
        ),
    },
    {
        "url": "https://example.com/fox-trade-2026",
        "title": "Critics warn US trade concessions could weaken American workers",
        "source_name": "Fox News",
        "content": (
            "Conservative lawmakers criticized the administration for considering tariff relief "
            "without securing stronger commitments from China on intellectual property theft. "
            "Manufacturing groups warned that any deal must protect domestic jobs and supply chains. "
            "The White House pushed back, saying negotiations remain focused on fair trade."
        ),
    },
    {
        "url": "https://example.com/bbc-trade-2026",
        "title": "Global markets rise as US-China trade tensions ease",
        "source_name": "BBC",
        "content": (
            "European and Asian stocks climbed after reports that Washington and Beijing would "
            "extend a tariff truce. Investors cited reduced uncertainty for semiconductor and "
            "automotive supply chains. Economists cautioned that structural disputes over "
            "technology and national security remain unresolved."
        ),
    },
    {
        "url": "https://example.com/cnn-trade-2026",
        "title": "Timeline: Key moments in the latest US-China trade dispute",
        "source_name": "CNN",
        "content": (
            "January: New tariffs announced on select imports. "
            "March: Retaliatory measures from Beijing target US agricultural goods. "
            "May: Diplomatic backchannel opens after G7 summit. "
            "June: Geneva talks produce a temporary pause. "
            "Analysts say the sequence shows familiar cycles of escalation and negotiation."
        ),
    },
    {
        "url": "https://example.com/ap-trade-2026",
        "title": "Farmers hope trade pause brings relief to export markets",
        "source_name": "Associated Press",
        "content": (
            "Midwestern farmers welcomed news of renewed talks, saying prior tariffs had "
            "disrupted soybean and corn shipments to China. Agricultural exporters urged "
            "negotiators to restore predictable market access. Trade associations noted "
            "that commodity prices remain volatile despite the diplomatic thaw."
        ),
    },
]


def _article_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def _to_raw_articles() -> list[RawArticle]:
    now = datetime.now(tz=UTC)
    return [
        RawArticle(
            url=item["url"],
            title=item["title"],
            content=item["content"],
            publish_ts=now,
            source_name=item["source_name"],
        )
        for item in DEMO_ARTICLES
    ]


def _write_pathway_json(target: Path, articles: list[RawArticle]) -> int:
    target.mkdir(parents=True, exist_ok=True)
    written = 0
    for article in articles:
        path = target / f"{_article_id(article.url)}.json"
        path.write_text(article.model_dump_json(), encoding="utf-8")
        written += 1
    return written


def seed_demo_data(*, reset: bool = False) -> dict[str, int | str]:
    """Populate in-process store and Pathway JSON folder with demo articles."""
    settings = get_settings()
    target = Path(settings.pathway_source_glob.split("*", 1)[0]).resolve()
    articles = _to_raw_articles()

    pipeline = get_pipeline()
    if reset:
        pipeline._chunk_store.clear()  # noqa: SLF001

    before = pipeline.chunk_count
    pipeline._process_raw_articles(articles)  # noqa: SLF001
    after = pipeline.chunk_count

    json_written = _write_pathway_json(target, articles)

    summary: dict[str, int | str] = {
        "articles": len(articles),
        "chunks_added": after - before,
        "total_chunks": after,
        "json_files": json_written,
        "pathway_dir": str(target),
    }
    logger.info("Demo data seeded", **{k: str(v) for k, v in summary.items()})
    return summary
