import json
import logging
import re
from collections import defaultdict

from anthropic import AsyncAnthropic

from app.config import settings
from app.schemas import Cluster, OutletAnalysis, Source
from app.services.rss import RawStory

logger = logging.getLogger(__name__)

_client: AsyncAnthropic | None = None

LEAN_ORDER = ["left", "centre-left", "centre", "centre-right", "right"]


def _normalize_name(name: str) -> str:
    """Lowercase and strip parenthetical suffixes so Claude's outlet names match our keys."""
    return re.sub(r"\s*\(.*?\)", "", name).strip().lower()


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


def _group_by_outlet(stories: list[RawStory]) -> dict[str, list[RawStory]]:
    grouped: dict[str, list[RawStory]] = defaultdict(list)
    for s in stories:
        grouped[s["outlet"]].append(s)
    return dict(grouped)


def _build_prompt(cluster: list[RawStory]) -> str:
    grouped = _group_by_outlet(cluster)
    outlet_lean = {s["outlet"]: s["lean"] for s in cluster}

    blocks = []
    for outlet, stories in grouped.items():
        lean = outlet_lean[outlet]
        header = f"[{outlet.upper()} ({lean})]"
        lines = [header]
        for s in stories:
            snippet = s["summary"][:200] if s["summary"] else "(no summary)"
            lines.append(f"  • {s['title']} — {snippet}")
        blocks.append("\n".join(lines))

    outlets_block = "\n\n".join(blocks)

    return f"""You are a neutral news analyst. The same story has been covered by several UK news outlets with different political leanings. Your job is to:
1. Write a single objective account of what actually happened.
2. For each outlet, identify the narrative angle they are pushing and explain specifically how their coverage deviates from the objective facts — what do they emphasise, downplay, omit, or frame differently?

Coverage to analyse:

{outlets_block}

Return ONLY valid JSON with this exact shape — no markdown, no extra text:
{{
  "neutral_headline": "<bias-free headline under 30 words>",
  "unbiased_summary": "<objective 100-150 word account of what actually happened, with no editorial slant>",
  "outlet_analysis": [
    {{
      "outlet": "<exact outlet name as given above>",
      "angle": "<one sentence: what narrative frame or angle is this outlet pushing?>",
      "bias_notes": "<2-3 sentences: what specifically do they emphasise, downplay, or omit compared to the objective facts? How far do they stray from neutral?>"
    }}
  ]
}}

Include every outlet in outlet_analysis. Use the exact outlet names as given."""


def _fallback_cluster(cluster_id: str, stories: list[RawStory]) -> Cluster:
    grouped = _group_by_outlet(stories)
    outlets = []
    for outlet, outlet_stories in grouped.items():
        outlets.append(OutletAnalysis(
            outlet=outlet,
            lean=outlet_stories[0]["lean"],
            angle="Synthesis unavailable.",
            bias_notes="Synthesis unavailable.",
            articles=[
                Source(outlet=s["outlet"], lean=s["lean"], headline=s["title"],
                       url=s["url"], published=s["published"])
                for s in outlet_stories
            ],
        ))
    outlets.sort(key=lambda o: LEAN_ORDER.index(o.lean) if o.lean in LEAN_ORDER else 99)
    return Cluster(
        id=cluster_id,
        neutral_headline=stories[0]["title"] if stories else "Unknown story",
        unbiased_summary="Synthesis unavailable.",
        outlets=outlets,
    )


async def synthesise_cluster(cluster_id: str, stories: list[RawStory]) -> Cluster:
    grouped = _group_by_outlet(stories)
    sources_by_outlet: dict[str, list[Source]] = {
        outlet: [
            Source(outlet=s["outlet"], lean=s["lean"], headline=s["title"],
                   url=s["url"], published=s["published"])
            for s in outlet_stories
        ]
        for outlet, outlet_stories in grouped.items()
    }
    outlet_lean = {s["outlet"]: s["lean"] for s in stories}
    # Case-insensitive lookup so Claude's returned names (e.g. "THE GUARDIAN (left)") resolve correctly
    canonical_outlet = {_normalize_name(o): o for o in grouped.keys()}

    try:
        response = await get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": _build_prompt(stories)}],
        )
        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)

        outlets = []
        for entry in data.get("outlet_analysis", []):
            raw_name = entry["outlet"]
            outlet_name = canonical_outlet.get(_normalize_name(raw_name), raw_name)
            outlets.append(OutletAnalysis(
                outlet=outlet_name,
                lean=outlet_lean.get(outlet_name, "unknown"),
                angle=entry.get("angle", ""),
                bias_notes=entry.get("bias_notes", ""),
                articles=sources_by_outlet.get(outlet_name, []),
            ))
        outlets.sort(key=lambda o: LEAN_ORDER.index(o.lean) if o.lean in LEAN_ORDER else 99)

        return Cluster(
            id=cluster_id,
            neutral_headline=data.get("neutral_headline", stories[0]["title"]),
            unbiased_summary=data.get("unbiased_summary", ""),
            outlets=outlets,
        )

    except Exception as exc:
        logger.warning("Synthesis failed for cluster %s: %s", cluster_id, exc)
        return _fallback_cluster(cluster_id, stories)
