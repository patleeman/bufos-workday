#!/bin/sh
# Build the real game and play it in PyBoy:
#   Level 1: from the phone call in the cubicle to The Printer's defeat.
#   Level 2: from the Floor 2 elevator to the Espresso Machine's defeat.
# Fails if any key step doesn't happen.
# Needs: tools/setup_cli.sh run once, and a Python with pyboy + pillow (set PYBOY_PYTHON).
# Set BUFO_PROJECT_DIR to build somewhere other than gbstudio/ (for example while GB Studio has it open).
set -e
cd "$(dirname "$0")/.."
PY="${PYBOY_PYTHON:-/tmp/pyboy-venv/bin/python}"
run() {
  rm -rf "build/$1"
  "$PY" -I tools/playtest.py build/bufos_workday.gb "build/$1" "$(tr '\n' ' ' < "tools/$2")" 2>&1 \
    | grep -v Warning | tee "build/$1.log" | grep -E "^ok:|FAIL|timed out" || true
  ! grep -q FAIL "build/$1.log"
}
# The scripted player never dodges, so its builds give Bufo extra coffee.
BUFO_START_HP=20 tools/build.sh
run playthrough playthrough.txt
BUFO_START=elevator_landing,9,14 BUFO_HP=20 BUFO_MAX_HP=4 tools/build.sh
run playthrough_level2 playthrough_level2.txt
if [ -f tools/make_open_office.py ]; then
  BUFO_START=office_landing,9,14 BUFO_HP=20 BUFO_MAX_HP=5 tools/build.sh
  run playthrough_level3 playthrough_level3.txt
fi
# Focused tests for the later floors.
grep -v '^#' tools/segments.txt | while IFS='|' read -r name start items steps; do
  name=$(echo $name); start=$(echo $start); items=$(echo $items)
  BUFO_START=$start BUFO_ITEMS=$items BUFO_HP=20 BUFO_MAX_HP=5 tools/build.sh > /dev/null
  printf '%s: ' "$name"
  echo "$steps" > "build/segment_$name.txt"
  run "segment_$name" "../build/segment_$name.txt" | tr '\n' ' '; echo
done
tools/build.sh
grep -l FAIL build/*.log 2>/dev/null && exit 1
echo "Playthroughs passed. Screenshots: build/playthrough/ and build/playthrough_level2/"
