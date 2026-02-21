"""CV module intake adapter.

This is the bridge between your friend's CV output and the decision engine.
It reads a folder of CV results and builds a DecisionInput payload.

Expected folder structure from the CV module:
    cv_output/
    ├── scene.jpg (or .png, .mp4)       ← the full top-down image/video
    ├── detections.json                  ← list of detected objects (see below)
    └── crops/                           ← zoomed-in screenshots of each object
        ├── obj-001.jpg
        ├── obj-002.jpg
        └── ...

detections.json format (what your friend needs to produce):
    {
      "scene_id": "rally-2026-02-20-14h",
      "timestamp": "2026-02-20T14:00:00",
      "detections": [
        {
          "object_id": "obj-001",
          "label": "suspicious_person",
          "confidence": 0.82,
          "crop_filename": "obj-001.jpg",
          "bbox": [430, 340, 30, 40],
          "center": [445, 360],
          "track_id": "trk-101",
          "risk_hints": {"concealed_object": 0.7, "loitering": 0.8},
          "notes": "Individual near east barricade, hand in jacket."
        }
      ]
    }

That's it — the CV module just needs to drop files in that format.
Everything else (scoring, actions, alerts) is handled here.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from decision_engine.models import (
    DecisionInput,
    DroneState,
    ObjectOfInterest,
    OperatorInstruction,
    Polygon,
    PriorityMode,
    SceneContext,
)


def _find_scene_media(cv_dir: Path) -> str:
    """Find the top-down scene image/video in the CV output folder."""
    for pattern in ["scene.*", "topdown.*", "overview.*", "frame.*"]:
        matches = list(cv_dir.glob(pattern))
        if matches:
            return str(matches[0])
    # Fall back to any image/video in the root
    for ext in [".jpg", ".jpeg", ".png", ".mp4", ".avi"]:
        matches = list(cv_dir.glob(f"*{ext}"))
        if matches:
            return str(matches[0])
    return str(cv_dir / "scene.jpg")


def _find_crop(cv_dir: Path, crop_filename: str | None, object_id: str) -> str:
    """Resolve the path to a crop image."""
    crops_dir = cv_dir / "crops"
    if crop_filename:
        path = crops_dir / crop_filename
        if path.exists():
            return str(path)
    # Try common naming conventions
    for ext in [".jpg", ".png", ".jpeg"]:
        candidate = crops_dir / f"{object_id}{ext}"
        if candidate.exists():
            return str(candidate)
    return str(crops_dir / f"{object_id}.jpg")


def load_cv_output(
    cv_dir: str | Path,
    instruction_text: str,
    priority_mode: str = "general",
    drone_position_px: tuple[int, int] = (500, 500),
    drone_altitude_ft: float = 150.0,
    drone_heading_deg: float = 0.0,
    drone_zoom: float = 1.0,
    venue_scale_ft_per_px: float | None = None,
    restricted_zones: list[dict] | None = None,
) -> DecisionInput:
    """Load CV module output from a folder and build a DecisionInput.

    Args:
        cv_dir: Path to folder containing scene image + detections.json + crops/
        instruction_text: What the operator or event planner wants to watch for.
        priority_mode: One of "safety", "crowd", "theft", "general".
        drone_position_px: Current drone camera center in top-down pixel coords.
        drone_altitude_ft: Current drone altitude in feet.
        drone_heading_deg: Current drone heading in degrees.
        drone_zoom: Current camera zoom level.
        venue_scale_ft_per_px: Feet per pixel. None = use default (0.5 ft/px).
        restricted_zones: List of polygon dicts with "vertices" key, or None.

    Returns:
        DecisionInput ready to pass to run_pipeline().
    """
    cv_path = Path(cv_dir)
    detections_file = cv_path / "detections.json"

    if not detections_file.exists():
        raise FileNotFoundError(
            f"No detections.json found in {cv_path}. "
            f"Your friend's CV module needs to produce this file. "
            f"See cv_intake.py docstring for the expected format."
        )

    with open(detections_file) as f:
        cv_data = json.load(f)

    # Build scene context
    scene_media = _find_scene_media(cv_path)
    scene_id = cv_data.get("scene_id", cv_path.name)
    timestamp = cv_data.get("timestamp", datetime.now().isoformat())

    zones = None
    if restricted_zones:
        zones = [Polygon(vertices=z["vertices"]) for z in restricted_zones]

    scene = SceneContext(
        scene_id=scene_id,
        topdown_media_path=scene_media,
        timestamp=timestamp,
        venue_map_scale_ft_per_px=venue_scale_ft_per_px,
        restricted_zones=zones,
        drone_state=DroneState(
            position_px=drone_position_px,
            altitude_ft=drone_altitude_ft,
            heading_deg=drone_heading_deg,
            zoom_level=drone_zoom,
        ),
    )

    # Build objects from CV detections
    objects: list[ObjectOfInterest] = []
    for det in cv_data.get("detections", []):
        crop_path = _find_crop(
            cv_path,
            det.get("crop_filename"),
            det["object_id"],
        )

        bbox = tuple(det["bbox"])
        center = tuple(det.get("center", [
            bbox[0] + bbox[2] // 2,
            bbox[1] + bbox[3] // 2,
        ]))

        objects.append(ObjectOfInterest(
            object_id=det["object_id"],
            label=det["label"],
            confidence=det.get("confidence", 0.5),
            crop_media_path=crop_path,
            topdown_bbox=bbox,
            topdown_center=center,
            track_id=det.get("track_id"),
            risk_hints=det.get("risk_hints", {}),
            notes=det.get("notes"),
        ))

    # Build instruction
    instruction = OperatorInstruction(
        text=instruction_text,
        priority_mode=PriorityMode(priority_mode),
    )

    return DecisionInput(
        scene=scene,
        objects=objects,
        instruction=instruction,
    )
