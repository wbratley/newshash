import json
import logging
import os
import re
from datetime import date, datetime, timezone
from pathlib import Path

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

logger = logging.getLogger(__name__)

# Auto-detect Lambda environment; can be overridden with CACHE_BACKEND=dynamo|filesystem
_CACHE_BACKEND = os.environ.get(
    "CACHE_BACKEND",
    "dynamo" if os.environ.get("AWS_LAMBDA_FUNCTION_NAME") else "filesystem",
)

_CACHE_DIR = Path(".cache")
_dynamo_resource = None


def _dynamo():
    global _dynamo_resource
    if _dynamo_resource is None:
        import boto3
        _dynamo_resource = boto3.resource("dynamodb")
    return _dynamo_resource


def _table_name() -> str:
    from app.config import settings
    return settings.cache_table_name


def _pk(key: str) -> str:
    return f"{date.today().isoformat()}_{key}"


def _dynamo_load(key: str) -> dict | None:
    table = _dynamo().Table(_table_name())
    resp = table.get_item(Key={"pk": _pk(key)})
    item = resp.get("Item")
    if not item:
        return None
    return json.loads(item["data"])


def _dynamo_save(key: str, data: dict) -> None:
    table = _dynamo().Table(_table_name())
    ttl = int(datetime.now(timezone.utc).timestamp()) + 2 * 86400  # 2 days
    table.put_item(Item={"pk": _pk(key), "data": json.dumps(data), "ttl": ttl})


def _fs_path(key: str) -> Path:
    _CACHE_DIR.mkdir(exist_ok=True)
    return _CACHE_DIR / f"{date.today().isoformat()}_{key}.json"


def load_today(key: str) -> dict | None:
    try:
        if _CACHE_BACKEND == "dynamo":
            return _dynamo_load(key)
        path = _fs_path(key)
        return json.loads(path.read_text()) if path.exists() else None
    except Exception as exc:
        logger.warning("Cache read failed (%s): %s", key, exc)
        return None


def load_date(key: str, date_str: str) -> dict | None:
    """Load cache for a specific date (YYYY-MM-DD). Rejects anything that isn't a valid date string."""
    if not _DATE_RE.match(date_str):
        logger.warning("Rejected invalid date_str: %r", date_str)
        return None
    try:
        if _CACHE_BACKEND == "dynamo":
            table = _dynamo().Table(_table_name())
            resp = table.get_item(Key={"pk": f"{date_str}_{key}"})
            item = resp.get("Item")
            return json.loads(item["data"]) if item else None
        candidate = (_CACHE_DIR / f"{date_str}_{key}.json").resolve()
        if not candidate.is_relative_to(_CACHE_DIR.resolve()):
            logger.warning("Path traversal attempt blocked for date_str: %r", date_str)
            return None
        return json.loads(candidate.read_text()) if candidate.exists() else None
    except Exception as exc:
        logger.warning("Cache read failed (%s/%s): %s", date_str, key, exc)
        return None


def list_cached_dates(key: str) -> list[str]:
    """Return all dates with cached data for the given key, newest first."""
    try:
        if _CACHE_BACKEND == "dynamo":
            return [date.today().isoformat()]
        _CACHE_DIR.mkdir(exist_ok=True)
        dates = sorted(
            {p.name.replace(f"_{key}.json", "") for p in _CACHE_DIR.glob(f"*_{key}.json")},
            reverse=True,
        )
        return dates
    except Exception as exc:
        logger.warning("list_cached_dates failed: %s", exc)
        return []


def save_today(key: str, data: dict) -> None:
    try:
        if _CACHE_BACKEND == "dynamo":
            _dynamo_save(key, data)
        else:
            _fs_path(key).write_text(json.dumps(data))
        logger.info("Cached response under key '%s'", key)
    except Exception as exc:
        logger.warning("Cache write failed (%s): %s", key, exc)
