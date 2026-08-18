from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

from .jd_signals import analyse_jd


@dataclass
class MatchResult:
    score: int
    verdict: str
    matched_core: list[str]
    matched_strong: list[str]
    matched_ai: list[str]
    hard_gaps: list[str]
    soft_gaps: list[str]
    jd_openness: int
    jd_rigidity: int
    working_style_alignment: int
    transferable_experience_tolerance: str
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(text: str) -> str:
    text = text.lower()
    # Match common recruiter-language variants without pretending adjacent skills are identical.
    replacements = {
        "programme": "program",
        "management": "manager",
        "managing": "manager",
        "e-commerce": "ecommerce",
        "customer experience": "cx",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"[^a-z0-9+#]+", " ", text).strip()


def _contains(text: str, phrase: str) -> bool:
    p = _norm(phrase)
    return len(p) >= 3 and p in _norm(text)


def _flatten(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, list):
        for x in value:
            out.extend(_flatten(x))
    elif isinstance(value, dict):
        for x in value.values():
            out.extend(_flatten(x))
    return out


def _matches(text: str, section: Any, limit: int = 16) -> list[str]:
    seen: list[str] = []
    for phrase in _flatten(section):
        if phrase not in seen and _contains(text, phrase):
            seen.append(phrase)
            if len(seen) >= limit:
                break
    return seen


def _hard_gaps(text: str) -> list[str]:
    t = _norm(text)
    gaps: list[str] = []
    rules = [
        (("bss" in t or "oss" in t) and any(x in t for x in ["must", "mandatory", "required", "deep expertise"]), "BSS/OSS specialist experience"),
        (("telecommunications" in t or "telecom" in t) and "mandatory" in t, "mandatory telecommunications experience"),
        (any(x in t for x in ["baseline clearance", "nv1 clearance", "nv2 clearance"]) and any(x in t for x in ["current", "existing", "must hold", "required"]), "existing security clearance"),
        ("government experience" in t and any(x in t for x in ["mandatory", "must have", "required"]), "mandatory government experience"),
        (any(x in t for x in ["essential eight", "iso 27001", "nist"]) and any(x in t for x in ["must", "mandatory", "required", "expert"]), "specialist cyber/governance framework experience"),
    ]
    for condition, label in rules:
        if condition:
            gaps.append(label)
    return gaps


def score_job(job: Any, profile: dict[str, Any], preferences: dict[str, Any]) -> MatchResult:
    text = "\n".join(filter(None, [getattr(job, "title", ""), getattr(job, "teaser", ""), getattr(job, "description", "")]))
    core = _matches(text, profile.get("core_deep", {}))
    strong = _matches(text, profile.get("strong_direct", {}))
    ai = _matches(text, profile.get("ai_agentic_technology", {}), limit=10)
    methods = _matches(text, profile.get("delivery_methods", []), limit=8)
    role_titles = _matches(text, profile.get("target_role_families", {}), limit=6)
    hard = _hard_gaps(text)

    signals = analyse_jd(text)
    openness = signals.openness
    rigidity = signals.rigidity
    style = signals.working_style_alignment
    tolerance = signals.transferable_experience_tolerance

    # Evidence dominates the score. Platform/AI/behavioural signals help, but cannot rescue hard gaps.
    evidence = min(
        70,
        len(core) * 6
        + len(strong) * 5
        + len(ai) * 3
        + len(methods) * 3
        + len(role_titles) * 7,
    )

    title = _norm(getattr(job, "title", ""))
    if any(x in title for x in ["head of", "director", "program manager", "senior project manager", "senior program manager", "delivery lead", "transformation lead"]):
        seniority = 15
    elif "project manager" in title:
        seniority = 9
    else:
        seniority = 0

    practical = 8
    if getattr(job, "is_hybrid", False) or getattr(job, "is_remote", False):
        practical += 5
    practical += min(5, style // 20)
    practical += min(4, openness // 25)
    practical -= min(4, rigidity // 25)

    score = min(100, evidence + seniority + practical)
    if hard:
        score = min(score - 30 * len(hard), 49)
    score = max(0, score)

    if hard:
        verdict = "SKIP"
    elif score >= 85:
        verdict = "STRONG APPLY"
    elif score >= 72:
        verdict = "APPLY"
    elif score >= 60:
        verdict = "REVIEW"
    else:
        verdict = "LOW PRIORITY"

    reasons = []
    if core:
        reasons.append("Strong core delivery/leadership evidence overlap")
    if strong:
        reasons.append("Direct platform/transformation capability overlap")
    if ai:
        reasons.append("Relevant AI/agentic technology alignment")
    if openness >= 60:
        reasons.append("JD language appears open to transferable experience")
    if style >= 60:
        reasons.append("Working style aligns with strategy-to-execution and ambiguity leadership")
    if hard:
        reasons.append("Mandatory evidence gap: " + ", ".join(hard))

    return MatchResult(score, verdict, core, strong, ai, hard, [], openness, rigidity, style, tolerance, reasons)
