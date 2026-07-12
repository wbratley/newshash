#!/usr/bin/env python3
"""One-off backfill: tag historical cached digests with which model generated
each cluster's bias analysis.

Every digest generated before NIM support existed used Claude, so cached
clusters get retroactively labelled with ANTHROPIC_LABEL — except clusters
that fell back to "Synthesis unavailable." (no model successfully produced
output for those). Digests generated after this feature shipped already carry
a `model` field and are left untouched.

Today's file is always skipped: "untagged" only reliably means "predates NIM"
for *past* days. Today's digest may have been generated after NIM support
landed but before model-tracking code was deployed, in which case it was
already using a different model and this script has no way to tell — labelling
it Claude would be a guess, not a backfill. Today's digest gets a correct
label automatically the next time it's freshly generated (or run
scripts/fix_model_label.py to correct a mislabelled one without regenerating
content).

Run against the .cache/ directory that actually backs the live site (this
repo's local .cache/ only has a handful of local test runs), then re-run
scripts/generate.py to regenerate dist/ with the label included.
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.synthesis import ANTHROPIC_LABEL

CACHE_DIR = Path(".cache")
FALLBACK_MARKER = "Synthesis unavailable."
TODAY_FILE = f"{date.today().isoformat()}_news.json"


def backfill_file(path: Path) -> bool:
    data = json.loads(path.read_text())
    changed = False
    for cluster in data.get("clusters", []):
        if "model" in cluster and cluster["model"] is not None:
            continue  # already tagged
        fell_back = all(
            o.get("bias_notes") == FALLBACK_MARKER for o in cluster.get("outlets", [])
        )
        cluster["model"] = None if fell_back else ANTHROPIC_LABEL
        changed = True
    if changed:
        path.write_text(json.dumps(data))
    return changed


def main() -> None:
    files = sorted(CACHE_DIR.glob("*_news.json"))
    if not files:
        print(f"No cache files found in {CACHE_DIR}/")
        return

    updated = 0
    for f in files:
        if f.name == TODAY_FILE:
            print(f"skipping {f.name} (today's digest — never guess-backfilled)")
            continue
        if backfill_file(f):
            updated += 1
            print(f"backfilled {f.name}")

    print(f"\n{updated}/{len(files)} files updated.")
    if updated:
        print("Run scripts/generate.py to regenerate dist/ with the labels included.")


if __name__ == "__main__":
    main()
