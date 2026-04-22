import tempfile
import unittest
from pathlib import Path

from src.gui.rag_store import (
    RagStore,
    build_rag_context,
    chunk_text,
    cosine_similarity,
)


class RagStoreTests(unittest.TestCase):
    def test_cosine_similarity_scores_related_vectors(self) -> None:
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_store_search_returns_top_k_chunks(self) -> None:
        db_path = Path(tempfile.mkdtemp()) / "rag.db"
        store = RagStore(str(db_path))
        store.replace_source_chunks(
            source_type="message",
            source_id="session-1",
            source_label="Long chat",
            chunks=["about embeddings", "about recipes", "about vector memory"],
            embeddings=[
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.9, 0.0, 0.1],
            ],
        )

        results = store.search([1.0, 0.0, 0.0], top_k=2, min_score=0.1)

        self.assertEqual([result.content for result in results], ["about embeddings", "about vector memory"])
        context = build_rag_context(results)
        self.assertIn("[1] Long chat", context)
        self.assertIn("about vector memory", context)

    def test_chunk_text_uses_overlap(self) -> None:
        chunks = chunk_text("alpha beta gamma delta epsilon", max_chars=16, overlap=5)

        self.assertGreaterEqual(len(chunks), 2)
        self.assertIn("alpha beta", chunks[0])


if __name__ == "__main__":
    unittest.main()
