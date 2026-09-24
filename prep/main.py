import os
import shutil
import uuid
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()


def get_video_source_mode(value=None):
    """Return the configured source mode or raise a user-facing configuration error."""
    mode = (os.getenv("VIDEO_SOURCE_MODE", "") if value is None else value).strip().lower()
    if mode not in {"local", "url"}:
        raise ValueError("VIDEO_SOURCE_MODE должен быть равен local или url.")
    return mode


def _process_saved_video(saved_path):
    # Lazy imports keep application entry points importable without loading optional
    # media/UI packages and never initiate model or network work during import.
    from prepare_files.prepare_files import prepare_files
    from transcription_audio.transcription import Transcription
    from create_file.create_docx import create_docx
    from model_api import get_default_client

    if not saved_path or not os.path.isfile(saved_path):
        raise FileNotFoundError(f"Видеофайл не найден: {saved_path}")

    print(f"[LOG] Исходный видеофайл: {saved_path}")

    # 1. Подготовка аудиофайлов из видео
    prep = prepare_files(saved_path)
    files = prep.process_file()
    audio_file = files['audio']
    video_file = files['video']
    if not video_file:
        raise ValueError("Выбранный файл не содержит видеопоток.")
    print(f"[LOG] prepare_files результат: {files}")

    # 2. Транскрибация аудиофайла
    prompt = "Техническая документация на русском языке. Используйте корректную пунктуацию, соблюдайте терминологию 1С, излагайте содержание техническим языком. Термины: 1С, НСИ, БИТ финанс, проведение документа, проводки, конфигурация, обработка, запрос, документ, справочник, модуль:"
    model_client = get_default_client()
    transcription = Transcription(prompt=prompt, client=model_client)
    transcription_json = transcription.save_json(audio_file)
    print(f"[LOG] Transcription результат: {transcription_json}")

    # 3. Создание DOCX из транскрипта
    class_create_docx = create_docx(transcription_json, video_file, True, client=model_client)
    paragraph = class_create_docx.get_docx()
    print(f"[LOG] create_docx результат: {paragraph}")
    return paragraph


def process_local_video(file_path, user_folder):
    """Copy a local source into an isolated work directory and process the copy."""
    if get_video_source_mode() != "local":
        raise ValueError("Локальная обработка отключена: установите VIDEO_SOURCE_MODE=local.")

    source_path = Path(file_path).resolve(strict=True)
    if not source_path.is_file():
        raise FileNotFoundError(f"Видеофайл не найден: {source_path}")

    work_root = Path(user_folder).expanduser().resolve()
    work_dir = work_root / f"local_user_{uuid.uuid4().hex[:8]}"
    work_dir.mkdir(parents=True, exist_ok=False)
    saved_path = work_dir / source_path.name
    shutil.copy2(source_path, saved_path)

    return _process_saved_video(str(saved_path))


def process_video(url, folder):
    if get_video_source_mode() != "url":
        raise ValueError("Обработка ссылок отключена: установите VIDEO_SOURCE_MODE=url.")

    from download_audio_video.download_audio_video import SynologyDownloader, YandexDownloader

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

    print(f"[LOG] Загрузчик результата: {saved_path}")
    return _process_saved_video(saved_path)

# Пример использования:
if __name__ == "__main__":
    video_path = 'Просковья инструкция_PV.mp4'
    #url = "https://pro-1c-virtualnas.quickconnect.to/d/s/14Fcxa6WJMw96JQUCRB7lPLEuIoRptvU/zFh_5S--OFIGZs-B0NaiNL_icd4HlUOm-s7SAj3ZJcgw"
    url = "https://disk.yandex.ru/i/KzF8C83q_JbcPw"
    process_video(url, "./user_data")
