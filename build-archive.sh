#!/usr/bin/env bash
# Builds a single deploy archive for Zerve Hosted Apps.
#
# Steps:
#   1. Re-export model artifacts from the canvas pipeline → web/public/data/
#   2. Build Next.js static export → web/out/
#   3. Zip { server.py, web/out/, requirements.txt } → app.zip
#
# Upload app.zip via Zerve UI → Hosted Apps → Python.
set -euo pipefail
cd "$(dirname "$0")"

echo "── 1/3  exporting model + funnel data → JSON"
uv run python export-data.py

echo "── 2/3  building Next.js static export"
( cd web && npm run build )

echo "── 3/3  packaging app.zip"
rm -f app.zip
zip -rq app.zip server.py requirements.txt web/out
ls -lh app.zip

echo "✓ done. Upload app.zip via Zerve UI → Hosted Apps → Python."
