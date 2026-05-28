from functools import lru_cache

from PIL import Image
from transformers import pipeline

from app.core.config import settings

NSFW_LABEL = "nsfw"


@lru_cache(maxsize=1)
def get_classifier():
    return pipeline(
        "image-classification",
        model=settings.nsfw_model_name,
    )


def score_images(images: list[Image.Image]) -> list[float]:
    if not images:
        return []

    classifier = get_classifier()
    outputs = classifier(images, batch_size=settings.nsfw_batch_size)

    scores: list[float] = []
    for result in outputs:
        nsfw_prob = 0.0
        for item in result:
            label = str(item.get("label", "")).lower()
            if label == NSFW_LABEL:
                nsfw_prob = float(item["score"])
                break
        scores.append(nsfw_prob)

    return scores
