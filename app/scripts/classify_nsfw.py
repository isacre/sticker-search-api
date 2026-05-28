"""Atualiza nsfw_score em stickers já indexados (sem re-gerar embeddings)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import settings
from app.db.pool import close_pool, init_pool
from app.services.embeddings import load_image_rgb
from app.services.nsfw import score_images
from app.services.vector_store import list_indexed_filenames, update_nsfw_scores


def classify_indexed(
    stickers_dir: Path | None = None,
    *,
    batch_size: int | None = None,
) -> int:
    stickers_dir = stickers_dir or settings.stickers_dir
    batch_size = batch_size or settings.nsfw_batch_size

    filenames = list_indexed_filenames()
    if not filenames:
        print("No indexed stickers found.", file=sys.stderr)
        return 0

    total = 0
    for start in range(0, len(filenames), batch_size):
        chunk = filenames[start : start + batch_size]
        images = []
        valid_names: list[str] = []

        for name in chunk:
            path = stickers_dir / name
            if not path.is_file():
                print(f"Skip missing file: {name}", file=sys.stderr)
                continue
            images.append(load_image_rgb(path))
            valid_names.append(name)

        if not images:
            continue

        scores = score_images(images)
        update_nsfw_scores(list(zip(valid_names, scores, strict=True)))
        total += len(valid_names)
        print(f"Classified {total}/{len(filenames)}", flush=True)

    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify NSFW scores for indexed stickers",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Stickers directory (default: STICKERS_DIR)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Classification batch size (default: NSFW_BATCH_SIZE)",
    )
    args = parser.parse_args()

    if not settings.database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    try:
        init_pool()
        directory = Path(args.dir) if args.dir else settings.stickers_dir
        count = classify_indexed(directory, batch_size=args.batch_size)
        print(f"Done. {count} stickers classified.")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
