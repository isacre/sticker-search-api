from pathlib import Path

from app.services.stickers import StickerCatalog, catalog


def test_catalog_slice() -> None:
    cat = StickerCatalog()
    tmp = Path(__file__).parent / "fixtures"
    tmp.mkdir(exist_ok=True)
    (tmp / "b.webp").write_bytes(b"x")
    (tmp / "a.webp").write_bytes(b"x")

    cat.load(tmp)
    assert cat.total == 2
    assert cat.slice(0, 1) == ["a.webp"]
    assert cat.slice(1, 10) == ["b.webp"]

    (tmp / "a.webp").unlink(missing_ok=True)
    (tmp / "b.webp").unlink(missing_ok=True)


def test_list_stickers_after_catalog_load(client) -> None:
    catalog.load(Path(__file__).resolve().parents[2] / "stickers")
    response = client.get("/api/v1/stickers?offset=0&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert len(data["items"]) == 2
    assert data["items"][0]["url"].startswith("/stickers/")
