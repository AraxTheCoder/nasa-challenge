#!/usr/bin/env bash
# Wide per-epoch stitch test (T39): full SPHEREx images -> one mosaic per epoch -> HiPS -> Aladin page.
# Usage, from the repo root, with the venv active:
#   pipeline/reference/wide_stitch/run.sh <query.json> [detector=1] [images_per_epoch=2]
# <query.json> comes from: python -m pipeline.query --ra .. --dec .. --out data/queries/<name>.json
# Output: data/explore/hips_wide/ (tiles, labels, page). Open it through any static server, e.g.
#   python -m http.server 8082 --bind 127.0.0.1  ->  http://127.0.0.1:8082/data/explore/hips_wide/
set -euo pipefail
Q=${1:?query.json}; DET=${2:-1}; K=${3:-2}
HERE=$(cd "$(dirname "$0")" && pwd)
RAW=data/raw/explore/hips_wide; OUT=data/explore/hips_wide
python -I "$HERE/fetch_full.py" "$Q" "$DET" "$K" "$RAW"
python -I "$HERE/make_wide.py" "$RAW" "$OUT" 6
python -I "$HERE/labels_wide.py" "$OUT"
cp "$HERE/page_wide/index.html" "$OUT/index.html"
echo "open http://127.0.0.1:8082/$OUT/index.html (static server on 8082)"
