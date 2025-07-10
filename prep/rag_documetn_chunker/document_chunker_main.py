from document_chunker import DocumentChunker
from prep.transcription_audio.transcription_main import transcription_main

def main():
    _, docs = transcription_main(return_docs=True)

    if not docs:
        print("Не удалось получить документы для чанкинга.")
        return

    print(f"Количество сегментов: {len(docs)}")

    # Инициализация чанкера
    chunker = DocumentChunker(chunk_size=3, chunk_overlap=0.5)
    chunks = chunker.chunk(docs)

    print(f"\nСформировано чанков: {len(chunks)}\n")
    for i, chunk in enumerate(chunks[:3]):
        print(f"=== Чанк {i+1} ===")
        print(chunk.page_content)
        print("Metadata:", chunk.metadata)
        print()

if __name__ == "__main__":
    main()