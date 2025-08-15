import os
import json
import whisper
from langchain_core.documents import Document
from typing import List, Dict, Any, Tuple


class Transcription:
    def __init__(self, model_name: str = "medium", language: str = "ru", device: str | None = None):
        self.model = whisper.load_model(model_name, device=device) if device else whisper.load_model(model_name)
        self.language = language

    # Преобразование секунд возвращаемых Whisper в человекочитаемый формат времени
    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        if seconds is None:
            return "00:00:00"
        milliseconds = int(round(seconds - int(seconds)) * 1000)
        seconds = int(seconds) % 60
        minutes = (int(seconds) // 60) % 60
        hours = int(seconds // 3600)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    # Транскрибирование аудио файла с использованием Whisper
    def transcribe(self, audio_file: str, out_json_path: str | None = None) -> Tuple[str, Dict[str, Any]]:
        result = self.model.transcribe(
            audio_file, 
            language=self.language,
            verbose=False, 
            word_timestamps=True,
            condition_on_previous_text=False
        )

        segments = result.get("segments", []) or []
        words_total = 0
        json_segments: List[Dict[str, Any]] = []

        for i, seg in enumerate(segments):
            seg_start = float(seg.get("start", 0.0))
            seg_end = float(seg.get("end", 0.0))
            seg_text = seg.get("text", "").strip()

            seg_words = []
            for w in (seg.get("words") or []):
                word_start = float(w.get("start", 0.0))
                word_end = float(w.get("end", 0.0))
                seg_words.append({
                    "word": w.get("word", "").strip(),
                    "start": word_start,
                    "end": word_end
                })
                words_total += len(seg_words)

            json_segments.append({
                "id": i,
                "start": seg_start,
                "end": seg_end,
                "start_timestamp": self._format_timestamp(seg_start),
                "end_timestamp": self._format_timestamp(seg_end),
                "text": seg_text,
                "words": seg_words
            })
        audio_file = os.path.abspath(audio_file)
        duration = float(json_segments[-1]["end"]) if json_segments else 0.0

        json_object: Dict[str, Any] = {
            "audio_file": audio_file,
            "duration": duration,
            "segments": json_segments,
            "words_total": words_total
        }

        if out_json_path is None:
            base, _ = os.path.splitext(audio_file)
            out_json_path = f"{base}.json"

        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(json_object, f, ensure_ascii=False, indent=2)

        return out_json_path, json_object
    
    # Преобразование результата транскрипции в формат LangChain Document
    @staticmethod
    def json_to_documents(json_obj: Dict[str, Any]) -> List[Document]:
        docs: List[Document] = []
        audio_title = json_obj.get("audio_file", "")
        for seg in json_obj.get("segments", []):
            start = seg.get("start", 0.0)
            end = seg.get("end", 0.0)
            page = seg["text"]

            metadata = {
                "audio_title": audio_title,
                "start": start,
                "end": end,
                "timestamp_range": f"{seg['start_timestamp']} - {seg['end_timestamp']}",
                "segment_index": seg["id"]
            }
            docs.append(Document(page_content=page, metadata=metadata))

        return docs

    def transcribe_to_documents(self, audio_file: str, out_json_path: str | None = None) -> Tuple[str, List[Document]]:
        json_path, json_obj = self.transcribe(audio_file, out_json_path)
        docs = self.json_to_documents(json_obj)
        return json_path, docs