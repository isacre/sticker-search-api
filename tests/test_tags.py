from app.services.rerank import reciprocal_rank_fusion
from app.services.tags import normalize_tag, normalize_tags


def test_normalize_tag_lowercases_and_trims() -> None:
    assert normalize_tag("  Raiva  ") == "raiva"


def test_normalize_tags_dedupes_and_splits() -> None:
    assert normalize_tags(["Raiva", "raiva", "meme, raiva"]) == ["raiva", "meme"]


def test_search_terms_from_query_splits_words() -> None:
    from app.services.tags import search_terms_from_query

    terms = search_terms_from_query("homem aranha")
    assert "homem" in terms
    assert "aranha" in terms


def test_reciprocal_rank_fusion_merges_rankings() -> None:
    clip = [("a.webp", 0.9), ("b.webp", 0.8)]
    tags = [("b.webp", 1.0), ("d.webp", 0.5)]

    merged = reciprocal_rank_fusion([clip, tags], k=60)
    names = [name for name, _ in merged]
    assert "b.webp" in names
    assert names[0] == "b.webp"
