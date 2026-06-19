#!/bin/bash
# lint_check.sh — Portable syntax checker
# Uses language-specific tools if available, falls back to basic checks.

set -e

echo "Running lint checks..."
ERRORS=0

# Python
if command -v python &>/dev/null || command -v python3 &>/dev/null; then
  PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
  for f in $(find . -name "*.py" -not -path "./node_modules/*" -not -path "./.git/*" -not -path "./.venv/*" -not -path "./__pycache__/*" -not -path "./target/*"); do
    if ! $PY -c "import ast; ast.parse(open('$f').read())" 2>/dev/null; then
      echo "  [SYNTAX] $f"
      ERRORS=$((ERRORS + 1))
    fi
  done
fi

# Node.js / JavaScript
if command -v node &>/dev/null; then
  for f in $(find . -name "*.js" -not -path "./node_modules/*" -not -path "./.git/*" -maxdepth 3); do
    if ! node -c "$f" 2>/dev/null; then
      echo "  [SYNTAX] $f"
      ERRORS=$((ERRORS + 1))
    fi
  done
fi

if [ "$ERRORS" -gt 0 ]; then
  echo "  $ERRORS syntax error(s) found."
  exit 1
fi

echo "  OK — syntax clean."
exit 0