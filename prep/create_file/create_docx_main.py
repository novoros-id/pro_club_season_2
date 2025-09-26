from create_docx import create_docx
file = 'prep/create_file/test.json'
video_path = 'prep/create_file/instr.mp4'
UseTextModify = False
class_create_docx = create_docx(file, video_path, UseTextModify)
paragraph = class_create_docx.get_docx()