#!/bin/bash
set -e

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO"
source .venv/bin/activate
python scripts/generate.py

cd dist
git add -A
git commit -m "Daily update $(date -I)" || echo "Nothing to commit"
git push
