from fastapi import APIRouter

from app.api.routes import search, stickers

api_router = APIRouter()
api_router.include_router(stickers.router)
api_router.include_router(search.router)
