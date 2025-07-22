import sys
from download_audio_video import SynologyDownloader, YandexDownloader

def detect_downloader(url: str):
    # Простейшая логика определения по домену или шаблону ссылки
    if "yandex.ru" in url or "yadi.sk" in url or "disk.yandex.net" in url:
        return YandexDownloader(url)
    elif "quickconnect.to" in url or "synology" in url:
        return SynologyDownloader(url)
    else:
        return None

def main():
    if len(sys.argv) < 2:
        print("Использование: python main.py <ссылка>")
        sys.exit(1)

    url = sys.argv[1]

    downloader = detect_downloader(url)
    if not downloader:
        print("❌ Неизвестный тип ссылки, поддерживаются только Яндекс.Диск и Synology.")
        sys.exit(1)

    saved_path = downloader.download()
    if saved_path:
        print(f"\n🎉 Файл сохранён: {saved_path}")
    else:
        print("\n❌ Ошибка при скачивании файла.")

if __name__ == "__main__":
    main()
