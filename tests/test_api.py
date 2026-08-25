import unittest

from fastapi.testclient import TestClient

from app import create_app


class FakeKnowledgeBase:
    def __init__(self):
        self.items = []

    def documents(self):
        return self.items

    def clear(self):
        self.items.clear()


class FakeService:
    def __init__(self):
        self.kb = FakeKnowledgeBase()

    def ingest(self, name, raw):
        if not raw.strip():
            raise ValueError("Dosya boş.")
        self.kb.items.append({"source": name, "chunk_count": 1, "indexed_at": "test"})
        return 1

    def ask(self, question, top_k):
        return {
            "answer": "Belgeden bulunan örnek yanıt. [1]",
            "sources": [{"name": "belge.txt", "excerpt": "Örnek içerik"}],
            "mode": "local",
        }


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeService()
        self.client = TestClient(create_app(self.service))

    def test_home_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Belge Soru-Cevap", response.text)

    def test_uploads_document(self):
        response = self.client.post(
            "/api/ingest",
            files={"files": ("belge.txt", b"Ornek belge", "text/plain")},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["documents"][0]["source"], "belge.txt")

    def test_rejects_unsupported_document(self):
        response = self.client.post(
            "/api/ingest",
            files={"files": ("resim.png", b"data", "image/png")},
        )
        self.assertEqual(response.status_code, 400)

    def test_answers_question(self):
        response = self.client.post("/api/ask", json={"question": "Belgede ne yazıyor?"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("[1]", response.json()["answer"])

    def test_clears_documents(self):
        self.service.kb.items.append({"source": "belge.txt", "chunk_count": 1})
        response = self.client.post("/api/reset")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.kb.documents(), [])


if __name__ == "__main__":
    unittest.main()

