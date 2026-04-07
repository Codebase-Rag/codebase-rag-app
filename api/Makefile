CELERY_PIDFILE := .celery.pid
CELERY_BEAT_PIDFILE := .celery-beat.pid
CELERY_LOGFILE := .celery.log
CELERY_BEAT_LOGFILE := .celery-beat.log

run: ## Run FastAPI only (for local dev with Docker Compose providing infra)
	uv run main.py

run-all: ## Run FastAPI + Celery locally (Ctrl+C stops all)
	@uv run celery -A celery_app.main worker --loglevel=info --logfile=$(CELERY_LOGFILE) --pidfile=$(CELERY_PIDFILE) & \
	uv run celery -A celery_app.main beat --loglevel=info --logfile=$(CELERY_BEAT_LOGFILE) --pidfile=$(CELERY_BEAT_PIDFILE) & \
	trap 'kill $$(cat $(CELERY_PIDFILE) 2>/dev/null) $$(cat $(CELERY_BEAT_PIDFILE) 2>/dev/null) 2>/dev/null; rm -f $(CELERY_PIDFILE) $(CELERY_BEAT_PIDFILE)' EXIT; \
	uv run main.py

celery-start: ## Start Celery worker and beat in background (persistent)
	@if [ -f $(CELERY_PIDFILE) ] && kill -0 $$(cat $(CELERY_PIDFILE)) 2>/dev/null; then \
		echo "Celery worker already running (PID: $$(cat $(CELERY_PIDFILE)))"; \
	else \
		echo "Starting Celery worker..."; \
		uv run celery -A celery_app.main worker --loglevel=info --pidfile=$(CELERY_PIDFILE) --logfile=$(CELERY_LOGFILE) --detach; \
	fi
	@if [ -f $(CELERY_BEAT_PIDFILE) ] && kill -0 $$(cat $(CELERY_BEAT_PIDFILE)) 2>/dev/null; then \
		echo "Celery beat already running (PID: $$(cat $(CELERY_BEAT_PIDFILE)))"; \
	else \
		echo "Starting Celery beat..."; \
		uv run celery -A celery_app.main beat --loglevel=info --pidfile=$(CELERY_BEAT_PIDFILE) --logfile=$(CELERY_BEAT_LOGFILE) --detach; \
	fi

celery-logs: ## Tail Celery logs (Ctrl+C to stop)
	tail -f $(CELERY_LOGFILE) $(CELERY_BEAT_LOGFILE)

celery-foreground: ## Run Celery in foreground (for debugging)
	uv run celery -A celery_app.main worker --beat --loglevel=info

celery-stop: ## Stop Celery worker and beat
	@if [ -f $(CELERY_PIDFILE) ]; then \
		echo "Stopping Celery worker (PID: $$(cat $(CELERY_PIDFILE)))..."; \
		kill $$(cat $(CELERY_PIDFILE)) 2>/dev/null || true; \
		rm -f $(CELERY_PIDFILE); \
	else \
		echo "No Celery worker PID file found"; \
	fi
	@if [ -f $(CELERY_BEAT_PIDFILE) ]; then \
		echo "Stopping Celery beat (PID: $$(cat $(CELERY_BEAT_PIDFILE)))..."; \
		kill $$(cat $(CELERY_BEAT_PIDFILE)) 2>/dev/null || true; \
		rm -f $(CELERY_BEAT_PIDFILE); \
	else \
		echo "No Celery beat PID file found"; \
	fi

celery-status: ## Check Celery worker and beat status
	@if [ -f $(CELERY_PIDFILE) ] && kill -0 $$(cat $(CELERY_PIDFILE)) 2>/dev/null; then \
		echo "Celery worker: running (PID: $$(cat $(CELERY_PIDFILE)))"; \
	else \
		echo "Celery worker: stopped"; \
	fi
	@if [ -f $(CELERY_BEAT_PIDFILE) ] && kill -0 $$(cat $(CELERY_BEAT_PIDFILE)) 2>/dev/null; then \
		echo "Celery beat: running (PID: $$(cat $(CELERY_BEAT_PIDFILE)))"; \
	else \
		echo "Celery beat: stopped"; \
	fi

.PHONY: help all install dev test clean python celery-start celery-stop celery-status

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

all: ## Install everything for full development environment (deps, grammars, hooks, tests)
	@echo "🚀 Setting up complete development environment..."
	uv sync --all-extras
	git submodule update --init --recursive --depth 1
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg
	@echo "🧪 Running tests in parallel to verify installation..."
	uv run pytest -n auto
	@echo "✅ Full development environment ready!"
	@echo "📦 Installed: All dependencies, grammars, pre-commit hooks"
	@echo "✓ Tests passed successfully"

install: ## Install project dependencies with full language support
	uv sync --extra treesitter-full

python: ## Install project dependencies for Python only
	uv sync

dev: ## Setup development environment (install deps + pre-commit hooks)
	uv sync --extra treesitter-full --extra dev --extra test
	uv run pre-commit install
	uv run pre-commit install --hook-type commit-msg
	@echo "✅ Development environment ready!"

test: ## Run tests
	uv run pytest

test-parallel: ## Run tests in parallel
	uv run pytest -n auto

clean: ## Clean up build artifacts and cache
	rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
build-grammars: ## Build grammar submodules
	git submodule update --init --recursive --depth 1
	@echo "Grammars built!"

watch: ## Watch repository for changes and update graph in real-time
	@if [ -z "$(REPO_PATH)" ]; then \
		echo "Error: REPO_PATH is required. Usage: make watch REPO_PATH=/path/to/repo"; \
		exit 1; \
	fi
	.venv/bin/python realtime_updater.py $(REPO_PATH) \
		--host $(or $(HOST),localhost) \
		--port $(or $(PORT),7687) \
		$(if $(BATCH_SIZE),--batch-size $(BATCH_SIZE),)
