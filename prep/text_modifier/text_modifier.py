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
