from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


TOKEN_RE = re.compile(r"[\wçğıöşüÇĞİÖŞÜ]+", re.UNICODE)
STOP_WORDS = {
    "acaba", "ama", "ancak", "bana", "bir", "bu", "da", "daha", "de", "gibi",
    "hakkında", "hangi", "ile", "için", "kaç", "mı", "mi", "mu", "mü", "nasıl",
    "nedir", "ne", "olan", "olarak", "ve", "veya",
}


def search_tokens(text: str) -> list[str]:
    return [
        token.casefold()
        for token in TOKEN_RE.findall(text)
        if len(token) > 2 and token.casefold() not in STOP_WORDS
    ]


def chunk_text(text: str, max_words: int = 180, overlap: int = 35) -> list[str]:
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    for paragraph in paragraphs:
        words = paragraph.split()
        while words:
            room = max_words - len(current)
            current.extend(words[:room])
            words = words[room:]
            if len(current) >= max_words:
                chunks.append(" ".join(current))
                current = current[-overlap:] if overlap else []
        if current and len(current) >= max_words * 0.65:
            chunks.append(" ".join(current))
            current = current[-overlap:] if overlap else []
    if current and (not chunks or " ".join(current) != chunks[-1]):
        chunks.append(" ".join(current))
    return chunks


def extract_text(name: str, raw: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in {".txt", ".md"}:
        return raw.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF desteği için 'pypdf' kurulmalı.") from exc
        return "\n\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(raw)).pages)
    raise ValueError("Yalnızca .txt, .md ve .pdf dosyaları desteklenir.")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    denom = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / denom if denom else 0.0


class HashEmbedder:
    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        return [self._one(text) for text in texts]

    def _one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = [t.casefold() for t in TOKEN_RE.findall(text)]
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            number = int.from_bytes(digest, "little")
            index = number % self.dimensions
            vector[index] += 1.0 if number & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class FoundryRuntime:
    _instance: "FoundryRuntime | None" = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> "FoundryRuntime":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        from foundry_local_sdk import Configuration, FoundryLocalManager

        FoundryLocalManager.initialize(Configuration(app_name="yerel_bilgi_asistani", log_level="warning"))
        self.manager = FoundryLocalManager.instance
        self.embedding_model = None
        self.chat_model = None
        self._model_lock = threading.Lock()

    def _load(self, alias: str, kind: str):
        attribute = f"{kind}_model"
        model = getattr(self, attribute)
        if model is not None:
            return model
        with self._model_lock:
            model = getattr(self, attribute)
            if model is None:
                model = self.manager.catalog.get_model(alias)
                model.download(lambda _progress: None)
                model.load()
                setattr(self, attribute, model)
            return model

    def embed(self, texts: list[str]) -> list[list[float]]:
        alias = os.getenv("RAG_EMBED_MODEL", "qwen3-embedding-0.6b")
        client = self._load(alias, "embedding").get_embedding_client()
        return [item.embedding for item in client.generate_embeddings(texts).data]

    def answer(self, system: str, question: str) -> str:
        alias = os.getenv("RAG_CHAT_MODEL", "phi-3.5-mini")
        client = self._load(alias, "chat").get_chat_client()
        client.settings.temperature = 0.0
        client.settings.max_tokens = 64
        client.settings.top_p = 0.9
        client.settings.random_seed = 42
        response = client.complete_chat([
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ])
        return response.choices[0].message.content.strip()

    def preload(self):
        self._load(os.getenv("RAG_EMBED_MODEL", "qwen3-embedding-0.6b"), "embedding")
        self._load(os.getenv("RAG_CHAT_MODEL", "phi-3.5-mini"), "chat")


def foundry_available() -> bool:
    try:
        import foundry_local_sdk
        return True
    except (ImportError, OSError):
        return False


def resolve_backend() -> str:
    requested = os.getenv("RAG_BACKEND", "auto").strip().lower()
    if requested not in {"auto", "foundry", "local"}:
        raise RuntimeError("RAG_BACKEND yalnızca auto, foundry veya local olabilir.")
    if requested == "local":
        return "local"
    if not foundry_available():
        if requested == "foundry":
            raise RuntimeError(
                "RAG_BACKEND=foundry seçildi ancak Foundry Local bulunamadı. "
                "Foundry Local kurulumunu kontrol edin."
            )
        return "local"
    if requested == "foundry":
        try:
            FoundryRuntime.instance()
        except Exception as exc:
            raise RuntimeError(
                "RAG_BACKEND=foundry seçildi ancak Foundry Local başlatılamadı."
            ) from exc
    return "foundry"


@dataclass
class SearchResult:
    source: str
    content: str
    score: float
    chunk_index: int
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    backend: str = ""


class KnowledgeBase:
    def __init__(self, path: Path):
        self.path = path
        self._cached_chunks: list[dict] | None = None
        self._cache_lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    source TEXT PRIMARY KEY, chunk_count INTEGER NOT NULL, indexed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    FOREIGN KEY(source) REFERENCES documents(source) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source);
            """)

    def replace_document(self, source: str, chunks: list[str], embeddings: list[list[float]], backend: str):
        if len(chunks) != len(embeddings):
            raise ValueError("Parça ve embedding sayıları eşleşmiyor.")
        with self.connect() as db:
            db.execute("DELETE FROM chunks WHERE source = ?", (source,))
            db.execute("DELETE FROM documents WHERE source = ?", (source,))
            db.execute(
                "INSERT INTO documents VALUES (?, ?, ?)",
                (source, len(chunks), datetime.now(timezone.utc).isoformat()),
            )
            db.executemany(
                "INSERT INTO chunks(source, chunk_index, content, embedding, backend) VALUES (?, ?, ?, ?, ?)",
                [(source, i, text, json.dumps(vector), backend) for i, (text, vector) in enumerate(zip(chunks, embeddings))],
            )
        with self._cache_lock:
            self._cached_chunks = None

    def documents(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM documents ORDER BY source")]

    def clear(self):
        with self.connect() as db:
            db.execute("DELETE FROM chunks")
            db.execute("DELETE FROM documents")
        with self._cache_lock:
            self._cached_chunks = None

    def _chunks(self) -> list[dict]:
        with self._cache_lock:
            if self._cached_chunks is None:
                with self.connect() as db:
                    rows = db.execute(
                        "SELECT source, chunk_index, content, embedding, backend FROM chunks"
                    )
                    self._cached_chunks = [
                        {
                            "source": row["source"],
                            "chunk_index": row["chunk_index"],
                            "content": row["content"],
                            "embedding": json.loads(row["embedding"]),
                            "backend": row["backend"],
                            "tokens": search_tokens(row["content"]),
                        }
                        for row in rows
                    ]
            return self._cached_chunks

    def search(self, question: str, top_k: int = 3) -> list[SearchResult]:
        rows = self._chunks()
        if not rows:
            return []
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(row["backend"], []).append(row)
        semantic_scores: dict[tuple[str, int], float] = {}
        for backend, backend_rows in grouped.items():
            if backend == "foundry" and foundry_available():
                query_vector = FoundryRuntime.instance().embed([question])[0]
            else:
                query_vector = HashEmbedder().embed([question])[0]
            for row in backend_rows:
                key = (row["source"], row["chunk_index"])
                semantic_scores[key] = cosine_similarity(query_vector, row["embedding"])

        keyword_scores = self._bm25(question, rows)
        semantic_ranking = sorted(semantic_scores, key=semantic_scores.get, reverse=True)
        keyword_ranking = sorted(
            (key for key, score in keyword_scores.items() if score > 0),
            key=keyword_scores.get,
            reverse=True,
        )
        semantic_rank = {key: rank for rank, key in enumerate(semantic_ranking, 1)}
        keyword_rank = {key: rank for rank, key in enumerate(keyword_ranking, 1)}
        rrf_constant = 10
        maximum_rrf = 2 / (rrf_constant + 1)
        row_by_key = {(row["source"], row["chunk_index"]): row for row in rows}
        results = []
        for key, row in row_by_key.items():
            score = 1 / (rrf_constant + semantic_rank[key])
            if key in keyword_rank:
                score += 1 / (rrf_constant + keyword_rank[key])
            results.append(
                SearchResult(
                    row["source"],
                    row["content"],
                    score / maximum_rrf,
                    row["chunk_index"],
                    semantic_scores[key],
                    keyword_scores[key],
                    row["backend"],
                )
            )
        return sorted(results, key=lambda item: item.score, reverse=True)[:top_k]

    @staticmethod
    def _bm25(question: str, rows: list[dict]) -> dict[tuple[str, int], float]:
        query = set(search_tokens(question))
        documents = [row["tokens"] for row in rows]
        if not query or not documents:
            return {(row["source"], row["chunk_index"]): 0.0 for row in rows}
        average_length = sum(len(tokens) for tokens in documents) / len(documents) or 1.0
        document_frequency = {
            token: sum(1 for document in documents if token in document) for token in query
        }
        scores = {}
        k1, b = 1.5, 0.75
        for row, tokens in zip(rows, documents):
            term_counts = {token: tokens.count(token) for token in query}
            score = 0.0
            for token, frequency in term_counts.items():
                if not frequency:
                    continue
                doc_frequency = document_frequency[token]
                inverse_frequency = math.log(
                    1 + (len(documents) - doc_frequency + 0.5) / (doc_frequency + 0.5)
                )
                denominator = frequency + k1 * (1 - b + b * len(tokens) / average_length)
                score += inverse_frequency * frequency * (k1 + 1) / denominator
            scores[(row["source"], row["chunk_index"])] = score
        return scores


class RAGService:
    def __init__(self, db_path: Path):
        self.kb = KnowledgeBase(db_path)
        self._mode = resolve_backend()

    @property
    def mode(self) -> str:
        return self._mode

    def preload(self):
        if self.mode == "foundry":
            FoundryRuntime.instance().preload()

    def ingest(self, source: str, raw: bytes) -> int:
        text = extract_text(source, raw)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("Dosyadan indekslenebilir metin çıkarılamadı.")
        if self.mode == "foundry":
            embeddings = FoundryRuntime.instance().embed(chunks)
        else:
            embeddings = HashEmbedder().embed(chunks)
        self.kb.replace_document(Path(source).name, chunks, embeddings, self.mode)
        return len(chunks)

    def ask(self, question: str, top_k: int = 3) -> dict:
        question = question.strip()
        if not question:
            raise ValueError("Lütfen bir soru yazın.")
        results = self.kb.search(question, max(1, min(top_k, 5)))
        best_score = results[0].score if results else 0.0
        relevant = [
            result
            for result in results
            if result.score >= max(0.20, best_score * 0.72)
            and (
                result.keyword_score > 0
                or result.semantic_score >= (0.08 if result.backend == "local" else 0.28)
            )
        ][:2]
        if not relevant:
            return {"answer": "Bu bilgi yüklenen belgelerde bulunmuyor.", "sources": [], "mode": self.mode}
        sources = [
            {"label": str(i), "name": result.source, "score": round(result.score, 3), "excerpt": result.content[:360]}
            for i, result in enumerate(relevant, 1)
        ]
        if self.mode == "foundry":
            context = "\n\n".join(f"[{i}] Kaynak: {r.source}\n{r.content}" for i, r in enumerate(relevant, 1))
            system = (
                "Use only CONTEXT. Answer the question directly in natural Turkish, in one or two "
                "short sentences. Copy numbers and chemical formulas exactly from CONTEXT. End each "
                "sentence with its source label such as [1]. Do not infer, explain, repeat, or add "
                "outside knowledge. If the answer is missing, output exactly: "
                "Bu bilgi yüklenen belgelerde bulunmuyor.\n\nCONTEXT:\n" + context
            )
            answer = self._finalize_answer(
                FoundryRuntime.instance().answer(system, question), len(relevant)
            )
        else:
            answer = self._extractive_answer(question, relevant)
        return {"answer": answer, "sources": sources, "mode": self.mode}

    @staticmethod
    def _finalize_answer(answer: str, source_count: int = 1) -> str:
        fallback = "Bu bilgi yüklenen belgelerde bulunmuyor."
        answer = re.sub(r"\s+", " ", answer).strip()
        if not answer or fallback.casefold() in answer.casefold():
            return fallback
        answer = re.sub(r"\s+Kaynak:\s*.*$", "", answer, flags=re.IGNORECASE)
        answer = re.sub(
            r"\[(\d+)\]",
            lambda match: match.group(0) if int(match.group(1)) <= source_count else "",
            answer,
        )
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", answer)
            if sentence.strip()
        ]
        answer = " ".join(sentences[:2])[:900].rstrip()
        if not re.search(r"\[\d+\]", answer):
            answer += " [1]"
        return answer

    @staticmethod
    def _extractive_answer(question: str, results: list[SearchResult]) -> str:
        query_tokens = {token.casefold() for token in TOKEN_RE.findall(question) if len(token) > 2}
        candidates = []
        for source_index, result in enumerate(results, 1):
            for sentence in re.split(r"(?<=[.!?])\s+", result.content):
                overlap = len(query_tokens & {t.casefold() for t in TOKEN_RE.findall(sentence)})
                candidates.append((overlap, len(sentence), sentence.strip(), source_index))
        best = sorted(candidates, key=lambda item: (item[0], -item[1]), reverse=True)[:3]
        text = " ".join(f"{sentence} [{index}]" for _, _, sentence, index in best if sentence)
        return text or "Bu bilgi yüklenen belgelerde bulunmuyor."
