from __future__ import annotations

import argparse
import json

from career_scout.pipeline import collect_verified_jobs
from career_scout.profile_loader import VaultLoader


DEFAULT_QUERIES = [
    "program manager transformation",
    "senior project manager digital transformation",
    "program director digital",
    "head of transformation",
    "technology transformation",
    "digital delivery director",
    "head of digital delivery",
    "ecommerce program manager",
    "martech transformation",
    "customer experience transformation",
    "AI transformation",
    "AI enablement lead",
    "SaaS implementation project manager",
    "digital platforms director",
    "customer technology transformation",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Career Scout AU")
    parser.add_argument("--where", default="All Sydney NSW")
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument("--output", default="career_scout_jobs.json")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--seek-only", action="store_true", help="Disable LinkedIn collection")
    args = parser.parse_args()

    context = VaultLoader().load()
    jobs = collect_verified_jobs(
        args.queries or DEFAULT_QUERIES,
        context=context,
        where=args.where,
        shortlist_size=args.limit,
        enable_linkedin=not args.seek_only,
    )
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(jobs, handle, indent=2, ensure_ascii=False)
    print(f"Wrote {len(jobs)} ranked, verified-live jobs to {args.output}")


if __name__ == "__main__":
    main()
