#!/bin/sh
# Regenerate the GB Studio project and compile it to build/bufos_workday.gb.
# Needs the GB Studio CLI (see README). Override its path with GBS_CLI.
set -e
cd "$(dirname "$0")/.."
GBS_CLI="${GBS_CLI:-/tmp/gbs-src/out/cli/gb-studio-cli.js}"
python3 -I tools/make_gbstudio_project.py
mkdir -p build
node "$GBS_CLI" make:rom "${BUFO_PROJECT_DIR:-gbstudio}/project.gbsproj" "$PWD/build/bufos_workday.gb" > build/build.log 2>&1 \
  || { tail -30 build/build.log; exit 1; }
echo "Built build/bufos_workday.gb"
