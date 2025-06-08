import subprocess
import os
import shutil
import ffmpeg

class prepare_files:

    # для конверации необходимо установить ffmpeg и ffprobe
    # использование 
    # convert_to_mp4_h264("path/to/your/video.avi") или convert_to_mp4_h264("video.mkv", "new_video.mp4")

    def __init__(self, file_name):
        self.file_name = file_name

    def check_nvenc_available(self):
        # Проверяет наличие поддержки h264_nvenc в ffmpeg
        try:
            output = subprocess.check_output(["ffmpeg", "-encoders"], stderr=subprocess.DEVNULL).decode('utf-8')
            return 'h264_nvenc' in output
        except subprocess.CalledProcessError:
            return False

    def convert_to_mp4_h264(self, output_video_path=None):
        #Конвертирует любое видео в .mp4 с кодеком H.264.
        #Использует GPU (h264_nvenc), если доступно.
        
        #:param input_path: путь к исходному видео
        #:param output_path: путь к выходному файлу (если None — создается автоматически)
        #:return: путь к сконвертированному файлу
        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"Файл {self.file_name} не найден.")

        # Генерация выходного имени файла
        if output_video_path is None:
            base, _ = os.path.splitext(self.file_name)
            output_path = base + "_converted.mp4"
        
        # Получение кодека видео
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

        # Если уже правильный формат
        if codec == 'h264' and ext == '.mp4':
            shutil.copy2(self.file_name, output_path)
            print(f"Файл уже mp4+h264. Копируем без перекодирования -> {output_path}")
            return output_path

        # Проверяем доступность NVENC
        use_nvenc = self.check_nvenc_available()

        if use_nvenc:
            print("Обнаружена поддержка h264_nvenc. Используем GPU для ускорения конвертации.")
            cmd = [
                "ffmpeg", "-y", "-hwaccel", "cuda", "-i", self.file_name,
                "-c:v", "h264_nvenc", "-preset", "fast", "-cq", "23",
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ]
        else:
            print("GPU ускорение недоступно. Используем CPU (libx264, ultrafast).")
            cmd = [
                "ffmpeg", "-y", "-i", self.file_name,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ]

        subprocess.run(cmd, check=True)
        print(f"Конвертация завершена -> {output_path}")
        return output_path
    
    def extract_clean_audio(self, output_audio_path=None):
        # Конвертация аудио из видео (с применением нормализации громкости и шумподавления)
        # для конверации необходимо установить ffmpeg и ffprobe
        # использование 
        # extract_clean_audio("path/to/your/video.avi") или extract_clean_audio("video.mkv", "output_audio.wav")
        # шумоподавление просто отсекает частоты, теоретически можно сложнее, но это самый простой вариант
        # может быть его вообще надо отключить
        # решить после тестов распознования

        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"Файл {self.file_name} не найден.")

        # Промежуточные файлы
        temp_raw_audio = os.path.splitext(self.file_name)[0] + "_temp_raw.wav"
        temp_normalized_audio = os.path.splitext(self.file_name)[0] + "_temp_normalized.wav"

        if output_audio_path is None:
            output_audio_path = os.path.splitext(self.file_name)[0] + "_clean.wav"

        try:
            # Шаг 1: Извлечь аудио из видео
            (
                ffmpeg
                .input(self.file_name)
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

            # Шаг 3: Применение шумоподавления (highpass + lowpass)
            (
                ffmpeg
                .input(temp_normalized_audio)
                .filter_("highpass", f=200)
                .filter_("lowpass", f=5000)
                .output(output_audio_path, ac=1, ar=16000, format="wav")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Удаляем временные файлы
            if os.path.exists(temp_raw_audio):
                os.remove(temp_raw_audio)
            if os.path.exists(temp_normalized_audio):
                os.remove(temp_normalized_audio)

            print(f"Аудио успешно извлечено и очищено -> {output_audio_path}")
            return output_audio_path

        except ffmpeg.Error as e:
            print("Ошибка ffmpeg:")
            print("STDOUT:", e.stdout.decode() if e.stdout else "")
            print("STDERR:", e.stderr.decode() if e.stderr else "")
            raise RuntimeError(f"Ошибка при обработке аудио через ffmpeg: {e}")
        
    def clean_audio(self, output_audio_path=None):

        # Очистка аудио из аудиоо (с применением нормализации громкости и шумподавления) 
        # для конверации необходимо установить ffmpeg и ffprobe использование extract_clean_audio("path/to/your/video.avi") 
        # или extract_clean_audio("video.mkv", "output_audio.wav") шумоподавление просто 
        # отсекает частоты, теоретически можно сложнее, но это самый простой вариант может 
        # быть его вообще надо отключить решить после тестов распознования

        if not os.path.exists(self.file_name):
            raise FileNotFoundError(f"Файл {self.file_name} не найден.")

        # Промежуточные файлы
        temp_raw_audio = os.path.splitext(self.file_name)[0] + "_temp_raw.wav"
        temp_normalized_audio = os.path.splitext(self.file_name)[0] + "_temp_normalized.wav"

        if output_audio_path is None:
            output_audio_path = os.path.splitext(self.file_name)[0] + "_clean.wav"

        try:
            # Шаг 1: Привести входное аудио к 16kHz и моно (если вдруг нет)
            (
                ffmpeg
                .input(self.file_name)
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

            # Шаг 3: Применение шумоподавления (highpass + lowpass)
            (
                ffmpeg
                .input(temp_normalized_audio)
                .filter_("highpass", f=200)
                .filter_("lowpass", f=3000)
                .output(output_audio_path, ac=1, ar=16000, format="wav")
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )

            # Удаляем временные файлы
            if os.path.exists(temp_raw_audio):
                os.remove(temp_raw_audio)
            if os.path.exists(temp_normalized_audio):
                os.remove(temp_normalized_audio)

            print(f"Аудио успешно очищено -> {output_audio_path}")
            return output_audio_path

        except ffmpeg.Error as e:
            print("Ошибка ffmpeg:")
            print("STDOUT:", e.stdout.decode() if e.stdout else "")
            print("STDERR:", e.stderr.decode() if e.stderr else "")
            raise RuntimeError(f"Ошибка при обработке аудио через ffmpeg: {e}")