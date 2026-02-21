import threading
import time

import cv2
import numpy as np

from backend.config import settings


class Camera:
    """Thread-safe webcam capture with support for an annotated overlay frame."""

    def __init__(self, index: int | None = None):
        self._index = index if index is not None else settings.camera_index
        self._cap: cv2.VideoCapture | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._raw_frame: np.ndarray | None = None
        self._annotated_frame: np.ndarray | None = None

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._cap = cv2.VideoCapture(self._index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.frame_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.frame_height)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera at index {self._index}")
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    # -- frame access -----------------------------------------------------

    def get_raw_frame(self) -> np.ndarray | None:
        """Return a copy of the latest raw (unannotated) frame."""
        with self._lock:
            if self._raw_frame is None:
                return None
            return self._raw_frame.copy()

    def set_annotated_frame(self, frame: np.ndarray) -> None:
        """Store the latest frame with detection overlays drawn on it."""
        with self._lock:
            self._annotated_frame = frame

    def get_display_jpeg(self) -> bytes | None:
        """Return the annotated frame as JPEG bytes (falls back to raw if
        no annotated frame is available yet)."""
        with self._lock:
            frame = self._annotated_frame if self._annotated_frame is not None else self._raw_frame
            if frame is None:
                return None
            ok, buf = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality]
            )
            return buf.tobytes() if ok else None

    @property
    def is_running(self) -> bool:
        return self._running

    # -- internal ---------------------------------------------------------

    def _capture_loop(self) -> None:
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                break
            ok, frame = self._cap.read()
            if ok:
                with self._lock:
                    self._raw_frame = frame
            else:
                time.sleep(0.01)


camera = Camera()
