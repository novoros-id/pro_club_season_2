import requests
import os
import sys

class YandexDownloader:
    def __init__(self, public_url: str, output_dir: str = "videoinput"):
        self.public_url = public_url
        self.output_dir = output_dir

    def _get_filename_from_api(self) -> str:
        api_info_url = f"https://cloud-api.yandex.net/v1/disk/public/resources?public_key={self.public_url}"
        response = requests.get(api_info_url)
        if response.status_code == 200:
            data = response.json()
            filename = data.get("name", "yadisk_downloaded_file")
            if not filename.lower().endswith(".mp4"):
                filename += ".mp4"
            return filename
        else:
            print(f"❌ Не удалось получить имя файла из API: {response.status_code}")
            return "yadisk_downloaded_file.mp4"

    def _download_file(self, file_url, path):
        response = requests.get(file_url, stream=True, allow_redirects=True)
        response.raise_for_status()
        with open(path, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

    def download(self) -> str:
        print("🌐 Получаем прямую ссылку на файл с Яндекс.Диска...")
        api_url = f"https://cloud-api.yandex.net/v1/disk/public/resources/download?public_key={self.public_url}"
        response = requests.get(api_url)
        if response.status_code == 200:
            download_url = response.json()["href"]
            filename = self._get_filename_from_api()
            output_path = os.path.join(self.output_dir, filename)
            print(f"⬇️ Скачивание файла: {filename}...")
            self._download_file(download_url, output_path)
            print(f"✅ Сохранено: {output_path}")
            return output_path
        else:
            print(f"❌ Не удалось получить ссылку от Яндекса: {response.status_code}")
            return ""

# CLI запуск
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Укажите публичную ссылку на Яндекс.Диск")
        sys.exit(1)

    url = sys.argv[1]
    downloader = YandexDownloader(url)
    downloader.download()
