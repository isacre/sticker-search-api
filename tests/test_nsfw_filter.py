def test_search_sql_filters_by_nsfw_ceiling() -> None:
    from app.services.vector_store import SEARCH_BY_SCORE_SQL

    assert "COALESCE(nsfw_score, 1.0)" in SEARCH_BY_SCORE_SQL
