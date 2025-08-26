import math
from typing import List, Dict, DefaultDict
from collections import defaultdict
from langchain_core.documents import Document
from pathlib import Path


class DocumentChunker:
    """
    Группирует Document-сегменты в чанки с overlap, сохраняя метаданные.
    """

    def __init__(self, chunk_size: int = 3, chunk_overlap: float = 0.5):
        if not (0 <= chunk_overlap < 1):
            raise ValueError("chunk_overlap должен быть в диапазоне [0, 1)")
        if chunk_size <= 0:
            raise ValueError("chunk_size должен быть > 0")
        self.chunk_size = int(chunk_size)
        self.chunk_overlap = float(chunk_overlap)

    @staticmethod
    def _fmt_ts(seconds: float) -> str:
        msec = int(round((seconds - int(seconds)) * 1000))
        seconds = int(seconds)
        s = seconds % 60
        minutes = (seconds // 60) % 60
        hours = seconds // 3600
        return f"{hours:02d}:{minutes:02d}:{s:02d}.{msec:03d}"

    def chunk(self, documents: List[Document]) -> List[Document]:
        if not documents:
            return []

        # Группировка по audio_title
        buckets: DefaultDict[str, List[Document]] = defaultdict(list)
        for d in documents:
            at = d.metadata.get("audio_title", "")
            buckets[at].append(d)

        result: List[Document] = []
        # Безопасный шаг окна: минимум 1
        step = max(1, math.ceil(self.chunk_size * (1 - self.chunk_overlap)))

        for audio_title, docs in buckets.items():
            # Сортируем по start (число), не по строковому диапазону
            docs_sorted = sorted(docs, key=lambda x: float(x.metadata.get("start", 0.0)))
            n = len(docs_sorted)

            i = 0
            while i < n:
                chunk_docs = docs_sorted[i:i + self.chunk_size]
                if not chunk_docs:
                    break

                page = "\n".join(d.page_content for d in chunk_docs)

                start_s = float(chunk_docs[0].metadata["start"])
                end_s = float(chunk_docs[-1].metadata["end"])

                metadata = {
                    "audio_title": Path(str(audio_title)).name,
                    "start": start_s,
                    "end": end_s,
                    "timestamp_range": f"{self._fmt_ts(start_s)} - {self._fmt_ts(end_s)}",
                    "segment_indices": [int(d.metadata.get("segment_index", -1)) for d in chunk_docs],
                    "segments_in_chunk": len(chunk_docs),
                }

                result.append(Document(page_content=page, metadata=metadata))
                i += step

        return result