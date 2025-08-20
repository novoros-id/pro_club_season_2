import os
import argparse
import json
import hashlib
import pickle
from typing import List, Dict, Any, Tuple, Optional

import chromadb
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings


class RagIndexer:
    """
    Класс-обёртка для индексирования чанков (LangChain Document) в ChromaDB.

    Использование из кода:
        indexer = RagIndexer(persist_dir="vectorstore", collection="audio_chunks", batch_size=64, device=None)
        manifest = indexer.index(pkl_path="out/chunks.pkl")
    """

    def __init__(
        self,
        persist_dir: str = "vectorstore",
        collection: str = "audio_chunks",
        batch_size: int = 64,
        device: Optional[str] = None,
    ) -> None:
        # Переменная окружения CHROMA_PERSIST_DIR имеет приоритет
        self.persist_dir = os.getenv("CHROMA_PERSIST_DIR", persist_dir)
        self.collection_name = collection
        self.batch_size = batch_size
        self.device = device

        # Инициализация эмбеддера e5-large (нормализация включена)
        model_kwargs: Dict[str, Any] = {}
        if device:
            model_kwargs["device"] = device
        self.embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-large",
            model_kwargs=model_kwargs,
            encode_kwargs={"normalize_embeddings": True},
        )

        # Клиент Chroma с persist
        self.client = chromadb.PersistentClient(path=self.persist_dir)
        try:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},  # на случай новых версий
            )
        except TypeError:
            # Для старых версий chromadb без metadata
            self.collection = self.client.get_or_create_collection(name=self.collection_name)

    # -----------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # -----------------------
    @staticmethod
    def stable_id(audio_title: str, start: float, end: float, text: str) -> str:
        """Детерминированный ID по ключевым полям."""
        payload = f"{audio_title}|{int(round(start*1000))}|{int(round(end*1000))}|{text.strip()}"
        return hashlib.md5(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def load_docs(pkl_path: str) -> List[Document]:
        with open(pkl_path, "rb") as f:
            return pickle.load(f)

    @staticmethod
    def save_manifest(path: str, stats: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    @staticmethod
    def batch_iter(xs: List[Any], bs: int):
        for i in range(0, len(xs), bs):
            yield xs[i:i+bs]

    # -----------------------
    # ОСНОВНОЙ МЕТОД ИНДЕКСАЦИИ
    # -----------------------
    def index(self, pkl_path: str) -> Dict[str, Any]:
        if not os.path.isfile(pkl_path):
            raise FileNotFoundError(f"Не найден файл с чанками: {pkl_path}")

        docs: List[Document] = self.load_docs(pkl_path)
        if not docs:
            raise ValueError("Список Document пуст.")

        ids: List[str] = []
        metas: List[Dict[str, Any]] = []
        texts: List[str] = []

        # e5 best practice — префикс 'passage: '
        for d in docs:
            meta = dict(d.metadata or {})
            audio_title = meta.get("audio_title", "")
            start = float(meta.get("start", 0.0))
            end = float(meta.get("end", 0.0))

            the_id = self.stable_id(audio_title, start, end, d.page_content)
            ids.append(the_id)
            metas.append(meta)
            texts.append("passage: " + d.page_content.strip())

        # Считаем эмбеддинги батчами
        vectors: List[List[float]] = []
        for batch in self.batch_iter(texts, self.batch_size):
            vectors.extend(self.embeddings.embed_documents(batch))

        assert len(vectors) == len(texts) == len(ids)

        # Безопасный upsert
        upsert_supported = hasattr(self.collection, "upsert")
        if upsert_supported:
            self.collection.upsert(ids=ids, embeddings=vectors, metadatas=metas, documents=texts)
        else:
            # Ручной upsert: удалить существующие id порциями и добавить
            for bid in self.batch_iter(ids, 500):
                try:
                    self.collection.delete(ids=bid)
                except Exception:
                    pass
            for b_ids, b_vecs, b_meta, b_txt in zip(
                self.batch_iter(ids, 500),
                self.batch_iter(vectors, 500),
                self.batch_iter(metas, 500),
                self.batch_iter(texts, 500),
            ):
                self.collection.add(ids=b_ids, embeddings=b_vecs, metadatas=b_meta, documents=b_txt)

        manifest = {
            "persist_dir": os.path.abspath(self.persist_dir),
            "collection": self.collection_name,
            "count_indexed": len(ids),
            "unique_audio_titles": sorted({m.get("audio_title", "") for m in metas}),
        }
        return manifest


def _cli() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs_pkl", default="out/chunks.pkl", help="Pickle со списком langchain Document (чанки)")
    ap.add_argument("--persist_dir", default="vectorstore", help="Каталог для Chroma (persist)")
    ap.add_argument("--collection", default="audio_chunks", help="Имя коллекции")
    ap.add_argument("--batch_size", type=int, default=64, help="Размер батча для эмбеддингов")
    ap.add_argument("--device", default=None, help="Устройство вычислений (cuda|cpu|mps)")
    args = ap.parse_args()

    indexer = RagIndexer(
        persist_dir=args.persist_dir,
        collection=args.collection,
        batch_size=args.batch_size,
        device=args.device,
    )
    manifest = indexer.index(args.docs_pkl)

    os.makedirs("out", exist_ok=True)
    RagIndexer.save_manifest("out/ingest_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _cli()