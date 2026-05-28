import logging

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.db.pool import get_pool
from app.schemas.search import StickerSearchItem, StickerSearchResponse
from app.services.embeddings import encode_query_variants, encode_text
from app.services.rerank import reciprocal_rank_fusion, rerank_by_max_variant_similarity
from app.services.tags import search_by_tags
from app.services.vector_store import (
    count_indexed,
    fetch_embeddings,
    fetch_nsfw_scores,
    search,
)

router = APIRouter(tags=["search"])
logger = logging.getLogger(__name__)


def _rerank_candidates(
    query: str,
    candidates: list[tuple[str, float, float | None]],
    final_limit: int,
) -> list[tuple[str, float, float | None]]:
    if not candidates:
        return []

    nsfw_by_name = {name: nsfw for name, _, nsfw in candidates}
    filenames = [name for name, _, _ in candidates]
    embeddings_map = fetch_embeddings(filenames)

    ordered_names: list[str] = []
    ordered_embeddings: list[np.ndarray] = []
    for name in filenames:
        emb = embeddings_map.get(name)
        if emb is not None:
            ordered_names.append(name)
            ordered_embeddings.append(emb)

    if not ordered_names:
        return candidates[:final_limit]

    query_variants = encode_query_variants(query)
    stacked = np.stack(ordered_embeddings, axis=0)
    reranked = rerank_by_max_variant_similarity(
        query_variants,
        ordered_names,
        stacked,
    )

    return [
        (name, score, nsfw_by_name.get(name)) for name, score in reranked[:final_limit]
    ]


def _hybrid_search(
    query: str,
    *,
    min_similarity: float,
    recall_limit: int,
    final_limit: int,
    nsfw_ceiling: float,
) -> list[tuple[str, float, float | None]]:
    query_embedding = encode_text(query)
    clip_candidates = search(
        query_embedding,
        min_score=min_similarity,
        max_results=recall_limit,
        hnsw_ef_search=settings.search_hnsw_ef_search,
        nsfw_max_score=nsfw_ceiling,
    )
    clip_hits = _rerank_candidates(query, clip_candidates, recall_limit)
    tag_hits = search_by_tags(
        query,
        max_results=recall_limit,
        nsfw_max_score=nsfw_ceiling,
    )

    clip_ranking = [(name, score) for name, score, _ in clip_hits]
    merged = reciprocal_rank_fusion(
        [clip_ranking, tag_hits],
        k=settings.search_hybrid_rrf_k,
    )[:final_limit]

    if not merged:
        return []

    nsfw_by_name = {name: nsfw for name, _, nsfw in clip_hits}
    missing = [name for name, _ in merged if name not in nsfw_by_name]
    if missing:
        nsfw_by_name.update(fetch_nsfw_scores(missing))

    return [(name, score, nsfw_by_name.get(name)) for name, score in merged]


@router.get("/search", response_model=StickerSearchResponse)
def search_stickers(
    q: str = Query(..., min_length=1, max_length=500),
    min_score: float | None = Query(None, ge=0.0, le=1.0),
    limit: int | None = Query(None, ge=1, le=5000),
) -> StickerSearchResponse:
    if not settings.search_enabled:
        raise HTTPException(
            status_code=503,
            detail="Search is not configured (DATABASE_URL)",
        )

    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        get_pool()
        min_similarity = (
            min_score if min_score is not None else settings.search_min_score
        )
        nsfw_ceiling = settings.nsfw_max_score if settings.nsfw_filter_enabled else 2.0
        final_limit = limit if limit is not None else settings.search_return_size
        recall_limit = max(settings.search_recall_size, final_limit)

        hits = _hybrid_search(
            query,
            min_similarity=min_similarity,
            recall_limit=recall_limit,
            final_limit=final_limit,
            nsfw_ceiling=nsfw_ceiling,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Search failed for query=%r", query)
        detail = f"Search failed: {exc}" if settings.debug else "Search failed"
        raise HTTPException(status_code=503, detail=detail) from exc

    items = [
        StickerSearchItem(
            name=filename,
            url=f"/stickers/{filename}",
            score=round(score, 4),
            nsfw_score=round(nsfw_score, 4) if nsfw_score is not None else None,
        )
        for filename, score, nsfw_score in hits
    ]

    return StickerSearchResponse(
        items=items,
    )
