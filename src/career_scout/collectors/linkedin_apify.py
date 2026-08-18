from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from career_scout.models import Job


class LinkedInApifyCollector:
    """Discover LinkedIn vacancies via Apify, but do not trust discovery as live proof.

    Discovery results are candidates only. A vacancy becomes actionable only after a
    fresh retrieval of its canonical individual LinkedIn job URL confirms that the
    page still represents that exact job and does not expose a closed/expired state.
    """

    ACTOR = "automation-lab~linkedin-jobs-scraper"
    API = "https://api.apify.com/v2"
    CLOSED_MARKERS = (
        "no longer accepting applications",
        "this job is no longer available",
        "job is no longer available",
        "position has been filled",
    )

    def __init__(self, token: str | None = None, timeout: float = 180.0) -> None:
        self.token = token or os.getenv("APIFY_TOKEN")
        if not self.token:
            raise RuntimeError("APIFY_TOKEN is required for the LinkedIn collector")
        self.client = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})

    def close(self) -> None:
        self.client.close()

    @staticmethod
    def _job_id(row: dict[str, Any]) -> str:
        value = str(row.get("id") or row.get("jobId") or row.get("job_id") or "")
        if value.isdigit():
            return value
        url = str(row.get("jobUrl") or row.get("url") or row.get("link") or "")
        m = re.search(r"/jobs/view/(?:[^/?]+-)?(\d+)", url)
        return m.group(1) if m else ""

    @staticmethod
    def _canonical_url(job_id: str) -> str:
        return f"https://www.linkedin.com/jobs/view/{job_id}/"

    @staticmethod
    def _text(row: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def search(self, keywords: str, *, where: str = "Sydney, New South Wales, Australia", page: int = 1, sortmode: str = "ListedDate") -> list[Job]:
        endpoint = f"{self.API}/acts/{self.ACTOR}/run-sync-get-dataset-items"
        payload = {
            "searchQuery": keywords,
            "location": where,
            "maxJobs": 40,
            "scrapeJobDetails": True,
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
                source="linkedin",
                source_job_id=job_id,
                title=title,
                company=self._text(row, "companyName", "company", "company_name"),
                location=self._text(row, "location", "jobLocation"),
                work_arrangement=self._text(row, "workplaceType", "workplace_type", "workArrangement"),
                employment_type=self._text(row, "employmentType", "jobType", "employment_type"),
                salary_text=self._text(row, "salary", "salaryText", "salaryRange"),
                url=self._canonical_url(job_id),
                apply_url=self._text(row, "applyUrl", "apply_url"),
                posted_at=self._text(row, "postedDate", "postedAt", "datePosted"),
                description=description,
                teaser=self._text(row, "snippet", "summary", "abstract"),
                # Discovery is explicitly NOT verification.
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
            job.is_expired = None
            job.status = "VERIFICATION_REQUEST_FAILED"
            return job

        final_url = str(response.url)
        body = response.text.lower()
        exact_job = job.source_job_id in final_url or job.source_job_id in response.text
        closed = any(marker in body for marker in self.CLOSED_MARKERS)
        wrong_surface = "/jobs/view/" not in final_url and job.source_job_id not in response.text

        if response.status_code != 200 or not exact_job or wrong_surface or closed:
            job.is_live = False
            job.is_expired = closed
            job.status = "CLOSED" if closed else "UNVERIFIED_CANONICAL_JOB"
            return job

        job.is_live = True
        job.is_expired = False
        job.status = "VERIFIED_LIVE_CANONICAL"
        return job
