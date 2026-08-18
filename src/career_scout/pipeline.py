from __future__ import annotations

from dataclasses import asdict

from career_scout.collectors.seek import SeekCollector
from career_scout.jd_signals import analyse_jd
from career_scout.preferences import evaluate_preferences


def collect_verified_seek_jobs(keywords: list[str], where: str = "All Sydney NSW") -> list[dict]:
    """Prototype 0.2 collection stage.

    Only individually verified live jobs are returned. Matching-profile scoring is
    deliberately a separate next stage so acquisition quality can be tested first.
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
                output.append(
                    {
                        "job": job.to_dict(),
                        "preference": asdict(preference),
                        "jd_signals": asdict(signals),
                    }
                )
        return output
    finally:
        collector.close()
