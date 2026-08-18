from __future__ import annotations

import re
from dataclasses import dataclass, field

from career_scout.models import Job


@dataclass(slots=True)
class PreferenceDecision:
    allowed: bool = True
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


AGENCY_PATTERNS = (
    r"\badvertising agency\b",
    r"\bmedia agency\b",
    r"\bcreative agency\b",
    r"\bdigital agency\b",
)
GOVERNMENT_PATTERNS = (r"\bgovernment\b", r"\bpublic sector\b", r"\bnsw government\b")
MANDATORY_GOV_EXPERIENCE = (
    r"government experience (?:is )?(?:mandatory|required|essential)",
    r"must have .{0,50}government experience",
    r"prior .{0,30}government experience .{0,30}(?:mandatory|required|essential)",
)
MANDATORY_BASELINE = (
    r"must (?:hold|have|possess).{0,40}baseline",
    r"existing .{0,20}baseline (?:clearance|security clearance)",
    r"baseline (?:clearance|security clearance).{0,30}(?:mandatory|required|essential)",
)
HYBRID_REMOTE = (r"\bhybrid\b", r"\bwork from home\b", r"\bwfh\b", r"\bremote\b", r"\bflexible work")


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text, re.I | re.S) for p in patterns)


def evaluate_preferences(job: Job) -> PreferenceDecision:
    text = "\n".join(
        x for x in [job.title, job.company, job.location, job.teaser, job.description, job.salary_text]
        if x
    )
    decision = PreferenceDecision()

    if _matches(text, AGENCY_PATTERNS):
        decision.allowed = False
        decision.reasons.append("Excluded agency environment")

    is_government = _matches(text, GOVERNMENT_PATTERNS)
    if is_government:
        decision.flags.append("government")
        if _matches(text, MANDATORY_GOV_EXPERIENCE):
            decision.allowed = False
            decision.reasons.append("Mandatory prior government experience")
        if _matches(text, MANDATORY_BASELINE):
            decision.allowed = False
            decision.reasons.append("Existing Baseline clearance required")

    location = (job.location or "").lower()
    is_sydney = "sydney" in location or "nsw" in location
    if is_sydney and job.description and not _matches(text, HYBRID_REMOTE):
        decision.flags.append("hybrid_not_confirmed")

    if not job.salary_text:
        decision.flags.append("salary_not_disclosed")

    return decision
