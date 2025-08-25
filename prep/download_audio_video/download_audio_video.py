from playwright.sync_api import sync_playwright
import requests
import os

OUTPUT_DIR = "videoinput"
os.makedirs(OUTPUT_DIR, exist_ok=True)


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
        filename_holder = {"name": "downloaded_video"}  # пока без расширения

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # Первая попытка — ловим media response на главной странице
            def handle_response(response):
                if response.request.resource_type == "media":
                    video_url_holder["url"] = response.url

            page.on("response", handle_response)
            page.goto(self.video_page_url)
            page.wait_for_timeout(3000)

            # Пытаемся взять имя файла из meta
            meta_tag = page.locator('meta[property="og:title"]').first
            if meta_tag:
                content = meta_tag.get_attribute("content")
                if content:
                    filename_holder["name"] = content.strip()

            page.wait_for_timeout(5000)

            # Если видео не найдено на основной странице — используем кнопку Download
            if not video_url_holder["url"]:
                frame = None
                for f in page.frames:
                    try:
                        if "uv.html" in f.url:
                            frame = f
                            break
                    except:
                        continue

                if frame:
                    selectors = ['text=Download', '#ext-gen70', '#ext-comp-1047', 'button:has-text("Download")']
                    button = None
                    for sel in selectors:
                        try:
                            btn = frame.locator(sel).first
                            if btn and btn.is_visible():
                                button = btn
                                break
                        except:
                            continue

                    if button:
                        with page.expect_download() as download_info:
                            button.click()
                        download = download_info.value
                        ext = os.path.splitext(download.suggested_filename)[1] or ".mp4"
                        filename = filename_holder["name"]
                        if not filename.lower().endswith(ext):
                            filename += ext
                        output_path = os.path.join(OUTPUT_DIR, filename)
                        download.save_as(output_path)
                        browser.close()
                        return os.path.abspath(output_path)

                # Если кнопка не найдена — закрываем браузер
                browser.close()
                return ""

            # Если meta-ссылка найдена — скачиваем через requests
            video_url = video_url_holder["url"]
            filename = filename_holder["name"]

            resp_head = requests.head(video_url, allow_redirects=True)
            content_type = resp_head.headers.get("Content-Type", "").lower()
            ext_map = {
                "video/mp4": ".mp4",
                "video/quicktime": ".mov",
                "video/webm": ".webm",
                "video/x-matroska": ".mkv"
            }
            ext = ext_map.get(content_type, "")
            if not filename.lower().endswith(ext):
                filename += ext

            output_path = os.path.join(OUTPUT_DIR, filename)
            download_file(video_url, output_path)
            browser.close()
            return os.path.abspath(output_path)


class YandexDownloader:
    def __init__(self, public_url: str):
        self.public_url = public_url

    def _get_filename_from_api(self) -> str:
        api_info_url = f"https://cloud-api.yandex.net/v1/disk/public/resources?public_key={self.public_url}"
        response = requests.get(api_info_url)
        if response.status_code == 200:
            data = response.json()
            filename = data.get("name", "yadisk_downloaded_file")
            return filename  # НЕ добавляем .mp4
        else:
            print(f"❌ Не удалось получить имя файла из API: {response.status_code}")
            return "yadisk_downloaded_file"

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
