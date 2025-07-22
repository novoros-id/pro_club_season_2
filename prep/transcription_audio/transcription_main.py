from transcription import Transcription

def main():
    # TODO: заменить на передачу из класса PrepareAudioVideo
    # Здесь должен быть путь к .wav файлу, подготовленному предыдущим шагом пайплайна
    audio_file = '/Users/alexeyvaganov/Documents/doc/Работа/КЛУБ РАЗРАБОТЧИКОВ/Просковья инструкция_PA.wav' # Пример: путь от PrepareAudioVideo
    transcriber = Transcription(model_name="antony66/whisper-large-v3-russian", language="ru")

    print(f"▶ Начинаем распознавание файла: {audio_file}")
    json_path = transcriber.save_json(audio_file)

    if json_path:
        print(f"Результат сохранён в: {json_path}")

        # Первые 3 документа для примера
        try:
            docs = transcriber.as_documents()
            print("\nПример документов для LLM:")
            for doc in docs[:3]:
                print("---")
                print(f"Text: {doc.page_content}")
                print(f"Metadata: {doc.metadata}")
        except Exception as e:
            print(f"Ошибка при формировании документов: {e}")
    else:
        print("Не удалось распознать или сохранить результат.")

if __name__ == "__main__":
    main()