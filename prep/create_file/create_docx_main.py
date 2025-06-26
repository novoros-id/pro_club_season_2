from create_docx import create_docx
file = 'prep/create_file/test.json'
class_create_docx = create_docx(file)
paragraph = class_create_docx.get_docx()
print(paragraph)