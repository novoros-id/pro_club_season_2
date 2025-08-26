from prep.transcription_audio.transcription_main import transcription_main
from prep.rag_documetn_chunker.document_chunker_main import run_chunker
from prep.rag_db.rag_index_to_chroma_db_main import run_index
import os, json, datetime
from typing import List, Dict, Any
import textwrap, chromadb, pytest
import chromadb
import logging
from chromadb.utils import embedding_functions
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def test_full_pipeline_with_mains(sample_audio_path, tmp_chroma_dir, tmp_path):
    # 1) Транскрипция → JSON + Documents
    logging.info(f"Testing started at {datetime.datetime.now()}")
    json_path, docs = transcription_main(return_docs=True, audio_file=sample_audio_path, out_dir=str(tmp_path))
    logging.info(f"[Stage 1] Transcription completed")
    logging.info(f"  - JSON saved at: {json_path}")
    logging.info(f"  - Documents count: {len(docs)}")
    if docs:
        logging.info(f"  - First doc audio_title: {docs[0].metadata.get('audio_title')}")
        logging.info(f"  - First doc start time: {docs[0].metadata.get('start')}")

    assert isinstance(json_path, str) and os.path.isfile(json_path)
    assert docs and len(docs) > 0
    assert "audio_title" in docs[0].metadata
    assert isinstance(docs[0].metadata["start"], float)

    # 2) Чанкинг → chunks.pkl
    chunks, out_pkl = run_chunker(docs=docs, out_pkl=str(tmp_path / "chunks.pkl"))
    logging.info(f"[Stage 2] Chunking completed")
    logging.info(f"  - Chunks count: {len(chunks)}")
    logging.info(f"  - Saved to: {out_pkl}")

    assert chunks and len(chunks) > 0
    assert os.path.isfile(out_pkl)

    # 3) Индексация → ChromaDB (persist в tmp_chroma_dir), манифест
    tmp_chroma_dir: str = "/Users/dmitriy.grishaev/Documents/Разработка/files/ChromaDB_season2"
    manifest = run_index(docs_pkl=out_pkl, persist_dir=tmp_chroma_dir, collection="test_audio_chunks")
    logging.info(f"[Stage 3] Indexing completed")
    logging.info(f"  - Indexed chunks: {manifest['count_indexed']}")
    logging.info(f"  - Persist dir: {tmp_chroma_dir}")

    assert manifest["count_indexed"] == len(chunks)
    assert os.path.isdir(tmp_chroma_dir)

    # 4) Проверим, что манифест сохранился
    manifest_path = "out/ingest_manifest.json"
    assert os.path.isfile(manifest_path)
    with open(manifest_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    logging.info(f"[Stage 4] Manifest validation completed")
    logging.info(f"  - Manifest collection: {saved['collection']}")

    assert saved["collection"] == "test_audio_chunks"
    logging.info(f"Testing completed at {datetime.datetime.now()}")


# --- Manual QA of retrieval: ask a fixed set of queries against ChromaDB ---
def debug_chroma_queries(
    persist_dir: str = "/Users/dmitriy.grishaev/Documents/Разработка/files/ChromaDB_season2",
    collection: str = "test_audio_chunks",
    n_results: int = 3,
) -> Dict[str, Any]:
    """Run a suite of semantic queries against the persisted Chroma collection and print results.

    Returns a dict with raw Chroma responses keyed by the query text.
    """
    logging.info("[QA] Connecting to ChromaDB…")
    client = chromadb.PersistentClient(path=persist_dir)
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="intfloat/multilingual-e5-large")
    coll = client.get_collection(collection)

    # тестовые вопросы
    queries: List[str] = [
        # Темы про веб‑сервис и документацию
        "Что у нас сделано по веб‑сервису и где хранятся его настройки?",
        "Нужно ли прописывать названия методов веб‑сервиса или достаточно общего описания?",
        "Какие триггеры срабатывания обсуждались для запуска процесса?",
        "Кто будет актуализировать документацию, если она изменится через месяц?",
        "Что имелось в виду под 'работа ради работы'?",
        # Имена/сущности
        "Где упоминается Назарычев и в каком контексте?",
        "Где упоминается Динар и что про него говорится?",
        "Кто будет проверять техническую спецификацию (упоминалась Улицкая)?",
        # Про формат/процесс
        "Как предлагалось заполнять описание: по шагам и по сущностям?",
        "Как планируется оцифровать встречу и сделать выжимку?",
        "Нужно ли называть названия сервисов и как это потом переложится?",
        "Что такое SPPR/PR перечень и зачем он?",
    ]

    logging.info(f"[QA] Running {len(queries)} queries; top {n_results} results each…")
    results: Dict[str, Any] = {}

    for i, q in enumerate(queries, 1):
        logging.info(f"\n[Q{i:02d}] {q}")
        try:
            emb = ef([q])
            resp = coll.query(query_embeddings=emb, n_results=n_results, include=["metadatas", "documents", "distances"])
        except Exception as e:
            logging.warning("  ! Запрос не удался. Вероятно, функция встраивания не прикреплена к коллекции.")
            logging.warning("    Ошибка: %s", repr(e))
            logging.warning("  > Воссоздайте коллекцию с функцией встраивания или выполните запрос с query_embeddings.")
            results[q] = {"ошибка": repr(e)}
            continue

        results[q] = resp
        ids = resp.get("ids", [[]])[0]
        docs = resp.get("documents", [[]])[0]
        metas = resp.get("metadatas", [[]])[0]
        dists = resp.get("distances") or resp.get("embeddings")

        if not docs:
            logging.info("  (no results)")
            continue

        for rank, (doc, mid) in enumerate(zip(docs, ids), 1):
            meta = metas[rank-1] if metas and len(metas) >= rank else {}
            audio_title = meta.get("audio_title")
            start = meta.get("start")
            end = meta.get("end")
            snippet = (doc[:180] + "…") if isinstance(doc, str) and len(doc) > 180 else doc
            logging.info(f"  [{rank}] id={mid}")
            if audio_title is not None:
                logging.info(f"      audio_title={audio_title}")
            if start is not None and end is not None:
                logging.info(f"      time={start}–{end}")
            if dists and isinstance(dists, list) and dists and isinstance(dists[0], list):
                score = dists[0][rank-1]
                logging.info(f"      score={score}")
            logging.info("      text: %s", textwrap.shorten(snippet or "", width=160, placeholder="…"))

    logging.info("\n[QA] Done.")
    return results

def test_debug_chroma_queries():
    results = debug_chroma_queries()
    assert isinstance(results, dict)
    assert results  # проверяем, что словарь не пустой