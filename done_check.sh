#!/bin/bash
# done_check.sh — Pre-commit documentation sync verifier
#
# Checks that documentation files are updated alongside source code.
# Designed to be language-agnostic — works with any project.
#
# Usage: bash done_check.sh
# Exit code: 0 = all clean, 1 = docs out of sync

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

check_pass() {
  echo -e "  ${GREEN}[PASS]${NC} $1"
  PASS=$((PASS + 1))
}

check_fail() {
  echo -e "  ${RED}[FAIL]${NC} $1"
  FAIL=$((FAIL + 1))
}

check_warn() {
  echo -e "  ${YELLOW}[WARN]${NC} $1"
  WARN=$((WARN + 1))
}

echo "================================================"
echo " Pre-Commit Documentation Sync Check"
echo "================================================"
echo ""

# ---- 1. progress.md updated? ----
echo "  [1. progress.md sync]"

# Find source files newer than progress.md
PROGRESS="progress.md"
if [ ! -f "$PROGRESS" ]; then
  check_fail "$PROGRESS not found"
else
  # Find .py / .js / .ts / .rs / .go files newer than progress.md
  NEWER=$(find . -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.rs" -o -name "*.go" \) \
    -not -path "./node_modules/*" -not -path "./.git/*" -not -path "./__pycache__/*" \
    -not -path "./target/*" -not -path "./.venv/*" -newer "$PROGRESS" 2>/dev/null | head -10)

  if [ -n "$NEWER" ]; then
    check_fail "Source files newer than $PROGRESS:"
    echo "$NEWER" | while read -r f; do echo "         $f"; done
    echo "         Update $PROGRESS with evidence references."
  else
    check_pass "$PROGRESS is current"
  fi
fi
echo ""

# ---- 2. feature_list.json updated? ----
echo "  [2. feature_list.json sync]"

FEATURES="feature_list.json"
if [ -f "$PROGRESS" ] && [ -f "$FEATURES" ]; then
  if [ "$PROGRESS" -nt "$FEATURES" ]; then
    check_warn "$PROGRESS is newer than $FEATURES"
    echo "         Did you complete a feature? Update $FEATURES status."
  else
    check_pass "$FEATURES is current"
  fi
elif [ ! -f "$FEATURES" ]; then
  check_warn "$FEATURES not found (optional)"
fi
echo ""

# ---- 3. DECISIONS.md updated? ----
echo "  [3. DECISIONS.md sync]"

DECISIONS="DECISIONS.md"
if [ -f "$DECISIONS" ]; then
  # Check if core architecture files changed
  CORE_FILES=$(find . -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.rs" -o -name "*.go" \) \
    -not -path "./node_modules/*" -not -path "./.git/*" -not -path "./__pycache__/*" \
    -not -path "./target/*" -not -path "./.venv/*" \
    -not -name "test_*" -not -name "*_test*" \
    -newer "$DECISIONS" 2>/dev/null | head -10)

  if [ -n "$CORE_FILES" ]; then
    check_warn "Core files changed but $DECISIONS not updated"
    echo "$CORE_FILES" | while read -r f; do echo "         $f"; done
    echo "         Consider adding an ADR entry."
  else
    check_pass "$DECISIONS is current"
  fi
else
  check_warn "$DECISIONS not found (optional)"
fi
echo ""

# ---- 4. Debug artifacts? ----
echo "  [4. Debug artifacts]"

DEBUG_FOUND=0
for dir in $(find . -type d -not -path "./node_modules/*" -not -path "./.git/*" -not -path "./__pycache__/*" -not -path "./target/*" -not -path "./.venv/*" -maxdepth 1 -type d 2>/dev/null | grep -v "^\.$"); do
  for pattern in 'breakpoint()' 'pdb.set_trace()' 'console.log' 'debugger'; do
    MATCHES=$(grep -rln "$pattern" "$dir" --include="*.py" --include="*.js" --include="*.ts" 2>/dev/null | head -5)
    if [ -n "$MATCHES" ]; then
      echo "$MATCHES" | while read -r f; do
        echo -e "  ${YELLOW}[WARN]${NC} $f contains '$pattern'"
      done
      DEBUG_FOUND=1
    fi
  done
done

if [ "$DEBUG_FOUND" -eq 0 ]; then
  check_pass "No debug artifacts found"
fi
echo ""

# ---- Summary ----
echo "----------------------------------------------"
echo "  $PASS passed, $FAIL failed, $WARN warnings"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo -e "  ${RED}FIX the failures before committing.${NC}"
  exit 1
else
  echo -e "  ${GREEN}All checks passed. Ready to commit.${NC}"
  exit 0
fi