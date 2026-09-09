#!/usr/bin/env bash
# full-scenario test runner
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILL_VALIDATE="$HOME/.cursor/skills/svg-skill/scripts/validate.sh"
PASS=0
FAIL=0
TOTAL=0

echo "======================================"
echo " svg-skill Full Scenario Test"
echo "======================================"
echo ""

# 1. SVG validate via skill script
echo "[1/3] Skill validate.sh"
if bash "$SKILL_VALIDATE" "$ROOT"; then
  echo ""
else
  echo "validate.sh failed"
  exit 1
fi

# 2. Scenario manifest check
echo "[2/3] Manifest coverage (27 scenarios)"
declare -a EXPECTED=(
  "01-icons/bell-outline.svg"
  "01-icons/check-filled.svg"
  "01-icons/layers-multicolor.svg"
  "01-icons/map-pin.svg"
  "02-brand/logo.svg"
  "02-brand/favicon.svg"
  "03-illustration/empty-box.svg"
  "04-diagrams/flow-zh.svg"
  "04-diagrams/architecture.svg"
  "05-charts/bar.svg"
  "05-charts/line.svg"
  "05-charts/pie.svg"
  "06-progress/ring-75.svg"
  "06-progress/bar-60.svg"
  "07-ui/avatar.svg"
  "07-ui/badge.svg"
  "08-decor/wave.svg"
  "09-sprite/icons.svg"
  "10-motion/spinner.svg"
  "10-motion/heart-hover.svg"
  "11-effects/clip-card.svg"
  "11-effects/shadow.svg"
  "11-effects/dots-pattern.svg"
  "12-integration/email-icon.svg"
)

for f in "${EXPECTED[@]}"; do
  TOTAL=$((TOTAL + 1))
  if [ -f "$ROOT/$f" ]; then
    echo "  OK  $f"
    PASS=$((PASS + 1))
  else
    echo "  MISS $f"
    FAIL=$((FAIL + 1))
  fi
done

# Integration files (non-svg)
for f in "12-integration/demo.css" "12-integration/BellIcon.tsx" "12-integration/MailIcon.vue"; do
  TOTAL=$((TOTAL + 1))
  if [ -f "$ROOT/$f" ]; then
    echo "  OK  $f"
    PASS=$((PASS + 1))
  else
    echo "  MISS $f"
    FAIL=$((FAIL + 1))
  fi
done

# 3. Spot checks
echo ""
echo "[3/3] Spot checks"
SPOT_PASS=0
SPOT_FAIL=0

check_grep() {
  local file="$1" pattern="$2" label="$3"
  if grep -q "$pattern" "$file" 2>/dev/null; then
    echo "  OK  $label"
    SPOT_PASS=$((SPOT_PASS + 1))
  else
    echo "  FAIL $label"
    SPOT_FAIL=$((SPOT_FAIL + 1))
  fi
}

check_grep "$ROOT/08-decor/wave.svg" 'preserveAspectRatio="none"' "wave: full-width"
check_grep "$ROOT/06-progress/ring-75.svg" 'stroke-dashoffset' "progress ring: dashoffset"
check_grep "$ROOT/09-sprite/icons.svg" '<symbol id=' "sprite: symbols"
check_grep "$ROOT/04-diagrams/flow-zh.svg" 'encoding="UTF-8"' "flow-zh: UTF-8 decl"
if grep -q '<style' "$ROOT/12-integration/email-icon.svg" 2>/dev/null; then
  echo "  FAIL email: should not have style tag"
  SPOT_FAIL=$((SPOT_FAIL + 1))
else
  echo "  OK  email: no style tag"
  SPOT_PASS=$((SPOT_PASS + 1))
fi
check_grep "$ROOT/12-integration/BellIcon.tsx" '\.\.\.props' "react: spread props"

echo ""
echo "======================================"
echo " Manifest: $PASS/$TOTAL files"
echo " Spot checks: $SPOT_PASS passed, $SPOT_FAIL failed"
echo "======================================"

[ "$FAIL" -eq 0 ] && [ "$SPOT_FAIL" -eq 0 ]
