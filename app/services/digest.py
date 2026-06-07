import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.schemas import NewsResponse
from app.services.cache import load_today, save_today
from app.services.clustering import cluster_stories
from app.services.rss import fetch_all_feeds
from app.services.scraper import fetch_article_bodies
from app.services.synthesis import synthesise_cluster

logger = logging.getLogger(__name__)

_CACHE_KEY = "news"
_lock = asyncio.Lock()


async def get_or_generate() -> dict:
    """Return today's digest from cache, generating it first if needed."""
    cached = load_today(_CACHE_KEY)
    if cached:
        return cached

    async with _lock:
        cached = load_today(_CACHE_KEY)
        if cached:
            return cached

        logger.info("No cache for today — generating digest")
        stories = await fetch_all_feeds()
        clusters = cluster_stories(stories)[: settings.max_clusters]

        # Fetch full article text for clustered articles.
        # Some outlets include full text in <content:encoded> — those already have body set.
        # Only scrape the remainder.
        cluster_stories_flat = [s for cluster in clusters for s in cluster]
        from_feed = sum(1 for s in cluster_stories_flat if len(s["body"]) >= 200)
        to_scrape = list({s["url"] for s in cluster_stories_flat if s["url"] and len(s["body"]) < 200})
        logger.info(
            "%d articles have full text from feed; scraping %d more",
            from_feed, len(to_scrape),
        )
        bodies = await fetch_article_bodies(to_scrape)
        for s in cluster_stories_flat:
            if len(s["body"]) < 200:
                s["body"] = bodies.get(s["url"], "")

        total_usable = sum(1 for s in cluster_stories_flat if len(s["body"]) >= 200)
        logger.info(
            "Usable body text: %d / %d articles",
            total_usable, len(cluster_stories_flat),
        )

        synthesised = await asyncio.gather(
            *[synthesise_cluster(f"cluster-{i}", cluster) for i, cluster in enumerate(clusters)]
        )

        result = NewsResponse(
            generated_at=datetime.now(timezone.utc),
            cluster_count=len(synthesised),
            clusters=list(synthesised),
        )
        data = result.model_dump(mode="json")
        save_today(_CACHE_KEY, data)
        return data
