import os
from pathlib import Path
from prep.transcription_audio.transcription import Transcription


# TODO: заменить на передачу из класса PrepareAudioVideo
# Здесь должен быть путь к .wav файлу, подготовленному предыдущим шагом пайплайна
def transcription_main(
    return_docs: bool = True,
    audio_file: str = "/Users/dmitriy.grishaev/Documents/Разработка/files/Аудио файлы/test_voice.wav",
    model_name: str = "medium",
    language: str = "ru",
    out_dir: str | None = None
) -> tuple[str | None, dict | None]:
    """
    Запускает распознавание аудиофайла и сохраняет результат в JSON.
    Совместимый флаг return_docs теперь возвращает нормализованный результат вместо
    удалённых RAG/Document-объектов.
    """

    if not os.path.isfile(audio_file):
        msg = f"Файл не найден: {audio_file}"
        if return_docs:
            return None, None
        print(msg)
        return None, None

    base_name = os.path.splitext(os.path.basename(audio_file))[0]
    out_json_path = None
    if out_dir:
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        out_json_path = str(Path(out_dir) / f"{base_name}.whisper.json")

    transcriber = Transcription(model_name=model_name, language=language)
    json_path = transcriber.save_json(audio_file, out_json_path)
    result = transcriber.last_result

    if return_docs:
        return json_path, result

    print(f"JSON сохранён: {json_path}")
    segments = result.get("segments", []) if result else []
    print(f"Сегментов: {len(segments)}")
    for segment in segments[:3]:
        print("---")
        print(f"Text: {segment.get('text', '')}")
        print(f"Time: {segment.get('start')} - {segment.get('end')}")
    return json_path, None

def main():
    transcription_main(return_docs=False)

if __name__ == "__main__":
    main()
