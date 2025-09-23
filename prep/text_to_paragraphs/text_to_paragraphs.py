from sentence_transformers import SentenceTransformer, util
import numpy as np
import json

class text_to_paragraphs:
    def __init__(self, text, segments_time = ""):
        self.text = text
        self.segments_time = segments_time
    
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
    
    def get_text_to_paragraphs_array(self):

        # Загрузка модели
        model = SentenceTransformer('all-MiniLM-L6-v2')

        #with open(self.text, 'r', encoding='utf-8') as file:
        #    text = file.read()  # Правильный отступ здесь
        text = self.text

        # Разделение текста на предложения
        #sentences = text.split('. ')
        sentences = [sentence + '.' for sentence in text.split('. ')]

        # Удаляем последнюю точку, если она не нужна
        if sentences[-1].endswith('.'):
            sentences[-1] = sentences[-1][:-1]

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
        #result = '\n'.join(f"\t{paragraph}" for paragraph in paragraphs)
        return paragraphs

    def get_text_to_paragraphs_table_temp(self):

        # Загрузка модели
        model = SentenceTransformer('all-MiniLM-L6-v2')

        #with open(self.text, 'r', encoding='utf-8') as file:
        #    text = file.read()  # Правильный отступ здесь
        text = self.text
        segments_time = self.segments_time
        sentences =  [text for text, _ in segments_time]

        # Разделение текста на предложения
        #sentences = text.split('. ')
        #sentences = [sentence + '.' for sentence in text.split('. ')]

        # Удаляем последнюю точку, если она не нужна
        #if sentences[-1].endswith('.'):
        #    sentences[-1] = sentences[-1][:-1]

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
        #result = '\n'.join(f"\t{paragraph}" for paragraph in paragraphs)
        return paragraphs
    
    def get_text_to_paragraphs_table(self):

        # Загрузка модели
        model = SentenceTransformer('all-MiniLM-L6-v2')

        segments_time = self.segments_time  # [(text, end), ...]
        sentences = [text for text, _ in segments_time]
        times = [end for _, end in segments_time]

        # Векторизация предложений
        sentence_embeddings = model.encode(sentences)

        # Матрица схожести
        cosine_similarities = util.pytorch_cos_sim(sentence_embeddings, sentence_embeddings)

        # Порог схожести
        threshold = 0.7
        paragraphs = []
        current_paragraph = []
        current_times = []

        # Формирование абзацев
        for i in range(len(sentences)):
            current_paragraph.append(sentences[i])
            current_times.append(times[i])

            if i < len(sentences) - 1 and cosine_similarities[i][i + 1] < threshold:
                paragraphs.append((" ".join(current_paragraph), current_times[-1]))
                current_paragraph = []
                current_times = []

        # Добавляем последний абзац
        if current_paragraph:
            paragraphs.append((" ".join(current_paragraph), current_times[-1]))

        return paragraphs

