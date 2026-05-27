.PHONY: help install sync dev run test lint format clean

UV      ?= uv
APP     ?= app.main:app
HOST    ?= 0.0.0.0
PORT    ?= 8000

.DEFAULT_GOAL := help

help: ## Lista os comandos disponíveis
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: sync ## Instala dependências (alias de sync)

sync: ## Sincroniza o ambiente com uv.lock
	$(UV) sync --all-groups

dev: ## Sobe o servidor com reload
	$(UV) run uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

run: ## Sobe o servidor (produção local)
	$(UV) run uvicorn $(APP) --host $(HOST) --port $(PORT)

test: ## Roda os testes
	$(UV) run pytest

lint: ## Checa o código com ruff
	$(UV) run ruff check app tests

format: ## Formata o código com ruff
	$(UV) run ruff check --fix app tests
	$(UV) run ruff format app tests

clean: ## Remove caches Python
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -prune -exec rm -rf {} + 2>/dev/null || true
