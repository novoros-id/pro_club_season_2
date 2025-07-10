from transcription import Transcription

def main(return_docs=False):
    """
    Запускает распознавание аудиофайла и сохраняет результат в JSON.
    
    Если return_docs=True, возвращает кортеж (json_path, docs), где docs — список документов.
    Если return_docs=False, выводит информацию в консоль и ничего не возвращает.
    
    При возникновении ошибки или отсутствии результата возвращает (None, None) при return_docs=True.
    """
    # TODO: заменить на передачу из класса PrepareAudioVideo
    # Здесь должен быть путь к .wav файлу, подготовленному предыдущим шагом пайплайна
    audio_file = "PA_45.wav"  # Пример: путь от PrepareAudioVideo
    transcriber = Transcription(model_name="medium", language="ru")

    print(f"▶ Начинаем распознавание файла: {audio_file}")
    json_path = transcriber.save_json(audio_file)
    docs = None

    if json_path:
        try:
            docs = transcriber.as_documents()
        except Exception as e:
            if return_docs:
                return None, None
            print(f"Ошибка при формировании документов: {e}")
            docs = None

        if return_docs:
            return json_path, docs
        print(f"Результат сохранён в: {json_path}")

        # Первые 3 документа для примера
        if docs:
            print("\nПример документов для LLM:")
            for doc in docs[:3]:
                print("---")
                print(f"Text: {doc.page_content}")
                print(f"Metadata: {doc.metadata}")
    else:
        if return_docs:
            return None, None
        print("Не удалось распознать или сохранить результат.")

if __name__ == "__main__":
    main()