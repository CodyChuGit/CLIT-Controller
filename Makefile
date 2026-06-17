# CLIT Controller IDE — one memorable command surface.
# Backend uses the project venv at .venv; frontend uses npm in ./frontend.
# See docs/OPERATIONS.md for the full runtime model.

PY := .venv/bin/python
PIP := .venv/bin/pip
RUFF := .venv/bin/ruff
MYPY := .venv/bin/mypy
NPM := npm --prefix frontend

.DEFAULT_GOAL := help
.PHONY: help setup dev format format-check lint typecheck test test-backend test-frontend \
        build audit lock verify clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv + install backend (editable, dev extras) and frontend deps
	./scripts/install.sh

dev: ## Run backend (:8787) + Vite dev server (:5180)
	./scripts/dev.sh

format: ## Auto-format backend (ruff) and frontend (prettier)
	$(RUFF) format backend
	$(NPM) run format

format-check: ## Verify formatting without writing
	$(RUFF) format --check backend
	$(NPM) run format:check

lint: ## Lint backend (ruff) and frontend (eslint)
	$(RUFF) check backend
	$(NPM) run lint

typecheck: ## Type-check backend (mypy) and frontend (tsc)
	$(MYPY)
	$(NPM) run typecheck

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests with coverage
	$(PY) -m pytest backend/tests --cov=agentflow

test-frontend: ## Run frontend unit/component tests
	$(NPM) run test

build: ## Production build of the frontend (tsc && vite build)
	$(NPM) run build

audit: ## Dependency vulnerability scan (python + npm)
	$(PY) -m pip_audit || true
	$(NPM) audit || true

lock: ## Regenerate the Python lockfile from the current venv
	$(PIP) freeze --exclude-editable > requirements.lock

verify: format-check lint typecheck test build ## Full local verification (mirrors CI)
	@echo "✓ verify passed"

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache frontend/dist
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
