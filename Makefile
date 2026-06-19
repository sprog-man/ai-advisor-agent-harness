.PHONY: check done exit lint test clean setup-hooks

# --- Customize these for your project ---
PYTHON := python
TESTS := $(wildcard test_*.py)
LINT_CHECK := lint_check.sh
DONE_CHECK := done_check.sh

# Default: full verification
check: lint test
	@echo "=== All checks passed ==="

# Run tests
test:
	@echo "Running tests..."
	@for t in $(TESTS); do \
		echo "  $$t"; \
		$(PYTHON) $$t || { echo "FAILED: $$t"; exit 1; }; \
	done
	@echo "All tests passed."

# Lint / syntax check
lint:
	@echo "Running lint..."
	@bash $(LINT_CHECK)

# ------------------------------------------------------------------
# Forcing function: doc sync check (MUST pass before commit)
# ------------------------------------------------------------------
done:
	@echo "Checking documentation sync..."
	@bash $(DONE_CHECK)

# Setup git hooks (run once after clone)
setup-hooks:
	@git config core.hooksPath hooks
	@echo "hooks/pre-commit will run on every commit."

# ------------------------------------------------------------------
# Session exit checklist
# ------------------------------------------------------------------
exit:
	@echo "=== Exit Checklist ==="
	@echo "1. make check — tests pass"
	@echo "2. make done — docs synced"
	@echo "3. git status — no stray files"
	@echo "4. progress.md — updated"
	@echo "5. session-handoff.md — updated"
	@echo ""
	@echo "Run these manually before closing the session."

# Clean build artifacts
clean:
	@rm -rf __pycache__ .pyc .coverage htmlcov 2>/dev/null || true
	@echo "Cleaned."