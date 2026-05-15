import os
import uuid
import logging
import re
from flask import Flask, render_template_string, request, send_file
from dotenv import load_dotenv
from main import process_video

load_dotenv()

# --- Конфигурация ---
USER_FOLDER = os.getenv("USER_FOLDER")
if not USER_FOLDER:
    USER_FOLDER = "./user_data"
    os.makedirs(USER_FOLDER, exist_ok=True)

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

        input[type="url"] { 
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
        
        <!-- Ваш требуемый текст -->
        <div class="info-text">
            Вставьте ссылку на Synology Drive или Яндекс Диск. Не забудьте расшарить файл.
        </div>
        
        <form action="/api/video" method="POST">
            <input type="url" name="video_url" placeholder="https://..." required>
            <button type="submit" class="action-btn">Начать обработку</button>
        </form>

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

@app.route('/', methods=['GET'])
def index():
    return render_template_string(
        HTML_TEMPLATE, 
        video_error=None, 
        video_success=False, 
        video_filename=None
    )

@app.route('/api/video', methods=['POST'])
def api_video():
    global LAST_GENERATED_FILE
    url = request.form.get('video_url', '').strip()
    
    if not url or not re.compile(r'https?://').match(url):
        return render_template_string(
            HTML_TEMPLATE, 
            video_error="Некорректная ссылка. Пожалуйста, проверьте URL.",
            video_success=False
        )

    unique_id = str(uuid.uuid4())[:8]
    folder_name = f"web_user_{unique_id}"
    folder_path = os.path.join(USER_FOLDER, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    try:
        logging.info(f"Начало обработки видео: {url}")
        docx_path = process_video(url, folder_path)
        filename = os.path.basename(docx_path)
        
        # Сохраняем путь для скачивания
        LAST_GENERATED_FILE = docx_path
        
        logging.info(f"Обработка завершена. Файл: {filename}")

        return render_template_string(
            HTML_TEMPLATE, 
            video_error=None, 
            video_success=True, 
            video_filename=filename
        )

    except Exception as e:
        logging.error(f"Video Processing Error: {e}", exc_info=True)
        return render_template_string(
            HTML_TEMPLATE, 
            video_error=f"Произошла ошибка при обработке: {str(e)}",
            video_success=False
        )

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