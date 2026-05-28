def reciprocal_rank_fusion(
    rankings: list[list[tuple[str, float]]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    if not rankings:
        return []

    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, (name, _score) in enumerate(ranking):
            scores[name] = scores.get(name, 0.0) + 1.0 / (k + rank + 1)

    return sorted(scores.items(), key=lambda item: -item[1])
