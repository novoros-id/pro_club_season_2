import subprocess
import os
import shutil
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

        base_path, ext = os.path.splitext(self.file_name)
        dir_path = os.path.dirname(self.file_name)
        file_name_only = os.path.basename(base_path)

        # Проверяем, это видео или аудио
        try:
            output = subprocess.check_output([
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_type",
                "-of", "default=nw=1",
                self.file_name
            ], stderr=subprocess.STDOUT).decode('utf-8')
            is_video = 'video' in output
        except subprocess.CalledProcessError:
            is_video = False

        result = {
            'video': '',
            'audio': ''
        }

        if is_video:
            # Обработка видео: конвертация + извлечение аудио
            video_output = os.path.join(dir_path, f"{file_name_only}_PV.mp4")
            audio_output = os.path.join(dir_path, f"{file_name_only}_PA.wav")

            # Конвертируем видео (с обрезкой по MAX_DURATION внутри метода)
            converted_video = self.convert_to_mp4_h264(video_output)
            result['video'] = converted_video

            # Извлекаем аудио из обрезанного видео
            temp_self = prepare_files(converted_video)
            cleaned_audio = temp_self.extract_clean_audio(audio_output)
            result['audio'] = cleaned_audio

        else:
            # Это аудиофайл — просто очищаем его (с обрезкой)
            audio_output = os.path.join(dir_path, f"{file_name_only}_PA.wav")
            cleaned_audio = self.clean_audio(audio_output)
            result['audio'] = cleaned_audio

        return result

    def check_nvenc_available(self):
        try:
            output = subprocess.check_output(["ffmpeg", "-encoders"], stderr=subprocess.DEVNULL).decode('utf-8')
            return 'h264_nvenc' in output
        except subprocess.CalledProcessError:
            return False

    def convert_to_mp4_h264(self, output_video_path=None):
        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"Файл {self.file_name} не найден.")

        base, _ = os.path.splitext(self.file_name)
        if output_video_path is None:
            output_path = base + "_converted.mp4"
        else:
            output_path = output_video_path

        try:
            codec = subprocess.check_output([
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=nokey=1:noprint_wrappers=1",
                self.file_name
            ]).decode('utf-8').strip()
        except subprocess.CalledProcessError:
            raise RuntimeError("Ошибка при анализе файла через ffprobe.")

        ext = os.path.splitext(self.file_name)[1].lower()

        use_nvenc = self.check_nvenc_available()

        # Формируем команду ffmpeg
        cmd = ["ffmpeg", "-y", "-i", self.file_name]

        # Добавляем ограничение по времени
        cmd += ["-t", str(MAX_DURATION)]  # Обрезаем до MAX_DURATION секунд

        if codec == 'h264' and ext == '.mp4':
            # Даже если формат правильный, всё равно может быть нужно обрезать
            print(f"Файл уже mp4+h264, но будет обрезан до {MAX_DURATION} секунд -> {output_path}")
            cmd += [
                "-c:v", "copy",  # копируем без перекодирования
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ]
        else:
            if use_nvenc:
                print(f"GPU ускорение доступно. Конвертируем и обрезаем до {MAX_DURATION} секунд -> {output_path}")
                cmd += [
                    "-c:v", "h264_nvenc", "-preset", "fast", "-cq", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    output_path
                ]
            else:
                print(f"GPU недоступно. Используем CPU, обрезаем до {MAX_DURATION} секунд -> {output_path}")
                cmd += [
                    "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    output_path
                ]

        subprocess.run(cmd, check=True)
        print(f"Конвертация и обрезка завершены -> {output_path}")
        return output_path

    def extract_clean_audio(self, output_audio_path=None):
        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"Файл {self.file_name} не найден.")

        temp_raw_audio = os.path.splitext(self.file_name)[0] + "_temp_raw.wav"
        temp_normalized_audio = os.path.splitext(self.file_name)[0] + "_temp_normalized.wav"

        if output_audio_path is None:
            output_audio_path = os.path.splitext(self.file_name)[0] + "_clean.wav"

        try:
            # Шаг 1: Извлечь первые MAX_DURATION секунд аудио
            (
                ffmpeg
                .input(self.file_name, t=MAX_DURATION)  # Ограничиваем длительность
                .output(temp_raw_audio, ac=1, ar=16000, format="wav")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Шаг 2: Нормализация громкости
            (
                ffmpeg
                .input(temp_raw_audio)
                .filter_("loudnorm", i=-16, tp=-1.5, lra=11)
                .output(temp_normalized_audio, ac=1, ar=16000, format="wav")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Шаг 3: Шумоподавление
            (
                ffmpeg
                .input(temp_normalized_audio)
                .filter_("highpass", f=200)
                .filter_("lowpass", f=5000)
                .output(output_audio_path, ac=1, ar=16000, format="wav")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Удаление временных файлов
            for temp_file in [temp_raw_audio, temp_normalized_audio]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

            print(f"Аудио успешно извлечено, очищено и обрезано до {MAX_DURATION} секунд -> {output_audio_path}")
            return output_audio_path

        except ffmpeg.Error as e:
            print("Ошибка ffmpeg:")
            print("STDOUT:", e.stdout.decode() if e.stdout else "")
            print("STDERR:", e.stderr.decode() if e.stderr else "")
            raise RuntimeError(f"Ошибка при обработке аудио через ffmpeg: {e}")

    def clean_audio(self, output_audio_path=None):
        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"Файл {self.file_name} не найден.")

        temp_raw_audio = os.path.splitext(self.file_name)[0] + "_temp_raw.wav"
        temp_normalized_audio = os.path.splitext(self.file_name)[0] + "_temp_normalized.wav"

        if output_audio_path is None:
            output_audio_path = os.path.splitext(self.file_name)[0] + "_clean.wav"

        try:
            # Шаг 1: Привести к нужному формату и обрезать
            (
                ffmpeg
                .input(self.file_name, t=MAX_DURATION)  # Обрезка до MAX_DURATION
                .output(temp_raw_audio, ac=1, ar=16000, format="wav")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Шаг 2: Нормализация
            (
                ffmpeg
                .input(temp_raw_audio)
                .filter_("loudnorm", i=-16, tp=-1.5, lra=11)
                .output(temp_normalized_audio, ac=1, ar=16000, format="wav")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Шаг 3: Фильтрация шума
            (
                ffmpeg
                .input(temp_normalized_audio)
                .filter_("highpass", f=200)
                .filter_("lowpass", f=3000)
                .output(output_audio_path, ac=1, ar=16000, format="wav")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Удаление временных файлов
            for temp_file in [temp_raw_audio, temp_normalized_audio]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

            print(f"Аудио очищено и обрезано до {MAX_DURATION} секунд -> {output_audio_path}")
            return output_audio_path

        except ffmpeg.Error as e:
            print("Ошибка ffmpeg:")
            print("STDOUT:", e.stdout.decode() if e.stdout else "")
            print("STDERR:", e.stderr.decode() if e.stderr else "")
            raise RuntimeError(f"Ошибка при обработке аудио: {e}")