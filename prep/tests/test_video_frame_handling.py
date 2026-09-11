import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PREP_DIR = Path(__file__).resolve().parents[1]
if str(PREP_DIR) not in sys.path:
    sys.path.insert(0, str(PREP_DIR))

import create_file.create_docx as create_docx_module  # noqa: E402
import picture_description.picture_description as picture_module  # noqa: E402


class VideoFrameHandlingTests(unittest.TestCase):
    def test_timestamp_beyond_video_is_clamped_to_last_frame(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.get.side_effect = lambda prop: {
            picture_module.cv2.CAP_PROP_FRAME_COUNT: 100,
            picture_module.cv2.CAP_PROP_FPS: 10,
        }[prop]
        frame = Mock()
        frame.shape = (720, 1280, 3)
        capture.read.return_value = (True, frame)

        with patch.object(picture_module.cv2, "VideoCapture", return_value=capture), \
                patch.object(picture_module.cv2, "imwrite", return_value=True):
            result = picture_module.picture_description().save_frame_at_time(
                "video.mp4", "00:00:15"
            )

        self.assertIsNotNone(result)
        seek_position_ms = capture.set.call_args_list[0].args[1]
        self.assertAlmostEqual(seek_position_ms, 9900)
        capture.release.assert_called_once_with()

    def test_multiple_frames_open_video_once_and_keep_identifier_mapping(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.get.side_effect = lambda prop: {
            picture_module.cv2.CAP_PROP_FRAME_COUNT: 1000,
            picture_module.cv2.CAP_PROP_FPS: 10,
        }[prop]
        frame = Mock()
        frame.shape = (720, 1280, 3)
        capture.read.return_value = (True, frame)

        with patch.object(
            picture_module.cv2, "VideoCapture", return_value=capture
        ) as video_capture, patch.object(
            picture_module.cv2, "imwrite", return_value=True
        ):
            result = picture_module.picture_description().save_frames_at_times(
                "video.mp4", {7: "00:00:20", 3: "00:00:05", 9: "00:00:30"}
            )

        self.assertEqual(set(result), {3, 7, 9})
        video_capture.assert_called_once_with("video.mp4")
        self.assertEqual(capture.read.call_count, 3)
        capture.release.assert_called_once_with()

    def test_missing_optional_frame_does_not_abort_docx_creation(self):
        fake_document = Mock()
        paragraph_builder = Mock()
        paragraph_builder.get_text_to_paragraphs_table.return_value = [
            ("Текст абзаца", 416.26)
        ]
        frame_extractor = Mock()
        frame_extractor.save_frames_at_times.return_value = {}
        fake_client = Mock()

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "transcription.json"
            json_path.write_text(
                json.dumps({
                    "full_text": "Текст абзаца",
                    "segments": [{"text": "Текст абзаца.", "end": 416.26}],
                }),
                encoding="utf-8",
            )
            video_path = Path(temp_dir) / "video.mp4"
            video_path.write_bytes(b"video")

            with patch.object(create_docx_module, "Document", return_value=fake_document), \
                    patch.object(
                        create_docx_module,
                        "text_to_paragraphs",
                        return_value=paragraph_builder,
                    ), patch.object(
                        create_docx_module,
                        "process_paragraphs_in_batches",
                        return_value=[{
                            "number": 1,
                            "clean_text": "Текст абзаца",
                            "image_required": True,
                        }],
                    ), patch.object(
                        create_docx_module,
                        "get_sections_from_llm",
                        return_value=[{
                            "title": "Документ",
                            "start_par": 1,
                            "end_par": 1,
                        }],
                    ), patch.object(
                        create_docx_module,
                        "picture_description",
                        return_value=frame_extractor,
                    ):
                result = create_docx_module.create_docx(
                    str(json_path), str(video_path), client=fake_client
                ).get_docx()

        self.assertTrue(result.endswith("transcription.docx"))
        fake_document.add_picture.assert_not_called()
        fake_document.save.assert_called_once()

    def test_uniform_frames_are_inserted_from_extracted_paths_without_copy(self):
        fake_document = Mock()
        paragraph_builder = Mock()
        paragraphs_table = [(f"Абзац {i}", float(i)) for i in range(1, 11)]
        paragraph_builder.get_text_to_paragraphs_table.return_value = paragraphs_table
        processed = [
            {"number": i, "clean_text": text, "image_required": False}
            for i, (text, _) in enumerate(paragraphs_table, start=1)
        ]
        extracted = {i: f"extracted_{i}.jpg" for i in range(5)}
        frame_extractor = Mock()
        frame_extractor.save_frames_at_times.return_value = extracted

        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "transcription.json"
            json_path.write_text(
                json.dumps({
                    "full_text": "Текст",
                    "segments": [{"text": "Текст.", "end": 60.0}],
                }),
                encoding="utf-8",
            )
            video_path = Path(temp_dir) / "video.mp4"
            video_path.write_bytes(b"video")

            with patch.object(create_docx_module, "Document", return_value=fake_document), \
                    patch.object(
                        create_docx_module, "text_to_paragraphs", return_value=paragraph_builder
                    ), patch.object(
                        create_docx_module,
                        "process_paragraphs_in_batches",
                        return_value=processed,
                    ), patch.object(
                        create_docx_module,
                        "get_sections_from_llm",
                        return_value=[{"title": "Документ", "start_par": 1, "end_par": 10}],
                    ), patch.object(
                        create_docx_module, "picture_description", return_value=frame_extractor
                    ):
                create_docx_module.create_docx(
                    str(json_path), str(video_path), client=Mock()
                ).get_docx()

        inserted_paths = [call.args[0] for call in fake_document.add_picture.call_args_list]
        self.assertEqual(inserted_paths, list(extracted.values()))
        frame_extractor.save_frames_at_times.assert_called_once()


if __name__ == "__main__":
    unittest.main()
