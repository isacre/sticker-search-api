import logging
import re
import unicodedata
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.core.config import settings
from app.schemas.stickers import (
    StickerItem,
    StickerListResponse,
    StickerRegisterResponse,
)
from app.schemas.tags import StickerTagsBySource, StickerTagsUpdate
from app.services.embeddings import IMAGE_EXTENSIONS
from app.services.indexing import index_single
from app.services.llm_tags import generate_tags_for_image
from app.services.stickers import catalog
from app.services.tags import (
    fetch_tags,
    fetch_tags_bulk,
    get_sticker_id,
    parse_tag_form_values,
    replace_llm_tags,
    replace_manual_tags,
)

router = APIRouter(tags=["stickers"])
logger = logging.getLogger(__name__)

_FILENAME_SAFE_RE = re.compile(r"[^\w.\-]+", re.UNICODE)


def _sanitize_filename(name: str) -> str:
    base = Path(name).name
    stem = unicodedata.normalize("NFKC", Path(base).stem).strip()
    suffix = Path(base).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS:
        msg = f"Unsupported image type: {suffix or '(none)'}"
        raise HTTPException(status_code=400, detail=msg)
    safe_stem = _FILENAME_SAFE_RE.sub("_", stem).strip("._") or "sticker"
    return f"{safe_stem}{suffix}"


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    index = 1
    while True:
        candidate = directory / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _item(name: str, tags: StickerTagsBySource | None = None) -> StickerItem:
    return StickerItem(name=name, url=f"/stickers/{name}", tags=tags)


@router.get("/stickers", response_model=StickerListResponse)
def list_stickers(
    offset: int = Query(0, ge=0),
    limit: int = Query(120, ge=1, le=500),
    include_tags: bool = Query(False),
) -> StickerListResponse:
    total = catalog.total
    if total == 0:
        raise HTTPException(status_code=503, detail="Sticker catalog not loaded")

    names = catalog.slice(offset, limit)
    tags_map: dict[str, StickerTagsBySource] = {}

    if include_tags and settings.search_enabled:
        try:
            tags_map = fetch_tags_bulk(names)
        except Exception as exc:
            logger.exception("Failed to load tags")
            raise HTTPException(status_code=503, detail="Database unavailable") from exc

    items = [
        _item(name, tags_map.get(name) if include_tags else None) for name in names
    ]

    return StickerListResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=items,
    )


@router.post("/stickers", response_model=StickerRegisterResponse)
async def register_sticker(
    file: UploadFile = File(...),
    tags_pt: list[str] = Form(default=[]),
    tags_en: list[str] = Form(default=[]),
    generate_llm_tags: bool = Form(default=False),
) -> StickerRegisterResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    filename = _sanitize_filename(file.filename)
    destination = _unique_path(settings.stickers_dir, filename)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    settings.stickers_dir.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    catalog.load(settings.stickers_dir)

    indexed = False
    llm_generated = False
    tags = StickerTagsBySource()

    if settings.search_enabled:
        try:
            index_single(destination)
            indexed = True

            manual_pt = parse_tag_form_values(tags_pt)
            manual_en = parse_tag_form_values(tags_en)
            if manual_pt or manual_en:
                replace_manual_tags(
                    destination.name,
                    tags_pt=manual_pt,
                    tags_en=manual_en,
                )

            if generate_llm_tags:
                if not settings.llm_enabled:
                    raise HTTPException(
                        status_code=503,
                        detail="LLM is not configured (LLM_API_KEY)",
                    )
                result = generate_tags_for_image(destination)
                replace_llm_tags(
                    destination.name,
                    tags_pt=result.tags_pt,
                    tags_en=result.tags_en,
                )
                llm_generated = True

            tags = fetch_tags(destination.name)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to index sticker %s", destination.name)
            detail = (
                f"Failed to index sticker: {exc}"
                if settings.debug
                else "Failed to index sticker"
            )
            raise HTTPException(status_code=503, detail=detail) from exc

    return StickerRegisterResponse(
        name=destination.name,
        url=f"/stickers/{destination.name}",
        indexed=indexed,
        tags=tags,
        llm_tags_generated=llm_generated,
    )


@router.patch("/stickers/{filename}/tags", response_model=StickerTagsBySource)
def update_sticker_tags(
    filename: str,
    body: StickerTagsUpdate,
) -> StickerTagsBySource:
    if not catalog.contains(filename):
        raise HTTPException(status_code=404, detail="Sticker not found")

    if not settings.search_enabled:
        raise HTTPException(
            status_code=503,
            detail="Search is not configured (DATABASE_URL)",
        )

    if get_sticker_id(filename) is None:
        raise HTTPException(
            status_code=404,
            detail="Sticker is not indexed. Run: make index",
        )

    try:
        return replace_manual_tags(
            filename,
            tags_pt=body.tags_pt,
            tags_en=body.tags_en,
        )
    except Exception as exc:
        logger.exception("Failed to update tags for %s", filename)
        raise HTTPException(status_code=503, detail="Failed to update tags") from exc


@router.post("/stickers/{filename}/tags/llm", response_model=StickerTagsBySource)
def generate_sticker_llm_tags(filename: str) -> StickerTagsBySource:
    if not catalog.contains(filename):
        raise HTTPException(status_code=404, detail="Sticker not found")

    if not settings.search_enabled:
        raise HTTPException(
            status_code=503,
            detail="Search is not configured (DATABASE_URL)",
        )

    if get_sticker_id(filename) is None:
        raise HTTPException(
            status_code=404,
            detail="Sticker is not indexed. Run: make index",
        )

    if not settings.llm_enabled:
        raise HTTPException(
            status_code=503,
            detail="LLM is not configured (LLM_API_KEY)",
        )

    path = settings.stickers_dir / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Sticker file missing on disk")

    try:
        result = generate_tags_for_image(path)
        return replace_llm_tags(
            filename,
            tags_pt=result.tags_pt,
            tags_en=result.tags_en,
        )
    except Exception as exc:
        logger.exception("LLM tagging failed for %s", filename)
        detail = (
            f"LLM tagging failed: {exc}" if settings.debug else "LLM tagging failed"
        )
        raise HTTPException(status_code=503, detail=detail) from exc
