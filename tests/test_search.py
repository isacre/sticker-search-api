from app.core.config import settings


def test_search_status_when_db_not_configured(client) -> None:
    assert settings.database_url is None
    response = client.get("/api/v1/search/status")
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["indexed"] == 0


def test_search_returns_503_when_db_not_configured(client) -> None:
    response = client.get("/api/v1/search?q=cat")
    assert response.status_code == 503
