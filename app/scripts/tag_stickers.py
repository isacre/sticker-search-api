"""Gera tags PT/EN via LLM para stickers já indexados."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

import httpx

from app.core.config import settings
from app.db.pool import close_pool, init_pool
from app.services.llm_tags import generate_tags_for_image_async
from app.services.tags import list_filenames_without_llm_tags, replace_llm_tags
from app.services.vector_store import list_image_paths, list_indexed_filenames


def _filenames_in_directory(
    stickers_dir: Path,
    *,
    force: bool,
) -> list[str]:
    local_names = {path.name for path in list_image_paths(stickers_dir)}
    if not local_names:
        return []

    indexed = set(list_indexed_filenames())
    candidates = local_names & indexed
    if force:
        return sorted(candidates)

    without_llm = set(list_filenames_without_llm_tags())
    return sorted(candidates & without_llm)


def _format_progress(done: int, total: int, elapsed: float) -> str:
    pct = (done / total) * 100 if total else 0.0
    rate = done / elapsed if elapsed > 0 else 0.0
    remaining = total - done
    eta = remaining / rate if rate > 0 else 0.0
    return f"{done}/{total} ({pct:5.1f}%) | {rate:.1f}/s | ETA {eta:0.0f}s"


async def _tag_one(
    path: Path,
    *,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
) -> tuple[Path, bool, str | None]:
    async with semaphore:
        try:
            result = await generate_tags_for_image_async(path, client)
            await asyncio.to_thread(
                replace_llm_tags,
                path.name,
                tags_pt=result.tags_pt,
                tags_en=result.tags_en,
            )
            tag_preview = ", ".join(result.tags_pt[:3])
            suffix = "..." if len(result.tags_pt) > 3 else ""
            return path, True, f"{tag_preview}{suffix}"
        except BaseException as exc:
            return path, False, str(exc)


async def tag_indexed_async(
    stickers_dir: Path | None = None,
    *,
    concurrency: int | None = None,
    limit: int | None = None,
    force: bool = False,
) -> int:
    stickers_dir = stickers_dir or settings.stickers_dir
    workers = concurrency or settings.llm_concurrency

    if not settings.llm_enabled:
        print("LLM_API_KEY is required", file=sys.stderr)
        return 0

    filenames = _filenames_in_directory(stickers_dir, force=force)
    if limit is not None:
        filenames = filenames[:limit]
    if not filenames:
        print("No stickers to tag.", file=sys.stderr)
        return 0

    print(
        f"Tagging {len(filenames)} stickers from {stickers_dir} "
        f"(concurrency={workers})",
        flush=True,
    )

    paths = [stickers_dir / name for name in filenames]
    total = len(paths)
    done = 0
    ok_count = 0
    fail_count = 0
    started = time.monotonic()
    semaphore = asyncio.Semaphore(max(1, workers))
    timeout = httpx.Timeout(settings.llm_request_timeout)

    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            asyncio.create_task(
                _tag_one(path, client=client, semaphore=semaphore),
            )
            for path in paths
        ]
        for task in asyncio.as_completed(tasks):
            path, ok, detail = await task
            done += 1
            progress = _format_progress(done, total, time.monotonic() - started)

            if ok:
                ok_count += 1
                print(
                    f"[{progress}] ok  {path.name}  ({detail})",
                    flush=True,
                )
            else:
                fail_count += 1
                print(
                    f"[{progress}] ERR {path.name}: {detail}",
                    file=sys.stderr,
                    flush=True,
                )

    elapsed = time.monotonic() - started
    print(
        f"Finished in {elapsed:.1f}s — ok={ok_count}, failed={fail_count}",
        flush=True,
    )
    return ok_count


def tag_indexed(
    stickers_dir: Path | None = None,
    *,
    concurrency: int | None = None,
    limit: int | None = None,
    force: bool = False,
) -> int:
    return asyncio.run(
        tag_indexed_async(
            stickers_dir,
            concurrency=concurrency,
            limit=limit,
            force=force,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate bilingual PT/EN tags with LLM vision",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=None,
        help="Stickers directory (default: STICKERS_DIR)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Parallel LLM requests (default: LLM_CONCURRENCY)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Tag at most N stickers (smoke test)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-tag stickers that already have LLM tags",
    )
    args = parser.parse_args()

    if not settings.database_url:
        print("DATABASE_URL is required", file=sys.stderr)
        sys.exit(1)

    try:
        init_pool()
        directory = Path(args.dir) if args.dir else settings.stickers_dir
        count = tag_indexed(
            directory,
            concurrency=args.concurrency,
            limit=args.limit,
            force=args.force,
        )
        print(f"Done. {count} stickers tagged.")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
