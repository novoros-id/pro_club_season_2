#pip install python-docx
#from prep.text_to_paragraphs.text_to_paragraphs import text_to_paragraphs
from docx import Document
from docx.shared import Mm
import os
import sys
import json

# Добавляем родительский каталог в пути поиска модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Теперь импортируем модуль из соседнего каталога
from text_to_paragraphs.text_to_paragraphs import text_to_paragraphs
from picture_description.picture_description import picture_description

class create_docx:
    def __init__(self, json_file_path, video_path = ""):
        self.json_file_path = json_file_path
        self.video_path = video_path
        
    def get_docx(self):

       json_file_path = self.json_file_path

       # Проверяем, существует ли JSON файл
       if not os.path.isfile(json_file_path):
            raise FileNotFoundError(f"Файл {json_file_path} не найден.")

       # Создаем новый документ
       doc = Document()

       # Открываем JSON файл и читаем его содержимое
       with open(json_file_path, 'r', encoding='utf-8') as file:
           data = json.load(file)

       # Извлекаем текст из поля full_text
       full_text = data.get('full_text', '')
       
       # Словарь для хранения результатов
       #time_screen = {}
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

       class_text_to_paragraphs = text_to_paragraphs(full_text)
       paragraphs = class_text_to_paragraphs.get_text_to_paragraphs_array()

       count_time_scr = 0
       paragraphs_time_scr = {}
       # Обход массива paragraphs
       for par_count, paragraph in enumerate(paragraphs, start=1):
        lower_text = paragraph.lower()  # Приводим текст к нижнему регистру
        count_lower_text = lower_text.count("сейчас на экране")  # Считаем вхождения

        if count_lower_text > 0:
            for _ in range(count_lower_text):
                count_time_scr += 1  # Увеличиваем счетчик времени
                paragraphs_time_scr[par_count] = table_time_screen[count_time_scr-1]["Time"]

       #print(paragraphs_time_scr)           
       video_path = self.video_path
       if video_path != "":
           class_picture_description = picture_description()
       for par_count, paragraph in enumerate(paragraphs, start=1):
            doc.add_paragraph('\t' + paragraph)
            time_screen = paragraphs_time_scr.get(par_count, None)
            if time_screen != None:
               if video_path != "":
                    total_seconds = int(time_screen)
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    formatted_time = f"{hours:02}:{minutes:02}:{seconds:02}"
                    frame_at_time = class_picture_description.save_frame_at_time(video_path, formatted_time)
                    doc.add_picture(frame_at_time, width=Mm(165))

       # Формируем имя выходного файла
       docx_file_path = os.path.splitext(json_file_path)[0] + '.docx'
            
       # Сохраняем документ в формате .docx
       doc.save(docx_file_path)

       return docx_file_path