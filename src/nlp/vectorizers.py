"""Vectorizers used for evaluation.

Two families are exposed behind the same ``encode`` signature the existing
clustering and duplicate-detection modules already expect:

* ``TfidfEncoder``  — classical baseline (word or character n-grams), reduces
  sparse TF-IDF with truncated SVD and L2-normalises the result.
* ``build_encoder("sbert")`` — the multilingual Sentence-BERT path. It raises a
  clear error when the optional stack is not installed rather than silently
  falling back, so a missing model can never be mistaken for a measurement.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import scipy.sparse as sp
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from src.nlp.embeddings import (
    DEFAULT_MULTILINGUAL_MODEL,
    SentenceEncoder,
    load_sentence_encoder,
)
from src.nlp.text_preparation import prepare_text_for_tfidf


class TfidfEncoder:
    """L2-normalised, SVD-reduced TF-IDF features.

    ``ngram_range``/``analyzer`` decide the variant: ``("word", (1, 2))`` for the
    baseline and ``("char_wb", (3, 5))`` for a spelling-tolerant variant that
    copes with informal transliteration.
    """

    # Documents below this count get no ``max_df`` filter: a proportion is not
    # meaningful on a handful of rows, and dropping "frequent" terms there would
    # silently empty the vocabulary.
    BOILERPLATE_MIN_DOCUMENTS = 100

    def __init__(
        self,
        *,
        analyzer: str = "word",
        ngram_range: tuple[int, int] = (1, 2),
        min_df: int = 2,
        max_df: float = 0.03,
        max_features: int = 60_000,
        n_components: int = 128,
        random_state: int = 42,
    ) -> None:
        if analyzer not in {"word", "char_wb"}:
            raise ValueError("analyzer must be 'word' or 'char_wb'")
        if not 0 < max_df <= 1:
            raise ValueError("max_df must be in (0, 1]")
        self.analyzer = analyzer
        self.ngram_range = ngram_range
        self.min_df = min_df
        self.max_df = max_df
        self.max_features = max_features
        self.n_components = n_components
        self.random_state = random_state
        self._vectorizer: TfidfVectorizer | None = None
        self._svd: TruncatedSVD | None = None
        self.fitted_max_df: float = 1.0

    @property
    def name(self) -> str:
        return f"tfidf-{self.analyzer}{self.ngram_range[0]}-{self.ngram_range[1]}"

    def fit(self, texts: list[str]) -> "TfidfEncoder":
        cleaned = [prepare_text_for_tfidf(text) for text in texts]
        # Shared template sentences are the most frequent n-grams in a corpus of
        # complaint boilerplate, and they outvote the topic terms. Dropping terms
        # that appear in more than ``max_df`` of documents removes that shared
        # wording; see docs/RESULTS.md for the measured effect.
        max_df = self.max_df if len(cleaned) >= self.BOILERPLATE_MIN_DOCUMENTS else 1.0
        while True:
            vectorizer = TfidfVectorizer(
                analyzer=self.analyzer,
                ngram_range=self.ngram_range,
                min_df=self.min_df,
                max_df=max_df,
                max_features=self.max_features,
                sublinear_tf=True,
            )
            matrix = None
            try:
                matrix = vectorizer.fit_transform(cleaned)
                # A document made only of boilerplate loses every one of its terms
                # and becomes a zero row, which cannot be clustered or scored.
                # Loosen the filter instead of silently dropping the report.
                emptied = int(
                    np.count_nonzero(np.asarray(matrix.sum(axis=1)).ravel() == 0)
                )
                acceptable = matrix.shape[1] >= 2 and (emptied == 0 or max_df >= 1.0)
            except ValueError:
                # scikit-learn rejects a vocabulary that the filter emptied.
                acceptable = False
            if acceptable:
                break
            if max_df >= 1.0:
                raise ValueError(
                    "TF-IDF kept fewer than two terms; lower min_df or supply more text."
                )
            max_df = min(1.0, max_df * 1.5)
        assert matrix is not None
        self._vectorizer = vectorizer
        self.fitted_max_df = max_df
        n_features = matrix.shape[1]
        n_components = max(
            1, min(self.n_components, n_features - 1, max(1, matrix.shape[0] - 1))
        )
        self._svd = TruncatedSVD(n_components=n_components, random_state=self.random_state)
        self._svd.fit(matrix)
        return self

    def encode(
        self,
        sentences: list[str],
        *,
        batch_size: int = 64,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = True,
        **_: Any,
    ) -> np.ndarray:
        if self._vectorizer is None or self._svd is None:
            raise RuntimeError("TfidfEncoder must be fitted before encoding")
        cleaned = [prepare_text_for_tfidf(text) for text in sentences]
        matrix = self._vectorizer.transform(cleaned)
        dense = self._svd.transform(matrix).astype(np.float32)
        zero_rows = np.flatnonzero(np.abs(dense).sum(axis=1) == 0)
        if zero_rows.size:
            raise ValueError(
                f"{zero_rows.size} document(s) produced zero TF-IDF features "
                f"(first index {int(zero_rows[0])}); every term fell below min_df. "
                "Lower min_df or check the input text."
            )
        if normalize_embeddings:
            dense = normalize(dense, norm="l2", axis=1).astype(np.float32)
        return dense

    def encode_sparse(self, sentences: list[str]) -> sp.csr_matrix:
        """Return L2-normalised sparse TF-IDF rows.

        Duplicate detection needs the *exact* TF-IDF cosine, not an SVD
        approximation: the reduced dense space compresses unrelated documents
        together (hubness), which both inflates false positives and makes an
        identical-text pair round to 0.9999999 and miss a 1.00 threshold.

        A document whose every term was filtered out stays a zero row, which
        scores 0 against everything instead of raising: for duplicate review
        "no comparable terms" legitimately means "no candidate".
        """
        if self._vectorizer is None:
            raise RuntimeError("TfidfEncoder must be fitted before encoding")
        cleaned = [prepare_text_for_tfidf(text) for text in sentences]
        matrix = self._vectorizer.transform(cleaned)
        if matrix.shape[1] == 0:
            raise ValueError("TF-IDF kept no terms at all; check the input text.")
        return normalize(matrix, norm="l2", axis=1, copy=True)


class SbertEncoder:
    """Adapter giving the multilingual Sentence-BERT path the evaluation interface.

    ``fit`` is a deliberate no-op: a pretrained encoder has nothing to learn from
    the corpus, and the method exists only because TF-IDF must be fitted. Because
    neither ``fit`` nor ``encode_sparse`` exists on a raw SentenceTransformer, the
    adapter is what makes ``evaluate_clustering`` and
    ``sweep_duplicate_thresholds`` treat SBERT and TF-IDF through the same code.

    The model is loaded lazily on first ``encode`` so constructing the encoder
    cannot fail a run that only needs the TF-IDF baselines.
    """

    name = "sbert"

    def __init__(
        self,
        model_name: str = DEFAULT_MULTILINGUAL_MODEL,
        device: str = "cpu",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._encoder: SentenceEncoder | None = None

    def fit(self, _texts: list[str]) -> "SbertEncoder":
        return self

    def encode(self, sentences: list[str], **options: Any) -> np.ndarray:
        if self._encoder is None:
            self._encoder = load_sentence_encoder(self.model_name, self.device)
        defaults: dict[str, Any] = {
            "batch_size": 64,
            "show_progress_bar": False,
            "convert_to_numpy": True,
            "normalize_embeddings": True,
        }
        defaults.update(
            {key: value for key, value in options.items() if key in defaults}
        )
        return np.asarray(
            self._encoder.encode(list(sentences), **defaults), dtype=np.float32
        )


def build_encoder(kind: str) -> SentenceEncoder:
    """Return an encoder by name.

    ``tfidf``, ``tfidf-char`` and ``sbert`` are supported. The TF-IDF variants are
    returned *unfitted*; call ``fit`` on the corpus first.
    """
    normalized = kind.strip().lower()
    if normalized == "tfidf":
        return TfidfEncoder(analyzer="word", ngram_range=(1, 2))
    if normalized in {"tfidf-char", "tfidf_char"}:
        return TfidfEncoder(analyzer="char_wb", ngram_range=(3, 5), n_components=160)
    if normalized in {"sbert", "sentence-bert", "sentence_bert"}:
        return SbertEncoder()
    raise ValueError(f"Unknown encoder '{kind}'. Use tfidf, tfidf-char or sbert.")
