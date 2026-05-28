"""Index sticker images into Postgres (pgvector)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import settings
from app.db.pool import close_pool, init_pool
from app.services.indexing import index_paths
from app.services.vector_store import list_image_paths


def index_directory(
    directory: Path | None = None,
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
    total = len(paths)
    indexed = index_paths(paths, batch_size=batch_size)
    print(f"Indexed {indexed}/{total}", flush=True)
    return indexed


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
        directory = Path(args.dir) if args.dir else settings.stickers_dir
        count = index_directory(directory, batch_size=args.batch_size)
        print(f"Done. {count} stickers indexed.")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
