import json
import logging
import re
from datetime import date
from pathlib import Path

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(".cache")


def _fs_path(key: str) -> Path:
    _CACHE_DIR.mkdir(exist_ok=True)
    return _CACHE_DIR / f"{date.today().isoformat()}_{key}.json"


def load_today(key: str) -> dict | None:
    try:
        path = _fs_path(key)
        return json.loads(path.read_text()) if path.exists() else None
    except Exception as exc:
        logger.warning("Cache read failed (%s): %s", key, exc)
        return None


def load_date(key: str, date_str: str) -> dict | None:
    if not _DATE_RE.match(date_str):
        logger.warning("Rejected invalid date_str: %r", date_str)
        return None
    try:
        candidate = (_CACHE_DIR / f"{date_str}_{key}.json").resolve()
        if not candidate.is_relative_to(_CACHE_DIR.resolve()):
            logger.warning("Path traversal attempt blocked for date_str: %r", date_str)
            return None
        return json.loads(candidate.read_text()) if candidate.exists() else None
    except Exception as exc:
        logger.warning("Cache read failed (%s/%s): %s", date_str, key, exc)
        return None


def list_cached_dates(key: str) -> list[str]:
    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        return sorted(
            {p.name.replace(f"_{key}.json", "") for p in _CACHE_DIR.glob(f"*_{key}.json")},
            reverse=True,
        )
    except Exception as exc:
        logger.warning("list_cached_dates failed: %s", exc)
        return []


def save_today(key: str, data: dict) -> None:
    try:
        _fs_path(key).write_text(json.dumps(data))
        logger.info("Cached response under key '%s'", key)
    except Exception as exc:
        logger.warning("Cache write failed (%s): %s", key, exc)
