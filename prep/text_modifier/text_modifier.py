# text_modifier.py
from langchain_ollama import OllamaLLM
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain import PromptTemplate
from langchain.schema import HumanMessage
import os

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
URL_LLM = os.getenv("URL_LLM")
USER_LLM = os.getenv("USER_LLM")
PASSWORD_LLM = os.getenv("PASSWORD_LLM") 
MODEL = os.getenv("MODEL")

import base64

encoded_credentials = base64.b64encode(f"{USER_LLM}:{PASSWORD_LLM}".encode()).decode()
headers = {'Authorization': f'Basic {encoded_credentials}'}

class TextModify:
    def __init__(self, model_name="gpt-oss:latest", temperature="0.1"):
        self.llm = OllamaLLM(model=MODEL, temperature=0.1, base_url=URL_LLM, client_kwargs={'headers': headers})
        self.prompt_template = """
        Ты — профессиональный редактор и технический писатель. Твоя задача — улучшить следующий текст, полученный из аудиозаписи видеоинструкции. Сделай его грамматически правильным, стилистически гладким, логически связным и литературно выдержанным, полностью сохранив все исходные сведения.

        Правила обработки:
        1. Удали слова-паразиты (например: "ну", "вот", "как бы", "это самое", "значит", "короче", "типа" и т.п.), но не исключай ни одной смысловой детали.
        2. Исправь разговорные, нечёткие или грамматически неверные формулировки, переформулируй их ясно и профессионально, не искажая смысла.
        3. Сохрани все технические термины, шаги, примеры, уточнения и повторы — даже если они кажутся избыточными.
        4. Не добавляй новые идеи, пояснения, комментарии или выводы.
        5. Не сокращай и не обобщай — каждая мысль должна остаться, но быть выражена правильно и красиво.
        6. Верни только улучшенный текст, без пояснений, заголовков или комментариев.
        7. Не возвращай в тексте свои рассуждения, только итоговый текст
        """

    def improve_text(self, full_text):
        prompt = self.prompt_template + " Вот текст для улучшения: " + full_text
        return self.llm.invoke(prompt)
    
    def clean_paragraph_with_context_window(self, paragraphs, current_index):
        """
        Очищает текущий абзац, используя контекст раздела, предыдущий и следующий абзацы.
        
        Args:
            paragraphs: Список всех сырых абзацев раздела.
            current_index: Индекс текущего абзаца в списке (0-based).
            section_summary: Краткое содержание раздела (строка).
            model, url, headers: Параметры подключения к Ollama.
            
        Returns:
            Очищенный текст абзаца или пустую строку, если это мусор.
        """
        #llm = OllamaLLM(model=model, temperature=0.1, base_url=url, client_kwargs={'headers': headers})
        
        # 1. Получаем предыдущий контекст (последние 200 символов)
        prev_context = ""
        if current_index > 0:
            # Берем предыдущий абзац. Если он был очищен ранее, лучше брать его очищенную версию,
            # но здесь у нас доступ только к сырому списку. 
            # Для простоты берем сырой, но можно передавать список уже очищенных.
            prev_text = paragraphs[current_index - 1]
            if len(prev_text) > 200:
                prev_context = "... " + prev_text[-200:]
            else:
                prev_context = prev_text

        # 2. Получаем следующий контекст (первые 200 символов)
        next_context = ""
        if current_index < len(paragraphs) - 1:
            next_text = paragraphs[current_index + 1]
            if len(next_text) > 200:
                next_context = next_text[:200] + " ..."
            else:
                next_context = next_text
                
        current_text = paragraphs[current_index]

        prompt = f"""
        Ты — редактор технической документации. Твоя задача — очистить транскрибацию от шума и привести её к читаемому виду.
        
        ПРЕДЫДУЩИЙ ТЕКСТ (для связности):
        "{prev_context}"

        СЛЕДУЮЩИЙ ТЕКСТ (для понимания продолжения):
        "{next_context}"

        ТЕКУЩИЙ ФРАГМЕНТ (требует обработки):
        "{current_text}"

        ИНСТРУКЦИИ:
        1. Если текущий фрагмент — это явный мусор (набор символов OCR, английский текст вроде "I'm sorry", бессвязные слова), верни ТОЛЬКО слово: EMPTY
        2. Если фрагмент нормальный:
        - Исправь ошибки распознавания.
        - Удали слова-паразиты ("эээ", "ну", "как бы").
        - Сохрани технический смысл и термины.
        - Обеспечь логическую связку с предыдущим текстом.
        - Верни ТОЛЬКО готовый текст на русском языке. Без пояснений.
        
        Результат:
        """
        
        try:
            response = self.llm.invoke(prompt)
            result = response.strip()
            
            # Проверка на маркер пустоты
            if result.upper() == "EMPTY":
                return ""
                
            return result
            
        except Exception as e:
            print(f"Ошибка LLM при очистке абзаца {current_index}: {e}")
            return current_text # В случае ошибки возвращаем оригинал, чтобы не терять данные
