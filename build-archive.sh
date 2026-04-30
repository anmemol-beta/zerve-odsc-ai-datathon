#!/usr/bin/env bash
# One-shot deploy pipeline for the Zerve Custom Deployment.
#
# Steps:
#   1. Re-export model + funnel artifacts from the canvas pipeline → JSON
#   2. Build the Next.js static export → web/out/
#   3. Pack { server.py, web/out/, requirements.txt } → app.zip
#   4. Commit + push app.zip so the deployed main.py can pull it from
#      raw.githubusercontent.com on next Restart.
#
# After this script: open Zerve UI → Deployment → Restart. The container
# re-fetches the new zip and serves the updated bundle.
set -euo pipefail
cd "$(dirname "$0")"

echo "── 1/4  exporting model + funnel data → JSON"
uv run python export-data.py

echo "── 2/4  building Next.js static export"
( cd web && npm run build )

echo "── 3/4  packaging app.zip"
rm -f app.zip
zip -rq app.zip server.py requirements.txt web/out
ls -lh app.zip

echo "── 4/4  committing + pushing app.zip"
if git diff --quiet app.zip 2>/dev/null && git diff --cached --quiet app.zip 2>/dev/null; then
    echo "   (no zip changes — skipping commit)"
else
    git add app.zip
    git commit -m "chore: refresh app.zip ($(date -u +%Y-%m-%dT%H:%MZ))"
    git push
fi

echo
echo "✓ done. Open Zerve UI → Deployment → Restart to pull the new zip."
