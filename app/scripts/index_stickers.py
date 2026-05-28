"""Index sticker images into Postgres (pgvector)."""

from __future__ import annotations

import argparse
import sys

from app.core.config import settings
from app.db.pool import close_pool, init_pool
from app.services.embeddings import encode_images, load_image_rgb
from app.services.nsfw import score_images
from app.services.vector_store import list_image_paths, upsert_batch


def index_directory(
    directory=None,
    *,
    batch_size: int | None = None,
) -> int:
    directory = directory or settings.stickers_dir
    batch_size = batch_size or settings.index_batch_size
    paths = list_image_paths(directory)

    if not paths:
        print(f"No images found in {directory}", file=sys.stderr)
        return 0

    init_pool()
    total = 0

    for start in range(0, len(paths), batch_size):
        chunk = paths[start : start + batch_size]
        images = [load_image_rgb(path) for path in chunk]
        embeddings = encode_images(images, batch_size=batch_size)
        nsfw_scores = score_images(images)
        filenames = [path.name for path in chunk]
        upsert_batch(filenames, embeddings, nsfw_scores=nsfw_scores)
        total += len(chunk)
        print(f"Indexed {total}/{len(paths)}", flush=True)

    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Index stickers into pgvector")
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Stickers directory (default: STICKERS_DIR from settings)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Encoding batch size (default: INDEX_BATCH_SIZE)",
    )
    args = parser.parse_args()

    if not settings.database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    try:
        from pathlib import Path

        directory = Path(args.dir) if args.dir else settings.stickers_dir
        count = index_directory(directory, batch_size=args.batch_size)
        print(f"Done. {count} stickers indexed.")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
