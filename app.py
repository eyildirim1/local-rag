from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from rag.core import RAGService


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
MAX_FILE_SIZE = 15 * 1024 * 1024
ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=5)


def create_app(service: RAGService | None = None) -> FastAPI:
    rag = service or RAGService(ROOT / "data" / "rag.db")
    app = FastAPI(title="Belge Soru-Cevap", docs_url="/api/docs", redoc_url=None)
    preload = getattr(rag, "preload", None)
    if callable(preload) and os.getenv("RAG_PRELOAD_MODELS", "1") != "0":
        app.router.add_event_handler("startup", preload)

    @app.get("/", include_in_schema=False)
    def index():
        return no_cache_file(WEB_DIR / "index.html", "text/html")

    @app.get("/styles.css", include_in_schema=False)
    def styles():
        return no_cache_file(WEB_DIR / "styles.css", "text/css")

    @app.get("/app.js", include_in_schema=False)
    def javascript():
        return no_cache_file(WEB_DIR / "app.js", "text/javascript")

    @app.get("/api/documents")
    def documents():
        return {"documents": rag.kb.documents()}

    @app.post("/api/ingest", status_code=201)
    def ingest(files: list[UploadFile] = File(...)):
        if not files:
            raise HTTPException(400, "En az bir dosya seçin.")

        indexed = []
        for upload in files:
            name = Path(upload.filename or "").name
            if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
                raise HTTPException(400, f"{name}: Yalnızca PDF, TXT ve MD desteklenir.")

            raw = upload.file.read(MAX_FILE_SIZE + 1)
            if len(raw) > MAX_FILE_SIZE:
                raise HTTPException(413, f"{name}: Dosya 15 MB sınırını aşıyor.")

            try:
                chunk_count = rag.ingest(name, raw)
            except (ValueError, RuntimeError) as exc:
                raise HTTPException(400, str(exc)) from exc
            indexed.append({"name": name, "chunks": chunk_count})

        return {"indexed": indexed, "documents": rag.kb.documents()}

    @app.post("/api/ask")
    def ask(request: QuestionRequest):
        try:
            return rag.ask(request.question, request.top_k)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/reset")
    def reset():
        rag.kb.clear()
        return {"ok": True, "documents": []}

    return app


def no_cache_file(path: Path, media_type: str) -> FileResponse:
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=os.getenv("RAG_HOST", "127.0.0.1"),
        port=int(os.getenv("RAG_PORT", "8000")),
        log_level="info",
    )
