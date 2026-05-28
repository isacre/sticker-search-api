from pydantic import BaseModel, Field


class StickerTags(BaseModel):
    pt: list[str] = Field(default_factory=list)
    en: list[str] = Field(default_factory=list)


class StickerTagsBySource(BaseModel):
    manual: StickerTags = Field(default_factory=StickerTags)
    llm: StickerTags = Field(default_factory=StickerTags)


class StickerTagsUpdate(BaseModel):
    tags_pt: list[str] = Field(default_factory=list, max_length=50)
    tags_en: list[str] = Field(default_factory=list, max_length=50)


class LlmTagResult(BaseModel):
    text_on_sticker: str | None = None
    tags_pt: list[str] = Field(default_factory=list)
    tags_en: list[str] = Field(default_factory=list)
