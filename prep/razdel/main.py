from langchain_ollama import OllamaLLM
import base64
from docx import Document
URL_LLM="http://188.225.36.45"
USER_LLM="ollamaadmin"
PASSWORD_LLM="@TLYInb%5T#c"

def extract_text_from_docx(file_path):
    """Извлекает только текст из .docx файла (игнорируя изображения)."""
    doc = Document(file_path)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():  # Игнорируем пустые строки
            full_text.append(para.text.strip())
    return '\n'.join(full_text)

def create_prompt_for_sectioning(text):
    """Создаёт промт для LLM, чтобы разбить текст на разделы."""
    prompt = f"""
    Ты — интеллектуальный анализатор текста. Проанализируй следующий текст и разбей его на логические разделы. 
    Для каждого раздела:
    1. Придумай информативное название.
    2. Чётко укажи, где начинается и заканчивается раздел (приведи первые и последние несколько слов).
    3. Сохрани структуру: используй формат:

    ---
    **Название раздела**: [Название]
    **Начало**: "[первые слова раздела]..."
    **Конец**: "...[последние слова раздела]"
    **Содержание**:
    [Полный текст раздела]
    ---

    Если текст небольшой и не содержит явных разделов, создай один раздел с названием "Основной текст".

    Текст:
    {text}
    """
    return prompt

def get_sectioned_text(prompt):
    """Отправляет промт в LLM и возвращает ответ."""
    encoded_credentials = base64.b64encode(f"{USER_LLM}:{PASSWORD_LLM}".encode()).decode()
    headers = {'Authorization': f'Basic {encoded_credentials}'}

    llm_class = OllamaLLM(model="gemma3:12b", temperature = 0.1, base_url=URL_LLM, client_kwargs={'headers': headers})
    llm_response = llm_class.invoke(prompt)
    return llm_response

# === Основной код ===
if __name__ == "__main__":
    file_path = "/Users/alexeyvaganov/Documents/Project/pro_club_2/pro_club_season_2/prep/razdel/test.docx"  # Укажи путь к своему файлу

    # 1. Извлекаем текст
    print("Чтение файла...")
    text = extract_text_from_docx(file_path)

    if not text:
        print("Файл пуст или не содержит текста.")
    else:
        print(f"Извлечено {len(text)} символов.")

        # 2. Формируем промт
        prompt = create_prompt_for_sectioning(text)

        # 3. Отправляем в LLM
        print("Отправка запроса в модель...")
        result = get_sectioned_text(prompt)  

        # 4. Выводим результат
        print("\n=== Результат разбиения на разделы ===\n")
        print(result)

