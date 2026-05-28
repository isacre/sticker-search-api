from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.db.pool import close_pool, init_pool
from app.services.embeddings import warmup_models
from app.services.stickers import catalog


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    catalog.load(settings.stickers_dir)
    if settings.search_enabled:
        init_pool()
        warmup_models()
    yield
    close_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)
    app.mount(
        "/stickers",
        StaticFiles(directory=str(settings.stickers_dir)),
        name="stickers",
    )
    return app


app = create_app()
