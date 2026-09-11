import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class MWSConfig:
    base_url: str = "https://gpt.mwsapis.ru/projects/project-dmitriy-grishaev/openai/v1"
    api_key: str = ""
    llm_model: str = "gemma-4-31b-it"
    embedding_model: str = "bge-m3"
    stt_model: str = "whisper-large-v3"
    connect_timeout: float = 10.0
    read_timeout: float = 600.0
    embedding_batch_size: int = 64
    paragraph_processing_batch_size: int = 15
    paragraph_similarity_threshold: float = 0.7

    @classmethod
    def from_env(cls):
        # Resolve the private environment file from the project layout, never from
        # the caller's current working directory. Loading it is local-only and does
        # not initiate any network work during import.
        prep_dir = Path(__file__).resolve().parents[1]
        load_dotenv(dotenv_path=prep_dir / ".env", override=False)

        def positive_int(name, default):
            try:
                value = int(os.getenv(name, default))
            except (TypeError, ValueError):
                value = default
            return value if value > 0 else default

        def positive_float(name, default):
            try:
                value = float(os.getenv(name, default))
            except (TypeError, ValueError):
                value = default
            return value if value > 0 else default

        try:
            threshold = float(os.getenv("PARAGRAPH_SIMILARITY_THRESHOLD", "0.7"))
        except (TypeError, ValueError):
            threshold = 0.7

        return cls(
            base_url=os.getenv("MWS_BASE_URL", cls.base_url).rstrip("/"),
            api_key=os.getenv("MWS_API_KEY", "").strip(),
            llm_model=os.getenv("MWS_LLM_MODEL", cls.llm_model),
            embedding_model=os.getenv("MWS_EMBEDDING_MODEL", cls.embedding_model),
            stt_model=os.getenv("MWS_STT_MODEL", cls.stt_model),
            connect_timeout=positive_float("MWS_CONNECT_TIMEOUT", 10.0),
            read_timeout=positive_float("MWS_READ_TIMEOUT", 600.0),
            embedding_batch_size=positive_int("MWS_EMBEDDING_BATCH_SIZE", 64),
            paragraph_processing_batch_size=positive_int(
                "MWS_PARAGRAPH_BATCH_SIZE", 15
            ),
            paragraph_similarity_threshold=threshold,
        )
