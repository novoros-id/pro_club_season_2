from prepare_files.prepare_files import prepare_files
from transcription_audio.transcription import Transcription
from create_file.create_docx import create_docx
from download_audio_video.download_audio_video import SynologyDownloader, YandexDownloader
import sys

def process_video(url, folder):

    # 0. Скачивание файла
    if "yandex" in url or "disk.yandex" in url:
        print("🖥 Определён источник: Яндекс.Диск")
        downloader = YandexDownloader(url, folder)
    else:
        print("🖥 Определён источник: QuickConnect / Synology")
        downloader = SynologyDownloader(url, folder)
    #download = YandexDownloader(url, folder)
    saved_path = downloader.download()
    print(f"[LOG] YandexDownloader результат: {saved_path}")

    # 1. Подготовка аудиофайлов из видео
    prep = prepare_files(saved_path)
    files = prep.process_file()
    audio_file = files['audio']  # Получаем путь к аудиофайлу
    video_file = files['video']  # Получаем путь к аудиофайлу
    print(f"[LOG] prepare_files результат: {files}")
    
    # 2. Транскрибация аудиофайла
    #transcription = Transcription(model_name="antony66/whisper-large-v3-russian")
    transcription = Transcription(model_name="medium")
    transcription_json = transcription.save_json(audio_file)
    print(f"[LOG] Transcription результат: {transcription_json}")
    #transcription.unload()

    
    # 3. Создание DOCX из транскрипта
    class_create_docx = create_docx(transcription_json, video_file)
    paragraph = class_create_docx.get_docx()
    print(f"[LOG] create_docx результат: {paragraph}")
    return paragraph 

# Пример использования:
if __name__ == "__main__":
    video_path = 'Просковья инструкция_PV.mp4'
    #url = "https://pro-1c-virtualnas.quickconnect.to/d/s/14Fcxa6WJMw96JQUCRB7lPLEuIoRptvU/zFh_5S--OFIGZs-B0NaiNL_icd4HlUOm-s7SAj3ZJcgw"
    url = "https://disk.yandex.ru/i/KzF8C83q_JbcPw"
    process_video(url)