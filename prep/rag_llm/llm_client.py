from __future__ import annotations

import os
import base64
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

from dotenv import load_dotenv
load_dotenv()

from langchain_ollama import OllamaLLM



# ----------------------
# Вспомогательные утилиты
# ----------------------
def _read_env(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key, default)
    return v

def _format_ts(seconds: float) -> str:
    try:
        s = max(0, int(round(seconds)))
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"
    except Exception:
        return "00:00"


# ----------------------
# Пресеты
# ----------------------
@dataclass
class LlmPreset:
    name: str
    temperature: float = 0.1
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    # можно расширять по мере надобности

PRESETS = {
    "fact": LlmPreset(name="fact", temperature=0.0, top_p=0.9, top_k=None, max_tokens=None),
    "assistant": LlmPreset(name="assistant", temperature=0.1, top_p=0.95, top_k=None, max_tokens=None),
    "code": LlmPreset(name="code", temperature=0.0, top_p=0.9, top_k=None, max_tokens=None),
}


# ----------------------
# Настройки LLM
# ----------------------
@dataclass
class LLMSettings:
    model: str
    base_url: str
    user: Optional[str] = None
    password: Optional[str] = None

    @classmethod
    def from_env(cls) -> "LLMSettings":
        model = _read_env("MODEL")
        base_url = _read_env("URL_LLM")
        user = _read_env("USER_LLM")
        password = _read_env("PASSWORD_LLM")
        if not model or not base_url:
            raise ValueError("Отсутствуют обязательные переменные окружения: MODEL, URL_LLM")
        return cls(model=model, base_url=base_url, user=user, password=password)


# ----------------------
# Основной клиент
# ----------------------
class LLMClient:
    def __init__(
        self,
        settings: Optional[LLMSettings] = None,
        preset: str = "assistant",
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        self.settings = settings or LLMSettings.from_env()
        self.preset = PRESETS.get(preset, PRESETS["assistant"])

        # Параметры генерации — можно переопределить аргументами конструктора
        self.temperature = self.preset.temperature if temperature is None else temperature
        self.top_p = self.preset.top_p if top_p is None else top_p
        self.top_k = self.preset.top_k if top_k is None else top_k
        self.max_tokens = self.preset.max_tokens if max_tokens is None else max_tokens

        headers = {}
        if self.settings.user and self.settings.password:
            token = base64.b64encode(f"{self.settings.user}:{self.settings.password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"

        # Инициализация OllamaLLM
        self._llm = OllamaLLM(
            model=self.settings.model,
            base_url=self.settings.base_url,
            temperature=self.temperature,
            top_p=self.top_p,
            client_kwargs={"headers": headers} if headers else None,
        )

        # Дополнительные параметры
        self.additional_kwargs: Dict[str, Any] = {}
        if self.top_k is not None:
            self.additional_kwargs["top_k"] = self.top_k
        if self.max_tokens is not None:
            self.additional_kwargs["num_predict"] = self.max_tokens 

    def generate(self, prompt: str) -> str:
        """Синхронная генерация. На вход — уже готовый промпт."""
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt должен быть непустой строкой")
        result = self._llm.invoke(prompt)  # type: ignore
        if isinstance(result, str):
            return result
        return getattr(result, "content", str(result))

    def generate_with_retrieval(
        self,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        mmr: bool = False,
        context_char_limit: int = 12000,
    ) -> str:
        """Композитный метод: собирает контекст и добавляет раздел 'Источники' (audio + таймкоды)."""
        if not question or not isinstance(question, str):
            raise ValueError("question должен быть непустой строкой")
        chunks = list(retrieved_chunks or [])

        if score_threshold is not None:
            filtered = []
            for ch in chunks:
                score = None
                try:
                    score = float(ch.get("meta", {}).get("score", None))
                except Exception:
                    score = None
                if score is None or score <= score_threshold:
                    filtered.append(ch)
            chunks = filtered

        if k is not None and k > 0:
            chunks = chunks[:k]

        context_lines: List[str] = []
        citations = []  # (audio_title, time_range_str)
        total_len = 0

        def _format_ts(seconds: float) -> str:
            s = max(0, int(round(seconds)))
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"

        for idx, ch in enumerate(chunks, start=1):
            text = str(ch.get("text", "")).strip()
            meta = ch.get("meta", {}) or {}
            audio_title = str(meta.get("audio_title", "unknown_audio")).strip()
            ts = meta.get("timestamp_range", None)
            if isinstance(ts, (list, tuple)) and len(ts) == 2:
                t1 = _format_ts(float(ts[0]))
                t2 = _format_ts(float(ts[1]))
                time_range_str = f"{t1}-{t2}"
            else:
                time_range_str = "00:00-00:00"

            snippet = " ".join(text.replace("\n", " ").replace("\r", " ").split())
            candidate = f"[{idx}] {snippet}\n"
            if total_len + len(candidate) > context_char_limit:
                break
            context_lines.append(candidate)
            total_len += len(candidate)
            citations.append((audio_title, time_range_str))

        context_block = "\n".join(context_lines).strip()

        parts: List[str] = []
        if system_prompt:
            parts.append(f"СИСТЕМНЫЕ ИНСТРУКЦИИ:\n{system_prompt}\n---")
        parts.append("КОНТЕКСТ ИЗ БАЗЫ:")
        parts.append(context_block if context_block else "(контекст не найден)")
        parts.append("---")
        parts.append("ЗАДАЧА: ответь на вопрос пользователя максимально точно и по сути, опираясь ТОЛЬКО на контекст выше.")
        parts.append("Если ответа в контексте нет — честно скажи, что данных недостаточно.")
        parts.append("В конце ответа добавь раздел 'Источники' со списком аудиофайлов и таймкодов из контекста.")
        parts.append("---")
        parts.append(f"ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}")
        final_prompt = "\n".join(parts)

        raw_answer = self.generate(final_prompt).strip()

        if "Источники" not in raw_answer:
            sources_lines = ["", "Источники:"]
            seen = set()
            for (title, tr) in citations:
                key = (title, tr)
                if key in seen:
                    continue
                seen.add(key)
                sources_lines.append(f"- {title} — {tr}")
            raw_answer = raw_answer + "\n" + "\n".join(sources_lines)

        return raw_answer


if __name__ == "__main__":
    client = LLMClient()
    demo_chunks = [
        {
            "text": "В проекте используется модуль индексации аудио в ChromaDB...",
            "meta": {"audio_title": "meeting_2024_09_01.wav", "timestamp_range": [12.3, 45.8], "score": 0.08},
        },
        {
            "text": "Параметры подключения к Ollama берутся из .env: MODEL, URL_LLM...",
            "meta": {"audio_title": "tech_sync.wav", "timestamp_range": [120.0, 165.0], "score": 0.12},
        },
    ]
    system = "Ты — корпоративный ассистент, отвечаешь кратко и по делу, на русском."
    answer = client.generate_with_retrieval(
        question="Как подключаемся к локальной модели и где лежит конфигурация?",
        retrieved_chunks=demo_chunks,
        system_prompt=system,
        k=2,
        score_threshold=None,
    )
    print(answer)
