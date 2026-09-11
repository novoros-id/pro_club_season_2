import subprocess
import os
import json
import ffmpeg

# Константа: максимальная длительность в секундах (например, 30 минуты)
MAX_DURATION = 1800  # 30 минуты


class prepare_files:
    def __init__(self, file_name):
        self.file_name = file_name

    def process_file(self):
        """
        Анализирует тип файла (видео или аудио), обрабатывает его соответствующим образом,
        сохраняет результаты рядом с исходным файлом и возвращает пути к ним.
        Если файл длиннее MAX_DURATION, он автоматически обрезается.

        :return: dict {'video': str or '', 'audio': str or ''}
        """
        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"Файл {self.file_name} не найден.")

        base_path, _ = os.path.splitext(self.file_name)
        dir_path = os.path.dirname(self.file_name)
        file_name_only = os.path.basename(base_path)

        media_info = self._probe_media()
        video_stream = next(
            (stream for stream in media_info.get("streams", [])
             if stream.get("codec_type") == "video"),
            None,
        )
        is_video = video_stream is not None

        result = {
            'video': '',
            'audio': ''
        }

        if is_video:
            # Keep an already suitable, short MP4 untouched. OpenCV only needs a
            # decodable H.264 video stream; transcription audio is produced directly
            # from the source below and does not require an AAC intermediate track.
            video_output = os.path.join(dir_path, f"{file_name_only}_PV.mp4")
            audio_output = os.path.join(dir_path, f"{file_name_only}_PA.wav")
            format_names = set(
                media_info.get("format", {}).get("format_name", "").split(",")
            )
            try:
                duration = float(media_info.get("format", {}).get("duration", 0))
            except (TypeError, ValueError):
                duration = 0
            suitable_video = (
                video_stream.get("codec_name") == "h264"
                and "mp4" in format_names
                and 0 < duration <= MAX_DURATION
            )
            result['video'] = (
                self.file_name
                if suitable_video
                else self.convert_to_mp4_h264(video_output, media_info=media_info)
            )
            result['audio'] = self.extract_clean_audio(audio_output)

        else:
            # Это аудиофайл — просто очищаем его (с обрезкой)
            audio_output = os.path.join(dir_path, f"{file_name_only}_PA.wav")
            cleaned_audio = self.clean_audio(audio_output)
            result['audio'] = cleaned_audio

        return result

    def _probe_media(self):
        try:
            output = subprocess.check_output([
                "ffprobe", "-v", "error", "-show_streams", "-show_format",
                "-of", "json", self.file_name,
            ], stderr=subprocess.STDOUT).decode("utf-8")
            return json.loads(output)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise RuntimeError("Ошибка при анализе файла через ffprobe.") from exc

    def check_nvenc_available(self):
        try:
            output = subprocess.check_output(["ffmpeg", "-encoders"], stderr=subprocess.DEVNULL).decode('utf-8')
            return 'h264_nvenc' in output
        except subprocess.CalledProcessError:
            return False

    def convert_to_mp4_h264(self, output_video_path=None, media_info=None):
        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"Файл {self.file_name} не найден.")

        base, _ = os.path.splitext(self.file_name)
        if output_video_path is None:
            output_path = base + "_converted.mp4"
        else:
            output_path = output_video_path

        media_info = media_info or self._probe_media()
        video_stream = next(
            (stream for stream in media_info.get("streams", [])
             if stream.get("codec_type") == "video"),
            None,
        )
        if video_stream is None:
            raise ValueError("Файл не содержит видеопоток.")
        codec = video_stream.get("codec_name")
        format_names = set(
            media_info.get("format", {}).get("format_name", "").split(",")
        )

        # Формируем команду ffmpeg
        cmd = ["ffmpeg", "-y", "-i", self.file_name]

        # Добавляем ограничение по времени
        cmd += ["-t", str(MAX_DURATION)]  # Обрезаем до MAX_DURATION секунд

        if codec == 'h264' and 'mp4' in format_names:
            print(f"Файл уже mp4+h264, но будет обрезан до {MAX_DURATION} секунд -> {output_path}")
            cmd += [
                "-map", "0:v:0", "-c:v", "copy", "-an",
                output_path
            ]
        else:
            use_nvenc = self.check_nvenc_available()
            if use_nvenc:
                print(f"GPU ускорение доступно. Конвертируем и обрезаем до {MAX_DURATION} секунд -> {output_path}")
                cmd += [
                    "-map", "0:v:0",
                    "-c:v", "h264_nvenc", "-preset", "fast", "-cq", "23",
                    "-an",
                    output_path
                ]
            else:
                print(f"GPU недоступно. Используем CPU, обрезаем до {MAX_DURATION} секунд -> {output_path}")
                cmd += [
                    "-map", "0:v:0",
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                    "-an",
                    output_path
                ]

        subprocess.run(cmd, check=True)
        print(f"Конвертация и обрезка завершены -> {output_path}")
        return output_path

    def extract_clean_audio(self, output_audio_path=None):
        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"Файл {self.file_name} не найден.")

        if output_audio_path is None:
            output_audio_path = os.path.splitext(self.file_name)[0] + "_clean.wav"
        return self._write_clean_audio(output_audio_path, lowpass_frequency=5000)

    def clean_audio(self, output_audio_path=None):
        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"Файл {self.file_name} не найден.")

        if output_audio_path is None:
            output_audio_path = os.path.splitext(self.file_name)[0] + "_clean.wav"
        return self._write_clean_audio(output_audio_path, lowpass_frequency=3000)

    def _write_clean_audio(self, output_audio_path, lowpass_frequency):
        """Decode, normalize and filter into the final STT WAV in one FFmpeg run."""
        try:
            stream = (
                ffmpeg.input(self.file_name, t=MAX_DURATION).audio
                .filter_("loudnorm", i=-16, tp=-1.5, lra=11)
                .filter_("highpass", f=200)
                .filter_("lowpass", f=lowpass_frequency)
            )
            (
                ffmpeg.output(
                    stream, output_audio_path, ac=1, ar=16000,
                    acodec="pcm_s16le", format="wav",
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            print(f"Аудио очищено и обрезано до {MAX_DURATION} секунд -> {output_audio_path}")
            return output_audio_path
        except ffmpeg.Error as e:
            print("Ошибка ffmpeg:")
            print("STDOUT:", e.stdout.decode() if e.stdout else "")
            print("STDERR:", e.stderr.decode() if e.stderr else "")
            raise RuntimeError(f"Ошибка при обработке аудио через ffmpeg: {e}")
