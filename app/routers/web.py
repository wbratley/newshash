from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services.cache import list_cached_dates, load_date
from app.services.digest import get_or_generate

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")

_KEY = "news"


def _template_context(data: dict, viewing_date: str | None = None) -> dict:
    today = date.today().isoformat()
    return {
        "data": data,
        "generated_at": data["generated_at"][:10],
        "available_dates": list_cached_dates(_KEY),
        "viewing_date": viewing_date,
        "today": today,
        "is_archive": viewing_date is not None and viewing_date != today,
    }


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, archive_date: str | None = None):
    if archive_date:
        data = load_date(_KEY, archive_date)
        if not data:
            return RedirectResponse("/")
        return templates.TemplateResponse(request, "index.html", _template_context(data, archive_date))

    data = await get_or_generate()
    return templates.TemplateResponse(request, "index.html", _template_context(data))


@router.get("/story/{cluster_id}", response_class=HTMLResponse)
async def story(request: Request, cluster_id: str, archive_date: str | None = None):
    if archive_date:
        data = load_date(_KEY, archive_date)
        if not data:
            return RedirectResponse("/")
    else:
        data = await get_or_generate()

    cluster = next((c for c in data["clusters"] if c["id"] == cluster_id), None)
    ctx = _template_context(data, archive_date)
    ctx["cluster"] = cluster
    ctx["archive_date"] = archive_date
    return templates.TemplateResponse(request, "story.html", ctx)
