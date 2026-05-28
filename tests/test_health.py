def test_root(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "ok"}


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
