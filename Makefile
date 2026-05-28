.PHONY: help sync dev run test lint format clean db-up db-down db-logs db-migrate db-reset reindex index tag

UV      ?= uv
APP     ?= app.main:app
HOST    ?= 0.0.0.0
PORT    ?= 8000

.DEFAULT_GOAL := help

help: ## Lista os comandos disponíveis
	@grep -E '^[a-zA-Z0-9_-]+:.*##' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

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

db-up: ## Sobe Postgres + pgvector (docker compose na raiz)
	docker compose -f ../docker-compose.yml up -d postgres

db-down: ## Para o Postgres
	docker compose -f ../docker-compose.yml down

db-logs: ## Logs do Postgres
	docker compose -f ../docker-compose.yml logs -f postgres

db-migrate: ## Aplica migração de tags (DBs antigos sem sticker_tags)
	PGPASSWORD=sticker psql -h localhost -p 5433 -U sticker -d sticker_search -f ../db/init/03-tags.sql

db-reset: ## Zera stickers + tags no banco
	PGPASSWORD=sticker psql -h localhost -p 5433 -U sticker -d sticker_search -f ../db/scripts/truncate.sql

reindex: db-reset index ## Zera o banco e indexa STICKERS_DIR

index: ## Indexa figurinhas (STICKERS_DIR) no pgvector
	$(UV) run python -m app.scripts.index_stickers

tag: ## Gera tags PT/EN via LLM (usa LLM_CONCURRENCY do .env)
	$(UV) run python -m app.scripts.tag_stickers
