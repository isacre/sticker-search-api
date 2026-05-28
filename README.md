# Backend — sticker-search

API FastAPI com [uv](https://docs.astral.sh/uv/). Ver [README da raiz](../README.md) para o fluxo completo.

## Setup

```bash
cp .env.example .env
make sync
make index
make dev
```

Endpoints usados pelo frontend:

- `GET /api/v1/stickers` — listagem paginada
- `GET /api/v1/search?q=...` — busca híbrida (CLIP + tags + RRF)

## Comandos

```bash
make help
make index   # embeddings + NSFW
make tag     # tags LLM (opcional)
make test
make lint
```
