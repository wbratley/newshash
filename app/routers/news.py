import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.config import settings
from app.schemas import NewsResponse
from app.services.cache import load_today, save_today
from app.services.clustering import cluster_stories
from app.services.rss import fetch_all_feeds
from app.services.synthesis import synthesise_cluster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/today", response_model=NewsResponse, summary="Get today's news synthesised from all sources")
async def get_today(
    max_clusters: int = Query(
        default=None,
        ge=1,
        le=100,
        description="Maximum number of topic clusters to return (default from config)",
    )
) -> NewsResponse:
    limit = max_clusters if max_clusters is not None else settings.max_clusters
    cache_key = f"news_{limit}"

    cached = load_today(cache_key)
    if cached:
        logger.info("Serving today's news from cache (key=%s)", cache_key)
        return NewsResponse.model_validate(cached)

    stories = await fetch_all_feeds()
    clusters = cluster_stories(stories)[:limit]

    synthesised = await asyncio.gather(
        *[synthesise_cluster(f"cluster-{i}", cluster) for i, cluster in enumerate(clusters)]
    )

    result = NewsResponse(
        generated_at=datetime.now(timezone.utc),
        cluster_count=len(synthesised),
        clusters=list(synthesised),
    )
    save_today(cache_key, result.model_dump(mode="json"))
    return result
