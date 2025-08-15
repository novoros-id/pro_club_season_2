import os
import argparse
import json
import math
import hashlib
import pickle
from typing import List, Dict, Any, Tuple

import chromadb
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings


def stable_id(audio_title: str, start: float, end: float, text: str) -> str:
    """
    Хешируем ключевые поля.
    """
    payload = f"{audio_title}|{int(round(start*1000))}|{int(round(end*1000))}|{text.strip()}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def load_docs(pkl_path: str) -> List[Document]:
    with open(pkl_path, "rb") as f:
        return pickle.load(f)


def save_manifest(path: str, stats: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def batch_iter(xs, bs: int):
    for i in range(0, len(xs), bs):
        yield xs[i:i+bs]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs_pkl", default="out/chunks.pkl", help="Pickle со списком langchain Document (чанки)")
    ap.add_argument("--persist_dir", default="vectorstore", help="Каталог для Chroma (persist)")
    ap.add_argument("--collection", default="audio_chunks", help="Имя коллекции")
    ap.add_argument("--batch_size", type=int, default=64, help="Размер батча для эмбеддингов")
    ap.add_argument("--device", default=None, help="Устройство для вычислений модели эмбеддингов (например: cuda, cpu, mps)")
    args = ap.parse_args()

    persist_dir = os.getenv("CHROMA_PERSIST_DIR", args.persist_dir)

    if not os.path.isfile(args.docs_pkl):
        raise SystemExit(f"Не найден файл с чанками: {args.docs_pkl}")

    docs: List[Document] = load_docs(args.docs_pkl)
    if not docs:
        raise SystemExit("Список Document пуст.")

    # Подготовим эмбеддер e5-large (нормализуем векторы, префиксы passage:/query:)
    model_kwargs = {}
    if args.device:
        model_kwargs["device"] = args.device

    embeddings = HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-large",
        model_kwargs=model_kwargs,
        encode_kwargs={"normalize_embeddings": True}
    )

    # Chroma с persist
    client = chromadb.PersistentClient(path=persist_dir)
    # В Chroma метрика по умолчанию cosine; зададим явно на всякий случай
    try:
        collection = client.get_or_create_collection(
            name=args.collection,
            metadata={"hnsw:space": "cosine"}
        )
    except TypeError:
        # Для старых версий chromadb без metadata
        collection = client.get_or_create_collection(name=args.collection)

    # Подготовим данные
    ids: List[str] = []
    metas: List[Dict[str, Any]] = []
    texts: List[str] = []

    # Сразу применим префикс 'passage: ' — это best practice для e5
    for d in docs:
        meta = dict(d.metadata or {})
        audio_title = meta.get("audio_title", "")
        start = float(meta.get("start", 0.0))
        end = float(meta.get("end", 0.0))

        the_id = stable_id(audio_title, start, end, d.page_content)
        ids.append(the_id)
        metas.append(meta)
        texts.append("passage: " + d.page_content.strip())

    # Считаем эмбеддинги батчами
    vectors: List[List[float]] = []
    for batch in batch_iter(texts, args.batch_size):
        vectors.extend(embeddings.embed_documents(batch))

    assert len(vectors) == len(texts) == len(ids)

    # Безопасный upsert: если метод недоступен — вручную удалим пересекающиеся ID и добавим
    upsert_supported = hasattr(collection, "upsert")
    if upsert_supported:
        collection.upsert(ids=ids, embeddings=vectors, metadatas=metas, documents=texts)
    else:
        # Частями удалим существующие id (если API не поддерживает массовое удаление, делаем батчами)
        for bid in batch_iter(ids, 500):
            try:
                collection.delete(ids=bid)
            except Exception:
                # не критично; продолжаем
                pass
        for b_ids, b_vecs, b_meta, b_txt in zip(
            batch_iter(ids, 500),
            batch_iter(vectors, 500),
            batch_iter(metas, 500),
            batch_iter(texts, 500),
        ):
            collection.add(ids=b_ids, embeddings=b_vecs, metadatas=b_meta, documents=b_txt)

    # Итоговая статистика
    manifest = {
        "persist_dir": os.path.abspath(persist_dir),
        "collection": args.collection,
        "count_indexed": len(ids),
        "unique_audio_titles": sorted({m.get("audio_title", "") for m in metas}),
    }
    os.makedirs("out", exist_ok=True)
    save_manifest("out/ingest_manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()