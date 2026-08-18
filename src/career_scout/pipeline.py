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


def collect_verified_jobs(
    keywords: list[str],
    context: ScoutContext,
    where: str = "All Sydney NSW",
    shortlist_size: int = 15,
    enable_linkedin: bool = True,
) -> list[dict]:
    """Discover, verify, filter, deduplicate and rank current vacancies.

    Every actionable result must come from a current per-job retrieval with a full
    description. Career Operator Vault remains authoritative for candidate evidence
    and Scout preferences.
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
                    if not job.is_live:
                        continue

                    # Cross-board dedupe: same company/title/location becomes one opportunity.
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
                    output.append({
                        "job": job.to_dict(),
                        "preference": asdict(preference),
                        "jd_signals": asdict(signals),
                        "match": match.to_dict(),
                    })
        output.sort(key=lambda row: row["match"]["score"], reverse=True)
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
