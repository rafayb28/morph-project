from __future__ import annotations

import logging
from collections import Counter

import cv2
import numpy as np
from ultralytics import YOLO

from backend.config import settings
from backend.models import Alert, BBox, Detection, DetectionResult

log = logging.getLogger(__name__)

PERSON_LABEL = "person"

# Colour palette for bounding boxes (BGR)
COLOURS = [
    (255, 96, 96),
    (96, 255, 96),
    (96, 96, 255),
    (255, 255, 96),
    (255, 96, 255),
    (96, 255, 255),
    (200, 160, 96),
    (96, 200, 160),
]

ALERT_COLOUR = (0, 0, 255)   # red for alerts
DEFAULT_COLOUR = (0, 220, 0)  # green for normal detections


class Detector:
    """Local YOLOv8 object detector with prompt-based alerting."""

    def __init__(self) -> None:
        log.info("Loading YOLO model: %s", settings.yolo_model)
        self._model = YOLO(settings.yolo_model)
        self._class_names: dict[int, str] = self._model.names  # type: ignore[assignment]
        log.info("YOLO loaded — %d classes available", len(self._class_names))

    def detect(
        self, frame: np.ndarray, prompt: str = ""
    ) -> tuple[DetectionResult, np.ndarray]:
        """Run detection on a frame.

        Returns (structured result, annotated frame copy).
        """
        results = self._model(frame, conf=settings.confidence_threshold, verbose=False)
        result = results[0]

        detections: list[Detection] = []
        counts: Counter[str] = Counter()
        people = 0
        watch_tokens = _parse_prompt(prompt)

        annotated = frame.copy()

        for box in result.boxes:
            cls_id = int(box.cls[0])
            label = self._class_names.get(cls_id, f"class_{cls_id}")
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            detections.append(
                Detection(
                    label=label,
                    confidence=round(conf, 3),
                    bbox=BBox(x1=x1, y1=y1, x2=x2, y2=y2),
                )
            )
            counts[label] += 1
            if label == PERSON_LABEL:
                people += 1

            is_alert = _matches_prompt(label, watch_tokens)
            colour = ALERT_COLOUR if is_alert else DEFAULT_COLOUR
            _draw_box(annotated, label, conf, int(x1), int(y1), int(x2), int(y2), colour)

        alerts = _build_alerts(detections, watch_tokens)

        det_result = DetectionResult(
            detections=detections,
            alerts=alerts,
            object_counts=dict(counts),
            total_people=people,
            prompt_used=prompt,
        )
        return det_result, annotated


# -- prompt matching helpers ----------------------------------------------

def _parse_prompt(prompt: str) -> set[str]:
    """Extract lowercase tokens from the user's watch prompt."""
    if not prompt.strip():
        return set()
    return {tok.strip().lower() for tok in prompt.replace(",", " ").split() if tok.strip()}


def _matches_prompt(label: str, tokens: set[str]) -> bool:
    if not tokens:
        return False
    label_lower = label.lower()
    return any(tok in label_lower or label_lower in tok for tok in tokens)


def _build_alerts(detections: list[Detection], tokens: set[str]) -> list[Alert]:
    if not tokens:
        return []
    alerts: list[Alert] = []
    seen: set[str] = set()
    for det in detections:
        if _matches_prompt(det.label, tokens) and det.label not in seen:
            seen.add(det.label)
            alerts.append(
                Alert(
                    label=det.label,
                    confidence=det.confidence,
                    reason=f"Matched watch keyword in prompt",
                )
            )
    return alerts


# -- drawing helpers ------------------------------------------------------

def _draw_box(
    img: np.ndarray,
    label: str,
    conf: float,
    x1: int, y1: int, x2: int, y2: int,
    colour: tuple[int, int, int],
) -> None:
    cv2.rectangle(img, (x1, y1), (x2, y2), colour, 2)
    text = f"{label} {conf:.0%}"
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.rectangle(img, (x1, y1 - th - 8), (x1 + tw + 4, y1), colour, -1)
    cv2.putText(img, text, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)


detector = Detector()
