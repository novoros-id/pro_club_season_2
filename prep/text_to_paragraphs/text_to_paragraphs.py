import math
import numbers
import re
from typing import List, Optional, Tuple, Union

from model_api import get_default_client


def cosine_similarity(left, right):
    if len(left) != len(right):
        raise ValueError("Нельзя сравнить embeddings различной размерности.")
    if not left:
        raise ValueError("Нельзя сравнить пустые embeddings.")
    if not all(isinstance(value, numbers.Real) for value in list(left) + list(right)):
        raise ValueError("Embedding содержит нечисловое значение.")
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


class text_to_paragraphs:
    def __init__(
        self,
        text: Union[str, List[Tuple[str, float]]],
        segments_time: Optional[List[Tuple[str, float]]] = None,
        client=None,
    ):
        self.client = client or get_default_client()
        if segments_time is not None:
            self.segments_time = segments_time
            self.mode = "segments"
        else:
            self.text = text.strip() if isinstance(text, str) else ""
            self.mode = "text"

    def _split_sentences_from_text(self, text: str) -> List[str]:
        if not text:
            return []
        # Network-free baseline splitter. Segment mode, used by the main flow, does
        # not perform any extra tokenization.
        return [item.strip() for item in re.split(r"(?<=[.!?])\s+", text) if item.strip()]

    def _inputs(self):
        if self.mode == "segments":
            return ([str(item[0]).strip() for item in self.segments_time],
                    [float(item[1]) for item in self.segments_time])
        sentences = self._split_sentences_from_text(self.text)
        return sentences, [float(index) for index in range(len(sentences))]

    def _build(self, threshold, min_sents, max_sents, min_words, max_words):
        sentences, times = self._inputs()
        if not sentences:
            return []
        if len(sentences) == 1:
            return [(sentences[0], times[0])]
        embeddings = self.client.embed_texts(sentences)
        if len(embeddings) != len(sentences):
            raise ValueError("Число embeddings не совпадает с числом предложений.")
        similarities = [
            cosine_similarity(embeddings[index], embeddings[index + 1])
            for index in range(len(embeddings) - 1)
        ]

        paragraphs = []
        current_sentences = []
        current_times = []
        for index, sentence in enumerate(sentences):
            current_sentences.append(sentence)
            current_times.append(times[index])
            word_count = sum(len(item.split()) for item in current_sentences)
            semantic_break = index < len(similarities) and similarities[index] < threshold
            long_enough = len(current_sentences) >= min_sents or word_count >= min_words
            too_long = len(current_sentences) >= max_sents or word_count >= max_words
            if (semantic_break and long_enough) or too_long:
                paragraphs.append((" ".join(current_sentences), current_times[-1]))
                current_sentences, current_times = [], []
        if current_sentences:
            paragraphs.append((" ".join(current_sentences), current_times[-1]))
        return paragraphs

    def _threshold(self, value):
        if value is not None:
            return float(value)
        # 0.7 is the old model's starting threshold and must be calibrated on real
        # BGE-M3 transcription data after migration.
        return self.client.config.paragraph_similarity_threshold

    def get_text_to_paragraphs(self, threshold=None, min_sents=3, max_sents=12,
                               min_words=15, max_words=250):
        paragraphs = self.get_text_to_paragraphs_array(
            threshold, min_sents, max_sents, min_words, max_words
        )
        return "\n".join(f"\t{paragraph}" for paragraph in paragraphs)

    def get_text_to_paragraphs_array(self, threshold=None, min_sents=2, max_sents=8,
                                     min_words=15, max_words=150):
        return [row[0] for row in self._build(
            self._threshold(threshold), min_sents, max_sents, min_words, max_words
        )]

    def get_text_to_paragraphs_table(self, threshold=None, min_sents=2, max_sents=8,
                                     min_words=15, max_words=150):
        if self.mode != "segments":
            raise ValueError("Метод get_text_to_paragraphs_table требует segments_time.")
        return self._build(
            self._threshold(threshold), min_sents, max_sents, min_words, max_words
        )
