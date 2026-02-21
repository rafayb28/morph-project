"""Data models for the drone decision engine.

All input/output contracts are defined here using Pydantic for validation
and easy JSON serialization. These models mirror the CV module's output
format so plugging in the real pipeline is a drop-in replacement.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class PriorityMode(str, Enum):
    SAFETY = "safety"
    CROWD = "crowd"
    THEFT = "theft"
    GENERAL = "general"


class ActionType(str, Enum):
    MOVE = "MOVE"
    HOVER = "HOVER"
    ZOOM = "ZOOM"
    TRACK = "TRACK"
    ORBIT = "ORBIT"
    ASCEND = "ASCEND"
    DESCEND = "DESCEND"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NotifyTarget(str, Enum):
    EVENT_STAFF = "event_staff"
    SECURITY = "security"
    AUTHORITIES = "authorities"


# ── Input models ─────────────────────────────────────────────────────────────

class OperatorInstruction(BaseModel):
    text: str
    priority_mode: PriorityMode = PriorityMode.GENERAL


class DroneState(BaseModel):
    position_px: tuple[int, int]
    altitude_ft: float = 100.0
    heading_deg: float = 0.0
    zoom_level: float = 1.0


class Polygon(BaseModel):
    """Simple polygon as a list of (x, y) vertices in top-down pixel coords."""
    vertices: list[tuple[int, int]]


class SceneContext(BaseModel):
    scene_id: str
    topdown_media_path: str
    timestamp: datetime = Field(default_factory=datetime.now)
    venue_map_scale_ft_per_px: float | None = None
    restricted_zones: list[Polygon] | None = None
    drone_state: DroneState


class ObjectOfInterest(BaseModel):
    object_id: str
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    crop_media_path: str
    topdown_bbox: tuple[int, int, int, int]  # x, y, w, h
    topdown_center: tuple[int, int]
    track_id: str | None = None
    risk_hints: dict[str, float] = Field(default_factory=dict)
    notes: str | None = None


class DecisionInput(BaseModel):
    """Top-level payload combining all inputs for one decision cycle."""
    scene: SceneContext
    objects: list[ObjectOfInterest]
    instruction: OperatorInstruction


# ── Output models ────────────────────────────────────────────────────────────

class ScoredObject(BaseModel):
    """An ObjectOfInterest annotated with computed risk score and breakdown."""
    object: ObjectOfInterest
    risk_score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    matched_keywords: list[str] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    rank: int
    action_type: ActionType
    parameters: str
    target_object_id: str | None = None
    rationale: str


class Alert(BaseModel):
    severity: Severity
    notify: list[NotifyTarget]
    object_id: str | None = None
    reason: str
    next_steps: str


class Assumption(BaseModel):
    text: str


class DecisionOutput(BaseModel):
    summary: list[str]
    actions: list[RecommendedAction]
    alerts: list[Alert]
    assumptions: list[Assumption]
