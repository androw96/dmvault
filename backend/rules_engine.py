from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class RulePattern:
    tag: str
    pattern: re.Pattern[str]
    playmode_status: str


PLAYMODE_READY = "playmode_ready"
PLAYMODE_PARTIAL = "playmode_partial"
PLAYMODE_PENDING = "playmode_pending"


RULE_PATTERNS: tuple[RulePattern, ...] = (
    RulePattern("shield_trigger", re.compile(r"\bshield\s*trigger\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("blocker", re.compile(r"\bblocker\b", re.I), PLAYMODE_PENDING),
    RulePattern("double_breaker", re.compile(r"\bdouble\s+breaker\b", re.I), PLAYMODE_READY),
    RulePattern("triple_breaker", re.compile(r"\btriple\s+breaker\b", re.I), PLAYMODE_READY),
    RulePattern("speed_attacker", re.compile(r"\bspeed\s+attacker\b", re.I), PLAYMODE_READY),
    RulePattern("charger", re.compile(r"\bcharger\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("evolution", re.compile(r"\bevolution\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("vortex_evolution", re.compile(r"\bvortex\s+evolution\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("tap_ability", re.compile(r"(?:\$tap|\btap ability\b)", re.I), PLAYMODE_PENDING),
    RulePattern("silent_skill", re.compile(r"\bsilent\s+skill\b", re.I), PLAYMODE_PENDING),
    RulePattern("wave_striker", re.compile(r"\bwave\s+striker\b", re.I), PLAYMODE_PENDING),
    RulePattern("survivor", re.compile(r"\bsurvivor\b", re.I), PLAYMODE_PENDING),
    RulePattern("metamorph", re.compile(r"\bmetamorph\b", re.I), PLAYMODE_PENDING),
    RulePattern("turbo_rush", re.compile(r"\bturbo\s+rush\b", re.I), PLAYMODE_PENDING),
    RulePattern("slayer", re.compile(r"\bslayer\b", re.I), PLAYMODE_PENDING),
    RulePattern("power_attacker", re.compile(r"\bpower\s+attacker\b", re.I), PLAYMODE_PENDING),
    RulePattern("stealth", re.compile(r"\bstealth\b", re.I), PLAYMODE_PENDING),
    RulePattern("cant_attack", re.compile(r"\bcan(?:not|'t)\s+attack\b", re.I), PLAYMODE_PENDING),
    RulePattern("cant_be_blocked", re.compile(r"\bcan(?:not|'t)\s+be\s+blocked\b", re.I), PLAYMODE_PENDING),
    RulePattern("destroy_effect", re.compile(r"\bdestroy\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("bounce_effect", re.compile(r"\breturn\b.+\bhand\b|\bowners'? hands?\b", re.I | re.S), PLAYMODE_PARTIAL),
    RulePattern("draw_effect", re.compile(r"\bdraw\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("discard_effect", re.compile(r"\bdiscard\b", re.I), PLAYMODE_PARTIAL),
    RulePattern("search_effect", re.compile(r"\bsearch\b.+\bdeck\b", re.I | re.S), PLAYMODE_PENDING),
    RulePattern("mana_ramp", re.compile(r"\bput\b.+\bmana zone\b", re.I | re.S), PLAYMODE_PARTIAL),
    RulePattern("shield_add", re.compile(r"\badd\b.+\bshields?\b|\bput\b.+\bshields?\b", re.I | re.S), PLAYMODE_PARTIAL),
    RulePattern("extra_turn", re.compile(r"\bextra\s+turn\b", re.I), PLAYMODE_PENDING),
    RulePattern("lose_condition", re.compile(r"\blose\s+the\s+game\b", re.I), PLAYMODE_PENDING),
)


def classify_card_rules(card) -> dict:
    text = f"{getattr(card, 'name', '')} {getattr(card, 'type', '')} {getattr(card, 'race_label', '')} {getattr(card, 'text', '')}"
    tags: list[str] = []
    statuses: dict[str, str] = {}
    for rule in RULE_PATTERNS:
        if rule.pattern.search(text):
            tags.append(rule.tag)
            statuses[rule.tag] = rule.playmode_status
    if not tags and str(getattr(card, "text", "") or "").strip():
        tags.append("unique_text")
        statuses["unique_text"] = PLAYMODE_PENDING
    return {
        "id": getattr(card, "id", None),
        "name": getattr(card, "name", ""),
        "type": getattr(card, "type", ""),
        "tags": tags,
        "playmode_ready_tags": [tag for tag in tags if statuses.get(tag) == PLAYMODE_READY],
        "playmode_partial_tags": [tag for tag in tags if statuses.get(tag) == PLAYMODE_PARTIAL],
        "playmode_pending_tags": [tag for tag in tags if statuses.get(tag) == PLAYMODE_PENDING],
    }


def build_rules_coverage(cards: Iterable) -> dict:
    items = [classify_card_rules(card) for card in cards]
    tag_counts: Counter[str] = Counter()
    ready_counts: Counter[str] = Counter()
    partial_counts: Counter[str] = Counter()
    pending_counts: Counter[str] = Counter()
    for item in items:
        tag_counts.update(item["tags"])
        ready_counts.update(item["playmode_ready_tags"])
        partial_counts.update(item["playmode_partial_tags"])
        pending_counts.update(item["playmode_pending_tags"])
    cards_with_pending = [item for item in items if item["playmode_pending_tags"]]
    return {
        "total_cards": len(items),
        "cards_with_rules_text": sum(1 for item in items if item["tags"]),
        "cards_with_pending_playmode_rules": len(cards_with_pending),
        "tag_counts": dict(tag_counts.most_common()),
        "playmode_ready_tag_counts": dict(ready_counts.most_common()),
        "playmode_partial_tag_counts": dict(partial_counts.most_common()),
        "playmode_pending_tag_counts": dict(pending_counts.most_common()),
        "highest_priority_pending": cards_with_pending[:80],
    }
