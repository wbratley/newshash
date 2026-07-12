#!/usr/bin/env python3
"""Correct the `model` label on an already-cached digest without
re-running synthesis (i.e. without another API call).

Use this when a day's clusters were mislabelled — e.g. backfill_model.py
guessed Claude for a digest that actually ran on a different provider before
model-tracking code was deployed. Only overwrites clusters that already carry
a non-null `model` (real content); clusters that fell back to
"Synthesis unavailable." are left as None.

Usage: python scripts/fix_model_label.py <YYYY-MM-DD> "<correct label>"
Example: python scripts/fix_model_label.py 2026-07-12 "meta/llama-3.3-70b-instruct (NIM)"
"""
import json
import sys
from pathlib import Path

CACHE_DIR = Path(".cache")


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <YYYY-MM-DD> <correct label>")

    date_str, label = sys.argv[1], sys.argv[2]
    path = CACHE_DIR / f"{date_str}_news.json"
    if not path.exists():
        sys.exit(f"no cache file at {path}")

    data = json.loads(path.read_text())
    fixed = 0
    for cluster in data.get("clusters", []):
        if cluster.get("model") is not None:
            cluster["model"] = label
            fixed += 1

    path.write_text(json.dumps(data))
    print(f"Relabelled {fixed} cluster(s) in {path} -> {label!r}")
    print("Run scripts/generate.py to regenerate dist/ with the correction.")


if __name__ == "__main__":
    main()
