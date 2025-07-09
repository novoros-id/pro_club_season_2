import torch
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

import cv2
import requests

class picture_description:
    def __init__(self):
        а = 1
        #self.video_path = self.file_path
        #self.time_str = self.time_str
    
    def get_picture_description(self, file_path):

        # Загрузка модели и процессора
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")

        # Загрузка изображения
        image = Image.open(file_path)

        # Подготовка входных данных
        inputs = processor(images=image, return_tensors="pt")

        # Генерация описания с измененными параметрами
        with torch.no_grad():
            out = model.generate(**inputs, max_length=500, num_beams=10, temperature=0.7)

        # Декодирование и вывод результата
        description = processor.decode(out[0], skip_special_tokens=True)

        # Вывод результата
        return description
    
    def save_frame_at_time(self, video_path, time_str):

        hours, minutes, seconds = map(int, time_str.split(':'))
        total_seconds = hours * 3600 + minutes * 60 + seconds

        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            print("Не удалось открыть видеофайл")
            return None

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = frame_count / fps

        #print(f"Общее количество кадров: {frame_count}")
        #print(f"Длительность видео (в секундах): {duration}")

        if total_seconds > duration:
            print("Указанное время превышает длительность видео.")
            return None

        cap.set(cv2.CAP_PROP_POS_MSEC, total_seconds * 1000)

        ret, frame = cap.read()

        if ret:
            output_image_path = 'screenshot.png'
            cv2.imwrite(output_image_path, frame)
            #print(f"Кадр сохранен как {output_image_path}")
            cap.release()
            return output_image_path
        else:
            print("Не удалось извлечь кадр")
            print(f"Текущая позиция в миллисекундах: {cap.get(cv2.CAP_PROP_POS_MSEC)}")
            cap.release()
            return None
        
    def description_frame_at_time(self, video_path, time_str):

        picture_path = self.save_frame_at_time(video_path, time_str)
        description_picture = self.get_picture_description(picture_path)

        return description_picture