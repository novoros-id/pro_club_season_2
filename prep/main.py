from prepare_files.prepare_files import prepare_files
from transcription_audio.transcription import Transcription
from rag_documetn_chunker.document_chunker import DocumentChunker
from rag_db.rag_index_to_chroma_db import RagIndexer
from create_file.create_docx import create_docx
from download_audio_video.download_audio_video import SynologyDownloader, YandexDownloader
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
load_dotenv()
import os

CREATE_RAG = os.getenv("CREATE_RAG")
MODEL_WHISPER = os.getenv("MODEL_WHISPER")

def process_video(url, folder):

     # 0. Скачивание файла
    if "yandex" in url or "disk.yandex" in url:
        print("🖥 Определён источник: Яндекс.Диск")
        downloader = YandexDownloader(url, folder)
        saved_path = downloader.download()
    else:
        print("🖥 Определён источник: QuickConnect / Synology")
        #downloader = SynologyDownloader(url, folder)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            saved_path = executor.submit(lambda: SynologyDownloader(url, folder).download()).result()
    #download = YandexDownloader(url, folder)
    print(f"[LOG] YandexDownloader результат: {saved_path}")

    # 1. Подготовка аудиофайлов из видео
    prep = prepare_files(saved_path)
    files = prep.process_file()
    audio_file = files['audio']  # Получаем путь к аудиофайлу
    video_file = files['video']  # Получаем путь к аудиофайлу
    print(f"[LOG] prepare_files результат: {files}")
    
    # 2. Транскрибация аудиофайла
    #transcription = Transcription(model_name="antony66/whisper-large-v3-russian")
    transcription = Transcription(model_name= MODEL_WHISPER)
    transcription_json = transcription.save_json(audio_file)
    print(f"[LOG] Transcription результат: {transcription_json}")
    transcription_docs = transcription.as_documents()
    print(f"[LOG] Transcription as_documents количество: {len(transcription_docs)}")
    transcription.unload()
    
    # 3. Создание DOCX из транскрипта
    class_create_docx = create_docx(transcription_json, video_file)
    paragraph = class_create_docx.get_docx()
    print(f"[LOG] create_docx результат: {paragraph}")
    
    # 3.5 Проверка на тестовый режим
    if CREATE_RAG == False:
        print("[ERROR] Не создаем чанки, измените флаг чтобы создавать")
        return paragraph

    # 4. Создание чанков из транскрипта
    if not transcription_docs:
        print("[ERROR] Нет документов для создания чанков.")
        return paragraph
    
    chunker = DocumentChunker(chunk_size=3, chunk_overlap=0.5)
    chunks = chunker.chunk(transcription_docs)
    print(f"[LOG] DocumentChunker количество чанков: {len(chunks)}")
    for chunk in chunks[:3]:
        print(chunk.page_content)
        print("Metadata:", chunk.metadata)

    # 5. Индексация чанков в CromaDB
    indexer = RagIndexer()
    manifest = indexer.index(chunks)
    print(f"[LOG] RagIndexer manifest: {manifest}")

    return paragraph

# Пример использования:
if __name__ == "__main__":
    video_path = 'Просковья инструкция_PV.mp4'
    #url = "https://pro-1c-virtualnas.quickconnect.to/d/s/14Fcxa6WJMw96JQUCRB7lPLEuIoRptvU/zFh_5S--OFIGZs-B0NaiNL_icd4HlUOm-s7SAj3ZJcgw"
    url = "https://disk.yandex.ru/i/KzF8C83q_JbcPw"
    process_video(url)
