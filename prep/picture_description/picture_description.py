import os
import uuid
import logging

import cv2


logger = logging.getLogger(__name__)


class picture_description:
    """Legacy class name retained; the class now only extracts video frames."""

    def save_frame_at_time(self, video_path, time_str):
        """Backward-compatible single-frame wrapper."""
        return self.save_frames_at_times(video_path, {0: time_str}).get(0)

    def save_frames_at_times(self, video_path, timestamps):
        """Extract keyed timestamps while opening the video exactly once."""
        requested = list(timestamps.items())
        if not requested:
            return {}

        def seconds_from_timestamp(time_str):
            hours, minutes, seconds = map(int, time_str.split(":"))
            return hours * 3600 + minutes * 60 + seconds

        requested_with_seconds = [
            (identifier, time_str, seconds_from_timestamp(time_str))
            for identifier, time_str in requested
        ]
        cap = cv2.VideoCapture(video_path)
        try:
            if not cap.isOpened():
                logger.warning("Не удалось открыть видеофайл: %s", video_path)
                return {}
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0 or frame_count <= 0:
                logger.warning("Не удалось определить длительность видео: %s", video_path)
                return {}

            # Timestamps produced by speech recognition can be slightly longer than
            # the video stream. Clamp them to the last real frame and retry a little
            # earlier if the decoder cannot seek precisely near the end of the file.
            last_frame_seconds = max(0.0, (frame_count - 1) / fps)
            results = {}
            # Sparse frames can be far apart; sorted seeks avoid a full sequential
            # decode while keeping access monotonic within the one open capture.
            for identifier, time_str, total_seconds in sorted(
                requested_with_seconds, key=lambda item: item[2]
            ):
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
                    continue
                height, width = frame.shape[:2]
                if width > 1280:
                    scale = 1280 / width
                    frame = cv2.resize(
                        frame,
                        (1280, int(height * scale)),
                        interpolation=cv2.INTER_AREA,
                    )
                output_path = os.path.join(
                    os.path.dirname(video_path),
                    f"screenshot_{uuid.uuid4().hex[:8]}.jpg",
                )
                if not cv2.imwrite(
                    output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90]
                ):
                    logger.warning("Не удалось сохранить извлечённый кадр: %s", output_path)
                    continue
                results[identifier] = output_path
            return results
        finally:
            cap.release()
