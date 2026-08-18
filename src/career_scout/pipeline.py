from __future__ import annotations

import os
from dataclasses import asdict

import httpx

from career_scout.collectors.seek import SeekCollector
from career_scout.collectors.seek_apify import SeekApifyCollector
from career_scout.jd_signals import analyse_jd
from career_scout.preferences import evaluate_preferences
from career_scout.profile_loader import ScoutContext
from career_scout.scoring import score_job


def _collector():
    # GitHub-hosted runners are commonly blocked by SEEK. Prefer the managed
    # acquisition route when configured, while retaining direct collection for
    # local/dev environments where it works.
    if os.getenv("APIFY_TOKEN"):
        return SeekApifyCollector()
    return SeekCollector()


def collect_verified_seek_jobs(
    keywords: list[str],
    context: ScoutContext,
    where: str = "All Sydney NSW",
    shortlist_size: int = 15,
) -> list[dict]:
    """Discover, verify, filter and rank current SEEK vacancies.

    Search-index presence is never enough: only jobs individually verified live by
    the active collector can enter the result set. Career Operator Vault remains the
    authoritative source for matching evidence and Scout preferences.
    """
    collector = _collector()
    output: list[dict] = []
    seen: set[str] = set()
    try:
        for query in keywords:
            try:
                jobs = collector.search(query, where=where)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 403 and not os.getenv("APIFY_TOKEN"):
                    raise RuntimeError(
                        "SEEK blocked the direct collector from this runtime. Configure APIFY_TOKEN for the managed SEEK provider."
                    ) from exc
                raise
            for job in jobs:
                if job.key in seen:
                    continue
                seen.add(job.key)
                job = collector.verify_and_enrich(job)
                if not job.is_live:
                    continue
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
        collector.close()
