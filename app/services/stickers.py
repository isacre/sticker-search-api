from pathlib import Path

IMAGE_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg", ".gif"}


class StickerCatalog:
    def __init__(self) -> None:
        self._names: list[str] = []

    def load(self, directory: Path) -> None:
        if not directory.is_dir():
            msg = f"Stickers directory not found: {directory}"
            raise FileNotFoundError(msg)

        self._names = sorted(
            path.name
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )

    @property
    def total(self) -> int:
        return len(self._names)

    def slice(self, offset: int, limit: int) -> list[str]:
        return self._names[offset : offset + limit]


catalog = StickerCatalog()
