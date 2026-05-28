from pathlib import Path

from app.core.config import settings
from app.services.embeddings import encode_images, load_image_rgb
from app.services.nsfw import score_images
from app.services.vector_store import upsert_batch


def index_paths(paths: list[Path], *, batch_size: int | None = None) -> int:
    if not paths:
        return 0

    batch_size = batch_size or settings.index_batch_size
    total = 0

    for start in range(0, len(paths), batch_size):
        chunk = paths[start : start + batch_size]
        images = [load_image_rgb(path) for path in chunk]
        embeddings = encode_images(images, batch_size=batch_size)
        nsfw_scores = score_images(images)
        filenames = [path.name for path in chunk]
        upsert_batch(filenames, embeddings, nsfw_scores=nsfw_scores)
        total += len(chunk)

    return total
