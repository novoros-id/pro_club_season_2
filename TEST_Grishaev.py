from prep.transcription_audio.transcription import Transcription
from prep.rag_documetn_chunker.document_chunker import DocumentChunker
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
import os, pickle, torch, chromadb, json, argparse, hashlib


# Аргументы CLI (размещаем вверху, чтобы использовать --rebuild до чанкинга)
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--query", "-q", type=str, default=None, help="Текст запроса для быстрого теста")
parser.add_argument("--k", type=int, default=5, help="Сколько результатов возвращать")
parser.add_argument("--threshold", type=float, default=None, help="Если dist топ‑1 >= порога — вывести предупреждение")
parser.add_argument("--rebuild", action="store_true", help="Пересчитать транскрибацию/чанки и переиндексировать даже при наличии кэша")
parser.add_argument("--scope", choices=["audio","all"], default="audio", help="Фильтровать результаты только по текущему audio_title (по умолчанию)")
args, _unknown = parser.parse_known_args()


# audio = "/Users/dmitriy.grishaev/Documents/Разработка/files/Аудио файлы/test_voice.wav"
BASE_DIR = Path("/Users/dmitriy.grishaev/Documents/Разработка/files/Аудио файлы")
OUTPUT_DIR = BASE_DIR / "out"
audio = BASE_DIR / "test_voice.wav"

# Готовим выводной каталог и включаем режим переиспользования, если чанки уже посчитаны
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
chunks_pkl = OUTPUT_DIR / "chunks.pkl"
json_path = OUTPUT_DIR / "test_voice.json"
manifest_path = OUTPUT_DIR / "chunks.manifest.json"

# Хеш файла-источника — чтобы кэш не протухал, если WAV перезаписали
def _sha256(path: Path, buf_size: int = 1<<20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(buf_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

audio_hash = _sha256(audio) if audio.exists() else None
reuse_chunks = False
if not args.rebuild and chunks_pkl.exists() and manifest_path.exists():
    try:
        with open(manifest_path, "r") as mf:
            man = json.load(mf)
        reuse_chunks = (man.get("audio_sha256") == audio_hash and man.get("audio_path") == str(audio))
    except Exception:
        reuse_chunks = False

if reuse_chunks:
    # Повторный запуск: используем уже готовые чанки
    with open(chunks_pkl, "rb") as f:
        chunks = pickle.load(f)
    print("Reuse: валидный chunks.pkl по манифесту → пропускаю транскрибацию и чанкинг")
else:
    # Первый запуск или форс-пересчёт: транскрибуем и чанкём
    t = Transcription(model_name="base", language="ru", device="cpu")
    json_path, docs = t.transcribe_to_documents(
        audio_file=str(audio),
        out_json_path=str(json_path)
    )
    print("Docs:", len(docs), "| JSON:", json_path)

    chunker = DocumentChunker(chunk_size=3, chunk_overlap=0.5)
    chunks = chunker.chunk(docs)

    with open(chunks_pkl, "wb") as f:
        pickle.dump(chunks, f)

    # Сохраняем манифест кэша
    try:
        with open(manifest_path, "w") as mf:
            json.dump({
                "audio_path": str(audio),
                "audio_sha256": audio_hash,
                "audio_mtime": os.path.getmtime(audio),
                "chunks": len(chunks)
            }, mf, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Warn: не удалось записать manifest:", e)

    print("Chunks:", len(chunks))
    print("Sample content:", chunks[0].page_content[:150])
    print("Sample meta:", chunks[0].metadata)

# print("Всего чанков:", len(chunks))
# print("Пример текста:", chunks[0].page_content[:200])
print("Метаданные:", chunks[0].metadata)

# 1) есть ли содержимое
assert len(chunks) > 0
assert chunks[0].page_content.strip() != ""

# 2) порядок по времени
starts = [c.metadata["start"] for c in chunks]
assert starts == sorted(starts), "Чанки должны идти по возрастанию start"

# 3) overlap: следующий чанк начинается не позже конца текущего
for i in range(len(chunks)-1):
    assert chunks[i+1].metadata["start"] <= chunks[i].metadata["end"], "Нет перекрытия"

# 4) структуру метаданных видно
need = {"audio_title","start","end","timestamp_range","segment_indices","segments_in_chunk"}
assert need.issubset(chunks[0].metadata.keys())
print("OK ✓")

# =====================
# Шаг 3: Индексация в Chroma в заданную директорию и быстрый тест
# =====================

from pathlib import Path  # уже импортирован выше, но на всякий случай не помешает
CHROMA_DIR = Path("/Users/dmitriy.grishaev/Documents/Разработка/files/ChromaDB_season2")
CHROMA_DIR.mkdir(parents=True, exist_ok=True)
audio_title_current = Path(audio).name

# Клиент Chroma и коллекция
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client.get_or_create_collection(
    name="audio_chunks",
    metadata={"hnsw:space": "cosine"}
)

# Проверяем, есть ли уже данные для ТЕКУЩЕГО audio_title (а не просто любая коллекция)
try:
    existing_for_audio = collection.get(where={"audio_title": audio_title_current}, limit=1)
    existing_count = len(existing_for_audio.get("ids", []))
except Exception as e:
    existing_count = 0
    print("Warn: не удалось проверить существование объектов для", audio_title_current, ":", e)

# Эмбеддинги E5 (нормализуем);
DEVICE_E5 = "cpu"
emb = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-large",
    model_kwargs={"device": DEVICE_E5},
    encode_kwargs={"normalize_embeddings": True}
)

# Подготовка текстов + метаданных + стабильных ID
texts = [f"passage: {d.page_content}" for d in chunks]
metadatas, ids = [], []

def _normalize_metadata(md: dict) -> dict:
    # если ключ был опечатан, переименуем
    if "tamp_range" in md and "timestamp_range" not in md:
        md["timestamp_range"] = md["tamp_range"]
    out = {}
    for k, v in md.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        elif isinstance(v, (list, tuple, set)):
            # Chroma не любит списки — превращаем в компактную строку
            out[k] = ",".join(str(x) for x in v)
        else:
            # Path/даты/прочие типы
            out[k] = str(v)
    return out

for d in chunks:
    m = dict(d.metadata)
    start_ms = int(float(m.get("start", 0)) * 1000)
    end_ms   = int(float(m.get("end",   0)) * 1000)
    audio_title = str(m.get("audio_title", "unknown"))
    ids.append(f"{audio_title}:{start_ms}-{end_ms}")
    m["raw_text"] = d.page_content
    metadatas.append(_normalize_metadata(m))

if args.rebuild and existing_count > 0:
    try:
        collection.delete(where={"audio_title": audio_title_current})
        print("Rebuild: удалил старые объекты для", audio_title_current)
    except Exception as e:
        print("Warn: не удалось удалить старые объекты:", e)
        
# Индексируем, если нет данных для этого файла или мы запросили пересборку
if existing_count == 0 or args.rebuild:
    print(f"Indexing {len(texts)} chunks to Chroma at {CHROMA_DIR} (device={DEVICE_E5})…")
    embeddings = emb.embed_documents(texts)
    collection.upsert(documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)
    print("Indexed count:", len(ids))
else:
    print(f"Reuse: в коллекции уже есть данные для {audio_title_current} → пропускаю индексацию")
print("Chroma persist dir:", CHROMA_DIR)

# Формируем тестовый запрос
TEST_QUERY = args.query if args.query else (" ".join(chunks[0].page_content.split()[:8]) if chunks else "")
q_emb = emb.embed_query(f"query: {TEST_QUERY}")

# Ограничим поиск текущим аудио (по умолчанию), либо по всей коллекции (--scope all)
query_kwargs = {
    "query_embeddings": [q_emb],
    "n_results": args.k,
    "include": ["documents", "metadatas", "distances", "ids"],
}
if args.scope == "audio":
    query_kwargs["where"] = {"audio_title": audio_title_current}

res = collection.query(**query_kwargs)

print("\n=== TEST QUERY ===")
print("Q:", TEST_QUERY)
ids_list = res.get("ids", [[]])[0] if res.get("ids") else [None] * len(res.get("documents", [[]])[0])

# Пороговая проверка качества (если задано)
if args.threshold is not None and res.get("distances") and res["distances"][0]:
    top_dist = res["distances"][0][0]
    if top_dist >= args.threshold:
        print(f"WARN: top-1 dist {top_dist:.4f} ≥ threshold {args.threshold:.4f} — результат может быть нерелевантным")

for rank, (doc, meta, dist, _id) in enumerate(
    zip(res.get("documents", [[]])[0],
        res.get("metadatas", [[]])[0],
        res.get("distances", [[]])[0],
        ids_list),
    start=1
):
    rng = meta.get("timestamp_range") or meta.get("tamp_range") or f"{meta.get('start')}–{meta.get('end')}"
    print(f"#{rank}", f"dist={dist:.4f}", f"[{meta.get('audio_title')}] {rng}", f"id={_id}")
    print(doc[:160].replace("\n", " "), "…\n")
print("=== END ===")