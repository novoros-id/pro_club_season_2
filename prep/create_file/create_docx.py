# pip install python-docx opencv-python

from docx import Document
from docx.shared import Mm
import os
import sys
import json
import re
from config import URL_LLM
from config import USER_LLM
from config import PASSWORD_LLM

# Добавляем родительский каталог в пути поиска модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Импорты из соседних модулей
from text_to_paragraphs.text_to_paragraphs import text_to_paragraphs
from picture_description.picture_description import picture_description

# === LLM для разбиения на разделы ===
from langchain_ollama import OllamaLLM
import base64

encoded_credentials = base64.b64encode(f"{USER_LLM}:{PASSWORD_LLM}".encode()).decode()
headers = {'Authorization': f'Basic {encoded_credentials}'}

def create_prompt_for_sectioning(paragraphs):
    """
    Формирует промт для LLM: разбить список абзацев на разделы.
    Передаём абзацы с нумерацией, чтобы LLM могла ссылаться на них.
    """
    numbered_text = "\n".join([f"[{i+1}] {p}" for i, p in enumerate(paragraphs)])

    prompt = f"""
    Ты — интеллектуальный анализатор текста. Проанализируй следующие пронумерованные абзацы и сгруппируй их в логические разделы.
    ВАЖНО:
    - Не изменяй и не перефразируй текст абзацев.
    - Сохраняй порядок.
    - Каждый абзац должен быть включён ровно в один раздел.

    Для каждого раздела укажи:
    1. Название раздела.
    2. Номера абзацев, входящих в раздел (например, «Абзацы 1–4»).
    3. Первые и последние слова первого и последнего абзаца раздела (для проверки).

    Формат:
    ---
    **Название раздела**: [Название]
    **Абзацы**: [X]–[Y]
    **Начало**: "[первые слова абзаца X]..."
    **Конец**: "...[последние слова абзаца Y]"
    ---


    Текст (с нумерацией):
    {numbered_text}
    """
    return prompt


def get_sections_from_llm(paragraphs, max_paragraphs_per_chunk=20):
    """
    Разбивает список абзацев на куски (без разрыва абзацев),
    отправляет каждый кусок в LLM для определения разделов,
    возвращает общий список разделов: [{'title': ..., 'start_par': int, 'end_par': int}].
    """
    llm = OllamaLLM(model="gemma3:12b", temperature=0.1, base_url=URL_LLM, client_kwargs={'headers': headers})

    sections = []
    seen_titles = set()  # Чтобы избежать дублей

    # === Разбиваем абзацы на куски по max_paragraphs_per_chunk ===
    for chunk_start in range(0, len(paragraphs), max_paragraphs_per_chunk):
        chunk = paragraphs[chunk_start:chunk_start + max_paragraphs_per_chunk]
        
        # Формируем текст куска с нумерацией (для привязки)
        numbered_chunk = "\n".join([f"[{chunk_start + i + 1}] {p}" for i, p in enumerate(chunk)])
        
        # Промт для LLM
        prompt = f"""
        Проанализируй следующие пронумерованные абзацы и выдели в них логические разделы.
        Укажи:
        - Название раздела,
        - Начальный и конечный номер абзаца (например, «Абзацы 3–5»).

        Формат:
        ---
        **Название раздела**: Введение
        **Абзацы**: 3–5
        ---

        Если раздел один: просто укажи его.

        Текст:
        {numbered_chunk}
        """

        try:
            response = llm.invoke(prompt)
        except Exception as e:
            print(f"Ошибка при вызове LLM: {e}")
            continue

        # Парсим ответ
        lines = response.splitlines()
        for line in lines:
            if "Абзацы" in line and "–" in line:
                # Ищем "Абзацы 3–5"
                match = re.search(r"Абзацы\D*(\d+)\D*–\D*(\d+)", line)
                if match:
                    start = int(match.group(1))
                    end = int(match.group(2))
                    # Проверяем, что номера в пределах текущего куска (защита от ошибок)
                    if start < chunk_start + 1 or end > chunk_start + len(chunk):
                        continue

                    # Ищем название раздела (5 строк выше) // в коде поменял на 1, почему на 5??? в итоге массив с пропусками (не все параграфы) Василишин
                    title = "Раздел"
                    for i in range(max(0, lines.index(line) - 1), lines.index(line)):
                        if "Название раздела" in lines[i]:
                            title_match = re.search(r":\s*(.+)", lines[i])
                            if title_match:
                                title = title_match.group(1).strip(" .\"'")
                            break

                    # Уникализация по названию
                    if title not in seen_titles:
                        sections.append({
                            'title': title,
                            'start_par': start,
                            'end_par': end
                        })
                        seen_titles.add(title)

    # === Сортируем разделы по стартовому абзацу ===
    sections.sort(key=lambda x: x['start_par'])
    return sections #код ниже "портит" корректный массив. Василишин
    # === Опционально: объединяем пересекающиеся разделы (на всякий случай)
    #merged = []
    #for section in sorted(sections, key=lambda x: x['start_par']):
    #    if not merged:
    #        merged.append(section)
    #    else:
    #        last = merged[-1]
    #        if section['start_par'] <= last['end_par'] + 1:
    #            # Пересекаются или идут подряд — объединяем?
    #            # Или просто пропускаем? Пока пропускаем, чтобы не портить структуру
    #            continue
    #        else:
    #            merged.append(section)
    #
    #return merged


class create_docx:
    def __init__(self, json_file_path, video_path=""):
        self.json_file_path = json_file_path
        self.video_path = video_path

    def get_docx(self):
        json_file_path = self.json_file_path

        if not os.path.isfile(json_file_path):
            raise FileNotFoundError(f"Файл {json_file_path} не найден.")

        doc = Document()
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        full_text = data.get('full_text', '')

        # === Шаг 1: Поиск "сейчас на экране" в segments ===
        table_time_screen = []
        counter = 1
        search_sequence = ["сейчас", "на", "экране"]
        for segment in data['segments']:
            words = segment.get('words', [])
            lower_words = [word['word'].lower() for word in words]
            for i in range(len(lower_words) - 2):
                if lower_words[i:i+3] == search_sequence:
                    start_time = words[i]['start']
                    table_time_screen.append({
                        "Number": counter,
                        "Time": start_time
                    })
                    counter += 1
                    break

        # === Шаг 2: Разбиваем текст на абзацы ===
        class_text_to_paragraphs = text_to_paragraphs(full_text)
        paragraphs = class_text_to_paragraphs.get_text_to_paragraphs_array()

        # === Шаг 3: LLM разбивает на разделы (сохраняем оригинальные абзацы) ===
        print("Отправляем текст в LLM для разбиения на разделы...")
        sections = get_sections_from_llm(paragraphs)  # Список: {title, start_par, end_par}

        # === Шаг 4: Связываем абзацы с временем (по номеру абзаца) ===
        count_time_scr = 0
        paragraphs_time_scr = {}
        for par_count, paragraph in enumerate(paragraphs, start=1):
            lower_text = paragraph.lower()
            count_lower_text = lower_text.count("сейчас на экране")
            if count_lower_text > 0:
                for _ in range(count_lower_text):
                    if count_time_scr < len(table_time_screen):
                        paragraphs_time_scr[par_count] = table_time_screen[count_time_scr]["Time"]
                        count_time_scr += 1
                    else:
                        break

        # === Шаг 5: Формируем документ с разделами и картинками ===
        video_path = self.video_path
        current_paragraph_index = 0  # Считаем, сколько абзацев текста уже вставлено

        if video_path != "" and os.path.isfile(video_path):
            class_picture_description = picture_description()

            # --- Режим A: Есть упоминания "сейчас на экране" ---
            if paragraphs_time_scr:
                print("Вставляем текст с разделами и кадрами по упоминаниям.")
                for section in sections:
                    # Вставляем заголовок раздела
                    doc.add_heading(section['title'], level=1)

                    # Вставляем абзацы этого раздела
                    for par_num in range(section['start_par'], section['end_par'] + 1):
                        if par_num <= len(paragraphs):
                            current_paragraph_index += 1
                            para_text = paragraphs[par_num - 1]
                            doc.add_paragraph('\t' + para_text)

                            # Проверяем, нужно ли вставить картинку ПОСЛЕ этого абзаца
                            if current_paragraph_index in paragraphs_time_scr:
                                time_screen = paragraphs_time_scr[current_paragraph_index]
                                total_seconds = int(time_screen)
                                hours = total_seconds // 3600
                                minutes = (total_seconds % 3600) // 60
                                seconds = total_seconds % 60
                                formatted_time = f"{hours:02}:{minutes:02}:{seconds:02}"
                                frame_at_time = class_picture_description.save_frame_at_time(
                                    video_path, formatted_time
                                )
                                doc.add_picture(frame_at_time, width=Mm(165))

            # --- Режим B: Нет упоминаний — равномерные кадры ---
            else:
                print("Нет упоминаний. Добавляем 5 равномерных кадров.")
                try:
                    total_duration = data['segments'][-1]['end']
                except (IndexError, KeyError, TypeError):
                    raise ValueError("Не удалось определить длительность видео.")

                time_stamps = [total_duration * i / 6 for i in range(1, 6)]
                frame_paths = []
                import uuid
                import shutil

                base_temp_name = "frame.jpg"
                video_dir = os.path.dirname(video_path)
                for i, t in enumerate(time_stamps):
                    total_seconds = int(t)
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    formatted_time = f"{hours:02}:{minutes:02}:{seconds:02}"
                    temp_frame = class_picture_description.save_frame_at_time(video_path, formatted_time)
                    unique_path = f"temp_frame_{i}_{uuid.uuid4().hex[:8]}.jpg"
                    output_path = os.path.join(video_dir, unique_path)
                    shutil.copy(temp_frame, output_path)
                    frame_paths.append(output_path)

                # Определяем, после каких **общих** абзацев вставлять картинки
                total_paragraphs = len(paragraphs)
                image_positions = []
                num_images = len(frame_paths)
                for i in range(1, num_images + 1):
                    pos = int(round((i / (num_images + 1)) * total_paragraphs))
                    pos = max(1, min(pos, total_paragraphs))
                    image_positions.append(pos)

                # Вставляем разделы и картинки
                for section in sections:
                    doc.add_heading(section['title'], level=1)
                    for par_num in range(section['start_par'], section['end_par'] + 1):
                        if par_num <= len(paragraphs):
                            current_paragraph_index += 1
                            para_text = paragraphs[par_num - 1]
                            doc.add_paragraph('\t' + para_text)

                            if current_paragraph_index in image_positions:
                                img_idx = image_positions.index(current_paragraph_index)
                                doc.add_picture(frame_paths[img_idx], width=Mm(165))

        else:
            # Режим C: Только текст
            for section in sections:
                doc.add_heading(section['title'], level=1)
                for par_num in range(section['start_par'], section['end_par'] + 1):
                    if par_num <= len(paragraphs):
                        para_text = paragraphs[par_num - 1]
                        doc.add_paragraph('\t' + para_text)

        # === Шаг 6: Сохранение ===
        docx_file_path = os.path.splitext(json_file_path)[0] + '.docx'
        doc.save(docx_file_path)
        print(f"Документ с разделами сохранён: {docx_file_path}")
        return docx_file_path