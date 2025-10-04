from sentence_transformers import SentenceTransformer, util
import nltk
from typing import List, Tuple, Optional, Union

# Загрузка токенизатора предложений (один раз при импорте)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)


class text_to_paragraphs:
    _model = None  # Общая модель для всех экземпляров (опционально)

    def __init__(self, text: Union[str, List[Tuple[str, float]]], segments_time: Optional[List[Tuple[str, float]]] = None):
        """
        Инициализация.
        Поддерживает два режима:
        1. text = строка, segments_time = None → обработка обычного текста.
        2. text = игнорируется, segments_time = [(sentence, timestamp), ...] → обработка с врем. метками.
        """
        if segments_time is not None:
            self.segments_time = segments_time
            self.mode = 'segments'
        else:
            self.text = text.strip() if isinstance(text, str) else ""
            self.mode = 'text'

    @classmethod
    def get_model(cls):
        """Ленивая загрузка модели один раз."""
        if cls._model is None:
            cls._model = SentenceTransformer('all-MiniLM-L6-v2')
        return cls._model

    def _split_sentences_from_text(self, text: str) -> List[str]:
        """Надёжное разбиение текста на предложения с сохранением пунктуации."""
        if not text:
            return []
        # nltk поддерживает русский язык через параметр language
        sentences = nltk.sent_tokenize(text, language='russian')
        # Убираем лишние пробелы в начале/конце
        return [s.strip() for s in sentences if s.strip()]

    def get_text_to_paragraphs(
        self,
        threshold: float = 0.7,
        min_sents: int = 3,
        max_sents: int = 12,
        min_words: int = 15,
        max_words: int = 250
    ) -> str:
        """Возвращает текст, разбитый на абзацы (как строку с отступами)."""
        paragraphs = self.get_text_to_paragraphs_array(threshold, min_sents, max_sents, min_words, max_words)
        return '\n'.join(f"\t{p}" for p in paragraphs)

    def get_text_to_paragraphs_array(
        self,
        threshold: float = 0.7,
        min_sents: int = 2,
        max_sents: int = 8,
        min_words: int = 15,
        max_words: int = 150
    ) -> List[str]:
        """Возвращает список абзацев (без временных меток)."""
        if self.mode == 'segments':
            raw_sentences = [s for s, _ in self.segments_time]
            times = [t for _, t in self.segments_time]
        else:
            raw_sentences = self._split_sentences_from_text(self.text)
            times = list(range(len(raw_sentences)))  # фиктивные метки

        if not raw_sentences:
            return []

        model = self.get_model()
        embeddings = model.encode(raw_sentences, convert_to_tensor=True)
        sims = util.pytorch_cos_sim(embeddings, embeddings)

        paragraphs = []
        current_paragraph = []

        for i in range(len(raw_sentences)):
            current_paragraph.append(raw_sentences[i])

            word_count = sum(len(s.split()) for s in current_paragraph)

            # Условия для разрыва
            semantic_break = (i < len(raw_sentences) - 1 and sims[i][i + 1].item() < threshold)
            long_enough = (len(current_paragraph) >= min_sents or word_count >= min_words)
            too_long = (len(current_paragraph) >= max_sents or word_count >= max_words)

            if (semantic_break and long_enough) or too_long:
                paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []

        # Остаток
        if current_paragraph:
            paragraphs.append(" ".join(current_paragraph))

        return paragraphs

    def get_text_to_paragraphs_table(
        self,
        threshold: float = 0.7,
        min_sents: int = 2,
        max_sents: int = 8,
        min_words: int = 15,
        max_words: int = 150
    ) -> List[Tuple[str, float]]:
        """
        Возвращает список кортежей: (абзац, временная_метка_последнего_предложения).
        Работает ТОЛЬКО если был передан segments_time.
        """
        if self.mode != 'segments':
            raise ValueError("Метод get_text_to_paragraphs_table требует передачи segments_time при инициализации.")

        sentences = [s for s, _ in self.segments_time]
        times = [t for _, t in self.segments_time]

        if not sentences:
            return []

        model = self.get_model()
        embeddings = model.encode(sentences, convert_to_tensor=True)
        sims = util.pytorch_cos_sim(embeddings, embeddings)

        paragraphs = []
        current_paragraph = []
        current_times = []

        for i in range(len(sentences)):
            current_paragraph.append(sentences[i])
            current_times.append(times[i])

            word_count = sum(len(s.split()) for s in current_paragraph)

            semantic_break = (i < len(sentences) - 1 and sims[i][i + 1].item() < threshold)
            long_enough = (len(current_paragraph) >= min_sents or word_count >= min_words)
            too_long = (len(current_paragraph) >= max_sents or word_count >= max_words)

            if (semantic_break and long_enough) or too_long:
                paragraphs.append((" ".join(current_paragraph), current_times[-1]))
                current_paragraph = []
                current_times = []

        if current_paragraph:
            paragraphs.append((" ".join(current_paragraph), current_times[-1]))

        return paragraphs