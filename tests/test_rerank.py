import numpy as np
from app.services.embeddings import build_query_variants
from app.services.query_glossary import expand_to_english
from app.services.rerank import rerank_by_max_variant_similarity


def test_glossary_expands_raiva() -> None:
    assert expand_to_english("raiva") == "angry"


def test_build_query_variants_includes_english_gloss() -> None:
    variants = build_query_variants("raiva")
    assert "raiva" in variants
    assert any("angry" in v for v in variants)


def test_rerank_prefers_better_match() -> None:
    query = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    candidates = np.array(
        [[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]],
        dtype=np.float32,
    )
    filenames = ["a.webp", "b.webp", "c.webp"]

    ranked = rerank_by_max_variant_similarity(query, filenames, candidates)

    assert ranked[0][0] == "a.webp"
    assert ranked[0][1] > ranked[2][1]
