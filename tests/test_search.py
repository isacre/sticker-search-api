from app.core.config import settings


def test_search_returns_503_when_db_not_configured(client) -> None:
    assert settings.database_url is None
    response = client.get("/api/v1/search?q=cat")
    assert response.status_code == 503
