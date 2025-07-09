#pip install python-docx
#from prep.text_to_paragraphs.text_to_paragraphs import text_to_paragraphs
from docx import Document
import os
import sys
import json

# Добавляем родительский каталог в пути поиска модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Теперь импортируем модуль из соседнего каталога
from text_to_paragraphs.text_to_paragraphs import text_to_paragraphs

class create_docx:
    def __init__(self, json_file_path):
        self.json_file_path = json_file_path
    
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

       class_text_to_paragraphs = text_to_paragraphs(full_text)
       paragraphs = class_text_to_paragraphs.get_text_to_paragraphs()
            
       # Добавляем текст в документ
       doc.add_paragraph(paragraphs)

       # Формируем имя выходного файла
       docx_file_path = os.path.splitext(json_file_path)[0] + '.docx'
            
       # Сохраняем документ в формате .docx
       doc.save(docx_file_path)

       return docx_file_path