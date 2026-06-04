#!/usr/bin/env python3
"""Generate static HTML files from today's and archived news digests."""

import asyncio
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.cache import list_cached_dates, load_date
from app.services.digest import get_or_generate

DIST = Path("dist")
TEMPLATES = Path("app/templates")


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)


def _context(
    data: dict,
    available_dates: list[str],
    viewing_date: str | None = None,
    canonical_url: str = "",
) -> dict:
    today = date.today().isoformat()
    return {
        "data": data,
        "generated_at": data["generated_at"][:10],
        "available_dates": available_dates,
        "viewing_date": viewing_date,
        "today": today,
        "is_archive": viewing_date is not None and viewing_date != today,
        "site_url": settings.site_url,
        "canonical_url": canonical_url,
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
    today = date.today().isoformat()
    base = settings.site_url
    is_archive = viewing_date is not None and viewing_date != today

    index_canonical = f"{base}/{viewing_date}/" if is_archive else f"{base}/"
    _write(
        out_dir / "index.html",
        env.get_template("index.html").render(
            **_context(data, available_dates, viewing_date, canonical_url=index_canonical)
        ),
    )

    story_tmpl = env.get_template("story.html")
    for cluster in data["clusters"]:
        story_canonical = (
            f"{base}/{viewing_date}/story/{cluster['id']}/"
            if is_archive
            else f"{base}/story/{cluster['id']}/"
        )
        _write(
            out_dir / "story" / cluster["id"] / "index.html",
            story_tmpl.render(
                **_context(data, available_dates, viewing_date, canonical_url=story_canonical),
                cluster=cluster,
            ),
        )


def _generate_sitemap(data: dict, available_dates: list[str]) -> str:
    today = date.today().isoformat()
    base = settings.site_url
    urls = [
        f'  <url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>',
    ]
    for cluster in data["clusters"]:
        urls.append(
            f'  <url><loc>{base}/story/{cluster["id"]}/</loc>'
            f'<changefreq>daily</changefreq><priority>0.8</priority></url>'
        )
    for d in available_dates:
        if d == today:
            continue
        urls.append(
            f'  <url><loc>{base}/{d}/</loc>'
            f'<changefreq>never</changefreq><priority>0.5</priority></url>'
        )
        archive_data = load_date("news", d)
        if archive_data:
            for cluster in archive_data["clusters"]:
                urls.append(
                    f'  <url><loc>{base}/{d}/story/{cluster["id"]}/</loc>'
                    f'<changefreq>never</changefreq><priority>0.4</priority></url>'
                )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )


def _generate_news_sitemap(data: dict) -> str:
    base = settings.site_url
    pub_date = data["generated_at"][:10] + "T00:00:00Z"
    entries = []
    for cluster in data["clusters"]:
        title = xml_escape(cluster["neutral_headline"])
        entries.append(
            f"  <url>\n"
            f"    <loc>{base}/story/{cluster['id']}/</loc>\n"
            f"    <news:news>\n"
            f"      <news:publication>\n"
            f"        <news:name>Newshash</news:name>\n"
            f"        <news:language>en</news:language>\n"
            f"      </news:publication>\n"
            f"      <news:publication_date>{pub_date}</news:publication_date>\n"
            f"      <news:title>{title}</news:title>\n"
            f"    </news:news>\n"
            f"  </url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>"
    )


def _generate_robots() -> str:
    base = settings.site_url
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "\n"
        f"Sitemap: {base}/sitemap.xml\n"
        f"Sitemap: {base}/sitemap-news.xml\n"
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

    _write(DIST / "sitemap.xml", _generate_sitemap(data, available_dates))
    _write(DIST / "sitemap-news.xml", _generate_news_sitemap(data))
    _write(DIST / "robots.txt", _generate_robots())

    file_count = sum(1 for _ in DIST.rglob("*.html"))
    print(f"Generated {file_count} HTML files → {DIST}/")
    print(f"Generated sitemap.xml, sitemap-news.xml, robots.txt → {DIST}/")


if __name__ == "__main__":
    asyncio.run(main())
