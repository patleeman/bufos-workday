#!/bin/sh
# Build the website into site/: the landing page, the web player, and the ROM download.
# Needs the GB Studio CLI (tools/setup_cli.sh). Builds from gbstudio/ (or BUFO_PROJECT_DIR).
# With --deploy, also publishes site/ to the gh-pages branch (https://patleeman.github.io/bufos-workday/).
set -e
cd "$(dirname "$0")/.."
GBS_CLI="${GBS_CLI:-/tmp/gbs-src/out/cli/gb-studio-cli.js}"
PROJECT="${BUFO_PROJECT_DIR:-gbstudio}"
rm -rf site
mkdir -p site
cp -R site-src/. site/
node "$GBS_CLI" make:web "$PROJECT/project.gbsproj" "$PWD/site/play" > build/site.log 2>&1 || { tail -20 build/site.log; exit 1; }
cp site/play/rom/*.gbc site/bufos_workday.gbc
# Favicon: Bufo's front-facing frame.
python3 -c "
from PIL import Image
im = Image.open('assets/sprites/bufo.png').convert('RGBA').crop((0, 0, 16, 16))
px = im.load()
for y in range(16):
    for x in range(16):
        if px[x, y][:3] == (0x65, 0xFF, 0x00): px[x, y] = (0, 0, 0, 0)
im.resize((64, 64), Image.NEAREST).save('site/img/bufo.png')"
echo "Built site/ (open site/index.html through a local server: python3 -m http.server -d site)"

if [ "$1" = "--deploy" ]; then
  REMOTE=$(git remote get-url origin)
  OUT=$(mktemp -d)
  cp -R site/. "$OUT"
  touch "$OUT/.nojekyll"
  cd "$OUT"
  git init -q -b gh-pages
  git add -A
  git commit -qm "Publish site"
  git push -qf "$REMOTE" gh-pages
  rm -rf "$OUT"
  echo "Deployed. GitHub Pages updates in a minute or two."
fi
