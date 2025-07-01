from sentence_transformers import SentenceTransformer, util
import numpy as np

class text_to_paragraphs:
    def __init__(self, text):
        self.text = text
    
    def get_text_to_paragraphs(self):

        # Загрузка модели
        model = SentenceTransformer('all-MiniLM-L6-v2')

        #with open(self.text, 'r', encoding='utf-8') as file:
        #    text = file.read()  # Правильный отступ здесь
        text = self.text

        # Разделение текста на предложения
        sentences = text.split('. ')

        # Векторизация предложений
        sentence_embeddings = model.encode(sentences)

        # Расчет матрицы схожести
        cosine_similarities = util.pytorch_cos_sim(sentence_embeddings, sentence_embeddings)

        # Определение границ абзацев
        threshold = 0.7  # Порог схожести
        paragraphs = []
        current_paragraph = []

        # Формирование абзацев
        for i in range(len(sentences)):
            current_paragraph.append(sentences[i])
            if i < len(sentences) - 1 and cosine_similarities[i][i + 1] < threshold:
                paragraphs.append(' '.join(current_paragraph))
                current_paragraph = []

        # Добавление последнего абзаца
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))

        # Вывод абзацев с нумерацией
        #for idx, paragraph in enumerate(paragraphs, start=1):
        #    print(f"Абзац {idx}: {paragraph}")
        #return paragraph
        #result = '\n'.join(paragraphs)
        result = '\n'.join(f"\t{paragraph}" for paragraph in paragraphs)
        return result