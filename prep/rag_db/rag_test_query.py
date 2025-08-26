import os
import argparse
import chromadb
from dotenv import load_dotenv
from typing import Dict, Any, List
from langchain_huggingface import HuggingFaceEmbeddings

def format_hit(doc: str, meta: Dict[str, Any]) -> str:
    ts = meta.get("timestamp_range", "")
    title = meta.get("audio_title", "")
    start = meta.get("start", 0.0)
    end = meta.get("end", 0.0)
    return f"[{title}] {ts} ({start:.2f}s–{end:.2f}s)\n{doc}\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persist_dir", default="vectorstore")
    ap.add_argument("--collection", default="audio_chunks")
    ap.add_argument("--query", required=True)
    ap.add_argument("--top_k", type=int, default=5)
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    # Загружаем .env и подхватываем CHROMA_PERSIST_DIR
    load_dotenv()
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", args.persist_dir)

    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(name=args.collection)

    model_kwargs = {}
    if args.device:
        model_kwargs["device"] = args.device

    emb = HuggingFaceEmbeddings(
        model_name="intfloat/multilingual-e5-large",
        model_kwargs=model_kwargs,
        encode_kwargs={"normalize_embeddings": True}
    )

    q_vec = emb.embed_query("query: " + args.query.strip())
    res = collection.query(
        query_embeddings=[q_vec],
        n_results=args.top_k,
        include=["documents", "metadatas", "distances"]
    )

    docs: List[str] = res.get("documents", [[]])[0]
    metas: List[Dict[str, Any]] = res.get("metadatas", [[]])[0]
    dists: List[float] = res.get("distances", [[]])[0]

    print(f"\nTop-{args.top_k} по запросу: {args.query}\n")
    for i, (doc, meta, dist) in enumerate(zip(docs, metas, dists), start=1):
        print(f"#{i}  distance={dist:.4f}")
        print(format_hit(doc, meta))

if __name__ == "__main__":
    main()