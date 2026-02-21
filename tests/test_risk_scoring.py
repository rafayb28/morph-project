"""Tests for the risk scoring module."""

from __future__ import annotations

import pytest

from decision_engine.instruction_parser import parse_instruction
from decision_engine.models import DroneState, ObjectOfInterest, SceneContext
from decision_engine.risk_scoring import score_all_objects, score_object


def _make_scene(**overrides) -> SceneContext:
    defaults = dict(
        scene_id="test-scene",
        topdown_media_path="/tmp/test.jpg",
        timestamp="2026-02-20T12:00:00",
        drone_state=DroneState(position_px=(500, 500), altitude_ft=100.0),
    )
    defaults.update(overrides)
    return SceneContext(**defaults)


def _make_object(**overrides) -> ObjectOfInterest:
    defaults = dict(
        object_id="obj-test",
        label="person",
        confidence=0.9,
        crop_media_path="/tmp/crop.jpg",
        topdown_bbox=(100, 100, 30, 50),
        topdown_center=(115, 125),
    )
    defaults.update(overrides)
    return ObjectOfInterest(**defaults)


class TestScoreObject:
    def test_weapon_scores_higher_than_person(self):
        scene = _make_scene()
        parsed = parse_instruction("")
        weapon = _make_object(object_id="w", label="weapon?", confidence=0.8)
        person = _make_object(object_id="p", label="person", confidence=0.9)
        sw = score_object(weapon, scene, parsed)
        sp = score_object(person, scene, parsed)
        assert sw.risk_score > sp.risk_score

    def test_high_confidence_scores_higher(self):
        scene = _make_scene()
        parsed = parse_instruction("")
        high = _make_object(object_id="h", label="fight", confidence=0.95)
        low = _make_object(object_id="l", label="fight", confidence=0.3)
        sh = score_object(high, scene, parsed)
        sl = score_object(low, scene, parsed)
        assert sh.risk_score > sl.risk_score

    def test_instruction_boost_increases_score(self):
        scene = _make_scene()
        no_match = parse_instruction("monitor the area")
        match = parse_instruction("watch for fights immediately")
        obj = _make_object(label="fight", confidence=0.8)
        s_no = score_object(obj, scene, no_match)
        s_yes = score_object(obj, scene, match)
        assert s_yes.risk_score > s_no.risk_score

    def test_proximity_increases_score(self):
        scene = _make_scene()
        parsed = parse_instruction("")
        near = _make_object(object_id="n", topdown_center=(490, 500))
        far = _make_object(object_id="f", topdown_center=(100, 100))
        sn = score_object(near, scene, parsed)
        sf = score_object(far, scene, parsed)
        assert sn.risk_score > sf.risk_score

    def test_risk_hints_add_bonus(self):
        scene = _make_scene()
        parsed = parse_instruction("")
        with_hints = _make_object(risk_hints={"aggressive": 0.9, "running": 0.5})
        without_hints = _make_object(risk_hints={})
        sw = score_object(with_hints, scene, parsed)
        sn = score_object(without_hints, scene, parsed)
        assert sw.risk_score > sn.risk_score


class TestScoreAllObjects:
    def test_returns_sorted_descending(self):
        scene = _make_scene()
        parsed = parse_instruction("watch for weapons")
        objects = [
            _make_object(object_id="a", label="person", confidence=0.9),
            _make_object(object_id="b", label="weapon?", confidence=0.8),
            _make_object(object_id="c", label="fight", confidence=0.7),
        ]
        scored = score_all_objects(objects, scene, parsed)
        scores = [s.risk_score for s in scored]
        assert scores == sorted(scores, reverse=True)

    def test_all_objects_scored(self):
        scene = _make_scene()
        parsed = parse_instruction("")
        objects = [_make_object(object_id=f"o{i}") for i in range(5)]
        scored = score_all_objects(objects, scene, parsed)
        assert len(scored) == 5
