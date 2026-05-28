import pytest
from app.core.config import settings
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _disable_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", None)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
