"""
M0 — Playwright Scraper Connector  (Tier-3 Retrieval Fallback)
Fetches JS-rendered article pages when NewsAPI and RSS both fail to
return sufficient relevant chunks.  Called on-demand by M2's
RetrievalManager — NOT part of the background pw.run() loop.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from loguru import logger

from src.m0_ingestion.schemas import RawArticle


async def scrape_url(url: str, source_name: str = "web") -> RawArticle | None:
    """
    Asynchronously scrape a single URL with Playwright and return a
    RawArticle, or None if scraping fails.
    """
    try:
        from playwright.async_api import async_playwright  # lazy import
    except ImportError:
        logger.error("[Scraper] playwright not installed — `pip install playwright` + `playwright install chromium`")
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=20_000)

            # Extract visible text — prefer article body selectors
            content = ""
            for selector in ("article", "main", '[role="main"]', "body"):
                try:
                    el = await page.query_selector(selector)
                    if el:
                        content = (await el.inner_text()).strip()
                        if len(content) > 200:
                            break
                except Exception:
                    continue

            title = await page.title()
            await browser.close()

        if not content:
            logger.warning(f"[Scraper] No content extracted from {url}")
            return None

        return RawArticle(
            url=url,
            title=title or url,
            content=content[:8000],  # cap to avoid embedding overflows
            publish_ts=datetime.now(timezone.utc),
            source_name=source_name,
        )

    except Exception as exc:
        logger.error(f"[Scraper] Failed to scrape {url}: {exc}")
        return None


def scrape_url_sync(url: str, source_name: str = "web") -> RawArticle | None:
    """Synchronous wrapper around `scrape_url` for use in non-async contexts."""
    try:
        return asyncio.run(scrape_url(url, source_name))
    except RuntimeError:
        # Already inside an event loop (e.g. Jupyter / FastAPI)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(scrape_url(url, source_name))


async def scrape_urls(
    urls: list[tuple[str, str]],  # (url, source_name)
    concurrency: int = 3,
) -> list[RawArticle]:
    """
    Scrape multiple URLs concurrently, bounded by *concurrency*.
    Returns only successful RawArticle results.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _bounded(url: str, name: str) -> RawArticle | None:
        async with semaphore:
            return await scrape_url(url, name)

    results = await asyncio.gather(*[_bounded(u, n) for u, n in urls])
    articles = [r for r in results if r is not None]
    logger.info(f"[Scraper] Scraped {len(articles)}/{len(urls)} URLs successfully")
    return articless