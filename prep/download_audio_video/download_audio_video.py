import os
import requests
import subprocess
import shutil

class DownloadAudioVideo:
    def __init__(self, video_input_dir="videoinput"):
        self.video_input_dir = video_input_dir
        os.makedirs(self.video_input_dir, exist_ok=True)

    def download_video_directly(self, video_url, output_filename=None):
        """
        Пытается скачать видео через requests.
        """
        print("Попытка скачать через requests...")
        try:
            response = requests.get(video_url, stream=True, timeout=10)
            response.raise_for_status()

            if output_filename is None:
                output_filename = os.path.basename(video_url.split("?")[0])

            output_path = os.path.join(self.video_input_dir, output_filename)

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 10):
                    if chunk:
                        f.write(chunk)

            print(f"Видео успешно скачано через requests в '{output_path}'")
            return True

        except Exception as e:
            print(f"Ошибка при скачивании через requests: {e}")
            return False

    def download_with_curl(self, video_url, output_filename=None):
        """
        Скачивает файл через curl, если он установлен в системе.
        """
        print("Попытка скачать через curl...")
        if not shutil.which("curl"):
            print("curl не установлен или недоступен в PATH.")
            return False

        if output_filename is None:
            output_filename = os.path.basename(video_url.split("?")[0])

        output_path = os.path.join(self.video_input_dir, output_filename)

        try:
            subprocess.run(
                ["curl", "-L", video_url, "-o", output_path],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"Файл успешно скачан через curl в '{output_path}'")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при скачивании через curl: {e}")
            return False

    def download_with_wget(self, video_url, output_filename=None):
        """
        Скачивает файл через wget, если он установлен в системе.
        """
        print("Попытка скачать через wget...")
        if not shutil.which("wget"):
            print("wget не установлен или недоступен в PATH.")
            return False

        if output_filename is None:
            output_filename = os.path.basename(video_url.split("?")[0])

        output_path = os.path.join(self.video_input_dir, output_filename)

        try:
            subprocess.run(
                ["wget", "-O", output_path, video_url],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"Файл успешно скачан через wget в '{output_path}'")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Ошибка при скачивании через wget: {e}")
            return False

    def smart_download(self, video_url, output_filename=None):
        """
        Пытается скачать файл разными способами по порядку.
        """
        print(f"Начинаем умную загрузку по ссылке: {video_url}")

        result = self.download_video_directly(video_url, output_filename)
        if result:
            return

        result = self.download_with_curl(video_url, output_filename)
        if result:
            return

        result = self.download_with_wget(video_url, output_filename)
        if result:
            return

        print("Не удалось скачать файл ни одним из доступных способов.")