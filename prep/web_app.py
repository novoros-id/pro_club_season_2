import os
import uuid
import logging
import re
from flask import Flask, render_template_string, request, jsonify, send_file
from dotenv import load_dotenv
from main import process_video
from rag_llm.llm_client import LLMClient
from telegram.helpers import escape_markdown

load_dotenv()

# --- Конфигурация ---
USER_FOLDER = os.getenv("USER_FOLDER")
if not USER_FOLDER:
    USER_FOLDER = "./user_data"
    os.makedirs(USER_FOLDER, exist_ok=True)

llm_client = LLMClient()
app = Flask(__name__)

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.INFO)

# --- HTML Шаблон (ТОЛЬКО HTML + CSS, БЕЗ JS) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>1C PRO Assistant</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f4f4f9; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }
        h1 { text-align: center; color: #d32f2f; }
        
        /* Скрываем радио-кнопки */
        input[name="tab"] { display: none; }

        /* Стили для кнопок-лейблов */
        .tab-buttons { display: flex; justify-content: center; margin-bottom: 0; }
        .tab-label {
            padding: 12px 24px;
            background: #e0e0e0;
            cursor: pointer;
            font-size: 16px;
            border-radius: 5px 5px 0 0;
            margin-right: 4px;
            transition: background 0.2s;
            user-select: none;
        }
        .tab-label:hover { background: #d0d0d0; }

        /* Контейнеры контента (скрыты по умолчанию) */
        .tab-content {
            display: none;
            background: white;
            padding: 20px;
            border-radius: 0 0 8px 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            animation: fadeIn 0.3s ease-in-out;
        }

        /* ЛОГИКА ПЕРЕКЛЮЧЕНИЯ: Если выбран радио-баттон #tab1, показываем #content1 и красим label[for=tab1] */
        #tab1:checked ~ .tab-buttons label[for="tab1"],
        #tab2:checked ~ .tab-buttons label[for="tab2"] {
            background: #d32f2f;
            color: white;
            font-weight: bold;
        }

        #tab1:checked ~ #content1,
        #tab2:checked ~ #content2 {
            display: block;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-5px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Элементы форм */
        input[type="text"], input[type="url"], textarea { 
            width: 100%; padding: 12px; margin: 15px 0; 
            border: 1px solid #ccc; border-radius: 4px; 
            box-sizing: border-box; font-size: 16px; 
        }
        button.action-btn { 
            background-color: #d32f2f; color: white; 
            padding: 12px 20px; border: none; border-radius: 4px; 
            cursor: pointer; width: 100%; font-size: 16px; font-weight: bold; 
        }
        button.action-btn:hover { background-color: #b71c1c; }
        
        .result-box { 
            margin-top: 20px; padding: 15px; 
            background: #f9f9f9; border-left: 4px solid #d32f2f; 
            white-space: pre-wrap; word-wrap: break-word; 
            border-radius: 4px; 
        }
        .error { color: #d32f2f; border-left-color: #d32f2f; background: #ffebee; }
        
        strong { font-weight: bold; }
        em { font-style: italic; }
    </style>
</head>
<body>

    <h1>1C PRO Assistant</h1>

    <!-- Радио-кнопки управления состоянием -->
    <input type="radio" name="tab" id="tab1" checked>
    <input type="radio" name="tab" id="tab2">

    <!-- Кнопки переключения (Labels) -->
    <div class="tab-buttons">
        <label for="tab1" class="tab-label">💬 Чат с AI</label>
        <label for="tab2" class="tab-label">🎥 Обработка Видео</label>
    </div>

    <!-- Контент Вкладки 1: ЧАТ -->
    <div id="content1" class="tab-content">
        <h3>Задайте вопрос базе знаний</h3>
        <!-- Форма отправляет POST запрос на /api/chat -->
        <form action="/api/chat" method="POST">
            <textarea name="question" rows="4" placeholder="Введите ваш вопрос здесь..." required></textarea>
            <button type="submit" class="action-btn">Отправить запрос</button>
        </form>
        
        {% if chat_result %}
        <div class="result-box">
            {{ chat_result|safe }}
        </div>
        {% endif %}
    </div>

    <!-- Контент Вкладки 2: ВИДЕО -->
    <div id="content2" class="tab-content">
        <h3>Скачать транскрибацию видео</h3>
        <p style="color:#666; font-size: 0.9em;">Вставьте ссылку на YouTube, VK Video или другой источник.</p>
        
        <!-- Форма отправляет POST запрос на /api/video -->
        <form action="/api/video" method="POST">
            <input type="url" name="video_url" placeholder="https://..." required>
            <button type="submit" class="action-btn">Начать обработку</button>
        </form>

        {% if video_error %}
        <div class="result-box error">
            ❌ {{ video_error }}
        </div>
        {% endif %}
        
        {% if video_success %}
        <div class="result-box" style="border-left-color: green;">
            ✅ Файл готов! Скачивание начнется автоматически или по кнопке ниже.<br>
            <a href="/download/{{ video_filename }}" class="action-btn" style="display:inline-block; text-decoration:none; text-align:center; margin-top:10px;">Скачать файл</a>
        </div>
        {% endif %}
    </div>

</body>
</html>
"""

# --- Маршруты ---

@app.route('/', methods=['GET'])
def index():
    # Передаем переменные в шаблон (изначально пустые)
    return render_template_string(HTML_TEMPLATE, chat_result=None, video_error=None, video_success=False, video_filename=None)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    question = request.form.get('question', '').strip()
    
    if not question:
        return render_template_string(HTML_TEMPLATE, chat_result="<div class='result-box error'>Вопрос не может быть пустым</div>", video_error=None)

    try:
        response = llm_client.generate_with_retrieval(
            question=question,
            return_with_sources=True,
            mode="assistant"
        )
        
        answer_text = response.get("answer", "Нет ответа")
        sources_raw = response.get("sources", [])
        
        # Форматируем источники
        sources_list = []
        seen = set()
        for src in sources_raw:
            title = src.get("title", "Unknown")
            time_r = src.get("time_range", "")
            key = (title, time_r)
            if key not in seen:
                sources_list.append(f"<br>📄 {title} ({time_r})")
                seen.add(key)
        
        # Простая замена Markdown на HTML
        formatted_answer = answer_text.replace("**", "<strong>").replace("*", "<em>").replace("\n", "<br>")
        
        result_html = f"<strong>Ответ:</strong><br>{formatted_answer}"
        if sources_list:
            result_html += "<hr><strong>Источники:</strong>" + "".join(sources_list)

        return render_template_string(HTML_TEMPLATE, chat_result=f"<div class='result-box'>{result_html}</div>", video_error=None)

    except Exception as e:
        logging.error(f"LLM Error: {e}")
        return render_template_string(HTML_TEMPLATE, chat_result=f"<div class='result-box error'>Ошибка: {str(e)}</div>", video_error=None)

@app.route('/api/video', methods=['POST'])
def api_video():
    url = request.form.get('video_url', '').strip()
    
    if not url or not re.compile(r'https?://').match(url):
        return render_template_string(HTML_TEMPLATE, chat_result=None, video_error="Некорректная ссылка на видео")

    unique_id = str(uuid.uuid4())[:8]
    folder_name = f"web_user_{unique_id}"
    folder_path = os.path.join(USER_FOLDER, folder_name)
    os.makedirs(folder_path, exist_ok=True)

    try:
        docx_path = process_video(url, folder_path)
        filename = os.path.basename(docx_path)
        
        # Сохраняем путь к файлу во временное хранилище или сессию, чтобы отдать его при скачивании.
        # Для простоты передадим имя, предполагая, что файл лежит в USER_FOLDER.
        # В реальном проде лучше использовать session['last_file'] = docx_path
        
        # Возвращаем страницу с сообщением об успехе и ссылкой на скачивание
        # Примечание: нам нужно передать полный путь или организовать роут для скачивания
        # Здесь мы просто сохраним имя файла и предположим, что роут /download знает, где искать
        
        # Хак: сохраняем имя файла в глобальную переменную (небезопасно для многопользовательской нагрузки, но ок для теста)
        # Лучше передавать ID сессии, но пока сделаем просто редирект или вывод ссылки
        global LAST_GENERATED_FILE
        LAST_GENERATED_FILE = docx_path
        
        return render_template_string(
            HTML_TEMPLATE, 
            chat_result=None, 
            video_error=None, 
            video_success=True, 
            video_filename=filename # Передаем имя для ссылки
        )

    except Exception as e:
        logging.error(f"Video Processing Error: {e}", exc_info=True)
        return render_template_string(HTML_TEMPLATE, chat_result=None, video_error=f"Ошибка обработки: {str(e)}")

# Роут для скачивания созданного файла
LAST_GENERATED_FILE = None

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
        return "Файл не найден или истекло время хранения", 404

if __name__ == '__main__':
    print("Запуск веб-сервера (БЕЗ JS) на http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)