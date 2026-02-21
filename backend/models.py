from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# -- Detection result models ----------------------------------------------

class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: BBox


class Alert(BaseModel):
    label: str
    confidence: float
    reason: str = ""


class DetectionResult(BaseModel):
    detections: list[Detection] = Field(default_factory=list)
    alerts: list[Alert] = Field(default_factory=list)
    object_counts: dict[str, int] = Field(default_factory=dict)
    total_people: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    prompt_used: str = ""


# -- WebSocket message models --------------------------------------------

class WSMessageType(str, Enum):
    SET_PROMPT = "set_prompt"
    DETECTION_RESULT = "detection_result"
    STATUS = "status"
    ERROR = "error"


class WSIncoming(BaseModel):
    type: WSMessageType
    payload: dict = Field(default_factory=dict)


class WSOutgoing(BaseModel):
    type: WSMessageType
    payload: dict = Field(default_factory=dict)
