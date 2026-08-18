from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from career_scout.models import Job


class SeekApifyCollector:
    """Managed SEEK collector using Apify when SEEK blocks GitHub-hosted runners.

    The actor performs the current-site retrieval outside GitHub Actions. Returned
    vacancies are accepted only when they contain an individual SEEK job URL/id and
    a non-empty current description. The pipeline still fails closed otherwise.
    """

    ACTOR = "crawlerbros~seek-jobs-scraper"
    API = "https://api.apify.com/v2"

    def __init__(self, token: str | None = None, timeout: float = 180.0) -> None:
        self.token = token or os.getenv("APIFY_TOKEN")
        if not self.token:
            raise RuntimeError("APIFY_TOKEN is required for the managed SEEK collector")
        self.client = httpx.Client(timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _seek_url_for_query(keywords: str, where: str) -> str:
        q = re.sub(r"[^a-z0-9]+", "-", keywords.lower()).strip("-")
        loc = where.replace(" ", "-")
        return f"https://www.seek.com.au/{q}-jobs/in-{loc}?sortmode=ListedDate"

    @staticmethod
    def _job_id(row: dict[str, Any]) -> str:
        value = str(row.get("id") or row.get("jobId") or row.get("job_id") or "")
        if value.isdigit():
            return value
        url = str(row.get("url") or row.get("jobUrl") or row.get("job_url") or row.get("link") or "")
        m = re.search(r"/job/(\d+)", url)
        return m.group(1) if m else ""

    @staticmethod
    def _text(row: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def search(self, keywords: str, *, where: str = "All Sydney NSW", page: int = 1, sortmode: str = "ListedDate") -> list[Job]:
        # One query per actor run keeps provenance clear and makes retries cheap.
        endpoint = f"{self.API}/acts/{self.ACTOR}/run-sync-get-dataset-items"
        payload = {
            "searchUrls": [self._seek_url_for_query(keywords, where)],
            "maxItems": 40,
            "proxyConfiguration": {"useApifyProxy": True},
        }
        response = self.client.post(endpoint, params={"token": self.token}, json=payload)
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            return []

        jobs: list[Job] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            job_id = self._job_id(row)
            title = self._text(row, "title", "jobTitle", "job_title")
            description = self._text(row, "description", "jobDescription", "job_description", "content")
            url = self._text(row, "url", "jobUrl", "job_url", "link")
            if not job_id or not title or not url or not description:
                continue
            jobs.append(Job(
                source="seek",
                source_job_id=job_id,
                title=title,
                company=self._text(row, "company", "companyName", "advertiserName", "advertiser"),
                location=self._text(row, "location", "locationName", "where"),
                work_arrangement=self._text(row, "workArrangement", "work_arrangement", "workType"),
                employment_type=self._text(row, "employmentType", "employment_type", "workType"),
                salary_text=self._text(row, "salary", "salaryText", "salaryLabel"),
                url=url,
                apply_url=self._text(row, "applyUrl", "apply_url"),
                posted_at=self._text(row, "postedAt", "listingDate", "datePosted"),
                valid_through=self._text(row, "validThrough", "expiresAt"),
                description=description,
                teaser=self._text(row, "teaser", "abstract", "summary"),
                is_live=True,
                is_expired=False,
                status="VERIFIED_APIFY_CURRENT",
                verified_at=datetime.now(timezone.utc).isoformat(),
                raw=row,
            ))
        return jobs

    def verify_and_enrich(self, job: Job) -> Job:
        # Actor output already came from a current per-job scrape with description.
        # Fail closed if required verification fields are absent.
        if not job.source_job_id or not job.url or not job.description:
            job.is_live = False
            job.status = "UNVERIFIED"
        return job
