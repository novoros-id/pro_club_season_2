import argparse, json, os
from typing import Optional, Dict, Any
from prep.rag_db.rag_index_to_chroma_db import RagIndexer

def run_index(
    docs_pkl: str = "out/chunks.pkl",
    persist_dir: str = "vectorstore",
    collection: str = "audio_chunks",
    batch_size: int = 64,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    indexer = RagIndexer(
        persist_dir=persist_dir,
        collection=collection,
        batch_size=batch_size,
        device=device,
    )
    manifest = indexer.index(docs_pkl)
    os.makedirs("out", exist_ok=True)
    RagIndexer.save_manifest("out/ingest_manifest.json", manifest)
    return manifest

def main():
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
    main()