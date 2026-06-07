#!/usr/bin/env python3
"""
Audit each RSS feed: how much text is in the feed itself, and how much
can we get by scraping the article URL directly vs. Wayback Machine.

Samples up to SAMPLE_SIZE articles per outlet.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import feedparser

from app.config import SOURCES, settings
from app.services.scraper import fetch_article_bodies, MIN_BODY_CHARS
from app.services.rss import _clean_summary

SAMPLE_SIZE = 3  # articles to probe per outlet


def _rss_summary_len(entry) -> int:
    raw = entry.get("summary", "") or ""
    return len(_clean_summary(raw))


def _content_len(entry) -> int:
    """Some feeds include full article text in <content:encoded>."""
    for content in entry.get("content", []):
        val = content.get("value", "")
        if val:
            return len(_clean_summary(val))
    return 0


async def audit_outlet(client: httpx.AsyncClient, source: dict) -> dict:
    outlet = source["outlet"]
    try:
        r = await client.get(source["feed_url"], timeout=settings.feed_timeout_seconds, follow_redirects=True)
        r.raise_for_status()
        feed = feedparser.parse(r.text)
    except Exception as exc:
        return {"outlet": outlet, "error": str(exc)}

    entries = [e for e in feed.entries if e.get("title")]
    sample = entries[:SAMPLE_SIZE]
    if not sample:
        return {"outlet": outlet, "error": "no entries"}

    feed_summary_lens = [_rss_summary_len(e) for e in sample]
    feed_content_lens = [_content_len(e) for e in sample]
    urls = [e.get("link", "") for e in sample if e.get("link")]

    bodies = await fetch_article_bodies(urls)

    scraped_lens = [len(bodies.get(u, "")) for u in urls]

    return {
        "outlet": outlet,
        "lean": source["lean"],
        "sample": len(sample),
        "feed_summary": {
            "min": min(feed_summary_lens),
            "max": max(feed_summary_lens),
            "avg": int(sum(feed_summary_lens) / len(feed_summary_lens)),
        },
        "feed_content": {
            "present": any(l > 0 for l in feed_content_lens),
            "avg": int(sum(feed_content_lens) / len(feed_content_lens)) if feed_content_lens else 0,
        },
        "scraped": {
            "min": min(scraped_lens) if scraped_lens else 0,
            "max": max(scraped_lens) if scraped_lens else 0,
            "avg": int(sum(scraped_lens) / len(scraped_lens)) if scraped_lens else 0,
            "usable": sum(1 for l in scraped_lens if l >= MIN_BODY_CHARS),
            "of": len(scraped_lens),
        },
        "sample_urls": urls,
    }


def _bar(n: int, scale: int = 50) -> str:
    filled = min(n // scale, 80)
    return "█" * filled


async def main():
    print(f"Auditing {len(SOURCES)} outlets ({SAMPLE_SIZE} articles each)…\n")
    async with httpx.AsyncClient(headers={"User-Agent": "Newshash/1.0 RSS reader"}) as client:
        results = await asyncio.gather(*[audit_outlet(client, s) for s in SOURCES])

    print(f"{'Outlet':<20} {'Lean':<14} {'Feed summary':>14} {'Feed full text':>14} {'Scraped body':>14}  {'Usable':>6}")
    print("─" * 90)
    for r in results:
        if "error" in r:
            print(f"{r['outlet']:<20}  ERROR: {r['error']}")
            continue
        feed_full = f"avg {r['feed_content']['avg']:,}c" if r['feed_content']['present'] else "—"
        print(
            f"{r['outlet']:<20} {r['lean']:<14} "
            f"avg {r['feed_summary']['avg']:>5,}c   "
            f"{feed_full:>14}   "
            f"avg {r['scraped']['avg']:>6,}c   "
            f"{r['scraped']['usable']}/{r['scraped']['of']}"
        )

    print("\n── Detail ──────────────────────────────────────────────────────────────────────")
    for r in results:
        if "error" in r:
            continue
        print(f"\n{r['outlet']} ({r['lean']})")
        print(f"  Feed summary:   {r['feed_summary']['min']}–{r['feed_summary']['max']} chars (avg {r['feed_summary']['avg']})")
        if r['feed_content']['present']:
            print(f"  Feed <content>: avg {r['feed_content']['avg']} chars  ← FULL TEXT IN FEED")
        else:
            print(f"  Feed <content>: not present")
        print(f"  Scraped body:   {r['scraped']['min']}–{r['scraped']['max']} chars (avg {r['scraped']['avg']}), "
              f"{r['scraped']['usable']}/{r['scraped']['of']} usable (≥{MIN_BODY_CHARS}c)")
        for url in r['sample_urls']:
            print(f"    {url}")


if __name__ == "__main__":
    asyncio.run(main())
