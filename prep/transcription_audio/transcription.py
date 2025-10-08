# pip install --upgrade "torch>=2.2" transformers accelerate
import os, json, torch, datetime
import whisper  # openai‑whisper
from typing import List, Tuple, Optional
from langchain_core.documents import Document

# --- НОВОЕ: импорт для разбиения аудио ---
from pydub import AudioSegment
from pydub.silence import detect_silence # <-- Правильный импорт
import tempfile
import math

class Transcription:
    # --- НОВОЕ: константы для разбиения ---
    # Задайте нужные значения
    PART_DURATION_SECONDS: int = 5 * 60  # 1 минута (для теста)
    LOOKBACK_SECONDS: int = 30           # 30 секунд до разреза
    PAUSE_THRESHOLD_DB: float = -40.0    # -40 dB как порог тишины
    PAUSE_MIN_DURATION_MS: int = 2000    # 2 секунды как минимальная пауза
    # --- /НОВОЕ ---

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
                device_map="auto",  # автоматическое распределение
                offload_folder="./offload",  # оффлокд на CPU при необходимости
            )#.to(device)

            # `return_timestamps="word"` → получаем тай‑коды каждого слова
            self.pipe = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=self.processor.tokenizer,
                feature_extractor=self.processor.feature_extractor,
                return_timestamps="word",
                chunk_length_s=30,
                torch_dtype=dtype
            )
        else:
            print("openai‑whisper")
            # --- классический openai‑whisper ---
            self.model = whisper.load_model(model_name)

    # переиспользуем вашу функцию
    def format_timestamp(self, seconds: float) -> str:
        ms = int((seconds - int(seconds)) * 1000)
        return f"{int(seconds // 3600):02d}:{int((seconds % 3600)//60):02d}:{int(seconds%60):02d}.{ms:03d}"

    # --- НОВОЕ: метод для поиска точки разреза ---
    def _find_split_point(self, audio_segment: AudioSegment, target_time_ms: int) -> int:
        """
        Находит подходящую точку для разреза в аудио.
        Ищет паузу заданной длительности в окне до target_time_ms.
        Возвращает время в миллисекундах, где нужно разрезать.
        """
        # 1. Определяем область поиска (lookback window)
        start_search_ms = max(0, target_time_ms - (self.LOOKBACK_SECONDS * 1000))
        search_segment = audio_segment[start_search_ms:target_time_ms]

        # 2. Ищем тишину (паузу) в этой области
        # Используем detect_silence напрямую, так как она импортирована из pydub.silence
        silence_ranges = detect_silence(
            search_segment,
            min_silence_len=self.PAUSE_MIN_DURATION_MS,
            silence_thresh=self.PAUSE_THRESHOLD_DB
        )

        # 3. Находим подходящую паузу, самую близкую к target_time_ms (но до неё)
        best_split_point = target_time_ms # Если пауза не найдена, разрезаем в target_time_ms
        for silence_start, silence_end in silence_ranges:
            # silence_start - это относительно начала search_segment
            absolute_silence_start = start_search_ms + silence_start
            # Выбираем паузу, которая максимально близка к target_time_ms, но до неё
            if absolute_silence_start < target_time_ms:
                # Обновляем best_split_point, если текущая пауза ближе к target_time_ms
                if absolute_silence_start > best_split_point:
                    best_split_point = absolute_silence_start

        return best_split_point
    # --- /НОВОЕ ---

    # --- НОВОЕ: метод для разбиения аудио ---
    def _split_audio_file(self, audio_path: str) -> List[str]:
        """
        Разбивает аудиофайл на части, учитывая паузы.
        Возвращает список временных файлов.
        """
        # from pydub import silence # <-- Было здесь, НЕПРАВИЛЬНО
        # from pydub.silence import detect_silence # <-- Теперь импортировано в начале файла, ПРАВИЛЬНО
        audio = AudioSegment.from_file(audio_path)

        duration_ms = len(audio)
        part_duration_ms = self.PART_DURATION_SECONDS * 1000
        split_points_ms = [i * part_duration_ms for i in range(1, math.ceil(duration_ms / part_duration_ms))]

        current_start_ms = 0
        temp_files = []
        for split_point_target_ms in split_points_ms:
            if current_start_ms >= duration_ms:
                break

            split_point_ms = self._find_split_point(audio, split_point_target_ms)
            # Убедимся, что точка разреза не меньше текущего начала
            split_point_ms = max(current_start_ms, split_point_ms)

            part_segment = audio[current_start_ms:split_point_ms]
            current_start_ms = split_point_ms

            # Создаём временный файл для части
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_path)[1]) as temp_file:
                part_segment.export(temp_file.name, format=os.path.splitext(audio_path)[1][1:]) # Убираем точку из формата
                temp_files.append(temp_file.name)

        # Добавляем остаток (последнюю часть), если она не пуста
        if current_start_ms < duration_ms:
            last_part_segment = audio[current_start_ms:]
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio_path)[1]) as temp_file:
                last_part_segment.export(temp_file.name, format=os.path.splitext(audio_path)[1][1:])
                temp_files.append(temp_file.name)

        return temp_files
    # --- /НОВОЕ ---

    # --- НОВОЕ: метод для объединения результатов разбиения ---
    def _merge_transcription_results(self, parts_results: List[dict], original_audio_path: str) -> dict:
        """
        Объединяет результаты транскрибации частей в один словарь.
        """
        full_text = ""
        all_segments = []
        current_offset = 0.0

        for idx, part_result in enumerate(parts_results):
            part_text = part_result.get("text", "")
            part_segments = part_result.get("segments", [])

            # Обновляем таймстампы с учётом смещения
            updated_segments = []
            for seg in part_segments:
                updated_seg = seg.copy()
                updated_seg["start"] += current_offset
                updated_seg["end"] += current_offset
                if "words" in updated_seg:
                    for word in updated_seg["words"]:
                        word["start"] += current_offset
                        word["end"] += current_offset
                updated_segments.append(updated_seg)

            all_segments.extend(updated_segments)
            full_text += part_text
            if idx < len(parts_results) - 1: # Не добавляем пробел после последней части
                full_text += " "

            # Смещение для следующей части - это конец текущей обработанной части
            if part_segments:
                current_offset = updated_segments[-1]["end"]

        return {
            "full_text": full_text.strip(),
            "segments": all_segments,
            "audio_file": original_audio_path,
        }
    # --- /НОВОЕ ---


    def transcribe(self, audio_path: str) -> dict:
        # --- НОВОЕ: проверка размера файла и разбиение ---
        audio_file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        # Грубая оценка, можно уточнить через длительность
        audio = AudioSegment.from_file(audio_path)
        duration_seconds = len(audio) / 1000.0
        print(f"[LOG] Размер аудио: {audio_file_size_mb:.2f} MB, Длительность: {duration_seconds:.2f} сек ({duration_seconds/60:.2f} мин)")

        if duration_seconds > self.PART_DURATION_SECONDS:
            print(f"[LOG] Длительность ({duration_seconds/60:.2f} мин) превышает лимит ({self.PART_DURATION_SECONDS/60:.2f} мин). Разбиваю файл...")
            part_files = self._split_audio_file(audio_path)
            print(f"[LOG] Аудио разбито на {len(part_files)} частей.")
            parts_results = []

            for i, part_file in enumerate(part_files):
                print(f"[LOG] Транскрибирую часть {i+1}/{len(part_files)}: {part_file}")
                # Используем внутренний метод для транскрибации одной части
                if self._hf_backend:
                    try:
                        print(f"[LOG] Начал транскрибацию части {i+1}")
                        out = self.pipe(
                            part_file,
                            generate_kwargs={
                                "language": self.language,
                                "task": "transcribe"
                            }
                        )
                        print(f"[LOG] Успешно завершил pipe части {i+1}")
                    except Exception as e:
                        print(f"[ERROR] Ошибка в self.pipe части {i+1}: {type(e).__name__}: {e}")
                        import traceback
                        traceback.print_exc()
                        raise
                    chunks = out.get("chunks", [])
                    segments = self._group_chunks(chunks, max_gap=0.6)
                    full_text = out.get("text", "").strip()
                    part_result = {
                        "text": full_text,
                        "segments": segments,
                    }
                else:
                    try:
                        print(f"[LOG] Начал транскрибацию части {i+1}")
                        result = self.model.transcribe(
                            part_file,
                            language=self.language,
                            word_timestamps=True,
                        )
                    except Exception as e:
                        print(f"[ERROR] Ошибка в транскрибации части {i+1}: {type(e).__name__}: {e}")
                        import traceback
                        traceback.print_exc()
                        raise
                    print(f"[LOG] Успешно завершил транскрибацию части {i+1}")
                    segments = result.get("segments", [])
                    full_text = result.get("text", "").strip()
                    part_result = {
                        "text": full_text,
                        "segments": segments,
                    }
                
                parts_results.append(part_result)

                # Удаляем временный файл после обработки
                os.unlink(part_file)
                print(f"[LOG] Удалён временный файл части {i+1}: {part_file}")

                # Освобождаем кэш GPU после каждой части
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            # Объединяем результаты всех частей
            final_result = self._merge_transcription_results(parts_results, audio_path)
            self._last_transcription_result = final_result
            return final_result
        else:
            print(f"[LOG] Длительность ({duration_seconds/60:.2f} мин) в пределах лимита ({self.PART_DURATION_SECONDS/60:.2f} мин). Обрабатываю файл целиком.")
        # --- /НОВОЕ ---

        if self._hf_backend:
            try:
                print(f"[LOG] Начал транскрибацию {datetime.datetime.now().isoformat()}")
                out = self.pipe(
                    audio_path,
                    generate_kwargs={
                        "language": self.language,
                        "task": "transcribe"
                    }
                )
                print(f"[LOG] Успешно завершил pipe, начало обработки чанков")
            except Exception as e:
                print(f"[ERROR] Ошибка в self.pipe: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                raise
            chunks = out.get("chunks", [])
            segments = self._group_chunks(chunks, max_gap=0.6)   # ← группируем
            full_text = out.get("text", "").strip()
        else:
            try:
                print(f"[LOG] Начал транскрибацию {datetime.datetime.now().isoformat()}")
                result = self.model.transcribe(
                    audio_path,
                    language=self.language,
                    word_timestamps=True,
                )
            except Exception as e:
                print(f"[ERROR] Ошибка в self.pipe: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                raise
            print(f"[LOG] Успешно завершил pipe, начало обработки чанков")
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
    def save_json(self, audio_path: str, out_json_path: Optional[str] = None) -> str:
        result = self.transcribe(audio_path)
        if not result:
            return None
        if out_json_path:
            os.makedirs(os.path.dirname(out_json_path) or ".", exist_ok=True)
            json_path = out_json_path
        else:
            json_path = os.path.splitext(audio_path)[0] + ".json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        return json_path
    
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
        json_path = self.save_json(audio_file, out_json_path)
        docs = self.as_documents()
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