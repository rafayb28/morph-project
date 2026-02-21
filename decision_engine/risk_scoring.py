"""Risk scoring engine for objects of interest.

Computes a composite risk score per object based on:
- Label base weight (configurable)
- CV confidence
- Proximity to drone (closer → higher priority for action)
- Risk hints from CV (unattended, aggressive, etc.)
- Instruction match boost (operator asked about this category)
"""

from __future__ import annotations

import math

from decision_engine.config import (
    CONFIDENCE_EXPONENT,
    DEFAULT_HINT_WEIGHT,
    DEFAULT_LABEL_WEIGHT,
    HINT_WEIGHTS,
    INSTRUCTION_MATCH_BOOST,
    LABEL_BASE_WEIGHTS,
    PROXIMITY_DECAY_PX,
)
from decision_engine.instruction_parser import (
    ParsedInstruction,
    instruction_matches_label,
)
from decision_engine.models import ObjectOfInterest, SceneContext, ScoredObject


def _pixel_distance(a: tuple[int, int], b: tuple[int, int]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _proximity_factor(distance_px: float) -> float:
    """Exponential decay: objects far from the drone get a lower factor (0..1)."""
    return math.exp(-distance_px / PROXIMITY_DECAY_PX)


def score_object(
    obj: ObjectOfInterest,
    scene: SceneContext,
    parsed_instruction: ParsedInstruction,
) -> ScoredObject:
    breakdown: dict[str, float] = {}

    # 1. Label base weight
    label_key = obj.label.lower().strip()
    base = LABEL_BASE_WEIGHTS.get(label_key, DEFAULT_LABEL_WEIGHT)
    breakdown["label_base"] = base

    # 2. Confidence factor — raise to exponent so low confidence drops fast
    conf_factor = obj.confidence ** CONFIDENCE_EXPONENT
    breakdown["confidence_factor"] = round(conf_factor, 3)

    # 3. Proximity factor
    dist = _pixel_distance(obj.topdown_center, scene.drone_state.position_px)
    prox = _proximity_factor(dist)
    breakdown["proximity_factor"] = round(prox, 3)
    breakdown["distance_px"] = round(dist, 1)

    # 4. Risk hints bonus
    hint_bonus = 0.0
    for hint_name, hint_value in obj.risk_hints.items():
        w = HINT_WEIGHTS.get(hint_name, DEFAULT_HINT_WEIGHT)
        hint_bonus += w * hint_value
    breakdown["hint_bonus"] = round(hint_bonus, 3)

    # 5. Instruction match boost — check both label and risk hint names
    matched, matched_cats = instruction_matches_label(parsed_instruction, obj.label)
    for hint_name in obj.risk_hints:
        hint_matched, hint_cats = instruction_matches_label(parsed_instruction, hint_name)
        if hint_matched:
            matched = True
            matched_cats.extend(c for c in hint_cats if c not in matched_cats)
    inst_boost = INSTRUCTION_MATCH_BOOST * parsed_instruction.global_urgency if matched else 0.0
    breakdown["instruction_boost"] = round(inst_boost, 3)

    # Composite score
    score = (base * conf_factor * (0.5 + 0.5 * prox)) + hint_bonus + inst_boost
    breakdown["total"] = round(score, 3)

    return ScoredObject(
        object=obj,
        risk_score=round(score, 3),
        score_breakdown=breakdown,
        matched_keywords=matched_cats,
    )


def score_all_objects(
    objects: list[ObjectOfInterest],
    scene: SceneContext,
    parsed_instruction: ParsedInstruction,
) -> list[ScoredObject]:
    """Score every object and return sorted by risk (highest first)."""
    scored = [score_object(obj, scene, parsed_instruction) for obj in objects]
    scored.sort(key=lambda s: s.risk_score, reverse=True)
    return scored
