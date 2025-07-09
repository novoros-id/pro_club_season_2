#pip install python-docx
from docx import Document
import os

def txt_to_docx(txt_file_path):
    # Проверяем, существует ли текстовый файл
    if not os.path.isfile(txt_file_path):
        raise FileNotFoundError(f"Файл {txt_file_path} не найден.")

    # Создаем новый документ
    doc = Document()

    # Открываем текстовый файл и читаем его содержимое
    with open(txt_file_path, 'r', encoding='utf-8') as file:
        for line in file:
            doc.add_paragraph(line)

    # Формируем имя выходного файла
    docx_file_path = os.path.splitext(txt_file_path)[0] + '.docx'
    
    # Сохраняем документ в формате .docx
    doc.save(docx_file_path)

    return docx_file_path

# Пример использования:
# путь к вашему текстовому файлу
result_path = txt_to_docx('README.md')
# print(f'Docx файл создан: {result_path}')
