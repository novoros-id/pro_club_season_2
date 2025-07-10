import math
from langchain_core.documents import Document
from typing import List, Dict
from collections import defaultdict

class DocumentChunker:
    """
    Группирует Document сегменты в чанки с overlap, сохраняя metadata,
    фильтруя ненужные поля для RAG.
    """
    def __init__(self, chunk_size: int = 3, chunk_overlap: float = 0.5):
        assert 0 <= chunk_overlap < 1
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, documents: List[Document]) -> List[Document]:
        doc_by_audio: Dict[str, List[Document]] = defaultdict(list)
        for doc in documents:
            audio_title = doc.metadata.get("audio_title")
            seg_id = doc.extra.get("segment_id")
            if audio_title and seg_id is not None:
                raise ValueError("Документы должен иметь audio_title и segment_id")
            doc_by_audio[audio_title].append(doc)

        result = []
        for audio_title, docs in doc_by_audio.items():
            docs_sorted = sorted(docs, key=lambda x: x.extra.get("segment_id", 0))
            n = len(docs_sorted)
            step = max(1, math.ceil(self.chunk_size * (1 - self.chunk_overlap)))

            for i in range(0, n, step):
                chunk_docs = docs_sorted[i:i + self.chunk_size]
                if not chunk_docs:
                    continue
                # Объединяем текст сегментов в чанке
                page = "\n".join(d.page_content for d in chunk_docs)
                # Собираем диапазон из уже подготовленных timestamp_range
                ts_range_start = chunk_docs[0].metadata["timestamp_range"].split(" - ")[0]
                ts_range_end = chunk_docs[-1].metadata["timestamp_range"].split(" - ")[1]
                metadata = {
                    "audio_title": audio_title,
                    "timestamp_range": f"{ts_range_start} - {ts_range_end}",
                }
                result.append(Document(page_content=page, metadata=metadata))
        return result