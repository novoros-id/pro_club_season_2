# pip install python-docx opencv-python

from docx import Document
from docx.shared import Mm
import os
import sys
import json
import re
import logging

# Добавляем родительский каталог в пути поиска модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Импорты из соседних модулей
from text_to_paragraphs.text_to_paragraphs import text_to_paragraphs
from picture_description.picture_description import picture_description
from text_modifier.text_modifier import TextModify
from model_api import get_default_client


DEFAULT_PARAGRAPH_BATCH_SIZE = 15


def parse_json_response(response):
    if not isinstance(response, str):
        raise ValueError("Ответ модели должен быть строкой.")
    cleaned = response.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.I | re.S)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def image_is_required(paragraph, client=None):
    client = client or get_default_client()
    prompt = (
    "Ты — эксперт по технической документации. Определи, требует ли данный фрагмент инструкции вставки иллюстрации (скриншота, схемы, фото интерфейса и т.п.).\n"
    "Придерживайся следующих правил, иллюстрация нужна, если в тексте:\n"
    "- описывается конкретный элемент интерфейса (кнопка, меню, поле ввода и т.д.),\n"
    "- даётся пошаговое руководство с действиями пользователя (нажать, выбрать, перейти, открыть, следует перейти, необходимо перейти  и т.п.),\n"
    "- упоминается визуальный результат (вы увидите, на экране появится, как показано на рисунке, в данном элементе),\n"
    "- есть ссылка на расположение чего-либо (в левом верхнем углу, под заголовком, она заполняется  и т.п.).\n\n"
    "- при необходимости догадывайся по контексту.\n"
    "Верни только JSON строго такого вида: {\"image_required\": true}. "
    "Если иллюстрация не нужна, используй false. Не добавляй пояснений.\n\n"
    "Текст: " + paragraph
    )
    try:
        payload = parse_json_response(client.generate_text(prompt, temperature=0.1))
        value = payload.get("image_required") if isinstance(payload, dict) else None
        if not isinstance(value, bool):
            raise ValueError("image_required должен быть boolean")
        return value
    except Exception as e:
        print(f"Ошибка MWS при определении необходимости кадра: {e}")
        return False


def _parse_paragraph_batch_response(response, expected_numbers, modify_text):
    payload = parse_json_response(response)
    rows = payload.get("paragraphs") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Ответ не содержит список paragraphs.")

    expected = set(expected_numbers)
    parsed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Элемент paragraphs должен быть объектом.")
        number = row.get("number")
        if isinstance(number, bool) or not isinstance(number, int):
            raise ValueError("number должен быть целым числом.")
        if number not in expected or number in parsed:
            raise ValueError("Ответ содержит неизвестный или повторяющийся number.")
        image_required = row.get("image_required")
        if not isinstance(image_required, bool):
            raise ValueError("image_required должен быть boolean.")
        clean_text = row.get("clean_text")
        if modify_text and not isinstance(clean_text, str):
            raise ValueError("clean_text должен быть строкой.")
        parsed[number] = {
            "number": number,
            "clean_text": clean_text if modify_text else None,
            "image_required": image_required,
        }

    if set(parsed) != expected:
        missing = sorted(expected - set(parsed))
        raise ValueError(f"Ответ не содержит абзацы: {missing}")
    return [parsed[number] for number in expected_numbers]


def _fallback_paragraph_batch(paragraphs, numbers, modify_text, client):
    """Preserve the former per-paragraph behavior for one failed batch only."""
    modifier = TextModify(client=client) if modify_text else None
    results = []
    for number in numbers:
        index = number - 1
        original = paragraphs[index]
        clean_text = (
            modifier.clean_paragraph_with_context_window(paragraphs, index)
            if modifier
            else original
        )
        results.append({
            "number": number,
            "clean_text": clean_text,
            "image_required": image_is_required(original, client=client),
        })
    return results


def process_paragraphs_in_batches(paragraphs, modify_text=True, client=None, batch_size=None):
    """Clean text and decide on images with one structured LLM call per batch."""
    client = client or get_default_client()
    if batch_size is None:
        configured = getattr(
            getattr(client, "config", None),
            "paragraph_processing_batch_size",
            DEFAULT_PARAGRAPH_BATCH_SIZE,
        )
        batch_size = configured if isinstance(configured, int) else DEFAULT_PARAGRAPH_BATCH_SIZE
    if batch_size <= 0:
        raise ValueError("batch_size должен быть положительным.")

    results = []
    for offset in range(0, len(paragraphs), batch_size):
        end = min(offset + batch_size, len(paragraphs))
        numbers = list(range(offset + 1, end + 1))
        items = []
        for number in numbers:
            index = number - 1
            previous = paragraphs[index - 1] if index > 0 else ""
            following = paragraphs[index + 1] if index + 1 < len(paragraphs) else ""
            items.append({
                "number": number,
                "text": paragraphs[index],
                "previous_context": previous[-200:],
                "next_context": following[:200],
            })

        clean_instruction = (
            "Для clean_text исправь распознавание и грамматику, удали слова-паразиты, "
            "сохрани все технические сведения и связность. Контекст используй только "
            "для понимания текущего абзаца. Для явного мусора верни пустую строку."
            if modify_text
            else "Поле clean_text не возвращай: редактирование текста отключено."
        )
        schema = (
            '{"paragraphs":[{"number":1,"clean_text":"...",'
            '"image_required":true}]}'
            if modify_text
            else '{"paragraphs":[{"number":1,"image_required":true}]}'
        )
        prompt = f"""
Ты обрабатываешь пакет абзацев технической документации. Для каждого входного number
верни ровно один результат с тем же number. Не объединяй, не удаляй и не переставляй
абзацы. {clean_instruction}

image_required оценивай по исходному полю text (не по clean_text) по прежним правилам:
true для конкретных элементов интерфейса, пошаговых действий пользователя, визуального
результата или указания расположения; иначе false. Соседний контекст не должен сам по
себе делать изображение обязательным для текущего абзаца.

Верни только валидный JSON вида:
{schema}

Входные абзацы:
{json.dumps(items, ensure_ascii=False)}
"""
        try:
            response = client.generate_text(prompt, temperature=0.1)
            batch_results = _parse_paragraph_batch_response(
                response, numbers, modify_text
            )
            if not modify_text:
                for row in batch_results:
                    row["clean_text"] = paragraphs[row["number"] - 1]
        except Exception as exc:
            print(
                f"Ошибка пакетной обработки абзацев {numbers[0]}–{numbers[-1]}: {exc}. "
                "Используется поабзацный fallback."
            )
            batch_results = _fallback_paragraph_batch(
                paragraphs, numbers, modify_text, client
            )
        results.extend(batch_results)
    if len(results) != len(paragraphs):
        raise RuntimeError("Пакетная обработка изменила количество абзацев.")
    return results

def table_segments_time(json_file_path):
    with open(json_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    buffer = ""  # сюда складываем "висящее" начало предложения

    for i, seg in enumerate(data.get("segments", [])):
        text = seg["text"].strip()

        # добавляем "хвост" из предыдущего сегмента, если он был
        if buffer:
            text = buffer + " " + text
            buffer = ""

        # режем на предложения по ". "
        sentences = text.split(". ")

        # проверяем, закончился ли последний кусок точкой
        last_part = sentences[-1]
        if not last_part.endswith((".", "!", "?")):
            # предложение не закончилось → переносим в buffer для следующего сегмента
            buffer = sentences.pop()

        # теперь фиксируем завершённые предложения
        for sent in sentences:
            sent = sent.strip()
            if sent:
                if not sent.endswith((".", "!", "?")):
                    sent += "."
                rows.append((sent, seg["end"]))

    # на всякий случай — если файл закончился, а buffer остался
    if buffer:
        rows.append((buffer, data["segments"][-1]["end"]))

    return rows

def format_seconds_hhmmss(value):
    """Конвертируем секунды (int/float/str) to HH:MM:SS."""
    try:
        total_seconds = int(float(value))
    except Exception:
        total_seconds = 0
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def parse_sections_response(response):
    payload = parse_json_response(response)
    rows = payload.get("sections") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Ответ не содержит список sections.")
    parsed = []
    for row in rows:
        if not isinstance(row, dict) or isinstance(row.get("start_paragraph"), bool):
            continue
        try:
            start = int(row["start_paragraph"])
        except (KeyError, TypeError, ValueError):
            continue
        title = row.get("title")
        if isinstance(title, str) and title.strip():
            parsed.append((start, title.strip()))
    return parsed


def get_sections_from_llm(paragraphs, max_paragraphs_per_chunk=25, overlap=5, client=None):
    """Find section starts using overlapping blocks and stable global numbering."""
    total_pars = len(paragraphs)
    if not total_pars:
        return []
    client = client or get_default_client()
    if max_paragraphs_per_chunk <= 0 or overlap < 0 or overlap >= max_paragraphs_per_chunk:
        raise ValueError("Некорректные параметры разбиения на блоки.")
    chunks = []
    start = 0
    while start < total_pars:
        end = min(start + max_paragraphs_per_chunk, total_pars)
        chunks.append((start, end))
        if end == total_pars:
            break
        start = end - overlap

    section_starts = {}
    print(f"Разбиение на {len(chunks)} чанков для анализа структуры...")
    for chunk_index, (chunk_start, chunk_end) in enumerate(chunks):
        numbered = "\n".join(
            f"[{index + 1}] {paragraphs[index]}" for index in range(chunk_start, chunk_end)
        )
        prompt = f"""
Ты — старший технический писатель. Найди начала крупных логических разделов в абзацах
[{chunk_start + 1}–{chunk_end}]. Раздел должен включать минимум 2–3 абзаца либо
описывать законченный этап. Не создавай разделы для фраз-связок. Название — не более
5 слов. Используй глобальные номера из текста.

Верни только JSON:
{{"sections": [{{"start_paragraph": 1, "title": "Название раздела"}}]}}

Текст:
{numbered}
"""
        try:
            response = client.generate_text(prompt, temperature=0.1)
            candidates = parse_sections_response(response)
        except Exception as exc:
            print(f"Ошибка MWS при формировании разделов в чанке {chunk_index}: {exc}")
            continue
        for paragraph_number, title in candidates:
            if chunk_start + 1 <= paragraph_number <= chunk_end:
                section_starts.setdefault(paragraph_number, title)

    if not section_starts:
        return [{"title": "Основной текст", "start_par": 1, "end_par": total_pars}]
    # Ensure the document prefix is never lost if the model starts its first section later.
    if 1 not in section_starts:
        section_starts[1] = "Основной текст"
    starts = sorted(section_starts.items())
    raw = []
    for index, (section_start, title) in enumerate(starts):
        section_end = starts[index + 1][0] - 1 if index + 1 < len(starts) else total_pars
        raw.append({"title": title, "start_par": section_start, "end_par": section_end})

    if len(raw) > 1 and raw[0]["end_par"] - raw[0]["start_par"] + 1 < 2:
        raw[1]["start_par"] = raw[0]["start_par"]
        raw = raw[1:]
    final = []
    for section in raw:
        length = section["end_par"] - section["start_par"] + 1
        if length < 2 and final:
            final[-1]["end_par"] = section["end_par"]
        else:
            final.append(section)
    return final


class create_docx:
    def __init__(self, json_file_path, video_path="", UseTextModify=False, client=None):
        self.json_file_path = json_file_path
        self.video_path = video_path
        self.UseTextModify = UseTextModify
        self.client = client or get_default_client()

    def get_docx(self):
        json_file_path = self.json_file_path
        UseTextModify = self.UseTextModify

        if not os.path.isfile(json_file_path):
            raise FileNotFoundError(f"Файл {json_file_path} не найден.")

        doc = Document()
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        full_text = data.get('full_text', '')

        # === Шаг 1: Поиск "сейчас на экране" в segments ===
        # table_time_screen = []
        # counter = 1
        # search_sequence = ["сейчас", "на", "экране"]
        # for segment in data['segments']:
        #     words = segment.get('words', [])
        #     lower_words = [word['word'].lower() for word in words]
        #     for i in range(len(lower_words) - 2):
        #         if lower_words[i:i+3] == search_sequence:
        #             start_time = words[i]['start']
        #             table_time_screen.append({
        #                 "Number": counter,
        #                 "Time": start_time
        #             })
        #             counter += 1
        #             break

        # === Шаг 2: Разбиваем текст на абзацы ===
        
        #1
        segments_time = table_segments_time(json_file_path)
        class_text_to_paragraphs = text_to_paragraphs(full_text, segments_time, client=self.client)
        paragraphs_table = class_text_to_paragraphs.get_text_to_paragraphs_table()
        paragraphs = [p[0] for p in paragraphs_table]

        # Приблизительный старт абзаца: берём end предыдущего абзаца.
        # Для первого абзаца считаем старт 0.
        paragraphs_start_time = {}
        prev_end = 0
        for idx, row in enumerate(paragraphs_table, start=1):
            try:
                end_time = row[1]
            except Exception:
                end_time = prev_end
            paragraphs_start_time[idx] = prev_end
            prev_end = end_time

        processed_paragraphs = process_paragraphs_in_batches(
            paragraphs, modify_text=UseTextModify, client=self.client
        )
        paragraphs_time_scr = {}

        for result, row in zip(processed_paragraphs, paragraphs_table):
            idx = result["number"]
            _, end_time = row
            if result["image_required"]:
                # Проверяем, есть ли уже такой end_time в словаре
                existing_keys = [k for k, v in paragraphs_time_scr.items() if v == end_time]

                if existing_keys:
                    # Если уже есть, удаляем старый ключ и вставляем новый
                    old_key = existing_keys[0]
                    del paragraphs_time_scr[old_key]
                    paragraphs_time_scr[idx] = end_time
                else:
                    # Если нет — добавляем
                    paragraphs_time_scr[idx] = end_time

        if UseTextModify:
            print("Проводим пакетное улучшение текста...")
            paragraphs = [result["clean_text"] for result in processed_paragraphs]
            

        # === Шаг 3: LLM разбивает на разделы (сохраняем оригинальные абзацы) ===
        print("Отправляем текст в LLM для разбиения на разделы...")
        sections = get_sections_from_llm(paragraphs, client=self.client)

        # Преобразуем в полные диапазоны без пропусков
        if sections:
            sections.sort(key=lambda x: x['start_par'])
            starts = [s['start_par'] for s in sections]
            starts.append(len(paragraphs) + 1)
            full_sections = []
            for i, sec in enumerate(sections):
                full_sections.append({
                    'title': sec['title'],
                    'start_par': sec['start_par'],
                    'end_par': min(starts[i + 1] - 1, len(paragraphs))
                })
            sections = full_sections
        else:
            # fallback: один раздел на весь текст
            sections = [{'title': 'Документ', 'start_par': 1, 'end_par': len(paragraphs)}]

        # === Вставляем оглавление с таймкодами ===
        # Требование: один абзац "Таймкоды" со списком всех заголовков и времени начала.
        doc.add_heading("Таймкоды", level=1)
        p_tc = doc.add_paragraph()
        for i, sec in enumerate(sections):
            start_par = sec.get('start_par', 1)
            start_time = paragraphs_start_time.get(start_par, 0)
            line = f"{sec.get('title', 'Раздел')} — {format_seconds_hhmmss(start_time)}"
            p_tc.add_run(line)
            if i != len(sections) - 1:
                p_tc.add_run().add_break()

        # === Шаг 4: Формируем документ с разделами и картинками ===
        video_path = self.video_path
        current_paragraph_index = 0  # Считаем, сколько абзацев текста уже вставлено

        if video_path != "" and os.path.isfile(video_path):
            class_picture_description = picture_description()

            # --- Режим A: Есть упоминания "сейчас на экране" ---
            if paragraphs_time_scr:
                print("Вставляем текст с разделами и кадрами по упоминаниям.")
                requested_frames = {
                    paragraph_number: format_seconds_hhmmss(end_time)
                    for paragraph_number, end_time in paragraphs_time_scr.items()
                }
                extracted_frames = class_picture_description.save_frames_at_times(
                    video_path, requested_frames
                )
                for section in sections:
                    # Вставляем заголовок раздела
                    doc.add_heading(section['title'], level=1)

                    # Вставляем абзацы этого раздела
                    for par_num in range(section['start_par'], section['end_par'] + 1):
                        if par_num <= len(paragraphs):
                            current_paragraph_index += 1
                            para_text = paragraphs[par_num - 1]
                            doc.add_paragraph('\t' + para_text)

                            # Проверяем, нужно ли вставить картинку ПОСЛЕ этого абзаца
                            if current_paragraph_index in paragraphs_time_scr:
                                formatted_time = requested_frames[current_paragraph_index]
                                frame_at_time = extracted_frames.get(current_paragraph_index)
                                if frame_at_time:
                                    doc.add_picture(frame_at_time, width=Mm(165))
                                else:
                                    logging.warning(
                                        "Кадр для таймкода %s не будет добавлен в DOCX.",
                                        formatted_time,
                                    )

            # --- Режим B: Нет упоминаний — равномерные кадры ---
            else:
                print("Нет упоминаний. Добавляем 5 равномерных кадров.")
                try:
                    total_duration = data['segments'][-1]['end']
                except (IndexError, KeyError, TypeError):
                    raise ValueError("Не удалось определить длительность видео.")

                time_stamps = [total_duration * i / 6 for i in range(1, 6)]
                requested_frames = {}
                for i, t in enumerate(time_stamps):
                    total_seconds = int(t)
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    formatted_time = f"{hours:02}:{minutes:02}:{seconds:02}"
                    requested_frames[i] = formatted_time
                extracted_frames = class_picture_description.save_frames_at_times(
                    video_path, requested_frames
                )
                frame_paths = []
                for i, formatted_time in requested_frames.items():
                    frame_path = extracted_frames.get(i)
                    if not frame_path:
                        logging.warning(
                            "Кадр для таймкода %s не будет добавлен в DOCX.",
                            formatted_time,
                        )
                        continue
                    frame_paths.append(frame_path)

                # Определяем, после каких **общих** абзацев вставлять картинки
                total_paragraphs = len(paragraphs)
                image_positions = []
                num_images = len(frame_paths)
                for i in range(1, num_images + 1):
                    pos = int(round((i / (num_images + 1)) * total_paragraphs))
                    pos = max(1, min(pos, total_paragraphs))
                    image_positions.append(pos)

                # Вставляем разделы и картинки
                for section in sections:
                    doc.add_heading(section['title'], level=1)
                    for par_num in range(section['start_par'], section['end_par'] + 1):
                        if par_num <= len(paragraphs):
                            current_paragraph_index += 1
                            para_text = paragraphs[par_num - 1]
                            doc.add_paragraph('\t' + para_text)

                            if current_paragraph_index in image_positions:
                                img_idx = image_positions.index(current_paragraph_index)
                                doc.add_picture(frame_paths[img_idx], width=Mm(165))

        else:
            # Режим C: Только текст
            for section in sections:
                doc.add_heading(section['title'], level=1)
                for par_num in range(section['start_par'], section['end_par'] + 1):
                    if par_num <= len(paragraphs):
                        para_text = paragraphs[par_num - 1]
                        doc.add_paragraph('\t' + para_text)

        # === Шаг 5: Сохранение ===
        docx_file_path = os.path.splitext(json_file_path)[0] + '.docx'
        doc.save(docx_file_path)
        print(f"Документ с разделами сохранён: {docx_file_path}")
        return docx_file_path
