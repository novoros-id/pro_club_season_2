import os
import json
import whisper
from langchain_core.documents import Document
from typing import List


class Transcription:
    def __init__(self, model_name: str = "medium", language: str = "ru"):
        self.model = whisper.load_model(model_name)
        self.language = language

    # Преобразование секунд возвращаемых Whisper в человекочитаемый формат времени
    def format_timestamp(self, seconds: float) -> str:
        milliseconds = int((seconds - int(seconds)) * 1000)
        return f"{int(seconds // 3600):02d}:{int((seconds % 3600) // 60):02d}:{int(seconds % 60):02d}.{milliseconds:03d}"

    # Транскрибирование аудио файла с использованием Whisper
    def transcribe(self, audio_path: str) -> dict:
        result = self.model.transcribe(audio_path, language=self.language, word_timestamps=True)
        full_text = result.get("text", "").strip()
        segments = []

        for i, seg in enumerate(result.get("segments", [])):
            words = seg.get("words", [])
            segments.append({
                "id": i,
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "text": seg.get("text", "").strip(),
                "words": [
                    {
                        "word": word.get("word", "").strip(),
                        "start": word.get("start", 0.0),
                        "end": word.get("end", 0.0)
                    }
                    for word in words
                ]
            })

        self._last_transcription_result = {
            "full_text": full_text,
            "segments": segments
        }
        return self._last_transcription_result

    # Сохранение результата транскрипции в формате JSON
    def save_json(self, audio_path: str) -> str:
        result = self.transcribe(audio_path)
        if result:
            json_path = os.path.splitext(audio_path)[0] + ".json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            return json_path
        return None
    
    # Получение результата транскрипции в виде словаря для llm
    def as_documents(self) -> List[Document]:
        if not self._last_transcription_result:
            raise ValueError("Нет результатов: сначала вызовите transcribe()")

        docs = []
        for seg in self._last_transcription_result["segments"]:
            docs.append(
                Document(
                    page_content=seg["text"],
                    metadata={
                        "start": self.format_timestamp(seg["start"]),
                        "end": self.format_timestamp(seg["end"]),
                        "segment_id": seg["id"]
                    }
                )
            )
        return docs