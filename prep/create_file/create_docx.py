# pip install python-docx opencv-python

from docx import Document
from docx.shared import Mm
import os
import sys
import json

# Добавляем родительский каталог в пути поиска модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Импорты из соседних модулей
from text_to_paragraphs.text_to_paragraphs import text_to_paragraphs
from picture_description.picture_description import picture_description
from text_modifier.text_modifier import TextModify


class create_docx:
    def __init__(self, json_file_path, video_path=""):
        self.json_file_path = json_file_path
        self.video_path = video_path

    def get_docx(self):
        json_file_path = self.json_file_path

        # Проверяем существование JSON файла
        if not os.path.isfile(json_file_path):
            raise FileNotFoundError(f"Файл {json_file_path} не найден.")

        # Создаем новый документ
        doc = Document()

        # Читаем JSON
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        full_text = data.get('full_text', '')

        #text_modifier = TextModify()
        #full_text = text_modifier.improve_text(full_text)

        # === Шаг 1: Поиск "сейчас на экране" в segments ===
        table_time_screen = []

        # Счетчик для нумерации найденных вхождений
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

        text_modifier = TextModify()

        for i in range(len(paragraphs)):
            paragraphs[i] = text_modifier.improve_text(paragraphs[i])

        count_time_scr = 0
        paragraphs_time_scr = {}
        # Обход массива paragraphs
        for par_count, paragraph in enumerate(paragraphs, start=1):
            lower_text = paragraph.lower()  # Приводим текст к нижнему регистру
            count_lower_text = lower_text.count("сейчас на экране")  # Считаем вхождения

            if count_lower_text > 0:
                for _ in range(count_lower_text):
                    # print(count_time_scr)
                    # Добавляем проверку на выход за пределы списка
                    if count_time_scr < len(table_time_screen):
                        paragraphs_time_scr[par_count] = table_time_screen[count_time_scr]["Time"]
                        count_time_scr += 1
                    else:
                        # Если превысили длину списка, можно либо прервать цикл,
                        # либо пропустить это значение
                        break

        # === Шаг 4: Формируем документ ===
        video_path = self.video_path

        if video_path != "" and os.path.isfile(video_path):
            class_picture_description = picture_description()

            # --- Режим A: Есть упоминания "сейчас на экране" ---
            if paragraphs_time_scr:
                print("Найдены упоминания 'сейчас на экране'. Вставляем кадры по контексту.")
                for par_count, paragraph in enumerate(paragraphs, start=1):
                    doc.add_paragraph('\t' + paragraph)
                    time_screen = paragraphs_time_scr.get(par_count)
                    if time_screen is not None:
                        total_seconds = int(time_screen)
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        seconds = total_seconds % 60
                        formatted_time = f"{hours:02}:{minutes:02}:{seconds:02}"
                        frame_at_time = class_picture_description.save_frame_at_time(
                            video_path, formatted_time
                        )
                        doc.add_picture(frame_at_time, width=Mm(165))

            # --- Режим B: Нет упоминаний — вставляем 5 равномерных кадров ---
            else:
                print("Упоминания 'сейчас на экране' не найдены. Добавляем 5 равномерных кадров.")

                # Получаем длительность видео из JSON
                try:
                    total_duration = data['segments'][-1]['end']
                except (IndexError, KeyError, TypeError):
                    raise ValueError("Не удалось определить длительность видео: отсутствует 'segments' или 'end'.")

                # Генерируем временные метки: 1/6, 2/6, ..., 5/6
                time_stamps = [total_duration * i / 6 for i in range(1, 6)]

                # Сохраняем кадры с принудительным копированием
                frame_paths = []
                import uuid
                import shutil

                base_temp_name = "frame.jpg"  # ← имя, которое возвращает save_frame_at_time
                video_dir = os.path.dirname(video_path)
                for i, t in enumerate(time_stamps):
                    total_seconds = int(t)
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    formatted_time = f"{hours:02}:{minutes:02}:{seconds:02}"

                    # Вызываем метод — он перезапишет frame.jpg
                    temp_frame = class_picture_description.save_frame_at_time(video_path, formatted_time)

                    # Создаём уникальное имя
                    unique_path = f"temp_frame_{i}_{uuid.uuid4().hex[:8]}.jpg"
                    output_path = os.path.join(video_dir, unique_path)
                    shutil.copy(temp_frame, output_path)
                    frame_paths.append(output_path)
                    
                # Определяем, после каких абзацев вставлять картинки
                num_paragraphs = len(paragraphs)
                image_positions = []
                num_images = len(frame_paths)

                if num_paragraphs > 0:
                    for i in range(1, num_images + 1):
                        pos = int(round((i / (num_images + 1)) * num_paragraphs))
                        pos = max(1, min(pos, num_paragraphs))  # в пределах [1, num_paragraphs]
                        image_positions.append(pos)

                # Добавляем абзацы и вставляем кадры
                for par_count, paragraph in enumerate(paragraphs, start=1):
                    doc.add_paragraph('\t' + paragraph)
                    if par_count in image_positions:
                        img_idx = image_positions.index(par_count)
                        doc.add_picture(frame_paths[img_idx], width=Mm(165))

        else:
            # Нет видео — просто добавляем текст
            for paragraph in paragraphs:
                doc.add_paragraph('\t' + paragraph)

        # === Шаг 5: Сохраняем документ ===
        docx_file_path = os.path.splitext(json_file_path)[0] + '.docx'
        doc.save(docx_file_path)
        print(f"Документ сохранён: {docx_file_path}")

        return docx_file_path