from pydantic import BaseModel, Field

from app.schemas.tags import StickerTagsBySource


class StickerItem(BaseModel):
    name: str
    url: str
    tags: StickerTagsBySource | None = None


class StickerListResponse(BaseModel):
    total: int
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    items: list[StickerItem]


class StickerRegisterResponse(BaseModel):
    name: str
    url: str
    indexed: bool
    tags: StickerTagsBySource
    llm_tags_generated: bool = False
