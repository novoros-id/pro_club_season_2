# pip install --upgrade "torch>=2.2" transformers accelerate
import os, json, torch
import whisper  # openai‑whisper
from typing import List
from langchain_core.documents import Document

class Transcription:
    def __init__(self, model_name: str = "medium", language: str = "ru"):
        self.language = language
        self._hf_backend = "/" in model_name  # признак Hugging Face модели

        if self._hf_backend:
            print("_hf_backend")
            # --- Hugging Face загрузка ---
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            device = "cuda:0" if torch.cuda.is_available() else "cpu"

            self.processor = AutoProcessor.from_pretrained(model_name)
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_name,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
                use_safetensors=True,
            ).to(device)

            # `return_timestamps="word"` → получаем тайм‑коды каждого слова :contentReference[oaicite:1]{index=1}
            self.pipe = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=self.processor.tokenizer,
                feature_extractor=self.processor.feature_extractor,
                return_timestamps="word",
                chunk_length_s=30,
                torch_dtype=dtype,
                device=device,
            )
        else:
            print("openai‑whisper")
            # --- классический openai‑whisper ---
            self.model = whisper.load_model(model_name)

    # переиспользуем вашу функцию
    def format_timestamp(self, seconds: float) -> str:
        ms = int((seconds - int(seconds)) * 1000)
        return f"{int(seconds // 3600):02d}:{int((seconds % 3600)//60):02d}:{int(seconds%60):02d}.{ms:03d}"

    def transcribe(self, audio_path: str) -> dict:
        if self._hf_backend:
            out = self.pipe(audio_path, generate_kwargs={"language": self.language})
            # формируем тот же самый словарь, что давал Whisper
            segments = []
            for i, ch in enumerate(out.get("chunks", [])):
                segments.append({
                    "id": i,
                    "start": ch["timestamp"][0],
                    "end":   ch["timestamp"][1],
                    "text":  ch["text"].strip(),
                    "words": [{
                        "word":  ch["text"].strip(),
                        "start": ch["timestamp"][0],
                        "end":   ch["timestamp"][1],
                    }],
                })
            result = {"text": out.get("text", "").strip(), "segments": segments}
        else:
            result = self.model.transcribe(
                audio_path,
                language=self.language,
                word_timestamps=True,
            )

        # унифицируем под старое API
        full_text = result.get("text", "").strip()
        self._last_transcription_result = {
            "full_text": full_text,
            "segments": result.get("segments", []),
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