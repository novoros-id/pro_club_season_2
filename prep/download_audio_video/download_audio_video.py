import os
import requests

class DownloadAudioVideo:
    def __init__(self, video_input_dir="videoinput"):
        """
        Инициализация класса для скачивания видео.
        :param video_input_dir: Директория для сохранения скачанных видео.
        """
        self.video_input_dir = video_input_dir
        os.makedirs(self.video_input_dir, exist_ok=True)

    def download_video_directly(self, video_url, output_filename=None):
        """
        Скачивает видео напрямую по URL и сохраняет его в видеофайловую директорию.
        :param video_url: URL видео для скачивания.
        :param output_filename: Название файла для сохранения. Если None, используется название из URL.
        """
        try:
            # Отправляем GET-запрос для скачивания видео
            response = requests.get(video_url, stream=True)
            
            # Формируем имя файла для сохранения
            if output_filename is None:
                output_filename = os.path.basename(video_url.split("?")[0])
            
            output_path = os.path.join(self.video_input_dir, output_filename)
            
            # Скачиваем файл частями и сохраняем
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
                        
            print(f"Видео успешно скачано в '{output_path}'")
        except Exception as e:
            print(f"Ошибка при скачивании видео: {e}")

