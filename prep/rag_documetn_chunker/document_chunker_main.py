import os, pickle
from typing import List, Optional, Tuple
from langchain_core.documents import Document
from prep.rag_documetn_chunker.document_chunker import DocumentChunker
from prep.transcription_audio.transcription_main import transcription_main

def run_chunker(
    docs: Optional[List[Document]] = None,
    out_pkl: str = "out/chunks.pkl",
    chunk_size: int = 3,
    chunk_overlap: float = 0.5,
) -> Tuple[List[Document], str]:
    """
    Управляющий вызов для тестов/кода: принимает Documents (если уже есть),
    либо сам их получит через transcription_main, формирует чанки и сохраняет pkl.
    Возвращает (chunks, out_pkl).
    """
    if docs is None:
        _, docs = transcription_main(return_docs=True)
    if not docs:
        raise RuntimeError("Не удалось получить документы для чанкинга")

    os.makedirs("out", exist_ok=True)
    chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = chunker.chunk(docs)

    with open(out_pkl, "wb") as f:
        pickle.dump(chunks, f)
    return chunks, out_pkl

def main():
    json_path, docs = transcription_main(return_docs=True)

    if not docs:
        print("Не удалось получить документы для чанкинга.")
        return

    print(f"Количество сегментов: {len(docs)}")

    chunker = DocumentChunker(chunk_size=3, chunk_overlap=0.5)
    chunks = chunker.chunk(docs)

    print(f"\nСформировано чанков: {len(chunks)}\n")
    for i, chunk in enumerate(chunks[:3]):
        print(f"=== Чанк {i+1} ===")
        print(chunk.page_content)
        print("Metadata:", chunk.metadata)
        print()

    os.makedirs("out", exist_ok=True)
    with open("out/chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)
    print("Pickle с чанками сохранён: out/chunks.pkl")

if __name__ == "__main__":
    main()