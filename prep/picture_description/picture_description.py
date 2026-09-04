import os
import uuid
import logging

import cv2


logger = logging.getLogger(__name__)


class picture_description:
    """Legacy class name retained; the class now only extracts video frames."""

    def save_frame_at_time(self, video_path, time_str):
        hours, minutes, seconds = map(int, time_str.split(":"))
        total_seconds = hours * 3600 + minutes * 60 + seconds
        cap = cv2.VideoCapture(video_path)
        try:
            if not cap.isOpened():
                logger.warning("Не удалось открыть видеофайл: %s", video_path)
                return None
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0 or frame_count <= 0:
                logger.warning("Не удалось определить длительность видео: %s", video_path)
                return None

            # Timestamps produced by speech recognition can be slightly longer than
            # the video stream. Clamp them to the last real frame and retry a little
            # earlier if the decoder cannot seek precisely near the end of the file.
            last_frame_seconds = max(0.0, (frame_count - 1) / fps)
            seek_seconds = min(float(total_seconds), last_frame_seconds)
            frame = None
            for fallback_seconds in (0.0, 0.25, 0.5, 1.0, 2.0):
                candidate = max(0.0, seek_seconds - fallback_seconds)
                cap.set(cv2.CAP_PROP_POS_MSEC, candidate * 1000)
                ok, decoded_frame = cap.read()
                if ok and decoded_frame is not None:
                    frame = decoded_frame
                    break
            if frame is None:
                logger.warning(
                    "Не удалось извлечь кадр из %s для таймкода %s",
                    video_path,
                    time_str,
                )
                return None
            height, width = frame.shape[:2]
            if width > 1280:
                scale = 1280 / width
                frame = cv2.resize(frame, (1280, int(height * scale)), interpolation=cv2.INTER_AREA)
            output_path = os.path.join(
                os.path.dirname(video_path), f"screenshot_{uuid.uuid4().hex[:8]}.jpg"
            )
            if not cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90]):
                logger.warning("Не удалось сохранить извлечённый кадр: %s", output_path)
                return None
            return output_path
        finally:
            cap.release()
