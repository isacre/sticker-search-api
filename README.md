# Backend — sticker-search

API FastAPI com [uv](https://docs.astral.sh/uv/).

## Setup

```bash
cp .env.example .env
make install
```

## Busca semântica (Postgres + pgvector)

Na **raiz do repo**:

```bash
docker compose up -d postgres   # ou: cd backend && make db-up
```

No **backend**:

```bash
cp .env.example .env            # DATABASE_URL já aponta pro compose
make index                      # embede stickers/ no banco (1ª vez baixa o CLIP)
make dev
```

Endpoints:

- `GET /api/v1/search?q=lagarto+joinha` — recall (`SEARCH_RECALL_SIZE` 200) + rerank → `SEARCH_RETURN_SIZE` (padrão 60)
- Texto: `clip-ViT-B-32-multilingual-v1` | Imagens (index): `clip-ViT-B-32`
- Parâmetros opcionais: `min_score`, `limit` (limite final após rerank)
- `GET /api/v1/search/status`

## Desenvolvimento

```bash
make dev
```

- App: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## Comandos

```bash
make help    # lista todos os targets
make db-up   # Postgres + pgvector
make index   # indexar figurinhas
make test
make lint
make format
```
