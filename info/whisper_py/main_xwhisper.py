import whisperx
import json
from langchain_core.documents import Document

# 1. Загружаем модель
model = whisperx.load_model("large-v3", device="cpu", language="ru", compute_type="int8)  # или "cuda" если есть GPU

# 2. Транскрипция
audio_path = "test_voice_clean.wav"
result = model.transcribe(audio_path, batch_size=16)

# 3. Выравнивание слов (очень точные тайминги!)
model_a, metadata = whisperx.load_align_model(language_code=result["language"], device="cpu")
result_aligned = whisperx.align(result["segments"], model_a, metadata, audio_path, device="cpu")

# 4. Сохраняем JSON с таймингами
with open("output.json", "w", encoding="utf-8") as f:
    json.dump(result_aligned, f, ensure_ascii=False, indent=2)

# 5. Преобразуем в LangChain документы
docs = [
    Document(
        page_content=segment["text"],
        metadata={
            "start": segment["start"],
            "end": segment["end"],
            "words": segment.get("words", [])
        }
    )
    for segment in result_aligned["segments"]
]

# Выводим
print(json.dumps(result_aligned["segments"], ensure_ascii=False, indent=2))
