from __future__ import annotations

import argparse
import json

from career_scout.pipeline import collect_verified_seek_jobs


DEFAULT_QUERIES = [
    "program manager transformation",
    "senior project manager digital transformation",
    "program director digital",
    "head of transformation",
    "technology transformation",
    "ecommerce program manager",
    "martech transformation",
    "customer experience transformation",
    "AI transformation",
    "SaaS implementation project manager",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Career Scout AU Prototype 0.2")
    parser.add_argument("--where", default="All Sydney NSW")
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument("--output", default="career_scout_jobs.json")
    args = parser.parse_args()

    jobs = collect_verified_seek_jobs(args.queries or DEFAULT_QUERIES, where=args.where)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(jobs, handle, indent=2, ensure_ascii=False)
    print(f"Wrote {len(jobs)} verified live jobs to {args.output}")


if __name__ == "__main__":
    main()
