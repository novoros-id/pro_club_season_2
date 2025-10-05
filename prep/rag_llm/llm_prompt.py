from typing import Optional
from pathlib import Path

def load_system_prompt(path: str = "prep/rag_llm/system_prompt.txt") -> str:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Файл системного промпта не найден: {path}")
    return p.read_text(encoding="utf-8").strip()

def compose_prompt(
    *,
    question: str,
    context: str,
    global_prompt: Optional[str] = None,
    mode: str = "assistant",
    system_prompt_path: Optional[str] = "prep/rag_llm/system_prompt.txt",
) -> str:
    """
    Возвращает полностью готовый промпт (одна строка), без "Источников".
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Вопрос не может быть пустым")
    context_block = context.strip() if isinstance(context, str) else ""

    if global_prompt is None:
        try:
            global_prompt = load_system_prompt(system_prompt_path)
        except FileNotFoundError:
            global_prompt = None

    # Набор инструкций под режимы (минимально, можно расширять стилем)
    if mode == "code":
        role_block = (
            "ЗАДАЧА: отвечай как опытный Python-разработчик, давай точный и сжатый код/советы.\n"
            "Если данных недостаточно — прямо укажи, чего не хватает."
        )
    elif mode == "fact":
        role_block = (
            "ЗАДАЧА: отвечай фактически точно и кратко, без рассуждений сверх контекста.\n"
            "Если данных недостаточно — скажи об этом."
        )
    else:  # assistant
        role_block = (
            "ЗАДАЧА: ответь на вопрос максимально по делу, опираясь ТОЛЬКО на контекст ниже.\n"
            "Если ответа в контексте нет — честно скажи, что данных недостаточно."
        )

    parts = []
    if global_prompt:
        parts.append(f"СИСТЕМНЫЕ ИНСТРУКЦИИ:\n{global_prompt}\n---")

    parts.append("КОНТЕКСТ:")
    parts.append(context_block if context_block else "(контекст не найден)")
    parts.append("---")
    parts.append(role_block)
    parts.append("---")
    parts.append(f"ВОПРОС: {question}")

    return "\n".join(parts)