#!/bin/sh
# Render docs/cv.html to site/cv.pdf with headless Chrome.
# Needs the preview server running:  python3 -m http.server 8787 --directory docs
set -e
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
DIR=$(cd "$(dirname "$0")" && pwd)
"$CHROME" --headless --disable-gpu --no-pdf-header-footer \
  --run-all-compositor-stages-before-draw --virtual-time-budget=30000 \
  --print-to-pdf="$DIR/docs/cv.pdf" http://localhost:8787/cv.html 2>/dev/null
ls -lh "$DIR/docs/cv.pdf"
