import sys
from download_audio_video import SynologyDownloader, YandexDownloader

def main():
    if len(sys.argv) < 2:
        print("❌ Укажи ссылку для скачивания.")
        return

    url = sys.argv[1]

    if "yandex" in url or "disk.yandex" in url:
        print("🖥 Определён источник: Яндекс.Диск")
        downloader = YandexDownloader(url)
    else:
        print("🖥 Определён источник: QuickConnect / Synology")
        downloader = SynologyDownloader(url)

    try:
        saved_path = downloader.download()
        if saved_path:
            print(f"🎉 Файл скачан: {saved_path}")
        else:
            print("❌ Скачивание не удалось.")
    except Exception as e:
        print(f"❌ Ошибка при скачивании файла: {e}")

if __name__ == "__main__":
    main()
