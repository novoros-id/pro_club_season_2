from create_file.create_docx import create_docx
file = 'Просковья инструкция_PV_PA.json'
video_path = 'Просковья инструкция_PV_PV.mp4'
class_create_docx = create_docx(file, video_path)
paragraph = class_create_docx.get_docx()