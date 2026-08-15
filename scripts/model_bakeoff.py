#!/usr/bin/env python3
"""Bake-off: run the real synthesis prompt through candidate NIM models."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import AsyncOpenAI
from app.config import settings
from app.services.rss import RawStory
from app.services.synthesis import _build_prompt

MODELS = sys.argv[1:] or ["deepseek-ai/deepseek-v4-flash-0731", "openai/gpt-oss-120b", "stepfun-ai/step-3.7-flash"]
CACHE = Path(".cache") / f"{__import__('datetime').date.today().isoformat()}_news.json"


def load_cluster(idx: int) -> list[RawStory]:
    data = json.loads(CACHE.read_text())
    cluster = data["clusters"][idx]
    stories = []
    for outlet in cluster["outlets"]:
        for a in outlet["articles"]:
            stories.append(RawStory(
                outlet=a["outlet"], lean=a["lean"], title=a["headline"],
                url=a["url"], published=a["published"], summary=a.get("summary", ""),
                body=a.get("body", ""),
            ))
    return stories


async def run(model: str, prompt: str) -> str:
    client = AsyncOpenAI(api_key=settings.nim_api_key, base_url=settings.nim_base_url)
    resp = await client.chat.completions.create(
        model=model, max_tokens=6000, messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()


def show(raw: str) -> None:
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        d = json.loads(raw.strip())
        print("JSON: VALID")
        print("headline:", d.get("neutral_headline"))
        print("summary:", d.get("unbiased_summary"))
        for o in d.get("outlet_analysis", [])[:3]:
            print(f"  [{o.get('outlet')}] angle: {o.get('angle')}")
            print(f"    notes: {o.get('bias_notes')}")
        print(f"  ... +{max(0, len(d.get('outlet_analysis', [])) - 3)} more outlets")
    except Exception as e:
        print("JSON: INVALID —", e)
        print(raw[:600])


async def main() -> None:
    stories = load_cluster(0)
    print(f"Cluster 0: {len(stories)} articles, "
          f"{sum(1 for s in stories if len(s.get('body', '')) >= 200)} with full text\n")
    prompt = _build_prompt(stories)
    print(f"prompt: {len(prompt)} chars\n")
    for m in MODELS:
        print("=" * 100)
        print(f"MODEL: {m}")
        try:
            raw = await run(m, prompt)
            show(raw)
        except Exception as e:
            print("FAILED:", e)
        print()


if __name__ == "__main__":
    asyncio.run(main())
