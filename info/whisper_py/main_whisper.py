import whisper
import json
from datetime import timedelta
from langchain_core.documents import Document

# Путь к аудио
audio_path = "test_voice_clean.wav"

# Загружаем модель
model = whisper.load_model("large")

# Выполняем транскрипцию
result = model.transcribe(
    audio_path,
    word_timestamps=True,
    verbose=False,
    language="ru"
)

# Формируем JSON-структуру
output = {
    "full_text": result["text"],
    "segments": []
}

for segment in result["segments"]:
    output["segments"].append({
        "id": segment.get("id"),
        "start": segment["start"],
        "end": segment["end"],
        "text": segment["text"],
        "words": [
            {
                "word": word["word"],
                "start": word["start"],
                "end": word["end"]
            } for word in segment.get("words", [])
        ]
    })

# Сохраняем JSON
with open("transcript.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("✅ JSON сохранён: transcript.json")

# ---------- Экспорт в SRT ----------

def format_timestamp(seconds: float) -> str:
    return str(timedelta(seconds=seconds)).replace('.', ',')[:12].rjust(12, '0')

with open("transcript.srt", "w", encoding="utf-8") as f:
    for i, seg in enumerate(output["segments"], 1):
        f.write(f"{i}\n")
        f.write(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n")
        f.write(f"{seg['text'].strip()}\n\n")

print("🎬 SRT сохранён: transcript.srt")

# ---------- Конвертация в LangChain Documents ----------

documents = [
    Document(
        page_content=seg["text"],
        metadata={
            "start": seg["start"],
            "end": seg["end"],
            "words": seg["words"],
            "segment_id": seg["id"]
        }
    )
    for seg in output["segments"]
]

print(f"📄 Готово: {len(documents)} LangChain документов сформировано")
