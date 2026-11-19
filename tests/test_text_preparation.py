import unittest

import pandas as pd

from src.nlp.text_preparation import (
    normalize_complaint_text,
    prepare_text_for_tfidf,
)


class TextPreparationTests(unittest.TestCase):
    def test_normalization_preserves_multilingual_text_and_context(self):
        text = "  पानी&nbsp;और ರಸ್ತೆ\nनहीं\u200d 🚰 "
        self.assertEqual(
            normalize_complaint_text(text),
            "पानी और ರಸ್ತೆ नहीं\u200d 🚰",
        )

    def test_normalization_applies_unicode_compatibility_and_control_cleanup(self):
        self.assertEqual(normalize_complaint_text("Ｆｏｏ\x00  BAR"), "Foo BAR")
        self.assertEqual(prepare_text_for_tfidf("Roads, DAMAGED!"), "roads damaged")

    def test_missing_values_become_empty_text(self):
        for value in (None, float("nan"), pd.NA):
            with self.subTest(value=repr(value)):
                self.assertEqual(normalize_complaint_text(value), "")
                self.assertEqual(prepare_text_for_tfidf(value), "")


if __name__ == "__main__":
    unittest.main()
