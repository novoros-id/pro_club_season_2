from playwright.sync_api import sync_playwright
import requests
import os

OUTPUT_DIR = "videoinput"


def download_file(url, path):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(path, "wb") as f:
        for chunk in response.iter_content(8192):
            f.write(chunk)


class SynologyDownloader:
    def __init__(self, video_page_url: str):
        self.video_page_url = video_page_url

    def download(self) -> str:
        video_url_holder = {"url": None}
        filename_holder = {"name": "downloaded_video.mp4"}

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            def handle_response(response):
                if response.request.resource_type == "media":
                    print("🎯 Найдена медиа-ссылка:", response.url)
                    video_url_holder["url"] = response.url

            page.on("response", handle_response)

            print("🌐 Открываю страницу...")
            page.goto(self.video_page_url)
            page.wait_for_timeout(3000)  # Ждём, чтобы meta успел загрузиться

            print("🔍 Получаю имя файла из meta-тега...")
            meta_tag = page.locator('meta[property="og:title"]').first
            if meta_tag:
                content = meta_tag.get_attribute("content")
                if content:
                    print("📁 Имя файла:", content)
                    filename_holder["name"] = content.strip()

            page.wait_for_timeout(5000)  # Ждём, пока поймается video-ссылка
            browser.close()

        video_url = video_url_holder["url"]
        filename = filename_holder["name"]
        output_path = os.path.join(OUTPUT_DIR, filename)

        if video_url:
            print("⬇️ Скачиваю видео...")
            download_file(video_url, output_path)
            print(f"✅ Сохранено: {output_path}")
            return os.path.abspath(output_path)
        else:
            print("❌ Медиа-ссылка не найдена.")
            return ""


class YandexDownloader:
    def __init__(self, public_url: str):
        self.public_url = public_url

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
            output_path = os.path.join(OUTPUT_DIR, filename)
            print(f"⬇️ Скачивание файла: {filename}...")
            self._download_file(download_url, output_path)
            print(f"✅ Сохранено: {output_path}")
            return os.path.abspath(output_path)
        else:
            print(f"❌ Не удалось получить ссылку от Яндекса: {response.status_code}")
            return ""
