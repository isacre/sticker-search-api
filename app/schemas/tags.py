from pydantic import BaseModel, Field


class LlmTagResult(BaseModel):
    text_on_sticker: str | None = None
    tags_pt: list[str] = Field(default_factory=list)
    tags_en: list[str] = Field(default_factory=list)
