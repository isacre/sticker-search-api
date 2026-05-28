import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.services.llm_tags import generate_tags_parallel


def test_generate_tags_parallel_collects_results(tmp_path: Path) -> None:
    paths = [tmp_path / "a.webp", tmp_path / "b.webp"]
    for path in paths:
        path.write_bytes(b"fake")

    mock_result = AsyncMock()
    mock_result.tags_pt = ["feliz"]
    mock_result.tags_en = ["happy"]

    with patch(
        "app.services.llm_tags.generate_tags_for_image_async",
        new=AsyncMock(return_value=mock_result),
    ):
        results = asyncio.run(generate_tags_parallel(paths, concurrency=2))

    assert len(results) == 2
    assert all(not isinstance(outcome, BaseException) for _, outcome in results)
