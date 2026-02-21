"""Tests for the instruction parser module."""

from __future__ import annotations

import pytest

from decision_engine.instruction_parser import (
    instruction_matches_label,
    parse_instruction,
)


class TestParseInstruction:
    def test_basic_keyword_detection(self):
        result = parse_instruction("Watch for unattended bags and fights")
        categories = {r.category for r in result.rules}
        assert "unattended_bag" in categories
        assert "fight" in categories

    def test_weapon_keywords(self):
        result = parse_instruction("Alert if anyone is armed or carrying a knife")
        categories = {r.category for r in result.rules}
        assert "weapon" in categories

    def test_urgency_modifier_immediately(self):
        result = parse_instruction("Immediately report any weapons")
        assert result.global_urgency == 2.0

    def test_urgency_modifier_high_priority(self):
        result = parse_instruction("High priority: watch for fights")
        assert result.global_urgency == 1.5

    def test_no_urgency_modifier(self):
        result = parse_instruction("Monitor the area for bags")
        assert result.global_urgency <= 1.0

    def test_multiple_categories(self):
        result = parse_instruction(
            "Watch for overcrowding, unattended bags, fights, and weapons"
        )
        categories = {r.category for r in result.rules}
        assert len(categories) >= 3

    def test_empty_instruction(self):
        result = parse_instruction("")
        assert result.rules == []
        assert result.global_urgency == 1.0

    def test_restricted_zone_keywords(self):
        result = parse_instruction("Alert if anyone enters the restricted area")
        categories = {r.category for r in result.rules}
        assert "restricted_zone" in categories

    def test_medical_keywords(self):
        result = parse_instruction("Watch for injuries and collapsed individuals")
        categories = {r.category for r in result.rules}
        assert "medical_emergency" in categories


class TestInstructionMatchesLabel:
    def test_direct_match(self):
        parsed = parse_instruction("Watch for fights")
        matched, cats = instruction_matches_label(parsed, "fight")
        assert matched is True
        assert "fight" in cats

    def test_weapon_question_mark(self):
        parsed = parse_instruction("High priority on weapons")
        matched, cats = instruction_matches_label(parsed, "weapon?")
        assert matched is True

    def test_no_match(self):
        parsed = parse_instruction("Watch for fights")
        matched, cats = instruction_matches_label(parsed, "bag")
        assert matched is False

    def test_unattended_bag_match(self):
        parsed = parse_instruction("Watch for unattended bags")
        matched, cats = instruction_matches_label(parsed, "unattended_bag")
        assert matched is True
