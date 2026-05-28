from fastapi import APIRouter, HTTPException, Query

from app.schemas.stickers import StickerItem, StickerListResponse
from app.services.stickers import catalog

router = APIRouter(tags=["stickers"])


@router.get("/stickers", response_model=StickerListResponse)
def list_stickers(
    offset: int = Query(0, ge=0),
    limit: int = Query(120, ge=1, le=500),
) -> StickerListResponse:
    total = catalog.total
    if total == 0:
        raise HTTPException(status_code=503, detail="Sticker catalog not loaded")

    names = catalog.slice(offset, limit)
    items = [StickerItem(name=name, url=f"/stickers/{name}") for name in names]

    return StickerListResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=items,
    )
