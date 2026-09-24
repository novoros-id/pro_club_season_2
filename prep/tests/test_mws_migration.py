import importlib
import ast
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PREP_DIR = Path(__file__).resolve().parents[1]
if str(PREP_DIR) not in sys.path:
    sys.path.insert(0, str(PREP_DIR))

from create_file.create_docx import (  # noqa: E402
    _parse_paragraph_batch_response,
    image_is_required,
    parse_json_response,
    parse_sections_response,
    process_paragraphs_in_batches,
)
from model_api.config import MWSConfig  # noqa: E402
from model_api.mws_client import MWSAPIError, MWSClient  # noqa: E402
from transcription_audio.transcription import Transcription  # noqa: E402
from text_to_paragraphs.text_to_paragraphs import (  # noqa: E402
    cosine_similarity,
    text_to_paragraphs,
)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")


def client_with_session(session, batch_size=64):
    return MWSClient(
        MWSConfig(api_key="test-key", embedding_batch_size=batch_size),
        session=session,
        max_retries=0,
    )


class MWSClientTests(unittest.TestCase):
    def test_chat_content_is_extracted(self):
        session = Mock()
        session.request.return_value = FakeResponse(
            {"choices": [{"message": {"content": "готово"}}]}
        )
        self.assertEqual(client_with_session(session).generate_text("текст"), "готово")

    def test_embedding_order_is_restored_by_index(self):
        session = Mock()
        session.request.return_value = FakeResponse({"data": [
            {"index": 2, "embedding": [3, 0]},
            {"index": 0, "embedding": [1, 0]},
            {"index": 1, "embedding": [2, 0]},
        ]})
        result = client_with_session(session, batch_size=3).embed_texts(["a", "b", "c"])
        self.assertEqual(result, [[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])

    def test_embedding_dimensions_must_match(self):
        session = Mock()
        session.request.return_value = FakeResponse({"data": [
            {"index": 0, "embedding": [1, 0]},
            {"index": 1, "embedding": [1, 0, 0]},
        ]})
        with self.assertRaisesRegex(MWSAPIError, "размерность"):
            client_with_session(session).embed_texts(["a", "b"])

    def test_verbose_transcription_is_normalized(self):
        session = Mock()
        session.request.return_value = FakeResponse({
            "text": "Полный текст",
            "segments": [{"id": 9, "start": 1, "end": 2.5, "text": " Фраза "}],
        })
        handle, path = tempfile.mkstemp(suffix=".wav")
        os.close(handle)
        try:
            result = client_with_session(session).transcribe(path)
        finally:
            os.unlink(path)
        self.assertEqual(result["full_text"], "Полный текст")
        self.assertEqual(result["segments"], [
            {"id": 0, "start": 1.0, "end": 2.5, "text": "Фраза"}
        ])
        self.assertEqual(result["audio_file"], path)

    def test_transcription_request_uses_only_documented_mws_fields(self):
        session = Mock()
        session.request.return_value = FakeResponse({
            "text": "Текст",
            "segments": [{"start": 0, "end": 1, "text": "Текст"}],
        })
        handle, path = tempfile.mkstemp(suffix=".wav")
        os.close(handle)
        try:
            client_with_session(session).transcribe(path)
        finally:
            os.unlink(path)

        form_data = session.request.call_args.kwargs["data"]
        self.assertEqual(
            set(form_data), {"model", "language", "response_format"}
        )
        self.assertNotIn("prompt", form_data)

    def test_legacy_transcription_prompt_is_not_forwarded_to_mws(self):
        client = Mock()
        client.transcribe.return_value = {"full_text": "", "segments": []}

        result = Transcription(prompt="Термины 1С", client=client).transcribe("audio.wav")

        self.assertEqual(result, {"full_text": "", "segments": []})
        client.transcribe.assert_called_once_with("audio.wav", language="ru")

    def test_transcription_requires_segments(self):
        session = Mock()
        session.request.return_value = FakeResponse({"text": "Без сегментов"})
        handle, path = tempfile.mkstemp(suffix=".wav")
        os.close(handle)
        try:
            with self.assertRaisesRegex(MWSAPIError, "segment timestamps"):
                client_with_session(session).transcribe(path)
        finally:
            os.unlink(path)


class StructuredOutputTests(unittest.TestCase):
    def test_markdown_json_fence_is_removed(self):
        self.assertEqual(parse_json_response('```json\n{"ok": true}\n```'), {"ok": True})

    def test_image_required_boolean_is_parsed(self):
        client = Mock()
        client.generate_text.return_value = '```json\n{"image_required": true}\n```'
        self.assertTrue(image_is_required("Нажмите кнопку", client=client))

    def test_section_list_is_parsed(self):
        response = json.dumps({"sections": [
            {"start_paragraph": 1, "title": "Настройка"},
            {"start_paragraph": 4, "title": "Проверка"},
        ]})
        self.assertEqual(parse_sections_response(response), [(1, "Настройка"), (4, "Проверка")])

    def test_paragraph_batches_preserve_count_order_and_use_one_call_per_batch(self):
        client = Mock()
        client.config.paragraph_processing_batch_size = 2
        client.generate_text.side_effect = [
            json.dumps({"paragraphs": [
                {"number": 1, "clean_text": "Чистый 1", "image_required": False},
                {"number": 2, "clean_text": "Чистый 2", "image_required": True},
            ]}),
            json.dumps({"paragraphs": [
                {"number": 3, "clean_text": "Чистый 3", "image_required": False},
            ]}),
        ]

        result = process_paragraphs_in_batches(
            ["Текст 1", "Текст 2", "Текст 3"], client=client
        )

        self.assertEqual([row["number"] for row in result], [1, 2, 3])
        self.assertEqual([row["clean_text"] for row in result], [
            "Чистый 1", "Чистый 2", "Чистый 3",
        ])
        self.assertEqual(client.generate_text.call_count, 2)

    def test_paragraph_batch_rejects_missing_or_duplicate_numbers(self):
        response = json.dumps({"paragraphs": [
            {"number": 1, "clean_text": "Один", "image_required": False},
            {"number": 1, "clean_text": "Дубль", "image_required": True},
        ]})
        with self.assertRaisesRegex(ValueError, "повторяющийся"):
            _parse_paragraph_batch_response(response, [1, 2], True)

    def test_invalid_batch_falls_back_only_for_that_batch(self):
        client = Mock()
        client.config.paragraph_processing_batch_size = 2
        client.generate_text.side_effect = [
            "не JSON",
            json.dumps({"paragraphs": [
                {"number": 3, "clean_text": "Три", "image_required": False},
            ]}),
        ]
        fallback_rows = [
            {"number": 1, "clean_text": "Один", "image_required": False},
            {"number": 2, "clean_text": "Два", "image_required": True},
        ]
        with patch(
            "create_file.create_docx._fallback_paragraph_batch",
            return_value=fallback_rows,
        ) as fallback:
            result = process_paragraphs_in_batches(["1", "2", "3"], client=client)

        self.assertEqual([row["number"] for row in result], [1, 2, 3])
        fallback.assert_called_once()
        self.assertEqual(client.generate_text.call_count, 2)


class ParagraphTests(unittest.TestCase):
    def test_cosine_similarity_handles_neighbors_and_zero_vector(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [1, 0]), 1.0)
        self.assertEqual(cosine_similarity([0, 0], [1, 0]), 0.0)
        with self.assertRaises(ValueError):
            cosine_similarity([1], [1, 2])

    def test_paragraphs_keep_end_timestamps(self):
        client = Mock()
        client.config.paragraph_similarity_threshold = 0.7
        client.embed_texts.return_value = [[1, 0], [1, 0], [0, 1]]
        converter = text_to_paragraphs("", [
            ("Первое.", 1.0), ("Второе.", 2.0), ("Третье.", 3.0)
        ], client=client)
        result = converter.get_text_to_paragraphs_table(
            min_sents=1, min_words=100, max_sents=10, max_words=100
        )
        self.assertEqual(result, [("Первое. Второе.", 2.0), ("Третье.", 3.0)])


class ImportSafetyTests(unittest.TestCase):
    def test_entry_points_import_without_network_or_api_key(self):
        with patch.dict(os.environ, {"MWS_API_KEY": ""}, clear=False), patch(
            "requests.sessions.Session.request", side_effect=AssertionError("network call during import")
        ):
            for name in ("main", "bot", "web_app"):
                sys.modules.pop(name, None)
                importlib.import_module(name)

    def test_main_source_has_no_rag_flow(self):
        source = (PREP_DIR / "main.py").read_text(encoding="utf-8").lower()
        for forbidden in ("documentchunker", "ragindexer", "as_documents", "create_rag"):
            self.assertNotIn(forbidden, source)

    def test_supported_code_has_no_local_model_backend_imports(self):
        forbidden_roots = {
            "chromadb",
            "huggingface_hub",
            "langchain",
            "sentence_transformers",
            "torch",
            "transformers",
            "whisper",
        }
        violations = []
        for path in PREP_DIR.rglob("*.py"):
            if "tests" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = {node.module.split(".")[0]}
                else:
                    continue
                for root in roots & forbidden_roots:
                    violations.append(f"{path.relative_to(PREP_DIR)}: {root}")
        self.assertEqual(violations, [])


class LocalVideoTests(unittest.TestCase):
    def test_video_source_mode_is_read_and_validated(self):
        import web_app

        with patch.dict(os.environ, {"VIDEO_SOURCE_MODE": " LOCAL "}):
            self.assertEqual(web_app.get_video_source_mode(), "local")
        with patch.dict(os.environ, {"VIDEO_SOURCE_MODE": "ftp"}):
            with self.assertRaisesRegex(ValueError, "local или url"):
                web_app.get_video_source_mode()

    def test_local_video_list_contains_only_supported_files(self):
        import web_app

        with tempfile.TemporaryDirectory(prefix="Видео каталог ") as source_dir:
            root = Path(source_dir)
            expected = set()
            for extension in (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"):
                filename = f"Запись {extension[1:]}{extension.upper()}"
                (root / filename).write_bytes(b"video")
                expected.add(filename)
            (root / "заметки.txt").write_text("text", encoding="utf-8")
            (root / "Вложенная папка").mkdir()
            (root / "Вложенная папка" / "демо.webm").write_bytes(b"video")
            expected.add("Вложенная папка/демо.webm")

            self.assertEqual(set(web_app.list_local_videos(root)), expected)

    def test_local_path_cannot_escape_configured_directory(self):
        import web_app

        with tempfile.TemporaryDirectory() as parent_dir:
            parent = Path(parent_dir)
            source_dir = parent / "allowed"
            source_dir.mkdir()
            outside = parent / "outside.mp4"
            outside.write_bytes(b"video")

            with self.assertRaisesRegex(ValueError, "вне LOCAL_VIDEO_DIR"):
                web_app.resolve_local_video_path(source_dir, "../outside.mp4")

    def test_local_video_bypasses_downloaders(self):
        import main

        with tempfile.TemporaryDirectory() as source_dir, tempfile.TemporaryDirectory() as user_dir:
            path = Path(source_dir) / "Видео с пробелами.mp4"
            path.write_bytes(b"video-data")
            with patch.dict(os.environ, {"VIDEO_SOURCE_MODE": "local"}), patch.object(
                main, "_process_saved_video", return_value="result.docx"
            ) as process:
                self.assertEqual(main.process_local_video(path, user_dir), "result.docx")

            process.assert_called_once()
            staged_path = Path(process.call_args.args[0])
            self.assertNotEqual(staged_path, path)
            self.assertEqual(staged_path.read_bytes(), b"video-data")
            self.assertEqual(staged_path.name, path.name)
            self.assertTrue(staged_path.is_relative_to(Path(user_dir)))

    def test_local_mode_blocks_network_entry_point(self):
        import main

        fake_downloaders = Mock()
        with patch.dict(os.environ, {"VIDEO_SOURCE_MODE": "local"}), patch.dict(
            sys.modules,
            {"download_audio_video.download_audio_video": fake_downloaders},
        ):
            with self.assertRaisesRegex(ValueError, "Обработка ссылок отключена"):
                main.process_video("https://disk.yandex.ru/test", ".")

        self.assertEqual(fake_downloaders.mock_calls, [])

    def test_selected_local_file_is_passed_to_local_pipeline(self):
        import web_app

        with tempfile.TemporaryDirectory(prefix="Источник видео ") as source_dir, \
                tempfile.TemporaryDirectory(prefix="Рабочая папка ") as output_dir:
            source = Path(source_dir) / "Видео с пробелами.mp4"
            source.write_bytes(b"video-data")
            with patch.dict(os.environ, {
                "VIDEO_SOURCE_MODE": "local",
                "LOCAL_VIDEO_DIR": source_dir,
            }), patch.object(web_app, "USER_FOLDER", output_dir), patch.object(
                web_app,
                "process_local_video",
                return_value=os.path.join(output_dir, "result.docx"),
            ) as process, patch.object(
                web_app, "request", Mock(form={"local_video": source.name})
            ), patch.object(web_app, "_render_result", side_effect=lambda **value: value):
                response = web_app.api_local_video()

            self.assertEqual(response["filename"], "result.docx")
            process.assert_called_once_with(source.resolve(), output_dir)

    def test_url_endpoint_does_not_call_network_pipeline_in_local_mode(self):
        import web_app

        with patch.dict(os.environ, {"VIDEO_SOURCE_MODE": "local", "LOCAL_VIDEO_DIR": "."}), \
                patch.object(web_app, "process_video") as process, patch.object(
                    web_app,
                    "request",
                    Mock(form={"video_url": "https://disk.yandex.ru/test"}),
                ), patch.object(web_app, "_render_result", side_effect=lambda **value: value):
            response, status_code = web_app.api_video()

        self.assertIn("Обработка ссылок отключена", response["error"])
        self.assertEqual(status_code, 422)
        process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
