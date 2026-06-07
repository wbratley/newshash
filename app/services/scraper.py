import asyncio
import logging

import httpx
import trafilatura

logger = logging.getLogger(__name__)

MIN_BODY_CHARS = 200
SCRAPE_CONCURRENCY = 6
REQUEST_TIMEOUT = 12.0
WAYBACK_API = "https://archive.org/wayback/available"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


def _extract(html: str) -> str:
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
    )
    return text or ""


async def _fetch_direct(client: httpx.AsyncClient, url: str) -> str:
    try:
        r = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        return await asyncio.to_thread(_extract, r.text)
    except Exception as exc:
        logger.debug("Direct fetch failed %s: %s", url, exc)
        return ""


async def _fetch_wayback(client: httpx.AsyncClient, url: str) -> str:
    try:
        r = await client.get(
            WAYBACK_API, params={"url": url}, timeout=REQUEST_TIMEOUT
        )
        snapshot_url = (
            r.json()
            .get("archived_snapshots", {})
            .get("closest", {})
            .get("url", "")
        )
        if not snapshot_url:
            logger.debug("No Wayback snapshot for %s", url)
            return ""
        r2 = await client.get(
            snapshot_url, timeout=REQUEST_TIMEOUT * 1.5, follow_redirects=True
        )
        r2.raise_for_status()
        return await asyncio.to_thread(_extract, r2.text)
    except Exception as exc:
        logger.debug("Wayback fetch failed %s: %s", url, exc)
        return ""


async def _scrape_one(
    sem: asyncio.Semaphore, client: httpx.AsyncClient, url: str
) -> tuple[str, str]:
    async with sem:
        body = await _fetch_direct(client, url)
        if len(body) < MIN_BODY_CHARS:
            logger.debug(
                "Direct thin (%d chars) for %s — trying Wayback", len(body), url
            )
            wayback = await _fetch_wayback(client, url)
            if len(wayback) > len(body):
                body = wayback
        level = "full" if len(body) >= MIN_BODY_CHARS else "none"
        logger.info("Scraped %s [%s, %d chars]", url, level, len(body))
        return url, body


async def fetch_article_bodies(urls: list[str]) -> dict[str, str]:
    """Fetch and extract article body text for each URL. Returns url → body mapping."""
    if not urls:
        return {}
    sem = asyncio.Semaphore(SCRAPE_CONCURRENCY)
    async with httpx.AsyncClient(headers=_HEADERS) as client:
        pairs = await asyncio.gather(
            *[_scrape_one(sem, client, url) for url in urls]
        )
    return dict(pairs)
