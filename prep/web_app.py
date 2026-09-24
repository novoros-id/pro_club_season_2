import os
import uuid
import logging
import re
from pathlib import Path
try:
    from flask import Flask, render_template_string, request, send_file
except ImportError:  # Keep the entry point importable for config/health checks.
    class Flask:
        def __init__(self, *_args, **_kwargs):
            pass

        def route(self, *_args, **_kwargs):
            return lambda function: function

        def run(self, *_args, **_kwargs):
            raise RuntimeError("Для запуска web UI установите зависимости из prep/requirements.txt.")

    request = None

    def render_template_string(*_args, **_kwargs):
        raise RuntimeError("Flask не установлен.")

    def send_file(*_args, **_kwargs):
        raise RuntimeError("Flask не установлен.")

from dotenv import load_dotenv
from main import get_video_source_mode, process_local_video, process_video

load_dotenv()

# --- Конфигурация ---
USER_FOLDER = os.getenv("USER_FOLDER")
if not USER_FOLDER:
    USER_FOLDER = "./user_data"
os.makedirs(USER_FOLDER, exist_ok=True)

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

app = Flask(__name__)

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("werkzeug").setLevel(logging.INFO)

# --- HTML Шаблон (Упрощенный: только обработка видео) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>1C PRO Assistant - Видео</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            background-color: #f4f4f9; 
            color: #333; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px; 
        }
        h1 { text-align: center; color: #d32f2f; }
        
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            margin-top: 20px;
        }

        .info-text {
            color: #555;
            font-size: 1.1em;
            margin-bottom: 25px;
            line-height: 1.5;
            background: #e3f2fd;
            padding: 15px;
            border-radius: 6px;
            border-left: 5px solid #2196f3;
        }

        input[type="url"], select {
            width: 100%; 
            padding: 15px; 
            margin-bottom: 20px; 
            border: 1px solid #ccc; 
            border-radius: 4px; 
            box-sizing: border-box; 
            font-size: 16px; 
        }
        
        button.action-btn { 
            background-color: #d32f2f; 
            color: white; 
            padding: 15px 20px; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer; 
            width: 100%; 
            font-size: 18px; 
            font-weight: bold; 
            transition: background 0.2s;
        }
        button.action-btn:hover { background-color: #b71c1c; }
        
        .result-box { 
            margin-top: 25px; 
            padding: 20px; 
            border-radius: 4px; 
            word-wrap: break-word; 
        }
        
        .error { 
            color: #c62828; 
            border: 1px solid #ef9a9a; 
            background: #ffebee; 
        }
        
        .success { 
            color: #2e7d32; 
            border: 1px solid #a5d6a7; 
            background: #e8f5e9; 
            text-align: center;
        }

        .download-link {
            display: inline-block;
            margin-top: 15px;
            background-color: #2e7d32;
            color: white;
            padding: 12px 24px;
            text-decoration: none;
            border-radius: 4px;
            font-weight: bold;
        }
        .download-link:hover { background-color: #1b5e20; }

    </style>
</head>
<body>

    <h1>1C PRO Assistant</h1>

    <div class="container">
        <h3>Обработка видео</h3>

        {% if source_mode == "local" %}
        <div class="info-text">
            Выберите видео из настроенного локального каталога. Исходный файл останется без изменений.
        </div>
        {% if local_videos %}
        <form action="/api/local-video" method="POST">
            <select name="local_video" required>
                <option value="" selected disabled>Выберите видео</option>
                {% for video in local_videos %}
                <option value="{{ video }}">{{ video }}</option>
                {% endfor %}
            </select>
            <button type="submit" class="action-btn">Обработать локальное видео</button>
        </form>
        {% elif not video_error %}
        <div class="result-box error">❌ В LOCAL_VIDEO_DIR нет поддерживаемых видеофайлов.</div>
        {% endif %}
        {% elif source_mode == "url" %}
        <div class="info-text">
            Вставьте ссылку на Synology Drive или Яндекс Диск. Не забудьте расшарить файл.
        </div>
        <form action="/api/video" method="POST">
            <input type="url" name="video_url" placeholder="https://..." required>
            <button type="submit" class="action-btn">Обработать по ссылке</button>
        </form>
        {% endif %}

        {% if video_error %}
        <div class="result-box error">
            ❌ <strong>Ошибка:</strong> {{ video_error }}
        </div>
        {% endif %}
        
        {% if video_success %}
        <div class="result-box success">
            ✅ <strong>Файл готов!</strong><br>
            Транскрибация успешно сохранена.
            <br>
            <a href="/download/{{ video_filename }}" class="download-link">Скачать файл (.docx)</a>
        </div>
        {% endif %}
    </div>

</body>
</html>
"""

# --- Глобальная переменная для хранения пути к последнему файлу ---
# Примечание: В продакшене с несколькими пользователями лучше использовать сессии или базу данных.
LAST_GENERATED_FILE = None

# --- Маршруты ---


def get_local_video_dir(value=None):
    """Resolve and validate LOCAL_VIDEO_DIR."""
    configured = os.getenv("LOCAL_VIDEO_DIR", "") if value is None else value
    configured = os.fspath(configured).strip() if configured else ""
    if not configured:
        raise ValueError("Для режима local укажите LOCAL_VIDEO_DIR.")
    directory = Path(configured).expanduser()
    try:
        directory = directory.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise ValueError("Каталог LOCAL_VIDEO_DIR не найден или недоступен.") from exc
    if not directory.is_dir():
        raise ValueError("LOCAL_VIDEO_DIR должен указывать на каталог.")
    return directory


def list_local_videos(directory):
    """List supported files below the configured directory as relative paths."""
    try:
        root = Path(directory).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("LOCAL_VIDEO_DIR должен указывать на каталог.")
        videos = []
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
                continue
            resolved_path = path.resolve(strict=True)
            try:
                resolved_path.relative_to(root)
            except ValueError:
                continue
            videos.append(path.relative_to(root).as_posix())
    except (FileNotFoundError, OSError) as exc:
        raise ValueError("Не удалось прочитать LOCAL_VIDEO_DIR.") from exc
    return sorted(videos, key=str.casefold)


def resolve_local_video_path(directory, selected_file):
    """Resolve a UI selection while preventing absolute paths and traversal."""
    if not selected_file or not selected_file.strip():
        raise ValueError("Выберите видеофайл из списка.")

    root = Path(directory).resolve(strict=True)
    relative_path = Path(selected_file.strip())
    if relative_path.is_absolute():
        raise ValueError("Выбранный файл находится вне LOCAL_VIDEO_DIR.")
    try:
        candidate = (root / relative_path).resolve(strict=False)
        candidate.relative_to(root)
    except ValueError:
        raise ValueError("Выбранный файл находится вне LOCAL_VIDEO_DIR.") from None
    except OSError:
        raise ValueError("Не удалось проверить выбранный видеофайл.") from None

    try:
        if not candidate.is_file():
            raise ValueError("Выбранный видеофайл не найден или это не файл.")
    except OSError:
        raise ValueError("Выбранный видеофайл недоступен.") from None
    if candidate.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_VIDEO_EXTENSIONS))
        raise ValueError(f"Неподдерживаемый формат видео. Допустимые расширения: {allowed}")
    return candidate


def _page_context(*, error=None, filename=None):
    try:
        source_mode = get_video_source_mode()
        local_videos = list_local_videos(get_local_video_dir()) if source_mode == "local" else []
    except ValueError as exc:
        source_mode = None
        local_videos = []
        error = error or str(exc)
    return {
        "source_mode": source_mode,
        "local_videos": local_videos,
        "video_error": error,
        "video_success": filename is not None,
        "video_filename": filename,
    }


def _render_result(*, error=None, filename=None):
    return render_template_string(
        HTML_TEMPLATE,
        **_page_context(error=error, filename=filename),
    )

@app.route('/', methods=['GET'])
def index():
    return _render_result()


@app.route('/api/local-video', methods=['POST'])
def api_local_video():
    global LAST_GENERATED_FILE
    try:
        if get_video_source_mode() != "local":
            raise ValueError("Локальная обработка отключена: установите VIDEO_SOURCE_MODE=local.")
        source_path = resolve_local_video_path(
            get_local_video_dir(), request.form.get("local_video", "")
        )
        logging.info("Начало обработки локального видео: %s", source_path.name)
        docx_path = process_local_video(source_path, USER_FOLDER)
        result_filename = os.path.basename(docx_path)
        LAST_GENERATED_FILE = docx_path
        logging.info("Обработка завершена. Файл: %s", result_filename)
        return _render_result(filename=result_filename)
    except Exception as e:
        logging.error("Local Video Processing Error: %s", e, exc_info=True)
        status_code = 422 if isinstance(e, ValueError) else 500
        return _render_result(error=f"Произошла ошибка при обработке: {e}"), status_code

@app.route('/api/video', methods=['POST'])
def api_video():
    global LAST_GENERATED_FILE
    try:
        if get_video_source_mode() != "url":
            raise ValueError("Обработка ссылок отключена: установите VIDEO_SOURCE_MODE=url.")
        url = request.form.get('video_url', '').strip()
        if not url or not re.compile(r'https?://').match(url):
            raise ValueError("Некорректная ссылка. Пожалуйста, проверьте URL.")

        unique_id = str(uuid.uuid4())[:8]
        folder_name = f"web_user_{unique_id}"
        folder_path = os.path.join(USER_FOLDER, folder_name)
        os.makedirs(folder_path, exist_ok=True)

        logging.info(f"Начало обработки видео: {url}")
        docx_path = process_video(url, folder_path)
        filename = os.path.basename(docx_path)
        
        # Сохраняем путь для скачивания
        LAST_GENERATED_FILE = docx_path
        
        logging.info(f"Обработка завершена. Файл: {filename}")

        return _render_result(filename=filename)

    except Exception as e:
        logging.error(f"Video Processing Error: {e}", exc_info=True)
        status_code = 422 if isinstance(e, ValueError) else 500
        return _render_result(error=f"Произошла ошибка при обработке: {str(e)}"), status_code

@app.route('/download/<filename>')
def download_file(filename):
    if LAST_GENERATED_FILE and os.path.exists(LAST_GENERATED_FILE):
        return send_file(
            LAST_GENERATED_FILE,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
    else:
        return "Файл не найден или время хранения истекло. Попробуйте обработать видео снова.", 404

if __name__ == '__main__':
    print("Запуск веб-сервера на http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
