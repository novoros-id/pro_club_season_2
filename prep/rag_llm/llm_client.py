from __future__ import annotations

import os
import base64
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Union
from rag_llm.llm_prompt import compose_prompt

from dotenv import load_dotenv
load_dotenv()

from langchain_ollama import OllamaLLM
from langchain_huggingface import HuggingFaceEmbeddings
import chromadb


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
    ) -> None:
        self.settings = settings or LLMSettings.from_env()
        self.preset = PRESETS.get(preset, PRESETS["assistant"])

        # Параметры генерации — можно переопределить аргументами конструктора
        self.temperature = self.preset.temperature if temperature is None else temperature
        self.top_p = self.preset.top_p if top_p is None else top_p
        self.top_k = self.preset.top_k if top_k is None else top_k

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
    

    def _build_context(
            self,
            chunks: List[Dict[str, Any]],
            top_k: int,
            score_threshold: float,
            max_chars: int,
    ) -> Tuple[str, List[Tuple[str, str]]]:
        """
        Args:
            chunks: Список словарей с ключами: 'text', 'score', 'source'
            top_k: Количество лучших чанков для включения в контекст. Если None, то все
            score_threshold: Мин. порог (дистанция векторов, чем меньше, тем лучше). Если None, то не учитывается
            max_chars: Максимальное число символов в итоговом контексте
        """

        # 1. Фильтрация по score_threshold
        filtered_chunks = []
        for ch in chunks:
            meta = ch.get("meta", {})
            score = meta.get("score")
            if score is None or score <= score_threshold:
                filtered_chunks.append(ch)

        if not filtered_chunks:
            return "", []

        # 2. Ограничение по top_k
        if top_k > 0:
            filtered_chunks = filtered_chunks[:top_k]

        # 3. Сборка текста и источников
        context_lines = []
        sources: List[Tuple[str, str]] = []
        total_len = 0

        for idx, ch in enumerate(filtered_chunks, start=1):
            text = ch.get("text", "").replace("\n", "  ").strip()
            meta = ch.get("meta", {})

            # Формируем таймкод
            ts = meta.get("timestamp_range", None)
            if isinstance(ts, (str)) and "-" in ts:
                time_range = ts.strip()
            elif isinstance(ts, (list, tuple)) and len(ts) == 2:
                t1 = _format_ts(float(ts[0]))
                t2 = _format_ts(float(ts[1]))
                time_range = f"{t1} - {t2}"
            else:
                time_range = "00:00 - 00:00 (unknown timestamp)"

            audio_title = meta.get("audio_title", "unknown_audio")

            # Добавляем кусков в контекст с лимитом по символам
            snipped_text = f"[{idx}] {text}"
            if total_len + len(snipped_text) > max_chars:
                break

            context_lines.append(snipped_text)
            sources.append((audio_title, time_range))
            total_len += len(snipped_text)

        context_block = "\n".join(context_lines)
        return context_block, sources
    
    def retrieve_chunks(self, question: str, collection_name: str = "audio_chunks", n_results: int = 5) -> List[Dict[str, Any]]:
        client = chromadb.PersistentClient(path=os.getenv("CHROMA_PERSIST_DIR"))
        collection = client.get_collection(collection_name)

        embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large")
        query_embedding = embeddings.embed_query(question)

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        scores = results["distances"][0]

        chunks = []
        for doc, meta, score in zip(docs, metas, scores):
            chunks.append({
                "text": doc,
                "meta": {
                    "score": score,
                    "timestamp_range": meta.get("timestamp_range"),
                    "audio_title": meta.get("audio_title", "unknown_audio")
                }
            })
        return chunks
    
    def generate_with_retrieval(
        self,
        question: str,
        *,
        system_prompt: Optional[str] = None,
        mode: str = "assistant",
        top_k: int = 5,
        score_threshold: float = 0.3,
        max_chars: int = 12000,
        return_with_sources: bool = False,
    ) -> Union[str, Dict[str, Any]]:
        """
        Генерация ответа с учётом RAG-контекста
        
        Args:
            question: Вопрос от пользователя.
            system_prompt: Системные инструкции для модели.
            mode: Режим работы промпта. Пресеты в llm_prompt.py.
            top_k: Количество лучших чанков.
            score_threshold: Порог отсечения по score.
            max_chars: Лимит символов в контексте.
            return_with_sources: Возвращать ли источники отдельно.
        
        Returns:
            Если return_with_sources=False → готовый ответ (str).
            Если return_with_sources=True → dict с полями:
                - "answer": ответ LLM
                - "sources": список источников
                - "context_len": длина использованного контекста
                - "mode": режим работы
        """
        if not question or not isinstance(question, str):
            raise ValueError("question должен быть непустой строкой")

        # 1. Строим контекст и источники
        retrieved_chunks = self.retrieve_chunks(question, n_results=top_k)
        context, sources = self._build_context(
            chunks=retrieved_chunks,
            top_k=top_k,
            score_threshold=score_threshold,
            max_chars=max_chars
        )

        # 2. Сборка финального промпта
        final_prompt = compose_prompt(
            question=question,
            context=context,
            mode=mode
        )

        # 3. Генерация ответа моделью
        raw_answer = self._llm(final_prompt).strip()

        # 4. Добавляем "Источники", если это не return_with_sources=True
        if sources and not return_with_sources:
            sources_lines = ["", "Источники:"]
            seen = set()
            for title, time_range in sources:
                if (title, time_range) not in seen:
                    sources_lines.append(f"- {title} — {time_range}")
                    seen.add((title, time_range))
            raw_answer += "\n" + "\n".join(sources_lines)

        # 5. Возвращаем ответ
        if return_with_sources:
            return {
                "answer": raw_answer,
                "sources": [{"title": t, "time_range": tr} for t, tr in sources],
                "context_len": len(context),
                "mode": mode
            }
        
        return raw_answer
