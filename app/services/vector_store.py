from pathlib import Path

import numpy as np

from app.db.pool import get_pool
from app.services.embeddings import IMAGE_EXTENSIONS

UPSERT_SQL = """
INSERT INTO stickers (filename, embedding, nsfw_score)
VALUES (%s, %s, %s)
ON CONFLICT (filename) DO UPDATE SET
    embedding = EXCLUDED.embedding,
    nsfw_score = EXCLUDED.nsfw_score,
    updated_at = now()
"""

SEARCH_BY_SCORE_SQL = """
SELECT filename,
       1 - (embedding <=> %s::vector) AS score,
       nsfw_score
FROM stickers
WHERE (embedding <=> %s::vector) <= %s
  AND COALESCE(nsfw_score, 1.0) < %s
ORDER BY embedding <=> %s::vector
LIMIT %s
"""


def upsert_batch(
    filenames: list[str],
    embeddings: np.ndarray,
    nsfw_scores: list[float | None] | None = None,
) -> int:
    if len(filenames) != len(embeddings):
        msg = "filenames and embeddings length mismatch"
        raise ValueError(msg)

    nsfw_scores = nsfw_scores or [None] * len(filenames)
    if len(nsfw_scores) != len(filenames):
        msg = "filenames and nsfw_scores length mismatch"
        raise ValueError(msg)

    rows = list(
        zip(filenames, embeddings.tolist(), nsfw_scores, strict=True),
    )

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, rows)

    return len(rows)


def count_indexed() -> int:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM stickers")
            row = cur.fetchone()
    return int(row[0]) if row else 0


FETCH_EMBEDDINGS_SQL = """
SELECT filename, embedding
FROM stickers
WHERE filename = ANY(%s)
"""


def fetch_embeddings(filenames: list[str]) -> dict[str, np.ndarray]:
    if not filenames:
        return {}

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(FETCH_EMBEDDINGS_SQL, (filenames,))
            rows = cur.fetchall()

    return {
        str(filename): np.asarray(embedding, dtype=np.float32)
        for filename, embedding in rows
    }


def search(
    query_embedding: np.ndarray,
    *,
    min_score: float,
    max_results: int,
    hnsw_ef_search: int,
    nsfw_max_score: float | None = None,
) -> list[tuple[str, float, float | None]]:
    vector = query_embedding.tolist()
    max_distance = 1.0 - min_score
    ef = max(1, min(hnsw_ef_search, 1000))
    nsfw_ceiling = nsfw_max_score if nsfw_max_score is not None else 1.0

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SET LOCAL hnsw.ef_search = {ef}")
            cur.execute(
                SEARCH_BY_SCORE_SQL,
                (vector, vector, max_distance, nsfw_ceiling, vector, max_results),
            )
            rows = cur.fetchall()
    return [
        (str(filename), float(score), float(nsfw) if nsfw is not None else None)
        for filename, score, nsfw in rows
    ]


FETCH_NSFW_SQL = """
SELECT filename, nsfw_score
FROM stickers
WHERE filename = ANY(%s)
"""


def fetch_nsfw_scores(filenames: list[str]) -> dict[str, float | None]:
    if not filenames:
        return {}

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(FETCH_NSFW_SQL, (filenames,))
            rows = cur.fetchall()

    return {
        str(filename): float(nsfw) if nsfw is not None else None
        for filename, nsfw in rows
    }


def list_indexed_filenames() -> list[str]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT filename FROM stickers ORDER BY filename")
            rows = cur.fetchall()
    return [str(row[0]) for row in rows]


def list_image_paths(directory: Path) -> list[Path]:
    if not directory.is_dir():
        msg = f"Stickers directory not found: {directory}"
        raise FileNotFoundError(msg)

    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
