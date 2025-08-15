import os
from typing import Tuple, List
from transcription import Transcription
from langchain_core.documents import Document


# TODO: заменить на передачу из класса PrepareAudioVideo
# Здесь должен быть путь к .wav файлу, подготовленному предыдущим шагом пайплайна
def transcription_main(
    return_docs: bool = False,
    audio_file: str = "PA_45.wav",
    model_name: str = "medium",
    language: str = "ru",
    out_dir: str | None = None
) -> Tuple[str | None, List[Document] | None]:
    """
    Запускает распознавание аудиофайла и сохраняет результат в JSON.
    Если return_docs=True — возвращает (json_path, docs), иначе печатает в консоль.
    """

    if not os.path.isfile(audio_file):
        msg = f"Файл не найден: {audio_file}"
        if return_docs:
            return None, None
        print(msg)
        return None, None

    base_name = os.path.splitext(os.path.basename(audio_file))[0]
    out_json = (os.path.join(out_dir, base_name + ".whisper.json") if out_dir else None)

    transcriber = Transcription(model_name=model_name, language=language)
    json_path, docs = transcriber.transcribe_to_docs(audio_file, out_json)

    if return_docs:
        return json_path, docs

    print(f"JSON сохранён: {json_path}")
    print(f"Сегментов: {len(docs)}")
    for d in docs[:3]:
        print("---")
        print(f"Text: {d.page_content}")
        print(f"Metadata: {d.metadata}")
    return json_path, None


def main():
    transcription_main(return_docs=False)


if __name__ == "__main__":
    main()