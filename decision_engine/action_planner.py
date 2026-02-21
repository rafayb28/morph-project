"""Generate ranked drone action recommendations from scored objects.

Translates risk-scored objects into concrete drone commands (MOVE, HOVER,
ZOOM, TRACK, ORBIT, ASCEND, DESCEND) with distances in feet. Actions are
sequenced realistically — e.g. stabilize before zoom, ascend when clusters
are detected.
"""

from __future__ import annotations

import math

from decision_engine.config import (
    DEFAULT_SCALE_FT_PER_PX,
    MAX_ACTIONS,
    SEVERITY_THRESHOLDS,
    TOP_N_OBJECTS,
)
from decision_engine.models import (
    ActionType,
    Assumption,
    RecommendedAction,
    SceneContext,
    ScoredObject,
    Severity,
)


def _severity_for_score(score: float) -> Severity:
    for threshold, sev in SEVERITY_THRESHOLDS:
        if score >= threshold:
            return Severity(sev)
    return Severity.LOW


def _px_to_ft(px: float, scale: float | None) -> tuple[float, bool]:
    """Convert pixel distance to feet. Returns (feet, used_default_scale)."""
    s = scale if scale is not None else DEFAULT_SCALE_FT_PER_PX
    return round(px * s, 1), scale is None


def _displacement(
    drone_px: tuple[int, int],
    target_px: tuple[int, int],
    scale: float | None,
) -> tuple[float, float, bool]:
    """Return (dx_ft, dy_ft, used_default) from drone to target."""
    dx_px = target_px[0] - drone_px[0]
    dy_px = target_px[1] - drone_px[1]
    s = scale if scale is not None else DEFAULT_SCALE_FT_PER_PX
    return round(dx_px * s, 1), round(dy_px * s, 1), scale is None


def _detect_cluster(scored: list[ScoredObject], radius_px: float = 150) -> bool:
    """Check if multiple high-risk objects are clustered together."""
    centers = [s.object.topdown_center for s in scored]
    if len(centers) < 3:
        return False
    count = 0
    for i in range(len(centers)):
        for j in range(i + 1, len(centers)):
            dist = math.hypot(centers[i][0] - centers[j][0], centers[i][1] - centers[j][1])
            if dist < radius_px:
                count += 1
    return count >= 3


def plan_actions(
    scored_objects: list[ScoredObject],
    scene: SceneContext,
) -> tuple[list[RecommendedAction], list[Assumption]]:
    """Produce a ranked list of drone actions + assumptions."""
    actions: list[RecommendedAction] = []
    assumptions: list[Assumption] = []
    rank = 0
    scale = scene.venue_map_scale_ft_per_px
    used_default = scale is None

    if used_default:
        assumptions.append(Assumption(
            text=f"No venue scale provided — assuming {DEFAULT_SCALE_FT_PER_PX} ft/px for movement conversions."
        ))

    top = scored_objects[:TOP_N_OBJECTS]

    # If objects form a cluster, recommend gaining altitude first
    if _detect_cluster(top):
        rank += 1
        actions.append(RecommendedAction(
            rank=rank,
            action_type=ActionType.ASCEND,
            parameters="ASCEND +30ft",
            target_object_id=None,
            rationale="Multiple objects clustered — gain altitude for wider field of view.",
        ))

    for so in top:
        severity = _severity_for_score(so.risk_score)
        obj = so.object
        dx_ft, dy_ft, _ = _displacement(scene.drone_state.position_px, obj.topdown_center, scale)
        dist_ft = round(math.hypot(dx_ft, dy_ft), 1)

        if severity in (Severity.CRITICAL, Severity.HIGH):
            # Move toward the object to maintain view
            rank += 1
            actions.append(RecommendedAction(
                rank=rank,
                action_type=ActionType.MOVE,
                parameters=f"MOVE dx={dx_ft:+.1f}ft dy={dy_ft:+.1f}ft (dist={dist_ft}ft)",
                target_object_id=obj.object_id,
                rationale=f"{severity.value} risk — reposition to maintain view of '{obj.label}' (score={so.risk_score}).",
            ))
            # Hover to stabilize before any zoom/track
            rank += 1
            actions.append(RecommendedAction(
                rank=rank,
                action_type=ActionType.HOVER,
                parameters="HOVER stabilize",
                target_object_id=obj.object_id,
                rationale="Stabilize position before tracking/zooming.",
            ))
            # Track the object
            rank += 1
            actions.append(RecommendedAction(
                rank=rank,
                action_type=ActionType.TRACK,
                parameters=f"TRACK object_id={obj.object_id}",
                target_object_id=obj.object_id,
                rationale=f"Lock tracking on '{obj.label}' for continuous monitoring.",
            ))

        elif severity == Severity.MEDIUM:
            # Move + zoom for better confirmation
            rank += 1
            actions.append(RecommendedAction(
                rank=rank,
                action_type=ActionType.MOVE,
                parameters=f"MOVE dx={dx_ft:+.1f}ft dy={dy_ft:+.1f}ft (dist={dist_ft}ft)",
                target_object_id=obj.object_id,
                rationale=f"MEDIUM risk — move closer to '{obj.label}' for confirmation (score={so.risk_score}).",
            ))
            rank += 1
            actions.append(RecommendedAction(
                rank=rank,
                action_type=ActionType.HOVER,
                parameters="HOVER stabilize",
                target_object_id=obj.object_id,
                rationale="Stabilize before zooming.",
            ))
            rank += 1
            actions.append(RecommendedAction(
                rank=rank,
                action_type=ActionType.ZOOM,
                parameters=f"ZOOM level={min(scene.drone_state.zoom_level + 1.0, 5.0):.1f}x",
                target_object_id=obj.object_id,
                rationale=f"Zoom in on '{obj.label}' for visual confirmation.",
            ))

        else:
            # LOW — just log & orbit if nearby
            if dist_ft < 50:
                rank += 1
                actions.append(RecommendedAction(
                    rank=rank,
                    action_type=ActionType.ORBIT,
                    parameters=f"ORBIT radius=20ft around object_id={obj.object_id}",
                    target_object_id=obj.object_id,
                    rationale=f"LOW risk — nearby '{obj.label}', orbit to keep in view.",
                ))

        if obj.confidence < 0.5:
            assumptions.append(Assumption(
                text=f"Object '{obj.object_id}' ({obj.label}) has low confidence ({obj.confidence:.0%}) — recommend human confirmation.",
            ))

        if len(actions) >= MAX_ACTIONS:
            assumptions.append(Assumption(
                text=f"Action list capped at {MAX_ACTIONS} — {len(scored_objects) - TOP_N_OBJECTS} lower-priority objects omitted.",
            ))
            break

    return actions, assumptions
