import httpx
from app.core.config import settings
from app.services.llm_tags import retry_delay_seconds


def test_retry_delay_uses_retry_after_header() -> None:
    response = httpx.Response(429, headers={"Retry-After": "12"})
    assert retry_delay_seconds(response, attempt=0) == 12.0


def test_retry_delay_exponential_backoff() -> None:
    response = httpx.Response(429)
    assert retry_delay_seconds(response, attempt=0) == settings.llm_retry_base_delay
    assert retry_delay_seconds(response, attempt=2) == settings.llm_retry_base_delay * 4


def test_retry_delay_capped_at_max() -> None:
    response = httpx.Response(429, headers={"Retry-After": "999"})
    assert retry_delay_seconds(response, attempt=0) == settings.llm_retry_max_delay
