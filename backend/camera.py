import logging
import threading
import time

import cv2
import numpy as np

from backend.config import settings

log = logging.getLogger(__name__)

# Placeholder shown when the camera is unavailable
_PLACEHOLDER: np.ndarray | None = None


def _make_placeholder(w: int = 640, h: int = 360) -> np.ndarray:
    img = np.zeros((h, w, 3), dtype=np.uint8)
    text = "Camera unavailable"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thickness = 0.9, 2
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    x = (w - tw) // 2
    y = (h + th) // 2
    cv2.putText(img, text, (x, y), font, scale, (80, 80, 80), thickness)
    return img


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
        self._camera_ok = False
        self._consecutive_failures = 0

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return

        self._cap = self._open_capture()

        if self._cap is None or not self._cap.isOpened():
            log.error(
                "Could not open camera %s — the dashboard will show a placeholder. "
                "Make sure no other app is using the camera, then restart.",
                self._index,
            )
            self._camera_ok = False
        else:
            self._camera_ok = True
            log.info("Camera %s opened successfully", self._index)

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def _open_capture(self) -> cv2.VideoCapture | None:
        """Try DirectShow first (more reliable on Windows), then fall back."""
        for backend_name, backend in [("DirectShow", cv2.CAP_DSHOW), ("default", cv2.CAP_ANY)]:
            cap = cv2.VideoCapture(self._index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings.frame_width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.frame_height)
                log.info("Opened camera with %s backend", backend_name)
                return cap
            cap.release()
            log.warning("Failed to open camera with %s backend", backend_name)
        return None

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
        with self._lock:
            if self._raw_frame is None:
                return None
            return self._raw_frame.copy()

    def set_annotated_frame(self, frame: np.ndarray) -> None:
        with self._lock:
            self._annotated_frame = frame

    def get_display_jpeg(self) -> bytes | None:
        """Return the best available frame as JPEG bytes.
        Priority: annotated > raw > placeholder."""
        with self._lock:
            frame = self._annotated_frame if self._annotated_frame is not None else self._raw_frame
        if frame is None:
            frame = self._get_placeholder()
        ok, buf = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality]
        )
        return buf.tobytes() if ok else None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def camera_ok(self) -> bool:
        return self._camera_ok

    # -- internal ---------------------------------------------------------

    def _get_placeholder(self) -> np.ndarray:
        global _PLACEHOLDER
        if _PLACEHOLDER is None:
            _PLACEHOLDER = _make_placeholder()
        return _PLACEHOLDER

    def _capture_loop(self) -> None:
        MAX_FAILURES_BEFORE_RETRY = 150  # ~5 s at 30 fps pace

        while self._running:
            if self._cap is None or not self._cap.isOpened():
                time.sleep(1.0)
                log.info("Attempting to reopen camera %s ...", self._index)
                self._cap = self._open_capture()
                if self._cap is None or not self._cap.isOpened():
                    continue
                self._camera_ok = True
                self._consecutive_failures = 0

            ok, frame = self._cap.read()
            if ok:
                self._consecutive_failures = 0
                self._camera_ok = True
                with self._lock:
                    self._raw_frame = frame
                time.sleep(0.033)  # cap at ~30 fps to save CPU
            else:
                self._consecutive_failures += 1
                if self._consecutive_failures == 1:
                    log.warning("Camera frame grab failed — retrying")
                if self._consecutive_failures >= MAX_FAILURES_BEFORE_RETRY:
                    log.warning(
                        "Camera failed %d times in a row — releasing and retrying",
                        self._consecutive_failures,
                    )
                    self._camera_ok = False
                    if self._cap is not None:
                        self._cap.release()
                        self._cap = None
                    self._consecutive_failures = 0
                time.sleep(0.03)


camera = Camera()
