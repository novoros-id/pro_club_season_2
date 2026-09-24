import sys
import tempfile
import unittest
import importlib
from pathlib import Path
from unittest.mock import Mock, patch


PREP_DIR = Path(__file__).resolve().parents[1]
if str(PREP_DIR) not in sys.path:
    sys.path.insert(0, str(PREP_DIR))

try:
    prepare_module = importlib.import_module("prepare_files.prepare_files")
except ModuleNotFoundError as exc:
    if exc.name != "ffmpeg":
        raise
    ffmpeg_stub = Mock()
    ffmpeg_stub.Error = Exception
    with patch.dict(sys.modules, {"ffmpeg": ffmpeg_stub}):
        prepare_module = importlib.import_module("prepare_files.prepare_files")


class PrepareFilesOptimizationTests(unittest.TestCase):
    def test_suitable_short_h264_mp4_is_reused(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.mp4"
            source.write_bytes(b"video")
            processor = prepare_module.prepare_files(str(source))
            media_info = {
                "streams": [
                    {"codec_type": "video", "codec_name": "h264"},
                    {"codec_type": "audio", "codec_name": "aac"},
                ],
                "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "60"},
            }
            with patch.object(processor, "_probe_media", return_value=media_info), \
                    patch.object(processor, "convert_to_mp4_h264") as convert, \
                    patch.object(
                        processor, "extract_clean_audio", return_value="final.wav"
                    ) as extract:
                result = processor.process_file()

        self.assertEqual(result, {"video": str(source), "audio": "final.wav"})
        convert.assert_not_called()
        extract.assert_called_once()

    def test_audio_filter_chain_has_one_ffmpeg_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "source.wav"
            source.write_bytes(b"audio")
            output = Path(temp_dir) / "final.wav"
            processor = prepare_module.prepare_files(str(source))
            input_stream = Mock()
            filter_stream = Mock()
            input_stream.audio = filter_stream
            filter_stream.filter_.return_value = filter_stream
            output_stream = Mock()
            output_stream.overwrite_output.return_value = output_stream

            with patch.object(
                prepare_module.ffmpeg, "input", return_value=input_stream
            ), patch.object(
                prepare_module.ffmpeg, "output", return_value=output_stream
            ) as ffmpeg_output:
                result = processor.clean_audio(str(output))

        self.assertEqual(result, str(output))
        self.assertEqual(filter_stream.filter_.call_count, 3)
        output_stream.run.assert_called_once_with(
            capture_stdout=True, capture_stderr=True
        )
        ffmpeg_output.assert_called_once_with(
            filter_stream, str(output), ac=1, ar=16000,
            acodec="pcm_s16le", format="wav",
        )


if __name__ == "__main__":
    unittest.main()
