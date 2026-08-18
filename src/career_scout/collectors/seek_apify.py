from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from career_scout.models import Job


class SeekApifyCollector:
    """Managed SEEK discovery with a strict individual-vacancy publication gate."""

    ACTOR = "crawlerbros~seek-jobs-scraper"
    API = "https://api.apify.com/v2"
    CLOSED_MARKERS = (
        "this job has expired",
        "job has expired",
        "this job is no longer available",
        "no longer accepting applications",
    )

    def __init__(self, token: str | None = None, timeout: float = 180.0) -> None:
        self.token = token or os.getenv("APIFY_TOKEN")
        if not self.token:
            raise RuntimeError("APIFY_TOKEN is required for the managed SEEK collector")
        self.client = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _seek_url_for_query(keywords: str, where: str) -> str:
        q = re.sub(r"[^a-z0-9]+", "-", keywords.lower()).strip("-")
        loc = where.replace(" ", "-")
        return f"https://www.seek.com.au/{q}-jobs/in-{loc}?sortmode=ListedDate"

    @staticmethod
    def _canonical_url(job_id: str) -> str:
        return f"https://www.seek.com.au/job/{job_id}"

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
            if not job_id or not title or not description:
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
                url=self._canonical_url(job_id),
                apply_url=self._text(row, "applyUrl", "apply_url"),
                posted_at=self._text(row, "postedAt", "listingDate", "datePosted"),
                valid_through=self._text(row, "validThrough", "expiresAt"),
                description=description,
                teaser=self._text(row, "teaser", "abstract", "summary"),
                is_live=None,
                is_expired=None,
                status="DISCOVERED_UNVERIFIED",
                raw=row,
            ))
        return jobs

    def verify_and_enrich(self, job: Job) -> Job:
        job.url = self._canonical_url(job.source_job_id)
        job.verified_at = datetime.now(timezone.utc).isoformat()
        try:
            response = self.client.get(job.url)
        except httpx.HTTPError:
            job.is_live = False
            job.status = "VERIFICATION_REQUEST_FAILED"
            return job

        final_url = str(response.url)
        body = response.text.lower()
        exact_job = re.search(rf"/job/{re.escape(job.source_job_id)}(?:\D|$)", final_url) is not None or job.source_job_id in response.text
        closed = any(marker in body for marker in self.CLOSED_MARKERS)
        redirected_to_search = "/job/" not in final_url

        if response.status_code != 200 or not exact_job or redirected_to_search or closed:
            job.is_live = False
            job.is_expired = closed
            job.status = "CLOSED" if closed else "UNVERIFIED_CANONICAL_JOB"
            return job

        job.is_live = True
        job.is_expired = False
        job.status = "VERIFIED_LIVE_CANONICAL"
        return job
