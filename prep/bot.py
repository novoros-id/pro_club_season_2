import re
import os
import uuid
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from main import process_video
from config import USER_FOLDER
from rag_llm.llm_client import LLMClient

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Проверка ссылки
def is_url(text):
    url_regex = re.compile(
        r'https?://(?:www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}'
    )
    return url_regex.match(text) is not None

# Функция генерации имени папки
def generate_user_folder(user):
    user_id = str(user.id)
    username = user.username or user_id  # если нет username, используем ID
    unique_id = str(uuid.uuid4())[:8]  # короткий UUID для уникальности
    folder_name = f"{username}_{unique_id}"
    folder_path = os.path.join(USER_FOLDER, folder_name)
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

llm_client = LLMClient()

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Пришли мне ссылку на видео или запрос, начинающийся с '$'.")

# Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text.strip()

    if text.startswith('$'):
        query = text[1:].strip()
        try:
            response = llm_client.generate_with_retrieval(
                question = query,
                return_with_sources = True,  # изменено на True для возврата источников
                mode = "assistant"
            )
            await update.message.reply_text(response)
        except Exception as e:
            logging.error(f"Ошибка при генерации ответа LLM для пользователя {user.id}: {e}")
            await update.message.reply_text("Произошла ошибка при обработке вашего запроса.")
        return

    if not is_url(text):
        await update.message.reply_text("Это не похоже на ссылку. Пожалуйста, пришли корректную ссылку на видео.")
        return

    await update.message.reply_text("Начинаю обработку видео. Это может занять несколько минут...")

    # Генерируем папку для пользователя
    folder = generate_user_folder(user)

    try:
        # Передаём ссылку и папку в обработку
        docx_path = process_video(text, folder)

        # Извлекаем имя файла из полного пути
        filename = os.path.basename(docx_path)
        
        with open(docx_path, 'rb') as docx_file:
            await update.message.reply_document(
                document=docx_file,
                filename=filename  # используем извлечённое имя файла
            )

    except Exception as e:
        logging.error(f"Ошибка при обработке видео для пользователя {user.id}: {e}")
        await update.message.reply_text("Произошла ошибка при обработке видео.")

# Запуск бота
def run_bot():
    from config import BOT_TOKEN

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    run_bot()