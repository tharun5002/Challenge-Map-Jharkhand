import unittest

import numpy as np

from src.nlp.embeddings import (
    encode_complaints,
    resolve_device,
)


class FakeEncoder:
    def __init__(self, vectors):
        self.vectors = vectors
        self.received_texts = None
        self.received_options = None

    def encode(
        self,
        sentences,
        *,
        batch_size,
        show_progress_bar,
        convert_to_numpy,
        normalize_embeddings,
    ):
        self.received_texts = sentences
        self.received_options = (
            batch_size,
            show_progress_bar,
            convert_to_numpy,
            normalize_embeddings,
        )
        return self.vectors


class EmbeddingTests(unittest.TestCase):
    def test_device_selection_supports_cpu_and_optional_cuda(self):
        self.assertEqual(resolve_device("cpu", False), "cpu")
        self.assertEqual(resolve_device("auto", False), "cpu")
        self.assertEqual(resolve_device("auto", True), "cuda")
        self.assertEqual(resolve_device("cuda", True), "cuda")
        with self.assertRaisesRegex(RuntimeError, "cannot access a CUDA device"):
            resolve_device("cuda", False)
        with self.assertRaisesRegex(ValueError, "device must be"):
            resolve_device("mps", False)

    def test_encodes_normalized_rows_and_preserves_original_scripts(self):
        encoder = FakeEncoder([[1.0, 0.0], [0.0, 1.0]])
        result = encode_complaints(
            encoder,
            ["  पानी&nbsp; नहीं  ", "Roads, DAMAGED!"],
            batch_size=8,
        )
        np.testing.assert_array_equal(
            result,
            np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        )
        self.assertEqual(encoder.received_texts, ["पानी नहीं", "Roads, DAMAGED!"])
        self.assertEqual(encoder.received_options, (8, False, True, True))

    def test_rejects_empty_complaints_and_invalid_model_outputs(self):
        with self.assertRaisesRegex(ValueError, "empty item index"):
            encode_complaints(FakeEncoder([[1.0]]), ["Water", "  "])
        with self.assertRaisesRegex(ValueError, "one non-empty vector"):
            encode_complaints(FakeEncoder([[1.0]]), ["first", "second"])
        with self.assertRaisesRegex(ValueError, "non-finite"):
            encode_complaints(FakeEncoder([[float("nan")]]), ["complaint"])
        with self.assertRaisesRegex(ValueError, "positive integer"):
            encode_complaints(FakeEncoder([[1.0]]), ["complaint"], batch_size=0)
        with self.assertRaisesRegex(ValueError, "positive integer"):
            encode_complaints(FakeEncoder([[1.0]]), ["complaint"], batch_size=1.5)


if __name__ == "__main__":
    unittest.main()
