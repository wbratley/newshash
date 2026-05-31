#!/usr/bin/env python3
"""Generate static HTML files from today's and archived news digests."""

import asyncio
import sys
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cache import list_cached_dates, load_date
from app.services.digest import get_or_generate

DIST = Path("dist")
TEMPLATES = Path("app/templates")


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)


def _context(data: dict, available_dates: list[str], viewing_date: str | None = None) -> dict:
    today = date.today().isoformat()
    return {
        "data": data,
        "generated_at": data["generated_at"][:10],
        "available_dates": available_dates,
        "viewing_date": viewing_date,
        "today": today,
        "is_archive": viewing_date is not None and viewing_date != today,
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _render_date(
    env: Environment,
    data: dict,
    available_dates: list[str],
    out_dir: Path,
    viewing_date: str | None = None,
) -> None:
    ctx = _context(data, available_dates, viewing_date)

    _write(out_dir / "index.html", env.get_template("index.html").render(**ctx))

    story_tmpl = env.get_template("story.html")
    for cluster in data["clusters"]:
        _write(
            out_dir / "story" / cluster["id"] / "index.html",
            story_tmpl.render(**ctx, cluster=cluster),
        )


async def main() -> None:
    DIST.mkdir(exist_ok=True)
    env = _env()

    data = await get_or_generate()
    available_dates = list_cached_dates("news")
    today = date.today().isoformat()

    _render_date(env, data, available_dates, DIST)

    for d in available_dates:
        if d == today:
            continue
        archive_data = load_date("news", d)
        if not archive_data:
            continue
        _render_date(env, archive_data, available_dates, DIST / d, viewing_date=d)

    file_count = sum(1 for _ in DIST.rglob("*.html"))
    print(f"Generated {file_count} HTML files → {DIST}/")


if __name__ == "__main__":
    asyncio.run(main())
