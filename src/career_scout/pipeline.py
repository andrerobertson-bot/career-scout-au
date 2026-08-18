from __future__ import annotations

import os
from dataclasses import asdict

import httpx

from career_scout.collectors.linkedin_apify import LinkedInApifyCollector
from career_scout.collectors.seek import SeekCollector
from career_scout.collectors.seek_apify import SeekApifyCollector
from career_scout.jd_signals import analyse_jd
from career_scout.preferences import evaluate_preferences
from career_scout.profile_loader import ScoutContext
from career_scout.scoring import score_job


def _collectors(enable_linkedin: bool = True):
    collectors: list[tuple[str, object]] = []
    if os.getenv("APIFY_TOKEN"):
        collectors.append(("seek", SeekApifyCollector()))
        if enable_linkedin:
            collectors.append(("linkedin", LinkedInApifyCollector()))
    else:
        collectors.append(("seek", SeekCollector()))
    return collectors


def _where_for(source: str, where: str) -> str:
    if source == "linkedin":
        if "Sydney" in where:
            return "Sydney, New South Wales, Australia"
        return where
    return where


def _publishable(job) -> bool:
    """Hard publication gate.

    Discovery is never proof of availability. A published job must have a canonical
    individual vacancy URL, a matching source/job id, a full description and a fresh
    successful verification result. Anything ambiguous is silently rejected.
    """
    if job.is_live is not True:
        return False
    if not job.source_job_id or not job.description or not job.verified_at:
        return False
    url = job.canonical_url or job.url or ""
    if job.source == "seek":
        return f"/job/{job.source_job_id}" in url
    if job.source == "linkedin":
        return "/jobs/view/" in url and job.source_job_id in url
    return False


def _freshness_bonus(age_days: int | None) -> int:
    if age_days is None:
        return 0
    if age_days <= 2:
        return 8
    if age_days <= 7:
        return 5
    if age_days <= 14:
        return 2
    if age_days <= 30:
        return -4
    return -12


def collect_verified_jobs(
    keywords: list[str],
    context: ScoutContext,
    where: str = "All Sydney NSW",
    shortlist_size: int = 15,
    enable_linkedin: bool = True,
) -> list[dict]:
    """Discover, verify, filter, deduplicate and rank current vacancies.

    Every actionable result must pass a per-job live-state verification immediately
    before publication. Search pages and search-engine indexes are discovery only.
    Career Operator Vault remains authoritative for candidate evidence/preferences.
    """
    output: list[dict] = []
    seen_ids: set[str] = set()
    seen_fingerprints: set[str] = set()
    collectors = _collectors(enable_linkedin=enable_linkedin)
    try:
        for source, collector in collectors:
            source_where = _where_for(source, where)
            for query in keywords:
                try:
                    jobs = collector.search(query, where=source_where)
                except httpx.HTTPStatusError as exc:
                    if source == "seek" and exc.response.status_code == 403 and not os.getenv("APIFY_TOKEN"):
                        raise RuntimeError(
                            "SEEK blocked the direct collector from this runtime. Configure APIFY_TOKEN for managed SEEK/LinkedIn acquisition."
                        ) from exc
                    raise
                for job in jobs:
                    if job.key in seen_ids:
                        continue
                    seen_ids.add(job.key)

                    job = collector.verify_and_enrich(job)
                    if not _publishable(job):
                        continue

                    fingerprint = "|".join(
                        (x or "").strip().lower()
                        for x in [job.company, job.title, job.location]
                    )
                    if fingerprint and fingerprint in seen_fingerprints:
                        continue
                    if fingerprint:
                        seen_fingerprints.add(fingerprint)

                    preference = evaluate_preferences(job)
                    if not preference.allowed:
                        continue

                    signals = analyse_jd(job.description)
                    match = score_job(job, context.profile, context.preferences)
                    freshness = _freshness_bonus(job.age_days)
                    adjusted_score = max(0, min(100, match.score + freshness))
                    match.score = adjusted_score
                    if not match.hard_gaps:
                        if adjusted_score >= 85:
                            match.verdict = "STRONG APPLY"
                        elif adjusted_score >= 72:
                            match.verdict = "APPLY"
                        elif adjusted_score >= 60:
                            match.verdict = "REVIEW"
                        else:
                            match.verdict = "LOW PRIORITY"

                    output.append({
                        "job": job.to_dict(),
                        "preference": asdict(preference),
                        "jd_signals": asdict(signals),
                        "match": match.to_dict(),
                        "publication": {
                            "canonical_url": job.canonical_url or job.url,
                            "verified_at": job.verified_at,
                            "verification_method": job.verification_method,
                            "freshness_adjustment": freshness,
                        },
                    })

        output.sort(
            key=lambda row: (
                row["match"]["score"],
                -(row["job"].get("age_days") if row["job"].get("age_days") is not None else 9999),
            ),
            reverse=True,
        )
        return output[:shortlist_size]
    finally:
        for _, collector in collectors:
            collector.close()


def collect_verified_seek_jobs(
    keywords: list[str],
    context: ScoutContext,
    where: str = "All Sydney NSW",
    shortlist_size: int = 15,
) -> list[dict]:
    """Compatibility wrapper for earlier Prototype 0.2 callers."""
    return collect_verified_jobs(
        keywords,
        context=context,
        where=where,
        shortlist_size=shortlist_size,
        enable_linkedin=False,
    )
