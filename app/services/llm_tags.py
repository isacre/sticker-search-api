import asyncio
import base64
import json
import logging
import sys
import time
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image

from app.core.config import settings
from app.schemas.tags import LlmTagResult

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503})

_SYSTEM_PROMPT = """\
You tag WhatsApp stickers for search. Return ONLY valid JSON with this shape:
{
  "text_on_sticker": "verbatim text visible on the image or null",
  "tags_pt": ["3-8 short tags in Brazilian Portuguese"],
  "tags_en": ["3-8 short tags in English, same meaning as tags_pt"]
}
Rules:
- tags_pt and tags_en must mirror each other (same concepts, natural in each language)
- Include emotion, meme/reference, character/series, artist if visible or obvious
- Include any readable phrase from the sticker as a tag in both languages when possible
- Lowercase, no hashtags, no sentences in tags
"""

_USER_PROMPT = (
    "Analyze this sticker and fill the JSON schema. "
    "Focus on searchability in PT-BR and English."
)


class _RequestPacer:
    def __init__(self, min_interval: float) -> None:
        self._min_interval = max(0.0, min_interval)
        self._lock = asyncio.Lock()
        self._last_at = 0.0

    async def wait(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            delay = self._min_interval - (now - self._last_at)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_at = time.monotonic()


_pacer = _RequestPacer(settings.llm_min_request_interval)


def _prepare_image_data_url(path: Path) -> str:
    image = Image.open(path)
    max_size = settings.llm_image_max_size
    if max(image.size) > max_size:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    if image.mode in ("RGBA", "LA") or (
        image.mode == "P" and "transparency" in image.info
    ):
        background = Image.new("RGB", image.size, (255, 255, 255))
        rgba = image.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[3])
        image = background
    else:
        image = image.convert("RGB")

    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=settings.llm_image_quality, optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _build_payload(data_url: str) -> dict:
    return {
        "model": settings.llm_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url,
                            "detail": settings.llm_image_detail,
                        },
                    },
                ],
            },
        ],
    }


def _llm_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }


def _chat_completions_url() -> str:
    return f"{settings.llm_base_url.rstrip('/')}/chat/completions"


def _parse_llm_json(content: str) -> LlmTagResult:
    data = json.loads(content)
    text = data.get("text_on_sticker")
    tags_pt = data.get("tags_pt") or []
    tags_en = data.get("tags_en") or []

    if text and isinstance(text, str) and text.strip().lower() not in ("null", "none"):
        tags_pt = [text.strip(), *tags_pt]
        tags_en = [text.strip(), *tags_en]

    return LlmTagResult(
        text_on_sticker=text if isinstance(text, str) else None,
        tags_pt=[str(t) for t in tags_pt if t],
        tags_en=[str(t) for t in tags_en if t],
    )


def _parse_response(body: dict, *, path: Path) -> LlmTagResult:
    content = body["choices"][0]["message"]["content"]
    try:
        return _parse_llm_json(content)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.exception("Invalid LLM tag response for %s: %s", path.name, content)
        msg = "LLM returned invalid tag JSON"
        raise ValueError(msg) from exc


def _ensure_llm_enabled() -> None:
    if not settings.llm_enabled:
        msg = "LLM is not configured (LLM_API_KEY)"
        raise RuntimeError(msg)


def retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return min(float(retry_after), settings.llm_retry_max_delay)
        except ValueError:
            pass
    delay = settings.llm_retry_base_delay * (2**attempt)
    return min(delay, settings.llm_retry_max_delay)


def _log_retry(path: Path, *, attempt: int, delay: float, status: int) -> None:
    msg = (
        f"  rate limited ({status}) {path.name}, "
        f"retry {attempt}/{settings.llm_max_retries} in {delay:.0f}s"
    )
    print(msg, file=sys.stderr, flush=True)
    logger.warning(msg)


async def _post_with_retry_async(
    client: httpx.AsyncClient,
    payload: dict,
    *,
    path: Path,
) -> LlmTagResult:
    await _pacer.wait()
    last_response: httpx.Response | None = None
    for attempt in range(settings.llm_max_retries + 1):
        response = await client.post(
            _chat_completions_url(),
            headers=_llm_headers(),
            json=payload,
        )
        if response.status_code not in _RETRYABLE_STATUS:
            response.raise_for_status()
            return _parse_response(response.json(), path=path)

        last_response = response
        if attempt >= settings.llm_max_retries:
            break

        delay = retry_delay_seconds(response, attempt)
        _log_retry(path, attempt=attempt + 1, delay=delay, status=response.status_code)
        await asyncio.sleep(delay)

    assert last_response is not None
    last_response.raise_for_status()
    return _parse_response(last_response.json(), path=path)


async def generate_tags_for_image_async(
    path: Path,
    client: httpx.AsyncClient,
) -> LlmTagResult:
    _ensure_llm_enabled()
    payload = _build_payload(_prepare_image_data_url(path))
    return await _post_with_retry_async(client, payload, path=path)
