"""Local sentence embeddings for multilingual complaint text."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np

from src.nlp.text_preparation import normalize_complaint_text


DEFAULT_MULTILINGUAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class SentenceEncoder(Protocol):
    def encode(
        self,
        sentences: list[str],
        *,
        batch_size: int,
        show_progress_bar: bool,
        convert_to_numpy: bool,
        normalize_embeddings: bool,
    ) -> np.ndarray: ...


def resolve_device(device: str, cuda_available: bool) -> str:
    """Resolve CPU/GPU selection and reject unavailable explicit GPU requests."""
    normalized_device = device.strip().lower()
    if normalized_device == "auto":
        return "cuda" if cuda_available else "cpu"
    if normalized_device == "cpu":
        return "cpu"
    if normalized_device == "cuda":
        if not cuda_available:
            raise RuntimeError(
                "CUDA was requested, but PyTorch cannot access a CUDA device. "
                "Use device='cpu' or install a CUDA-compatible PyTorch build."
            )
        return "cuda"
    raise ValueError("device must be 'cpu', 'cuda', or 'auto'.")


def load_sentence_encoder(
    model_name: str = DEFAULT_MULTILINGUAL_MODEL,
    device: str = "cpu",
) -> SentenceEncoder:
    """Load a Sentence Transformers model for local inference."""
    normalized_model_name = model_name.strip()
    if not normalized_model_name:
        raise ValueError("model_name must not be empty.")

    try:
        import torch
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError(
            "Sentence Transformers is an optional dependency. Install it with "
            "'python -m pip install -r requirements/ml.txt' inside a Python 3.12 environment."
        ) from error

    resolved_device = resolve_device(device, torch.cuda.is_available())
    return SentenceTransformer(normalized_model_name, device=resolved_device)


def encode_complaints(
    encoder: SentenceEncoder,
    complaint_texts: Sequence[object],
    *,
    batch_size: int = 32,
    normalize_embeddings: bool = True,
) -> np.ndarray:
    """Normalize complaint text and return finite, row-aligned embeddings."""
    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size < 1
    ):
        raise ValueError("batch_size must be a positive integer.")

    texts = [normalize_complaint_text(text) for text in complaint_texts]
    if not texts:
        return np.empty((0, 0), dtype=np.float32)

    empty_indices = [index for index, text in enumerate(texts) if not text]
    if empty_indices:
        raise ValueError(
            "Complaint text must not be empty; empty item index(es): "
            + ", ".join(map(str, empty_indices[:10]))
        )

    vectors = np.asarray(
        encoder.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=normalize_embeddings,
        ),
        dtype=np.float32,
    )
    if (
        vectors.ndim != 2
        or vectors.shape[0] != len(texts)
        or vectors.shape[1] == 0
    ):
        raise ValueError(
            "The embedding model must return one non-empty vector per complaint."
        )
    if not np.isfinite(vectors).all():
        raise ValueError("The embedding model returned non-finite values.")
    return vectors
