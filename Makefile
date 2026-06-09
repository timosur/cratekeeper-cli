.DEFAULT_GOAL := help
SHELL := /bin/bash

# ── Paths ────────────────────────────────────────────────────────────
PKG_DIR   := cratekeeper-cli
VENV      := .venv
BIN       := $(VENV)/bin
PYTHON    := $(BIN)/python
PIP       := $(BIN)/pip
PYTEST    := $(BIN)/pytest
RUFF      := $(BIN)/ruff

# ── Python discovery (first available ≥3.11) ────────────────────────
SYSTEM_PYTHON := $(shell \
	for p in python3.13 python3.12 python3.11; do \
		cmd=$$(command -v $$p 2>/dev/null); \
		if [ -n "$$cmd" ]; then echo "$$cmd"; break; fi; \
	done \
)
ifeq ($(SYSTEM_PYTHON),)
SYSTEM_PYTHON := $(shell \
	for p in \
		/opt/homebrew/opt/python@3.13/bin/python3.13 \
		/opt/homebrew/opt/python@3.12/bin/python3.12 \
		/opt/homebrew/opt/python@3.11/bin/python3.11; do \
		if [ -x "$$p" ]; then echo "$$p"; break; fi; \
	done \
)
endif

# ── Targets ──────────────────────────────────────────────────────────

.PHONY: help venv install test lint format check db db-stop docker-build docker-run clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

$(VENV)/pyvenv.cfg:
	@if [ -z "$(SYSTEM_PYTHON)" ]; then \
		echo "ERROR: No Python ≥3.11 found. Install via pyenv or Homebrew."; exit 1; \
	fi
	@echo "Creating venv with $(SYSTEM_PYTHON)…"
	$(SYSTEM_PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip

venv: $(VENV)/pyvenv.cfg ## Create .venv and install package + dev deps
	$(PIP) install -e "$(PKG_DIR)[dev]"
	@echo ""
	@echo "Done. Activate with:  source $(VENV)/bin/activate"

install: ## Re-install package + dev deps into existing venv
	$(PIP) install -e "$(PKG_DIR)[dev]"

test: ## Run pytest
	cd $(PKG_DIR) && ../$(PYTEST) $(ARGS)

lint: ## Run ruff check
	$(RUFF) check $(PKG_DIR)

format: ## Run ruff format
	$(RUFF) format $(PKG_DIR)

check: lint test ## Lint + test

db: ## Start Postgres (docker compose)
	docker compose up -d db

db-stop: ## Stop all docker compose services
	docker compose down

docker-build: ## Build Docker image
	docker compose build

docker-run: ## Run crate CLI in Docker (pass ARGS="…")
	docker compose run --rm crate $(ARGS)

clean: ## Remove .venv, caches, build artifacts
	rm -rf $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(PKG_DIR)/build $(PKG_DIR)/dist $(PKG_DIR)/*.egg-info
