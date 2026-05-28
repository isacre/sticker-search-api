from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "sticker-search-api"
    debug: bool = False
    api_prefix: str = "/api/v1"
    stickers_dir: Path = _REPO_ROOT / "stickers"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    database_url: str | None = None
    clip_image_model_name: str = Field(
        default="clip-ViT-B-32",
        validation_alias=AliasChoices("clip_image_model_name", "clip_model_name"),
    )
    clip_text_model_name: str = "clip-ViT-B-32-multilingual-v1"
    embedding_dimensions: int = 512
    index_batch_size: int = 32
    search_min_score: float = 0.25
    search_recall_size: int = 200
    search_return_size: int = 60
    search_rerank_enabled: bool = True
    search_max_results: int = 2000
    search_hnsw_ef_search: int = 1000
    nsfw_filter_enabled: bool = True
    nsfw_max_score: float = 0.6
    nsfw_model_name: str = "Falconsai/nsfw_image_detection"
    nsfw_batch_size: int = 16
    search_hybrid_enabled: bool = True
    search_hybrid_rrf_k: int = 60
    llm_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("llm_api_key", "LLM_API_KEY", "LLM_APY_KEY"),
    )
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_concurrency: int = 3
    llm_max_retries: int = 6
    llm_retry_base_delay: float = 2.0
    llm_retry_max_delay: float = 60.0
    llm_min_request_interval: float = 0.15
    llm_image_max_size: int = 512
    llm_image_quality: int = 85
    llm_image_detail: str = "low"
    llm_batch_size: int = 4
    llm_request_timeout: float = 60.0

    @property
    def search_enabled(self) -> bool:
        return bool(self.database_url)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)


settings = Settings()
