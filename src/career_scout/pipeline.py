from __future__ import annotations

from dataclasses import asdict

from career_scout.collectors.seek import SeekCollector
from career_scout.jd_signals import analyse_jd
from career_scout.preferences import evaluate_preferences
from career_scout.profile_loader import ScoutContext
from career_scout.scoring import score_job


def collect_verified_seek_jobs(
    keywords: list[str],
    context: ScoutContext,
    where: str = "All Sydney NSW",
    shortlist_size: int = 15,
) -> list[dict]:
    """Discover, verify, filter and rank current SEEK vacancies.

    Search-index presence is never enough: only jobs individually verified live by
    the collector can enter the result set. Career Operator Vault remains the
    authoritative source for matching evidence and Scout preferences.
    """
    collector = SeekCollector()
    output: list[dict] = []
    seen: set[str] = set()
    try:
        for query in keywords:
            for job in collector.search(query, where=where):
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
