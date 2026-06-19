# Command Hub — dev convenience targets.
# Usage: make <target>

VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: help setup test lint check-env check-supabase check-claude run dashboard \
        migrate seed load-schedule clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

setup: ## Create venv and install dependencies
	python -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test: ## Run the unit tests
	$(PY) -m pytest -q

lint: ## Lint with ruff (if installed)
	-$(PY) -m ruff check .

check-env: ## Phase-0: guardrail + config presence
	$(PY) -m scripts.check_env

check-supabase: ## Phase-0: verify Supabase connectivity
	$(PY) -m scripts.check_supabase

check-claude: ## Phase-0: verify the subscription-authed agent
	$(PY) -m scripts.check_claude

migrate: ## Apply DB migrations (needs DATABASE_URL) or print manual steps
	$(PY) -m db.migrate

seed: ## Seed people + channel routes from .env
	$(PY) -m db.seed

load-schedule: ## Load db/schedule_template.json into schedule_blocks
	$(PY) -m db.load_schedule

run: ## Start the Discord bot + scheduler
	$(PY) -m bot.main

dashboard: ## Start the admin dashboard
	$(PY) -m dashboard.app

clean: ## Remove caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache
