from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class JDSignals:
    openness: int
    rigidity: int
    working_style_alignment: int
    transferable_experience_tolerance: str


OPENNESS = (
    r"don't (?:need to )?tick every box",
    r"do not (?:need to )?tick every box",
    r"don't meet (?:all|every)",
    r"we(?:'d| would) still (?:love|like) to hear from you",
    r"transferable (?:skills|experience)",
    r"different backgrounds",
    r"encourage you to apply",
)
RIGIDITY = (
    r"\bmandatory\b", r"\bmust have\b", r"\bessential criteria\b",
    r"only candidates", r"will not be considered", r"existing .{0,20}clearance",
)
WORKING_STYLE = (
    r"clarity.{0,20}ambiguity|ambiguity.{0,20}clarity",
    r"create structure", r"strategy.{0,10}(?:and|&|to).{0,10}execution",
    r"trusted (?:partner|adviser|advisor)", r"navigate complexity",
    r"challenge the status quo", r"emerging technolog", r"experiment",
    r"shape the (?:role|function|capability)", r"commercial.{0,20}pragmatic",
    r"roll up (?:your|their) sleeves|hands-on leadership",
)


def _score(text: str, patterns: tuple[str, ...], points: int) -> int:
    hits = sum(bool(re.search(pattern, text, re.I | re.S)) for pattern in patterns)
    return min(100, hits * points)


def analyse_jd(text: str | None) -> JDSignals:
    text = text or ""
    openness = _score(text, OPENNESS, 20)
    rigidity = _score(text, RIGIDITY, 15)
    working = _score(text, WORKING_STYLE, 12)
    if openness >= 40 and rigidity < 45:
        tolerance = "HIGH"
    elif rigidity >= 45 and openness < 20:
        tolerance = "LOW"
    else:
        tolerance = "MEDIUM"
    return JDSignals(openness, rigidity, working, tolerance)
