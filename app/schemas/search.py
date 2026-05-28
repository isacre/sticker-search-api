from pydantic import BaseModel, Field


class StickerSearchItem(BaseModel):
    name: str
    url: str
    score: float = Field(ge=-1.0, le=1.0, description="Similaridade CLIP com a query")
    nsfw_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Probabilidade NSFW do classificador",
    )


class StickerSearchResponse(BaseModel):
    query: str
    total_indexed: int
    items: list[StickerSearchItem]


class SearchIndexStatus(BaseModel):
    enabled: bool
    indexed: int
    ready: bool
