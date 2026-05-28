import re
import unicodedata

from app.db.pool import get_pool

_TAG_SPLIT_RE = re.compile(r"[,;\n]+")
_MAX_TAG_LEN = 80


def normalize_tag(raw: str) -> str | None:
    text = unicodedata.normalize("NFKC", raw).strip().lower()
    if not text or len(text) > _MAX_TAG_LEN:
        return None
    return text


def normalize_tags(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in tags:
        for part in _TAG_SPLIT_RE.split(raw):
            tag = normalize_tag(part)
            if tag and tag not in seen:
                seen.add(tag)
                out.append(tag)
    return out


def get_sticker_id(filename: str) -> int | None:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM stickers WHERE filename = %s", (filename,))
            row = cur.fetchone()
    return int(row[0]) if row else None


def replace_llm_tags(
    filename: str,
    *,
    tags_pt: list[str],
    tags_en: list[str],
) -> None:
    sticker_id = get_sticker_id(filename)
    if sticker_id is None:
        msg = f"Sticker not indexed: {filename}"
        raise LookupError(msg)

    pt = normalize_tags(tags_pt)
    en = normalize_tags(tags_en)

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM sticker_tags WHERE sticker_id = %s AND source = 'llm'",
                (sticker_id,),
            )
            rows = [
                (sticker_id, tag, lang, "llm")
                for lang, tags in (("pt", pt), ("en", en))
                for tag in tags
            ]
            if rows:
                cur.executemany(
                    """
                    INSERT INTO sticker_tags (sticker_id, tag, lang, source)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (sticker_id, tag, lang, source) DO NOTHING
                    """,
                    rows,
                )


def list_filenames_without_llm_tags() -> list[str]:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.filename
                FROM stickers s
                LEFT JOIN sticker_tags t
                    ON t.sticker_id = s.id AND t.source = 'llm'
                GROUP BY s.id, s.filename
                HAVING COUNT(t.id) = 0
                ORDER BY s.filename
                """,
            )
            rows = cur.fetchall()
    return [str(row[0]) for row in rows]


def search_terms_from_query(query: str) -> list[str]:
    return normalize_tags([query, *query.split()])


def search_by_tags(
    query: str,
    *,
    max_results: int,
    nsfw_max_score: float | None = None,
) -> list[tuple[str, float]]:
    terms = search_terms_from_query(query)
    if not terms:
        return []

    nsfw_ceiling = nsfw_max_score if nsfw_max_score is not None else 1.0

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH terms AS (
                    SELECT unnest(%s::text[]) AS term
                ),
                matches AS (
                    SELECT s.filename,
                           COUNT(DISTINCT t.id) AS hit_count,
                           COUNT(DISTINCT terms.term) AS term_hits
                    FROM stickers s
                    JOIN sticker_tags t ON t.sticker_id = s.id
                    CROSS JOIN terms
                    WHERE (
                        t.tag ILIKE '%%' || terms.term || '%%'
                        OR terms.term ILIKE '%%' || t.tag || '%%'
                    )
                      AND COALESCE(s.nsfw_score, 1.0) < %s
                    GROUP BY s.filename
                )
                SELECT filename,
                       term_hits::float
                       / GREATEST(array_length(%s::text[], 1), 1) AS score
                FROM matches
                ORDER BY score DESC, hit_count DESC, filename
                LIMIT %s
                """,
                (terms, nsfw_ceiling, terms, max_results),
            )
            rows = cur.fetchall()

    return [(str(filename), float(score)) for filename, score in rows]
