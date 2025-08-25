from playwright.sync_api import sync_playwright
import requests
import os
import re
from urllib.parse import urlparse, unquote
from typing import Optional, Dict, Any
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_DIR = "videoinput"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def sanitize_filename(name: str) -> str:
    """Очистка имени файла от запрещенных символов"""
    return re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name)


def download_file(url: str, path: str, chunk_size: int = 8192) -> None:
    """Загрузка файла с прогресс-баром"""
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    downloaded = 0
    
    with open(path, "wb") as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    print(f"\r📥 Загрузка: {percent:.1f}% ({downloaded}/{total_size} bytes)", end='')
    
    print("\n✅ Загрузка завершена")


class SynologyDownloader:
    def __init__(self, video_page_url: str):
        self.video_page_url = video_page_url
        self.timeout = 30000
        self.browser_args = [
            "--ignore-certificate-errors",
            "--allow-insecure-localhost",
            "--disable-web-security"
        ]

    def _get_filename_from_page(self, page) -> str:
        """Получение имени файла из мета-тегов и заголовков"""
        filename = "downloaded_video"
        
        # Пробуем получить из og:title
        try:
            og_title = page.evaluate("""() => {
                const meta = document.querySelector('meta[property="og:title"]');
                return meta ? meta.getAttribute('content') : null;
            }""")
            if og_title and og_title.strip():
                filename = og_title.strip()
                logger.info(f"📌 Использую имя из og:title: {filename}")
                return filename
        except Exception as e:
            logger.warning(f"Не удалось получить og:title: {e}")

        # Пробуем получить из title страницы
        try:
            title = page.title()
            if title and title.strip():
                filename = title.strip()
                logger.info(f"📌 Использую имя из title: {filename}")
        except Exception as e:
            logger.warning(f"Не удалось получить title: {e}")

        return sanitize_filename(filename)

    def _find_player_frame(self, page):
        """Поиск iframe с Universal Viewer"""
        for frame in page.frames:
            try:
                if "uv.html" in frame.url:
                    logger.info(f"✅ Найден iframe плеера: {frame.url}")
                    return frame
            except Exception as e:
                logger.warning(f"Ошибка при проверке frame: {e}")
                continue
        return None

    def _find_download_button(self, frame):
        """Поиск кнопки Download в iframe"""
        selectors = [
            'text=Download',
            '#ext-gen70',
            '#ext-comp-1047',
            'button:has-text("Download")',
            'a:has-text("Download")',
            '.x-btn-button:has-text("Download")'
        ]

        for sel in selectors:
            try:
                btn = frame.locator(sel).first
                if btn and btn.is_visible():
                    logger.info(f"✅ Нашли кнопку по селектору: {sel}")
                    return btn
            except Exception as e:
                logger.debug(f"Селектор {sel} не сработал: {e}")
                continue
        
        return None

    def download(self) -> str:
        """Основной метод загрузки"""
        video_url_holder = {"url": None}
        filename_holder = {"name": "downloaded_video"}

        with sync_playwright() as p:
            try:
                # Запускаем браузер с настройками
                browser = p.chromium.launch(
                    headless=True,
                    args=self.browser_args
                )
                
                context = browser.new_context(
                    ignore_https_errors=True,
                    accept_downloads=True,
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = context.new_page()

                logger.info("🌐 Открываю страницу...")
                page.goto(self.video_page_url, timeout=self.timeout, wait_until='domcontentloaded')
                
                # Ждем загрузки
                page.wait_for_timeout(5000)

                # Получаем имя файла
                filename = self._get_filename_from_page(page)
                filename_holder["name"] = filename

                # Ищем iframe с плеером
                player_frame = self._find_player_frame(page)
                if not player_frame:
                    logger.error("❌ Не удалось найти iframe с плеером")
                    browser.close()
                    return ""

                # Ищем кнопку Download
                download_button = self._find_download_button(player_frame)
                if not download_button:
                    logger.error("❌ Кнопка 'Download' не найдена")
                    browser.close()
                    return ""

                # Пытаемся скачать через кнопку
                logger.info("📥 Кликаем по кнопке 'Download'...")
                try:
                    with page.expect_download(timeout=15000) as download_info:
                        download_button.click()
                    
                    download = download_info.value
                    suggested_name = download.suggested_filename
                    logger.info(f"📎 Сервер предлагает имя: {suggested_name}")
                    
                    # Используем предложенное имя или наше
                    final_filename = suggested_name if suggested_name else f"{filename}.mov"
                    final_filename = sanitize_filename(final_filename)
                    
                    output_path = os.path.join(OUTPUT_DIR, final_filename)
                    download.save_as(output_path)
                    
                    logger.info(f"🎉 Успешно скачано: {output_path}")
                    return os.path.abspath(output_path)

                except Exception as e:
                    logger.error(f"❌ Ошибка при скачивании: {e}")
                    # Пробуем альтернативный метод
                    return self._fallback_download_method(page, filename)

            except Exception as e:
                logger.error(f"❌ Критическая ошибка: {e}")
                return ""

    def _fallback_download_method(self, page, filename: str) -> str:
        """Альтернативный метод загрузки через перехват медиа-ответов"""
        logger.info("🔄 Использую альтернативный метод загрузки...")
        
        video_url_holder = {"url": None}
        
        def handle_response(response):
            if response.request.resource_type == "media":
                video_url = response.url
                if video_url and not video_url_holder["url"]:
                    video_url_holder["url"] = video_url
                    logger.info(f"🎬 Найдено видео: {video_url}")

        page.on("response", handle_response)
        
        # Обновляем страницу для перехвата
        page.reload(timeout=self.timeout)
        page.wait_for_timeout(10000)

        video_url = video_url_holder["url"]
        if video_url:
            # Определяем расширение
            resp_head = requests.head(video_url, allow_redirects=True, verify=False)
            content_type = resp_head.headers.get("Content-Type", "").lower()
            ext_map = {
                "video/mp4": ".mp4",
                "video/quicktime": ".mov",
                "video/webm": ".webm",
                "video/x-matroska": ".mkv"
            }
            ext = ext_map.get(content_type, ".mov")
            
            if not filename.endswith(ext):
                filename += ext
            
            output_path = os.path.join(OUTPUT_DIR, filename)
            download_file(video_url, output_path)
            logger.info(f"✅ Сохранено: {output_path}")
            return os.path.abspath(output_path)
        else:
            logger.error("❌ Не удалось найти ссылку на видео")
            return ""

    def set_timeout(self, timeout_ms: int) -> None:
        """Установка таймаута"""
        self.timeout = timeout_ms

    def add_browser_arg(self, arg: str) -> None:
        """Добавление аргументов браузера"""
        self.browser_args.append(arg)


# Пример использования
if __name__ == "__main__":
    downloader = SynologyDownloader(
        "https://pro-1c-virtualnas.direct.quickconnect.to:5001/d/s/14Fcxa6WJMw96JQUCRB7lPLEuIoRptvU/zFh_5S--OFIGZs-B0NaiNL_icd4HlUOm-s7SAj3ZJcgw"
    )
    
    # Дополнительные настройки (опционально)
    downloader.set_timeout(40000)
    downloader.add_browser_arg("--disable-gpu")
    
    result = downloader.download()
    if result:
        print(f"Файл сохранен: {result}")
    else:
        print("Не удалось скачать файл")