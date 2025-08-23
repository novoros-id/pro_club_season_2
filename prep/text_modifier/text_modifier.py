# text_modifier.py
from langchain_ollama import OllamaLLM
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain import PromptTemplate
from langchain.schema import HumanMessage

class TextModify:
    def __init__(self, model_name="gemma3:27b", temperature="0.1"):
        self.llm = OllamaLLM(
            model=model_name,
            callback_manager=CallbackManager([StreamingStdOutCallbackHandler()]),
            temperature=temperature
        )
        self.prompt_template = """
        Ты — профессиональный редактор и технический писатель. Твоя задача — улучшить следующий текст, полученный из аудиозаписи видеоинструкции. Сделай его грамматически правильным, стилистически гладким, логически связным и литературно выдержанным, полностью сохранив все исходные сведения.

        Правила обработки:
        1. Удали слова-паразиты (например: "ну", "вот", "как бы", "это самое", "значит", "короче", "типа" и т.п.), но не исключай ни одной смысловой детали.
        2. Исправь разговорные, нечёткие или грамматически неверные формулировки, переформулируй их ясно и профессионально, не искажая смысла.
        3. Сохрани все технические термины, шаги, примеры, уточнения и повторы — даже если они кажутся избыточными.
        4. Разбей текст на логические абзацы при необходимости, чтобы улучшить читаемость.
        5. Не добавляй новые идеи, пояснения, комментарии или выводы.
        6. Не сокращай и не обобщай — каждая мысль должна остаться, но быть выражена правильно и красиво.
        7. Верни только улучшенный текст, без пояснений, заголовков или комментариев.
        8. Предложения где есть фраза "сейчас на экране" изменять можно, но сама фраза "сейчас на экране" должна в остаться в предложении.
        """

    def improve_text(self, full_text):
        prompt = self.prompt_template + " Вот текст для улучшения: " + full_text
        return self.llm.invoke(prompt)
