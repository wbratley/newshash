import json
import logging
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(".cache")


def _path(key: str) -> Path:
    _CACHE_DIR.mkdir(exist_ok=True)
    return _CACHE_DIR / f"{date.today().isoformat()}_{key}.json"


def load_today(key: str) -> dict | None:
    path = _path(key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as exc:
        logger.warning("Cache read failed (%s): %s", key, exc)
        return None


def save_today(key: str, data: dict) -> None:
    try:
        _path(key).write_text(json.dumps(data))
        logger.info("Cached response under key '%s'", key)
    except Exception as exc:
        logger.warning("Cache write failed (%s): %s", key, exc)
