#!/usr/bin/env bash
# svg-skill: batch SVG quality checks
# Usage: bash scripts/validate.sh [dir_or_file ...]
# Defaults to current directory if no args.
set -euo pipefail

PASS=0
FAIL=0
XMLLINT=""
command -v xmllint >/dev/null 2>&1 && XMLLINT=1

check() {
  local file="$1"
  local name
  name="$(basename "$file")"

  if ! grep -q 'xmlns="http://www.w3.org/2000/svg"' "$file"; then
    echo "FAIL $name: missing xmlns"
    FAIL=$((FAIL + 1))
    return
  fi

  if ! grep -q 'viewBox=' "$file"; then
    echo "FAIL $name: missing viewBox"
    FAIL=$((FAIL + 1))
    return
  fi

  if grep -qiE 'TODO|d="\.\.\.|d=""' "$file"; then
    echo "FAIL $name: placeholder path"
    FAIL=$((FAIL + 1))
    return
  fi

  if grep -qiE 'inkscape|sodipodi|adobe:page' "$file"; then
    echo "FAIL $name: editor metadata"
    FAIL=$((FAIL + 1))
    return
  fi

  if [ -n "$XMLLINT" ]; then
    if ! xmllint --noout "$file" 2>/dev/null; then
      echo "FAIL $name: invalid XML (check UTF-8 encoding)"
      FAIL=$((FAIL + 1))
      return
    fi
  fi

  echo "PASS $name"
  PASS=$((PASS + 1))
}

TARGETS=("$@")
if [ ${#TARGETS[@]} -eq 0 ]; then
  TARGETS=(".")
fi

echo "=== svg-skill validate ==="
while IFS= read -r -d '' f; do
  check "$f"
done < <(find "${TARGETS[@]}" -name '*.svg' -print0 2>/dev/null)

echo ""
echo "Result: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
