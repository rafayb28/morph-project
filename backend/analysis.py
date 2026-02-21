from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime
from functools import partial

from fastapi import WebSocket

from backend.camera import camera
from backend.config import settings
from backend.detector import detector
from backend.models import DetectionResult, WSMessageType, WSOutgoing

log = logging.getLogger(__name__)


class AnalysisPipeline:
    """Background detection loop: grabs frames, runs YOLO, updates the
    annotated camera feed, and broadcasts results via WebSocket."""

    def __init__(self) -> None:
        self._prompt: str = ""
        self._clients: set[WebSocket] = set()
        self._history: deque[DetectionResult] = deque(maxlen=settings.max_history)
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_result: DetectionResult | None = None

    # -- prompt management ------------------------------------------------

    @property
    def prompt(self) -> str:
        return self._prompt

    @prompt.setter
    def prompt(self, value: str) -> None:
        self._prompt = value

    # -- WebSocket client management --------------------------------------

    def register(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def unregister(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    # -- history / state --------------------------------------------------

    @property
    def last_result(self) -> DetectionResult | None:
        return self._last_result

    @property
    def history(self) -> list[DetectionResult]:
        return list(self._history)

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

    # -- core loop --------------------------------------------------------

    async def _loop(self) -> None:
        log.info(
            "Detection pipeline started (interval=%.2fs, model=%s)",
            settings.detection_interval,
            settings.yolo_model,
        )
        loop = asyncio.get_running_loop()

        while self._running:
            await asyncio.sleep(settings.detection_interval)

            if not camera.is_running:
                continue

            frame = camera.get_raw_frame()
            if frame is None:
                continue

            # Run YOLO in a thread so we don't block the event loop
            result, annotated = await loop.run_in_executor(
                None, partial(detector.detect, frame, self._prompt)
            )

            result.timestamp = datetime.utcnow()
            self._last_result = result
            self._history.append(result)

            # Push annotated frame back to the camera for the MJPEG stream
            camera.set_annotated_frame(annotated)

            await self._broadcast(result)

    async def _broadcast(self, result: DetectionResult) -> None:
        msg = WSOutgoing(
            type=WSMessageType.DETECTION_RESULT,
            payload=result.model_dump(mode="json"),
        )
        raw = msg.model_dump_json()

        stale: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_text(raw)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self._clients.discard(ws)


pipeline = AnalysisPipeline()
