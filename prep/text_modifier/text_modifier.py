from model_api import get_default_client


class TextModify:
    def __init__(self, model_name=None, temperature=0.1, client=None):
        self.client = client or get_default_client()
        self.model_name = model_name
        self.temperature = float(temperature)
        self.prompt_template = """
Ты — профессиональный редактор технической документации. Исправь ошибки распознавания,
удали слова-паразиты, сохрани все технические сведения и не добавляй новых идей.
Верни только улучшенный текст без пояснений.
"""

    def improve_text(self, full_text):
        return self.client.generate_text(
            self.prompt_template + "\nТекст для улучшения:\n" + full_text,
            model=self.model_name,
            temperature=self.temperature,
        )

    def clean_paragraph_with_context_window(self, paragraphs, current_index):
        current_text = paragraphs[current_index]
        previous = paragraphs[current_index - 1] if current_index > 0 else ""
        following = paragraphs[current_index + 1] if current_index + 1 < len(paragraphs) else ""
        previous = ("... " + previous[-200:]) if len(previous) > 200 else previous
        following = (following[:200] + " ...") if len(following) > 200 else following
        prompt = f"""
Ты — редактор технической документации. Очисти текущий фрагмент транскрибации.

Предыдущий контекст: {previous!r}
Следующий контекст: {following!r}
Текущий фрагмент: {current_text!r}

Исправь ошибки распознавания и грамматику, удали слова-паразиты, сохрани технический
смысл и связность. Не добавляй новых сведений. Если фрагмент является явным мусором,
верни только EMPTY. Иначе верни только готовый русский текст без пояснений.
"""
        try:
            result = self.client.generate_text(
                prompt, model=self.model_name, temperature=self.temperature
            ).strip()
            return "" if result.upper() == "EMPTY" else result
        except Exception as exc:
            print(f"Ошибка MWS при очистке абзаца {current_index}: {exc}")
            return current_text
