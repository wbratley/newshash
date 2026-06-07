import asyncio
import logging
from typing import TypedDict

import feedparser
import httpx

from app.config import SOURCES, settings

logger = logging.getLogger(__name__)


class RawStory(TypedDict):
    outlet: str
    lean: str
    title: str
    summary: str
    url: str
    published: str | None
    body: str  # scraped article text; empty until filled by scraper


async def _fetch_feed(client: httpx.AsyncClient, source: dict) -> list[RawStory]:
    try:
        response = await client.get(
            source["feed_url"],
            timeout=settings.feed_timeout_seconds,
            follow_redirects=True,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.text)
        stories: list[RawStory] = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if not title:
                continue
            feed_body = _content_encoded(entry)
            stories.append(
                RawStory(
                    outlet=source["outlet"],
                    lean=source["lean"],
                    title=title,
                    summary=_clean_summary(entry.get("summary", "")),
                    url=entry.get("link", ""),
                    published=entry.get("published", None),
                    body=feed_body,
                )
            )
        logger.info("Fetched %d stories from %s", len(stories), source["outlet"])
        return stories
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", source["outlet"], exc)
        return []


def _clean_summary(raw: str) -> str:
    """Strip HTML tags from feed summaries."""
    import re
    return re.sub(r"<[^>]+>", "", raw).strip()


def _content_encoded(entry) -> str:
    """Extract full article text from <content:encoded> if substantially longer than a snippet."""
    import re
    for content in entry.get("content", []):
        val = content.get("value", "")
        if val:
            text = re.sub(r"<[^>]+>", "", val).strip()
            if len(text) >= 500:
                return text
    return ""


async def fetch_all_feeds() -> list[RawStory]:
    async with httpx.AsyncClient(
        headers={"User-Agent": "Newshash/1.0 RSS reader"}
    ) as client:
        results = await asyncio.gather(
            *[_fetch_feed(client, source) for source in SOURCES]
        )
    stories: list[RawStory] = []
    for batch in results:
        stories.extend(batch)
    logger.info("Total stories fetched: %d", len(stories))
    return stories
