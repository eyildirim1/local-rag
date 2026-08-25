import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rag.core import RAGService, chunk_text, cosine_similarity, extract_text


DOCUMENTS_DIR = Path(__file__).parent / "documents"


class CoreTests(unittest.TestCase):
    def test_extracts_text_file(self):
        self.assertEqual(extract_text("not.txt", "Türkçe içerik".encode()), "Türkçe içerik")

    def test_rejects_unsupported_file(self):
        with self.assertRaises(ValueError):
            extract_text("resim.png", b"data")

    def test_chunks_long_text(self):
        text = " ".join(f"kelime{i}" for i in range(240))
        chunks = chunk_text(text, max_words=100, overlap=20)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(len(chunk.split()) <= 100 for chunk in chunks))

    def test_cosine_similarity(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_indexes_and_answers_from_document(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"RAG_BACKEND": "local"}):
            service = RAGService(Path(directory) / "test.db")
            count = service.ingest("kimya.txt", b"Bir mol 6.02 x 10^23 parcacik icerir.")
            result = service.ask("Bir mol kac parcacik icerir?")

        self.assertEqual(count, 1)
        self.assertIn("6.02", result["answer"])
        self.assertEqual(result["sources"][0]["name"], "kimya.txt")

    def test_explicit_foundry_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"RAG_BACKEND": "foundry"}):
                with patch("rag.core.foundry_available", return_value=False):
                    with self.assertRaisesRegex(RuntimeError, "Foundry Local bulunamadı"):
                        RAGService(Path(directory) / "test.db")

    def test_removes_invalid_source_number(self):
        answer = RAGService._finalize_answer("Yanıt [14]", source_count=2)
        self.assertEqual(answer, "Yanıt [1]")

    def test_indexes_included_pdf_documents(self):
        documents = sorted(DOCUMENTS_DIR.glob("*.pdf"))
        self.assertEqual(len(documents), 2)

        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"RAG_BACKEND": "local"}):
            service = RAGService(Path(directory) / "test.db")
            counts = [service.ingest(document.name, document.read_bytes()) for document in documents]
            document_count = len(service.kb.documents())

        self.assertTrue(all(count > 0 for count in counts))
        self.assertEqual(document_count, 2)


if __name__ == "__main__":
    unittest.main()
