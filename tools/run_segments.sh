#!/bin/sh
# Run the focused tests in tools/segments.txt. Optional argument: a name filter (grep pattern).
# Each line: name | start room,x,y | items | steps
cd "$(dirname "$0")/.."
PY="${PYBOY_PYTHON:-/tmp/pyboy-venv/bin/python}"
failed=0
grep -v '^#' tools/segments.txt | grep -E "^(${1:-.*}) " > build/segments.list
while IFS='|' read -r name start items steps; do
  name=$(echo $name); start=$(echo $start); items=$(echo $items)
  BUFO_START=$start BUFO_ITEMS=$items BUFO_HP=${SEGMENT_HP:-20} BUFO_MAX_HP=5 tools/build.sh > /dev/null 2>&1 < /dev/null
  result=$("$PY" -I tools/playtest.py build/bufos_workday.gb "build/segment_$name" "$steps" 2>&1 < /dev/null \
    | grep -v Warning | grep -E "^ok:|FAIL|timed out" | tr '\n' ' ')
  printf '%-10s %s\n' "$name" "$result"
  case "$result" in *FAIL*) failed=1 ;; esac
done < build/segments.list
exit $failed
