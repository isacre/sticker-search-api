import logging
import threading

import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.services.query_glossary import expand_to_english

IMAGE_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg", ".gif"}

logger = logging.getLogger(__name__)
_model_lock = threading.Lock()
_image_model: SentenceTransformer | None = None
_text_model: SentenceTransformer | None = None


def get_image_model() -> SentenceTransformer:
    global _image_model
    if _image_model is not None:
        return _image_model
    with _model_lock:
        if _image_model is None:
            logger.info("Loading CLIP image model: %s", settings.clip_image_model_name)
            _image_model = SentenceTransformer(settings.clip_image_model_name)
    return _image_model


def get_text_model() -> SentenceTransformer:
    global _text_model
    if _text_model is not None:
        return _text_model
    with _model_lock:
        if _text_model is None:
            logger.info("Loading CLIP text model: %s", settings.clip_text_model_name)
            _text_model = SentenceTransformer(settings.clip_text_model_name)
    return _text_model


def warmup_models() -> None:
    """Load search models at startup to avoid races on the first request."""
    get_text_model()


def encode_images(
    images: list[Image.Image],
    batch_size: int | None = None,
) -> np.ndarray:
    model = get_image_model()
    kwargs: dict = {"convert_to_numpy": True, "show_progress_bar": False}
    if batch_size is not None:
        kwargs["batch_size"] = batch_size
    vectors = model.encode(images, **kwargs)
    return np.asarray(vectors, dtype=np.float32)


def _encode_text_raw(text: str) -> np.ndarray:
    model = get_text_model()
    vector = model.encode(text, convert_to_numpy=True, show_progress_bar=False)
    return np.asarray(vector, dtype=np.float32)


def build_query_variants(query: str) -> list[str]:
    q = query.strip()
    if not q:
        return []

    variants = [q, f"a whatsapp sticker of {q}"]
    english = expand_to_english(q)
    if english:
        variants.append(f"a whatsapp sticker of {english}")
    return variants


def encode_text(query: str) -> np.ndarray:
    variants = build_query_variants(query)
    if not variants:
        msg = "query cannot be empty"
        raise ValueError(msg)
    return _encode_text_raw(variants[0])


def encode_query_variants(query: str) -> np.ndarray:
    variants = build_query_variants(query)
    if not variants:
        msg = "query cannot be empty"
        raise ValueError(msg)
    model = get_text_model()
    vectors = model.encode(variants, convert_to_numpy=True, show_progress_bar=False)
    return np.asarray(vectors, dtype=np.float32)


def load_image_rgb(path) -> Image.Image:
    return Image.open(path).convert("RGB")
