from app.services.hybrid_search import reciprocal_rank_fusion
from app.services.tags import normalize_tag, normalize_tags, parse_tag_form_values


def test_normalize_tag_lowercases_and_trims() -> None:
    assert normalize_tag("  Raiva  ") == "raiva"


def test_normalize_tags_dedupes_and_splits() -> None:
    assert normalize_tags(["Raiva", "raiva", "meme, raiva"]) == ["raiva", "meme"]


def test_parse_tag_form_values_splits_commas() -> None:
    assert parse_tag_form_values(["feliz, Alegre", "happy"]) == [
        "feliz",
        "alegre",
        "happy",
    ]


def test_search_terms_from_query_keeps_phrase() -> None:
    from app.services.tags import search_terms_from_query

    terms = search_terms_from_query("vish maria")
    assert "vish maria" in terms
    assert "vish" in terms
    assert "maria" in terms


def test_reciprocal_rank_fusion_merges_rankings() -> None:
    clip = [("a.webp", 0.9), ("b.webp", 0.8), ("c.webp", 0.7)]
    tags = [("b.webp", 1.0), ("d.webp", 0.5)]

    merged = reciprocal_rank_fusion([clip, tags], k=60)

    names = [name for name, _ in merged]
    assert names[0] == "b.webp"
    assert set(names) == {"a.webp", "b.webp", "c.webp", "d.webp"}
