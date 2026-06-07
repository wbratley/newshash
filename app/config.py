import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    max_clusters: int = 10
    cluster_similarity_threshold: float = 0.25
    feed_timeout_seconds: int = 10
    site_url: str = "https://newshash.com"


settings = Settings()

SOURCES: list[dict] = [
    {
        "outlet": "Morning Star",
        "lean": "left",
        "feed_url": "https://morningstaronline.co.uk/rss.xml",
    },
    {
        "outlet": "The Guardian",
        "lean": "left",
        "feed_url": "https://www.theguardian.com/uk/rss",
    },
    {
        "outlet": "The Mirror",
        "lean": "centre-left",
        "feed_url": "https://www.mirror.co.uk/rss.xml",
    },
    {
        "outlet": "BBC News",
        "lean": "centre-left",
        "feed_url": "http://feeds.bbci.co.uk/news/rss.xml",
    },
    {
        "outlet": "The Independent",
        "lean": "centre-left",
        "feed_url": "https://www.independent.co.uk/news/uk/rss",
    },
    {
        "outlet": "i Paper",
        "lean": "centre",
        "feed_url": "https://inews.co.uk/feed",
    },
    {
        "outlet": "City AM",
        "lean": "centre-right",
        "feed_url": "https://www.cityam.com/feed/",
    },
    {
        "outlet": "Daily Mail",
        "lean": "right",
        "feed_url": "https://www.dailymail.co.uk/articles.rss",
    },
    {
        "outlet": "The Sun",
        "lean": "right",
        "feed_url": "https://www.thesun.co.uk/feed/",
    },
    {
        "outlet": "GB News",
        "lean": "right",
        "feed_url": "https://www.gbnews.com/feeds/news.rss",
    },
]
