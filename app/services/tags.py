import re
import unicodedata

from app.db.pool import get_pool
from app.schemas.tags import StickerTags, StickerTagsBySource

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


def parse_tag_form_values(values: list[str]) -> list[str]:
    parsed: list[str] = []
    for value in values:
        parsed.extend(_TAG_SPLIT_RE.split(value))
    return normalize_tags(parsed)


def get_sticker_id(filename: str) -> int | None:
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM stickers WHERE filename = %s", (filename,))
            row = cur.fetchone()
    return int(row[0]) if row else None


def replace_manual_tags(
    filename: str,
    *,
    tags_pt: list[str],
    tags_en: list[str],
) -> StickerTagsBySource:
    sticker_id = get_sticker_id(filename)
    if sticker_id is None:
        msg = f"Sticker not indexed: {filename}"
        raise LookupError(msg)

    pt = normalize_tags(tags_pt)
    en = normalize_tags(tags_en)

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM sticker_tags WHERE sticker_id = %s AND source = 'manual'",
                (sticker_id,),
            )
            rows = [
                (sticker_id, tag, lang, "manual")
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

    return fetch_tags(filename)


def replace_llm_tags(
    filename: str,
    *,
    tags_pt: list[str],
    tags_en: list[str],
) -> StickerTagsBySource:
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

    return fetch_tags(filename)


def fetch_tags(filename: str) -> StickerTagsBySource:
    sticker_id = get_sticker_id(filename)
    if sticker_id is None:
        return StickerTagsBySource()

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tag, lang, source
                FROM sticker_tags
                WHERE sticker_id = %s
                ORDER BY tag
                """,
                (sticker_id,),
            )
            rows = cur.fetchall()

    manual = StickerTags()
    llm = StickerTags()
    for tag, lang, source in rows:
        bucket = manual if source == "manual" else llm
        if lang == "pt":
            bucket.pt.append(tag)
        else:
            bucket.en.append(tag)
    return StickerTagsBySource(manual=manual, llm=llm)


def fetch_tags_bulk(filenames: list[str]) -> dict[str, StickerTagsBySource]:
    if not filenames:
        return {}

    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.filename, t.tag, t.lang, t.source
                FROM stickers s
                JOIN sticker_tags t ON t.sticker_id = s.id
                WHERE s.filename = ANY(%s)
                ORDER BY s.filename, t.tag
                """,
                (filenames,),
            )
            rows = cur.fetchall()

    out: dict[str, StickerTagsBySource] = {}
    for filename, tag, lang, source in rows:
        name = str(filename)
        if name not in out:
            out[name] = StickerTagsBySource()
        bucket = out[name].manual if source == "manual" else out[name].llm
        if lang == "pt":
            bucket.pt.append(str(tag))
        else:
            bucket.en.append(str(tag))

    for name in filenames:
        out.setdefault(name, StickerTagsBySource())

    return out


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
    terms = normalize_tags([query, *query.split()])
    return terms


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
