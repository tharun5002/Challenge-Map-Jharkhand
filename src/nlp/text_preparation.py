"""Language-neutral complaint text normalization for NLP pipelines."""

from __future__ import annotations

import html
import re
import unicodedata

import pandas as pd


_WHITESPACE = re.compile(r"\s+")
# Letters, digits and combining marks are kept. Marks matter: every Devanagari
# vowel sign (ा ि ी ु ू े ै ो ौ ं ँ ्) is category Mn/Mc, so a plain ``\w``
# filter would shred "उपलब्धता" into "उपलब" + "धत".
_KEEP_CATEGORIES = frozenset({"L", "M", "N"})


def normalize_complaint_text(value: object) -> str:
    """Normalize Unicode and whitespace without translating or dropping scripts."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    text = unicodedata.normalize("NFKC", html.unescape(str(value)))
    text = "".join(
        " " if unicodedata.category(character) in {"Cc", "Cs"} else character
        for character in text
    )
    return _WHITESPACE.sub(" ", text).strip()


def prepare_text_for_tfidf(value: object) -> str:
    """Case-fold text and remove punctuation while retaining Unicode words."""
    normalized = normalize_complaint_text(value).casefold()
    stripped = "".join(
        character
        if character.isspace() or unicodedata.category(character)[0] in _KEEP_CATEGORIES
        else " "
        for character in normalized
    )
    return _WHITESPACE.sub(" ", stripped).strip()
