from pydantic import BaseModel, Field


class StickerItem(BaseModel):
    name: str
    url: str


class StickerListResponse(BaseModel):
    total: int
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    items: list[StickerItem]
