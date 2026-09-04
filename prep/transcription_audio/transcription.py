import json
import os
from typing import Optional

from model_api import get_default_client


class Transcription:
    """Cloud transcription facade compatible with the former local implementation."""

    def __init__(self, model_name=None, language="ru", prompt="", client=None):
        # Legacy arguments remain accepted, while model selection is centralized.
        self.language = language
        self.client = client or get_default_client()
        self._last_transcription_result = None

    @property
    def last_result(self):
        return self._last_transcription_result

    def transcribe(self, audio_path: str) -> dict:
        result = self.client.transcribe(audio_path, language=self.language)
        self._last_transcription_result = result
        return result

    def save_json(self, audio_path: str, out_json_path: Optional[str] = None) -> str:
        result = self.transcribe(audio_path)
        json_path = out_json_path or os.path.splitext(audio_path)[0] + ".json"
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as output_file:
            json.dump(result, output_file, ensure_ascii=False, indent=2)
        return json_path

    def unload(self):
        """Compatibility no-op: cloud mode has no local model or GPU cache."""
        return None
