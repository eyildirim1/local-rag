import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["RAG_BACKEND"] = "foundry"
os.environ["RAG_PRELOAD_MODELS"] = "0"

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = sorted((ROOT / "tests" / "documents").glob("*.pdf"))
sys.path.insert(0, str(ROOT))

from rag.core import RAGService


FALLBACK = "Bu bilgi yüklenen belgelerde bulunmuyor."
QUESTIONS = [
    ("Avogadro sayısının değeri nedir?", True, ["6.02"]),
    ("STP koşullarında bir mol gaz kaç litre hacim kaplar?", True, ["22.4"]),
    ("STP koşullarında sıcaklık ve basınç nedir?", True, ["0", "1 atm"]),
    ("Belgeye göre TNT'nin ampirik formülü nedir?", True, ["C7H5N3O6"]),
    ("Gümüşün molar kütlesi kaç g/mol'dür?", True, ["108"]),
    ("C2X4 sorusunda X elementinin molar kütlesi kaçtır?", True, ["19"]),
    ("MgSO4.xH2O hidratı sorusunda x kaçtır?", True, ["7"]),
    ("Suyun kaynama noktası kaç derecedir?", False, []),
    ("Bu belgelerin yazarı kimdir?", False, []),
    ("Fransa'nın başkenti neresidir?", False, []),
]


def normalized(text):
    return text.casefold().replace("×", "x").replace(" ", "")


def main():
    if len(DOCUMENTS) != 2:
        raise RuntimeError("tests/documents içinde iki PDF bulunmalı.")

    with tempfile.TemporaryDirectory() as directory:
        service = RAGService(Path(directory) / "evaluation.db")
        service.preload()
        indexed = {document.name: service.ingest(document.name, document.read_bytes()) for document in DOCUMENTS}

        print("Otomatik indeksleme: " + ", ".join(f"{name} ({count} parça)" for name, count in indexed.items()))
        print("\n| # | Beklenti | Süre | Sonuç | Yanıt |")
        print("|---:|---|---:|---|---|")
        passed = 0
        total_time = 0.0
        for index, (question, answerable, expected) in enumerate(QUESTIONS, 1):
            started = time.perf_counter()
            result = service.ask(question)
            elapsed = time.perf_counter() - started
            total_time += elapsed
            answer = result["answer"]
            if answerable:
                success = answer != FALLBACK and all(
                    item.casefold().replace(" ", "") in normalized(answer) for item in expected
                )
            else:
                success = answer == FALLBACK
            passed += int(success)
            safe_answer = answer.replace("|", "\\|").replace("\n", " ")
            print(
                f"| {index} | {'Cevaplanabilir' if answerable else 'Cevaplanamaz'} "
                f"| {elapsed:.2f} sn | {'Başarılı' if success else 'Başarısız'} | {safe_answer} |"
            )
        print(
            f"\nÖzet: {passed}/{len(QUESTIONS)} başarılı, "
            f"ortalama yanıt süresi {total_time / len(QUESTIONS):.2f} saniye."
        )


if __name__ == "__main__":
    main()
