import numpy as np


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return matrix / norms


def rerank_by_max_variant_similarity(
    query_embeddings: np.ndarray,
    filenames: list[str],
    candidate_embeddings: np.ndarray,
) -> list[tuple[str, float]]:
    if not filenames:
        return []

    q = _normalize_rows(np.asarray(query_embeddings, dtype=np.float32))
    c = _normalize_rows(np.asarray(candidate_embeddings, dtype=np.float32))
    similarities = q @ c.T
    best = similarities.max(axis=0)

    order = np.argsort(-best)
    return [(filenames[i], float(best[i])) for i in order]


def reciprocal_rank_fusion(
    rankings: list[list[tuple[str, float]]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    if not rankings:
        return []

    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, (name, _score) in enumerate(ranking):
            scores[name] = scores.get(name, 0.0) + 1.0 / (k + rank + 1)

    return sorted(scores.items(), key=lambda item: -item[1])
