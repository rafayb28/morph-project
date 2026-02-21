"""Parse free-form operator instructions into structured watchlist rules.

The parser scans instruction text for known threat keywords, assigns each
a priority weight (boosted by urgency modifiers), and returns a WatchlistRule
set that the risk scorer uses to boost matching objects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from decision_engine.config import (
    URGENCY_MODIFIERS,
    WATCHLIST_KEYWORDS,
)


@dataclass
class WatchlistRule:
    category: str           # e.g. "weapon", "fight", "unattended_bag"
    matched_phrases: list[str] = field(default_factory=list)
    weight: float = 1.0     # urgency-adjusted weight


@dataclass
class ParsedInstruction:
    raw_text: str
    rules: list[WatchlistRule] = field(default_factory=list)
    global_urgency: float = 1.0


def parse_instruction(text: str) -> ParsedInstruction:
    """Convert operator instruction text into a set of watchlist rules.

    Strategy:
    1. Detect urgency modifiers in the full text → global_urgency multiplier.
    2. For each keyword category, check if any synonym appears in the text.
       If so, create a WatchlistRule with weight = global_urgency.
    """
    lower = text.lower()
    result = ParsedInstruction(raw_text=text)

    # Detect urgency modifiers (use the highest one found)
    max_urgency = 1.0
    for phrase, multiplier in sorted(URGENCY_MODIFIERS.items(), key=lambda x: -len(x[0])):
        if phrase in lower:
            max_urgency = max(max_urgency, multiplier)
    result.global_urgency = max_urgency

    # Match keyword categories
    for category, synonyms in WATCHLIST_KEYWORDS.items():
        matched: list[str] = []
        for syn in sorted(synonyms, key=len, reverse=True):
            pattern = re.compile(re.escape(syn), re.IGNORECASE)
            if pattern.search(text):
                matched.append(syn)
        if matched:
            result.rules.append(WatchlistRule(
                category=category,
                matched_phrases=matched,
                weight=max_urgency,
            ))

    return result


def merge_instructions(base: ParsedInstruction, update: ParsedInstruction) -> ParsedInstruction:
    """Layer a new instruction on top of the existing one.

    Rules:
    - All existing watchlist rules are kept.
    - New rules are added (or replace if same category with higher weight).
    - Global urgency takes the max of both.
    - Raw text is concatenated so the full history is visible.
    """
    merged = ParsedInstruction(
        raw_text=f"{base.raw_text} | {update.raw_text}",
        global_urgency=max(base.global_urgency, update.global_urgency),
    )

    rules_by_cat: dict[str, WatchlistRule] = {}
    for rule in base.rules:
        rules_by_cat[rule.category] = rule
    for rule in update.rules:
        existing = rules_by_cat.get(rule.category)
        if existing is None or rule.weight > existing.weight:
            rules_by_cat[rule.category] = rule

    merged.rules = list(rules_by_cat.values())
    return merged


def instruction_matches_label(parsed: ParsedInstruction, label: str) -> tuple[bool, list[str]]:
    """Check whether an object's label is covered by any watchlist rule.

    Returns (matched: bool, list of matched category names).
    """
    label_lower = label.lower().replace("?", "")
    matched_categories: list[str] = []
    for rule in parsed.rules:
        if rule.category.lower().startswith(label_lower) or label_lower.startswith(rule.category.lower()):
            matched_categories.append(rule.category)
        for phrase in rule.matched_phrases:
            if phrase.lower() in label_lower or label_lower in phrase.lower():
                if rule.category not in matched_categories:
                    matched_categories.append(rule.category)
    return (len(matched_categories) > 0, matched_categories)
