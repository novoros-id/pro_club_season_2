from prepare_files.prepare_files import prepare_files
from transcription_audio.transcription import Transcription
from create_file.create_docx import create_docx

def process_video(video_path):
    # 1. Подготовка аудиофайлов из видео
    prep = prepare_files(video_path)
    files = prep.process_file()
    audio_file = files['audio']  # Получаем путь к аудиофайлу
    print(f"[LOG] prepare_files результат: {files}")
    
    # 2. Транскрибация аудиофайла
    transcription = Transcription(model_name="antony66/whisper-large-v3-russian")
    transcription_json = transcription.save_json(audio_file)
    print(f"[LOG] Transcription результат: {transcription_json}")
    
    # 3. Создание DOCX из транскрипта
    class_create_docx = create_docx(transcription_json)
    paragraph = class_create_docx.get_docx()
    print(f"[LOG] create_docx результат: {paragraph}")

# Пример использования:
if __name__ == "__main__":
    video_path = 'Просковья инструкция_PV.mp4'
    process_video(video_path)