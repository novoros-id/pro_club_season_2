import json
import math
import numbers
import os
import time
from threading import Lock

import requests

from .config import MWSConfig


class MWSAPIError(RuntimeError):
    """Safe, user-readable Model Hub error (never includes credentials)."""


class MWSClient:
    def __init__(self, config=None, session=None, max_retries=2, backoff_seconds=0.5):
        self.config = config or MWSConfig.from_env()
        self.session = session or requests.Session()
        self.max_retries = max(0, int(max_retries))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self.last_response_status = None
        self.last_response_seconds = None

    @property
    def _timeout(self):
        return (self.config.connect_timeout, self.config.read_timeout)

    def _headers(self):
        if not self.config.api_key:
            raise MWSAPIError("Не задан MWS_API_KEY для обращения к MWS GPT Model Hub.")
        return {"Authorization": f"Bearer {self.config.api_key}"}

    def _request(self, method, path, *, retryable=True, **kwargs):
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        attempts = self.max_retries + 1 if retryable else 1
        last_error = None
        for attempt in range(attempts):
            try:
                # requests does not guarantee rewinding multipart streams between
                # retries; explicitly reset them before a cautious STT retry.
                for file_value in (kwargs.get("files") or {}).values():
                    stream = file_value[1] if isinstance(file_value, tuple) else file_value
                    if hasattr(stream, "seek"):
                        stream.seek(0)
                response = self.session.request(
                    method, url, headers=self._headers(), timeout=self._timeout, **kwargs
                )
                if response.status_code in (401, 403):
                    raise MWSAPIError("MWS отклонил авторизацию (HTTP %s). Проверьте MWS_API_KEY." % response.status_code)
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if attempt + 1 < attempts:
                        time.sleep(self.backoff_seconds * (2 ** attempt))
                        continue
                    raise MWSAPIError("MWS временно недоступен или ограничил запросы (HTTP %s)." % response.status_code)
                if response.status_code >= 400:
                    raise MWSAPIError("MWS отклонил запрос (HTTP %s)." % response.status_code)
                response.raise_for_status()
                self.last_response_status = response.status_code
                elapsed = getattr(response, "elapsed", None)
                self.last_response_seconds = (
                    elapsed.total_seconds() if elapsed is not None else None
                )
                return response
            except MWSAPIError:
                raise
            except (requests.ConnectTimeout, requests.ReadTimeout) as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(self.backoff_seconds * (2 ** attempt))
                    continue
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 < attempts:
                    time.sleep(self.backoff_seconds * (2 ** attempt))
                    continue
        if isinstance(last_error, requests.ConnectTimeout):
            raise MWSAPIError("Истекло время подключения к MWS.") from last_error
        if isinstance(last_error, requests.ReadTimeout):
            raise MWSAPIError("MWS не ответил за отведённое время.") from last_error
        raise MWSAPIError("Сетевая ошибка при обращении к MWS.") from last_error

    @staticmethod
    def _json(response, operation):
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise MWSAPIError(f"MWS вернул некорректный JSON для операции {operation}.") from exc

    def chat_completion(self, messages, model=None, temperature=None):
        payload = {"model": model or self.config.llm_model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        response = self._request("POST", "/chat/completions", json=payload)
        data = self._json(response, "chat completions")
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise MWSAPIError("Ответ MWS chat completions не содержит choices[0].message.content.") from exc
        if not isinstance(content, str):
            raise MWSAPIError("Ответ MWS chat completions содержит некорректный текст.")
        return content

    def generate_text(self, prompt, model=None, temperature=None):
        return self.chat_completion(
            [{"role": "user", "content": prompt}], model=model, temperature=temperature
        )

    def embed_texts(self, texts):
        texts = list(texts)
        if not texts:
            return []
        if not all(isinstance(item, str) for item in texts):
            raise ValueError("Все входы embeddings должны быть строками.")

        vectors = []
        batch_size = self.config.embedding_batch_size
        for offset in range(0, len(texts), batch_size):
            batch = texts[offset:offset + batch_size]
            response = self._request("POST", "/embeddings", json={
                "model": self.config.embedding_model,
                "input": batch,
            })
            payload = self._json(response, "embeddings")
            rows = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(rows, list) or len(rows) != len(batch):
                raise MWSAPIError("Число embeddings в ответе MWS не совпадает с числом входных строк.")
            ordered = [None] * len(batch)
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("index"), int):
                    raise MWSAPIError("Embedding response содержит некорректный index.")
                index = row["index"]
                vector = row.get("embedding")
                if index < 0 or index >= len(batch) or ordered[index] is not None:
                    raise MWSAPIError("Embedding response содержит повторяющийся или выходящий за диапазон index.")
                if not isinstance(vector, list) or not vector or not all(
                    isinstance(value, numbers.Real) and math.isfinite(float(value)) for value in vector
                ):
                    raise MWSAPIError("Embedding response содержит пустой или нечисловой vector.")
                ordered[index] = [float(value) for value in vector]
            if any(vector is None for vector in ordered):
                raise MWSAPIError("Embedding response не содержит всех запрошенных vectors.")
            vectors.extend(ordered)

        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise MWSAPIError("Embeddings имеют различающуюся размерность.")
        return vectors

    def transcribe(self, audio_path, language="ru"):
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Аудиофайл не найден: {audio_path}")
        try:
            with open(audio_path, "rb") as audio_file:
                response = self._request(
                    "POST", "/audio/transcriptions", retryable=True,
                    files={"file": (os.path.basename(audio_path), audio_file)},
                    data={
                        "model": self.config.stt_model,
                        "language": language,
                        "response_format": "verbose_json",
                    },
                )
        except OSError as exc:
            raise MWSAPIError(f"Не удалось прочитать аудиофайл: {audio_path}") from exc
        payload = self._json(response, "audio transcription")
        segments = payload.get("segments") if isinstance(payload, dict) else None
        if not isinstance(segments, list) or not segments:
            raise MWSAPIError(
                "Успешный ответ MWS STT не содержит segments. Основному сценарию нужны segment timestamps для кадров и разделов."
            )
        normalized = []
        for index, segment in enumerate(segments):
            try:
                start = float(segment["start"])
                end = float(segment["end"])
                text = str(segment["text"]).strip()
            except (KeyError, TypeError, ValueError) as exc:
                raise MWSAPIError("MWS STT вернул сегмент с некорректными start/end/text.") from exc
            if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
                raise MWSAPIError("MWS STT вернул недопустимые временные метки сегмента.")
            normalized.append({"id": index, "start": start, "end": end, "text": text})
        full_text = payload.get("full_text", payload.get("text", ""))
        if not isinstance(full_text, str):
            full_text = str(full_text or "")
        return {"full_text": full_text.strip(), "segments": normalized, "audio_file": audio_path}


_default_client = None
_default_client_lock = Lock()


def get_default_client():
    global _default_client
    if _default_client is None:
        with _default_client_lock:
            if _default_client is None:
                _default_client = MWSClient()
    return _default_client
