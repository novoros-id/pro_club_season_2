# pip install --upgrade "torch>=2.2" transformers accelerate
import os, json, torch
import whisper  # openai‑whisper
from typing import List, Tuple
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
            #out = self.pipe(audio_path, generate_kwargs={"language": self.language})
            # Стало:
            out = self.pipe(
                audio_path,
                generate_kwargs={
                    "language": self.language,
                    "return_timestamps": "word",
                    "task": "transcribe"
                }
            )
            chunks = out.get("chunks", [])
            segments = self._group_chunks(chunks, max_gap=0.6)   # ← группируем
            full_text = out.get("text", "").strip()
        else:
            result = self.model.transcribe(
                audio_path,
                language=self.language,
                word_timestamps=True,
            )
            segments = result.get("segments", [])
            full_text = result.get("text", "").strip()

        self._last_transcription_result = {
            "full_text": full_text,
            "segments": segments,
            "audio_file": audio_path,
        }

        # Освобождаем кэш GPU после транскрипции
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return self._last_transcription_result


    def _group_chunks(self, chunks, max_gap=0.6, max_words=20):
        """Объединяем word‑chunks обратно во фразы.
        • max_gap   – пауза (с) между словами, после которой начинаем новый сегмент
        • max_words – «страховка» от слишком длинных сегментов
        """
        import re

        def _flush(seg_words, seg_start, seg_end, segments):
            if not seg_words:
                return
            # --- 1. safely strip leading spaces ---
            clean_tokens = [w["text"].lstrip() for w in seg_words]       ### NEW
            text = " ".join(clean_tokens)                                ### NEW

            # --- 2. collapse multi‑spaces + fix punctuation ---
            text = re.sub(r"\s{2,}", " ", text)          # двойные → одиночные
            text = re.sub(r"\s+([.,!?;:%)\]])", r"\1", text)  # пробел перед знаками

            segments.append({
                "id": len(segments),
                "start": seg_start,
                "end":   seg_end,
                "text":  text.strip(),
                "words": [
                    {
                        "word":  w["text"].strip(),
                        "start": w["timestamp"][0],
                        "end":   w["timestamp"][1] or w["timestamp"][0],
                    } for w in seg_words
                ],
            })


        segments, seg_words = [], []
        seg_start = prev_end = None

        for ch in chunks:
            st, ed = ch.get("timestamp", (None, None))
            if st is None:                 # пропускаем «битый» чанκ
                continue

            # первый / новый сегмент
            if seg_start is None:
                seg_start = st
                prev_end  = ed or st

            gap = 0 if prev_end is None else st - prev_end
            if (gap > max_gap and seg_words) or len(seg_words) >= max_words:
                _flush(seg_words, seg_start, prev_end, segments)
                seg_words, seg_start = [], st

            seg_words.append(ch)
            prev_end = ed or st      # если ed == None, берём st

        _flush(seg_words, seg_start, prev_end, segments)
        return segments


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

        docs: List[Document] = []
        audio_path = self._last_transcription_result.get("audio_file", "")
        audio_title = os.path.basename(audio_path) if audio_path else ""
        for seg in self._last_transcription_result["segments"]:
            start = float(seg["start"])
            stop = float(seg["end"])
            docs.append(
                Document(
                    page_content=seg["text"],
                    metadata={
                        "audio_title": audio_title,
                        "start": start,
                        "end": stop,
                        "segment_index": seg["id"],
                        "timestamp_range": f"{self.format_timestamp(start)} - {self.format_timestamp(stop)}"
                    }
                )
            )
        return docs
    
    def transcribe_to_documents(self, audio_file: str, out_json_path: str | None = None) -> Tuple[str, List[Document]]:
        json_path, docs = self.save_json(audio_file), self.as_documents()
        return json_path, docs
    
    def unload(self):
        """Полностью удаляет модель и освобождает GPU-память."""
        if self._hf_backend:
            del self.pipe
            del self.model
            del self.processor
        else:
            del self.model

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self._last_transcription_result = None